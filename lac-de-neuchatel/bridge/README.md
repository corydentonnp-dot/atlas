# FusionBridge — let Claude Code drive Fusion 360

Fusion's API is in-process only: no CLI, no headless mode, no port. This add-in
adds the missing port, so anything on your machine — Claude Code included — can
run Python *inside* Fusion and read the answer back.

```
bridge/
├── FusionBridge/
│   ├── FusionBridge.py         the add-in (install this into Fusion)
│   └── FusionBridge.manifest
├── fusion_cli.py               the client you actually call
├── snippets/                   ready-made jobs
└── tests/test_bridge.py        runs without Fusion
```

## How it works

Fusion's API is **not thread safe** — every `adsk.*` call must happen on its main
thread. So the add-in never touches the API from the HTTP thread:

```
your command  ->  HTTP thread  ->  fireCustomEvent(job id)
                                        |
                                 Fusion's MAIN thread runs your code
                                        |
                  HTTP thread  <-  threading.Event is set
              <-  JSON response
```

The HTTP thread parks on an `Event` until the main thread leaves a result
behind. That handshake is the whole design; everything else is plumbing.

## Install

1. Copy the **`FusionBridge` folder** into Fusion's add-ins directory:

   | OS | path |
   |---|---|
   | Windows | `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\` |
   | macOS | `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/` |

   ```powershell
   $dest = "$env:APPDATA\Autodesk\Autodesk Fusion 360\API\AddIns"
   copy -Recurse bridge\FusionBridge $dest
   ```

2. In Fusion: `Utilities > Add-Ins > Add-Ins` tab → **FusionBridge** → **Run**.
   Tick *Run on Startup* if you want it always on.

3. Check it:

   ```bash
   python fusion_cli.py ping
   ```

   ```json
   { "version": "2.0.x", "document": "Untitled", "workspace": "CAMEnvironment" }
   ```

The token is generated on first run into `FusionBridge/bridge-token.txt`. The
CLI finds it automatically; `python fusion_cli.py token` shows where it looked.

## Using it

```bash
# one-liner
python fusion_cli.py exec -c "result = design.rootComponent.name"

# a file
python fusion_cli.py exec -f snippets/status.py

# stdin
echo "result = len(list(cam.setups))" | python fusion_cli.py exec -

# slow things need a longer leash
python fusion_cli.py exec -f snippets/build_cam.py --timeout 900
```

Your code runs with `adsk`, `app`, `ui`, `doc`, `design`, `cam` already in
scope. Set `result` and it comes back as JSON; `print()` comes back as stdout.
Exit status is 0 on success, 1 if the code raised — so `&&` works.

### Snippets

| snippet | does |
|---|---|
| `status.py` | what document, workspace, bodies, sketches, setups exist |
| `list_operations.py` | every operation, its tool, and the parameters that matter |
| `build_cam.py` | runs the whole CAM build headless |
| `regenerate.py` | regenerates all toolpaths, reports which are valid |
| `set_parameter.py` | change one parameter, regenerate that one operation |
| `post.py` | post everything to one GRBL file |

`build_cam.py` and `post.py` have a path at the top to edit.

`build_cam.py` re-imports the CAM script from disk on every call, so Claude Code
can edit `LacDeNeuchatel_CAM.py` and re-run without restarting Fusion. That loop
is the point of the whole exercise.

## The one rule

**Never call `ui.messageBox` in bridge code.** A modal dialog holds Fusion's main
thread — the same thread the bridge needs to answer on — so the request hangs
until someone clicks OK on a window they may not be looking at. The same goes
for `createFolderDialog` and any other modal.

`LacDeNeuchatel_CAM.py` has a `CONFIG["show_dialog"]` flag for exactly this;
`build_cam.py` sets it to `False`. If a call ever does hang, look at the Fusion
window — there is almost certainly a dialog waiting.

## Security

This endpoint executes arbitrary Python inside Fusion. Two things keep it honest:

- **Bound to `127.0.0.1`.** Nothing off your machine can reach it.
- **`X-Bridge-Token` header required.** This is the part that matters. A
  malicious web page you happen to have open *can* silently POST to localhost —
  but it cannot set a custom header without a CORS preflight, and the server
  answers every preflight with 403 and never sends CORS headers. That is what
  stops a random browser tab from driving your CNC job.

Turn the add-in off when you are not using it. Treat `bridge-token.txt` like a
password; it is gitignored.

## Tests

```bash
python tests/test_bridge.py
```

45 checks covering token comparison, the main-thread handshake, timeout
recovery, output capture, and every HTTP status path. It stubs `adsk`, so
**Fusion does not need to be running** and no socket is opened — the handler is
driven directly with in-memory streams.

Last full run here: **44 passed, 1 failed**, and that one failure was a bad
assertion in the test (`this is not python` is valid Python — an `is not`
comparison — so `NameError` was the correct outcome, not `SyntaxError`). That
assertion has been corrected and two checks added, but the suite has not been
re-run end to end since, because this sandbox blocks executing a module that
opens a server socket. **Run it once on your machine before trusting the
bridge.** It takes about three seconds.

## Limits worth knowing

- Fusion must be **running with a document open**. This is remote control, not
  headless — there is no headless Fusion, and Autodesk's Design Automation
  service covers AutoCAD, Inventor, Revit and 3ds Max, but not Fusion 360.
- **One request at a time.** Fusion's main thread is a single resource; requests
  queue.
- **Long operations block Fusion's UI** while they run. That is normal — it is
  the same thread the UI uses.
- **Fusion updates break add-ins.** When Autodesk changes the API this may need
  a touch-up. The failure mode is loud, not silent.
- Fusion is **Windows and macOS only**.
