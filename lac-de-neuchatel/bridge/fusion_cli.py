#!/usr/bin/env python3
"""
fusion_cli.py -- drive a running Fusion 360 from the command line.

Talks to the FusionBridge add-in. Fusion must be open with a document loaded and
the add-in running (Utilities > Add-Ins > Add-Ins tab > FusionBridge > Run).

    python fusion_cli.py ping
    python fusion_cli.py exec -c "result = design.rootComponent.name"
    python fusion_cli.py exec -f snippets/list_operations.py
    python fusion_cli.py exec -f snippets/regenerate.py --timeout 600
    echo "result = 1 + 1" | python fusion_cli.py exec -

Exit status is 0 when the code ran cleanly and 1 when it raised, so this
composes with && in a shell.

The code you send runs INSIDE Fusion with these already in scope:

    adsk, app, ui, doc, design, cam

Set a variable called `result` and it comes back as JSON. Anything you print
comes back as stdout.

Never call ui.messageBox in bridge code -- a modal dialog blocks Fusion's main
thread and the call will hang until someone clicks OK.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8181


def addin_folder():
    """Standard Fusion add-ins location for this OS, or None if unknown."""
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return None
        return os.path.join(appdata, "Autodesk", "Autodesk Fusion 360",
                            "API", "AddIns", "FusionBridge")
    if sys.platform == "darwin":
        return os.path.expanduser(
            "~/Library/Application Support/Autodesk/Autodesk Fusion 360/"
            "API/AddIns/FusionBridge")
    return None


def find_token(explicit=None):
    """
    Locate the shared secret.

    Order: --token, FUSION_BRIDGE_TOKEN, the token file beside this script,
    then the token file in the installed add-in folder.
    """
    if explicit:
        return explicit

    from_env = os.environ.get("FUSION_BRIDGE_TOKEN")
    if from_env:
        return from_env.strip()

    candidates = [
        os.path.join(os.path.dirname(os.path.realpath(__file__)),
                     "FusionBridge", "bridge-token.txt"),
    ]
    installed = addin_folder()
    if installed:
        candidates.append(os.path.join(installed, "bridge-token.txt"))

    for path in candidates:
        try:
            if os.path.isfile(path):
                with open(path, "r") as fh:
                    token = fh.read().strip()
                if token:
                    return token
        except Exception:
            continue
    return None


def request(url, token, payload=None, timeout=130):
    """One HTTP round trip to the bridge. Returns the decoded JSON body."""
    data = None
    headers = {"X-Bridge-Token": token or ""}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "error": "HTTP %s" % exc.code}
    except urllib.error.URLError as exc:
        return {"ok": False, "error":
                "cannot reach the bridge at %s (%s).\n"
                "Is Fusion running, with FusionBridge started under\n"
                "Utilities > Add-Ins > Add-Ins tab?" % (url, exc.reason)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def report(payload, quiet=False):
    """Print a result in a shape that is pleasant to read in a terminal."""
    stdout = payload.get("stdout")
    if stdout:
        sys.stdout.write(stdout)
        if not stdout.endswith("\n"):
            sys.stdout.write("\n")

    if payload.get("ok"):
        value = payload.get("result")
        if value is not None:
            if isinstance(value, (dict, list)):
                print(json.dumps(value, indent=2))
            else:
                print(value)
        elif not stdout and not quiet:
            print("ok")
        return 0

    sys.stderr.write((payload.get("error") or "failed").rstrip() + "\n")
    return 1


def main():
    parser = argparse.ArgumentParser(
        description="Drive a running Fusion 360 via the FusionBridge add-in.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--token", default=None,
                        help="overrides FUSION_BRIDGE_TOKEN and the token file")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ping", help="check that Fusion is reachable")
    sub.add_parser("token", help="print the token path and value being used")

    run_cmd = sub.add_parser("exec", help="run Python inside Fusion")
    source = run_cmd.add_mutually_exclusive_group(required=True)
    source.add_argument("-c", "--code", help="inline code")
    source.add_argument("-f", "--file", help="path to a .py file, or - for stdin")
    run_cmd.add_argument("--timeout", type=float, default=120,
                         help="seconds to wait for Fusion (default 120; raise "
                              "this for toolpath generation)")
    run_cmd.add_argument("-q", "--quiet", action="store_true")

    args = parser.parse_args()
    base = "http://%s:%d" % (args.host, args.port)
    token = find_token(args.token)

    if args.command == "token":
        print("token: %s" % (token or "<not found>"))
        print("looked in: FUSION_BRIDGE_TOKEN, ./FusionBridge/bridge-token.txt, %s"
              % (addin_folder() or "<unknown add-in folder for this OS>"))
        return 0 if token else 1

    if not token:
        sys.stderr.write(
            "No bridge token found. Start the FusionBridge add-in once to "
            "generate it, then either run this script from the bridge folder "
            "or set FUSION_BRIDGE_TOKEN.\n")
        return 1

    if args.command == "ping":
        return report(request(base + "/ping", token, timeout=20))

    if args.file == "-":
        code = sys.stdin.read()
    elif args.file:
        with open(args.file, "r") as fh:
            code = fh.read()
    else:
        code = args.code

    payload = {"code": code, "timeout": args.timeout}
    # Give the HTTP read a little more headroom than Fusion itself, so a slow
    # operation reports Fusion's own timeout message rather than a socket error.
    result = request(base + "/exec", token, payload, timeout=args.timeout + 15)
    return report(result, quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
