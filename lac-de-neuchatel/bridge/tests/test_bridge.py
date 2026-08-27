"""Unit tests for FusionBridge. Run with:  python3 tests/test_bridge.py

No socket is ever opened and Fusion is not required; adsk.py in this folder is
a stub that simulates Fusion's main-thread custom-event dispatch.

The HTTP handler is exercised by constructing it without BaseHTTPRequestHandler's
socket setup and driving do_GET / do_POST against in-memory streams.
"""
import email.message
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
BRIDGE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(BRIDGE, "FusionBridge"))

import adsk  # noqa: E402
import FusionBridge as FB  # noqa: E402

passed = failed = 0


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print("  pass  %s" % label)
    else:
        failed += 1
        print("  FAIL  %s   %s" % (label, detail))


def headers(**kw):
    m = email.message.Message()
    for k, v in kw.items():
        m[k.replace("_", "-")] = str(v)
    return m


class FakeHandler(FB.BridgeHandler):
    """BridgeHandler with the socket plumbing replaced by buffers."""

    def __init__(self, path, hdrs, body=b"", method="GET"):
        self.path = path
        self.headers = hdrs
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.command = method
        self.request_version = "HTTP/1.1"
        self.client_address = ("127.0.0.1", 0)
        self.status = None

    def send_response(self, code, message=None):
        self.status = code

    def send_header(self, k, v):
        pass

    def end_headers(self):
        pass

    def result(self):
        raw = self.wfile.getvalue()
        return self.status, (json.loads(raw.decode()) if raw else None)


# --------------------------------------------------------------------------
print("token handling")
check("identical tokens match", FB.tokens_match("abc123", "abc123"))
check("different tokens reject", not FB.tokens_match("abc123", "abc124"))
check("length mismatch rejects", not FB.tokens_match("abc", "abcd"))
check("empty supplied rejects", not FB.tokens_match("", "abc"))
check("None supplied rejects", not FB.tokens_match(None, "abc"))
check("None expected rejects", not FB.tokens_match("abc", None))
check("prefix does not pass", not FB.tokens_match("ab", "abc"))

tmp_token = os.path.join(HERE, "bridge-token.txt")
FB.TOKEN_FILE = tmp_token
if os.path.exists(tmp_token):
    os.remove(tmp_token)
first = FB.load_or_create_token()
check("token generated", bool(first) and len(first) == 32, first)
check("token persisted to disk", os.path.isfile(tmp_token))
check("token stable across calls", FB.load_or_create_token() == first)

# --------------------------------------------------------------------------
print("\nmain-thread execution")
FB._app = adsk._APP
FB._ui = adsk._APP.userInterface

r = FB.execute_on_main("result = 6 * 7")
check("returns result", r["ok"] and r["result"] == 42, r)

r = FB.execute_on_main("print('spoken')")
check("captures stdout", "spoken" in r["stdout"], r)

r = FB.execute_on_main("result = app.version")
check("app in scope", "stub" in str(r["result"]), r)

r = FB.execute_on_main("result = doc.name")
check("doc in scope", r["result"] == "TestDoc", r)

r = FB.execute_on_main("result = (design, cam)")
check("design and cam bound", r["ok"], r)

r = FB.execute_on_main("1/0")
check("exception -> ok False", r["ok"] is False, r)
check("traceback returned", "ZeroDivisionError" in r["error"], r)

r = FB.execute_on_main("print('before'); 1/0")
check("stdout preserved on error", "before" in r["stdout"], r)

r = FB.execute_on_main("result = object()")
check("unserialisable result -> repr",
      r["ok"] and isinstance(r["result"], str) and "object" in r["result"], r)

r = FB.execute_on_main("result = {'a': [1, 2, {'b': None}]}")
check("nested JSON survives", r["result"] == {"a": [1, 2, {"b": None}]}, r)

r = FB.execute_on_main("def (: broken")
check("syntax error handled", r["ok"] is False and "SyntaxError" in r["error"], r)

r = FB.execute_on_main("this is not python")
check("NameError surfaced too", r["ok"] is False and "NameError" in r["error"], r)

r = FB.execute_on_main("import sys; print('direct'); result = 'x'")
check("print captured without touching global stdout",
      "direct" in r["stdout"] and sys.stdout is not None, r)

# --------------------------------------------------------------------------
print("\ndispatch to main thread")
FB._token = first
try:
    FB._app.unregisterCustomEvent(FB.EVENT_ID)
except Exception:
    pass
ev = FB._app.registerCustomEvent(FB.EVENT_ID)
h = FB.ExecEventHandler()
ev.add(h)
FB._handlers.append(h)

r = FB.run_on_main_thread("result = 'round trip'", 10)
check("round trip works", r["ok"] and r["result"] == "round trip", r)
check("no pending job leaked", len(FB._pending) == 0, FB._pending)

r = FB.run_on_main_thread("import time; time.sleep(2)", 0.5)
check("timeout reported cleanly", r["ok"] is False and "timed out" in r["error"], r)
check("no pending job leaked after timeout", len(FB._pending) == 0, FB._pending)

r = FB.run_on_main_thread("result = 'still works'", 10)
check("usable after a timeout", r["result"] == "still works", r)

r = FB.execute_on_main("result = 1")
check("handler never raises out", r["ok"], r)

# --------------------------------------------------------------------------
print("\nHTTP layer (no socket)")
good = {"X_Bridge_Token": first}

s, b = FakeHandler("/ping", headers()).result() if False else (None, None)

h1 = FakeHandler("/ping", headers())
h1.do_GET()
check("GET /ping without token -> 401", h1.result()[0] == 401, h1.result())

h2 = FakeHandler("/ping", headers(X_Bridge_Token="wrong"))
h2.do_GET()
check("GET /ping bad token -> 401", h2.result()[0] == 401, h2.result())

h3 = FakeHandler("/ping", headers(**good))
h3.do_GET()
st, body = h3.result()
check("GET /ping good token -> 200", st == 200 and body.get("ok"), body)

h4 = FakeHandler("/nope", headers(**good))
h4.do_GET()
check("unknown GET path -> 404", h4.result()[0] == 404, h4.result())

h5 = FakeHandler("/exec", headers(**good), method="OPTIONS")
h5.do_OPTIONS()
check("CORS preflight refused -> 403", h5.result()[0] == 403, h5.result())

payload = json.dumps({"code": "result = 5 + 5"}).encode()
h6 = FakeHandler("/exec", headers(X_Bridge_Token=first,
                                  Content_Length=len(payload)),
                 payload, "POST")
h6.do_POST()
st, body = h6.result()
check("POST /exec runs code", st == 200 and body.get("result") == 10, body)

h7 = FakeHandler("/exec", headers(Content_Length=len(payload)), payload, "POST")
h7.do_POST()
check("POST /exec without token -> 401", h7.result()[0] == 401, h7.result())

bad = b"{not json"
h8 = FakeHandler("/exec", headers(X_Bridge_Token=first, Content_Length=len(bad)),
                 bad, "POST")
h8.do_POST()
check("malformed JSON -> 400", h8.result()[0] == 400, h8.result())

empty = json.dumps({"code": "   "}).encode()
h9 = FakeHandler("/exec", headers(X_Bridge_Token=first, Content_Length=len(empty)),
                 empty, "POST")
h9.do_POST()
check("blank code -> 400", h9.result()[0] == 400, h9.result())

nocode = json.dumps({"timeout": 5}).encode()
h10 = FakeHandler("/exec", headers(X_Bridge_Token=first, Content_Length=len(nocode)),
                  nocode, "POST")
h10.do_POST()
check("missing code -> 400", h10.result()[0] == 400, h10.result())

h11 = FakeHandler("/exec", headers(X_Bridge_Token=first, Content_Length=0),
                  b"", "POST")
h11.do_POST()
check("zero length body -> 400", h11.result()[0] == 400, h11.result())

huge = FakeHandler("/exec", headers(X_Bridge_Token=first,
                                    Content_Length=FB.MAX_BODY + 1), b"", "POST")
huge.do_POST()
check("oversize body -> 400", huge.result()[0] == 400, huge.result())

nonint = FakeHandler("/exec", headers(X_Bridge_Token=first,
                                      Content_Length="abc"), b"", "POST")
nonint.do_POST()
check("non-integer Content-Length -> 400", nonint.result()[0] == 400, nonint.result())

wild = json.dumps({"code": "result = 1", "timeout": "banana"}).encode()
h12 = FakeHandler("/exec", headers(X_Bridge_Token=first, Content_Length=len(wild)),
                  wild, "POST")
h12.do_POST()
check("bad timeout falls back to default", h12.result()[1].get("result") == 1,
      h12.result())

clamp = json.dumps({"code": "result = 1", "timeout": 99999}).encode()
h13 = FakeHandler("/exec", headers(X_Bridge_Token=first, Content_Length=len(clamp)),
                  clamp, "POST")
h13.do_POST()
check("absurd timeout clamped, still runs", h13.result()[1].get("result") == 1,
      h13.result())

h14 = FakeHandler("/nope", headers(X_Bridge_Token=first,
                                   Content_Length=len(payload)), payload, "POST")
h14.do_POST()
check("unknown POST path -> 404", h14.result()[0] == 404, h14.result())

# --------------------------------------------------------------------------
print("\nshutdown hygiene")
FB.stop(None)
check("handlers released on stop", len(FB._handlers) == 0, FB._handlers)
check("event unregistered", FB.EVENT_ID not in adsk._registered,
      list(adsk._registered))

if os.path.exists(tmp_token):
    os.remove(tmp_token)

print("\n%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
