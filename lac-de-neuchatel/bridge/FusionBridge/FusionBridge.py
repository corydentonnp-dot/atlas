"""
FusionBridge -- a localhost bridge that lets an outside process drive Fusion 360.

WHY THIS IS SHAPED THE WAY IT IS
--------------------------------
Fusion's API is in-process only and is NOT thread safe. Every adsk.* call has to
happen on Fusion's main thread. So:

    HTTP request  ->  worker thread  ->  fireCustomEvent(id)
                                             |
                                      Fusion main thread runs your code
                                             |
                      worker thread  <-  threading.Event is set
                  ->  HTTP response

The worker thread never touches the API. It parks on an Event until the main
thread has finished and left the result behind. That is the only safe pattern.

INSTALL
-------
Copy the whole FusionBridge folder to:

  Windows  %APPDATA%\\Autodesk\\Autodesk Fusion 360\\API\\AddIns\\
  macOS    ~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/

Then Fusion > Utilities > Add-Ins > Add-Ins tab > FusionBridge > Run,
and tick "Run on Startup" if you want it always available.

SECURITY -- please read
-----------------------
This endpoint executes arbitrary Python inside Fusion. It is bound to
127.0.0.1 so nothing off your machine can reach it, and every request must
carry a secret token in the X-Bridge-Token header. The header matters: a
malicious web page you happen to have open CAN silently POST to localhost, but
it cannot set a custom header without a CORS preflight, which this server
refuses. That is what keeps a random browser tab from driving your CNC job.

The token is generated on first run and written next to this file as
bridge-token.txt. Treat it like a password. Stop the add-in when you are not
using it.

NEVER call ui.messageBox from code you send through the bridge. A modal dialog
blocks Fusion's main thread, the bridge cannot answer, and your request will
sit there until you click OK on a dialog you cannot see.
"""

import json
import os
import threading
import traceback
import uuid
import io
import http.server

import adsk.core
import adsk.fusion
import adsk.cam


# --- configuration -----------------------------------------------------------

HOST = "127.0.0.1"
PORT = 8181
EVENT_ID = "FusionBridgeExecEvent"
TOKEN_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                          "bridge-token.txt")
MAX_BODY = 4 * 1024 * 1024        # 4 MB of code per request is plenty


# --- module state ------------------------------------------------------------
# Fusion garbage-collects event handlers that nothing holds a reference to, and
# then the event silently stops firing. _handlers exists purely to hold on.

_app = None
_ui = None
_handlers = []
_server = None
_server_thread = None
_custom_event = None
_token = None

_pending = {}                     # request id -> job dict
_pending_lock = threading.Lock()


# --- token -------------------------------------------------------------------

def load_or_create_token():
    """Read the shared secret, creating one on first run."""
    try:
        if os.path.isfile(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as fh:
                existing = fh.read().strip()
            if existing:
                return existing
    except Exception:
        pass

    token = uuid.uuid4().hex
    try:
        with open(TOKEN_FILE, "w") as fh:
            fh.write(token)
    except Exception:
        pass
    return token


def tokens_match(supplied, expected):
    """
    Constant-time-ish comparison.

    Not a serious side-channel defence over loopback, but it costs nothing and
    avoids the obvious early-exit leak.
    """
    if not supplied or not expected:
        return False
    if len(supplied) != len(expected):
        return False
    mismatch = 0
    for a, b in zip(supplied, expected):
        mismatch |= ord(a) ^ ord(b)
    return mismatch == 0


# --- the part that runs on Fusion's main thread -------------------------------

def execute_on_main(code):
    """
    Run a block of user code with the Fusion objects already in scope.

    Called ONLY from the custom event handler, ie on the main thread.

    The code gets app, ui, design, cam and the adsk modules for free. Set a
    variable named `result` and it comes back in the response; anything printed
    comes back as stdout.
    """
    scope = {
        "adsk": adsk,
        "app": _app,
        "ui": _ui,
        "traceback": traceback,
        "json": json,
        "os": os,
        "result": None,
    }

    # These are looked up per call, not cached, because the user switches
    # documents and workspaces between requests.
    try:
        doc = _app.activeDocument
        scope["doc"] = doc
        scope["design"] = adsk.fusion.Design.cast(
            doc.products.itemByProductType("DesignProductType"))
        scope["cam"] = adsk.cam.CAM.cast(
            doc.products.itemByProductType("CAMProductType"))
    except Exception:
        scope["doc"] = None
        scope["design"] = None
        scope["cam"] = None

    # Capture output by giving the code its own print, NOT by redirecting
    # sys.stdout. contextlib.redirect_stdout swaps the process-wide stream, so
    # anything else running in Fusion during this call would have its output
    # silently swallowed into our buffer. Shadowing print in the exec scope is
    # thread safe and affects only the submitted code.
    buffer = io.StringIO()

    def captured_print(*args, **kwargs):
        kwargs["file"] = buffer
        print(*args, **kwargs)

    scope["print"] = captured_print

    try:
        exec(compile(code, "<bridge>", "exec"), scope)
        value = scope.get("result")
        # Anything not JSON-serialisable comes back as its repr rather than
        # blowing up the response.
        try:
            json.dumps(value)
        except Exception:
            value = repr(value)
        return {"ok": True, "result": value, "stdout": buffer.getvalue()}
    except Exception:
        return {"ok": False,
                "error": traceback.format_exc(),
                "stdout": buffer.getvalue()}


class ExecEventHandler(adsk.core.CustomEventHandler):
    """Receives the fired event on the main thread and runs the pending job."""

    def notify(self, args):
        job = None
        try:
            request_id = args.additionalInfo
            with _pending_lock:
                job = _pending.get(request_id)
            if job is None:
                return
            job["result"] = execute_on_main(job["code"])
        except Exception:
            # This handler must never raise. An exception escaping a Fusion
            # event handler can take the whole application down.
            if job is not None:
                job["result"] = {"ok": False, "error": traceback.format_exc()}
        finally:
            if job is not None:
                job["event"].set()


def run_on_main_thread(code, timeout):
    """Hand code to the main thread and block this worker until it is done."""
    request_id = uuid.uuid4().hex
    job = {"code": code, "event": threading.Event(), "result": None}
    with _pending_lock:
        _pending[request_id] = job

    try:
        _app.fireCustomEvent(EVENT_ID, request_id)
    except Exception:
        with _pending_lock:
            _pending.pop(request_id, None)
        return {"ok": False, "error": "could not reach Fusion's main thread:\n"
                                      + traceback.format_exc()}

    finished = job["event"].wait(timeout)
    with _pending_lock:
        _pending.pop(request_id, None)

    if not finished:
        return {"ok": False, "error":
                "timed out after %ss. Fusion's main thread is still busy. "
                "A modal dialog (ui.messageBox, an open command) will do this "
                "-- check the Fusion window." % timeout}
    return job["result"]


# --- HTTP --------------------------------------------------------------------

class BridgeHandler(http.server.BaseHTTPRequestHandler):
    server_version = "FusionBridge/1.0"

    # Silence the default stderr logging; Fusion's console is noisy enough.
    def log_message(self, fmt, *args):
        pass

    def _reply(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # No CORS headers, deliberately. Browsers must not be able to use this.
        self.end_headers()
        self.wfile.write(body)

    def _authorised(self):
        return tokens_match(self.headers.get("X-Bridge-Token"), _token)

    def do_OPTIONS(self):
        # Refuse the preflight so a cross-origin caller can never proceed.
        self._reply(403, {"ok": False, "error": "cross-origin requests refused"})

    def do_GET(self):
        if self.path.rstrip("/") != "/ping":
            self._reply(404, {"ok": False, "error": "unknown path"})
            return
        if not self._authorised():
            self._reply(401, {"ok": False, "error": "bad or missing X-Bridge-Token"})
            return

        info = run_on_main_thread(
            "result = {"
            "  'version': app.version,"
            "  'document': app.activeDocument.name if app.activeDocument else None,"
            "  'workspace': ui.activeWorkspace.id if ui.activeWorkspace else None,"
            "}", 15)
        self._reply(200, info)

    def do_POST(self):
        if self.path.rstrip("/") != "/exec":
            self._reply(404, {"ok": False, "error": "unknown path"})
            return
        if not self._authorised():
            self._reply(401, {"ok": False, "error": "bad or missing X-Bridge-Token"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._reply(400, {"ok": False, "error": "bad Content-Length"})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as exc:
            self._reply(400, {"ok": False, "error": "bad JSON: %s" % exc})
            return

        code = payload.get("code")
        if not isinstance(code, str) or not code.strip():
            self._reply(400, {"ok": False, "error": "no code supplied"})
            return

        timeout = payload.get("timeout", 120)
        try:
            timeout = max(1, min(3600, float(timeout)))
        except Exception:
            timeout = 120

        self._reply(200, run_on_main_thread(code, timeout))


class BridgeServer(http.server.HTTPServer):
    # One request at a time. Fusion's main thread is a single resource and
    # queueing here is simpler than arbitrating there.
    daemon_threads = True
    allow_reuse_address = True


# --- add-in lifecycle --------------------------------------------------------

def run(context):
    global _app, _ui, _server, _server_thread, _custom_event, _token

    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        _token = load_or_create_token()

        # Re-registering a live event id throws, so clear any stale one first.
        try:
            _app.unregisterCustomEvent(EVENT_ID)
        except Exception:
            pass

        _custom_event = _app.registerCustomEvent(EVENT_ID)
        handler = ExecEventHandler()
        _custom_event.add(handler)
        _handlers.append(handler)          # keep it alive

        _server = BridgeServer((HOST, PORT), BridgeHandler)
        _server_thread = threading.Thread(target=_server.serve_forever,
                                          name="FusionBridge", daemon=True)
        _server_thread.start()

        _app.log("FusionBridge listening on http://%s:%d" % (HOST, PORT))
        _app.log("FusionBridge token file: %s" % TOKEN_FILE)

    except Exception:
        if _ui:
            _ui.messageBox("FusionBridge failed to start:\n\n%s"
                           % traceback.format_exc())


def stop(context):
    global _server, _server_thread, _custom_event

    try:
        if _server is not None:
            # shutdown() must be called from a thread other than the one
            # running serve_forever, which is exactly the case here.
            _server.shutdown()
            _server.server_close()
    except Exception:
        pass
    _server = None
    _server_thread = None

    try:
        if _custom_event is not None:
            for handler in _handlers:
                try:
                    _custom_event.remove(handler)
                except Exception:
                    pass
        _app.unregisterCustomEvent(EVENT_ID)
    except Exception:
        pass

    _handlers.clear()
    _custom_event = None

    try:
        if _app:
            _app.log("FusionBridge stopped")
    except Exception:
        pass
