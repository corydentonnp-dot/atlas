# Lac de Neuchâtel CNC project — notes for Claude Code

CAM for a maple relief carving of Lac de Neuchâtel, cut on a GRBL router driven
by gSender. Not related to the Tesla app in the rest of this repo.

## You can drive Fusion 360 directly

`bridge/` holds a Fusion add-in that exposes a localhost endpoint. When Fusion is
running with FusionBridge started, run Python **inside** Fusion:

```bash
cd lac-de-neuchatel/bridge
python fusion_cli.py ping                          # is Fusion reachable?
python fusion_cli.py exec -f snippets/status.py    # what is open
python fusion_cli.py exec -f snippets/list_operations.py
python fusion_cli.py exec -c "result = design.rootComponent.name"
```

Code runs with `adsk`, `app`, `ui`, `doc`, `design`, `cam` in scope. Set
`result` for a JSON return value. Exit status is 0 on success, 1 on exception,
so these compose with `&&`.

**Never call `ui.messageBox` or any modal dialog in bridge code** — modals hold
Fusion's main thread, which is the thread the bridge answers on, so the request
hangs. `LacDeNeuchatel_CAM.py` guards this with `CONFIG["show_dialog"]`.

The normal loop: edit `LacDeNeuchatel_CAM.py`, then
`python fusion_cli.py exec -f snippets/build_cam.py --timeout 900`. The snippet
re-imports the script from disk each call, so no Fusion restart is needed.

If `ping` fails, Fusion is closed or the add-in is not running
(`Utilities > Add-Ins > Add-Ins` tab). Do not guess — ask.

## Facts about this job that are easy to get wrong

- **`cam/01-terrain.stl` is broken and must never be carved.** 99.7% of its
  triangles have zero projected area. Use `cam/01-terrain-FIXED.stl`, produced
  by `repair_terrain_stl.py`. The CAM script refuses a degenerate mesh.
- **Build-sheet Z ≠ G-code Z.** The build sheet uses the lake datum (lake
  surface = 0). The WCS sits at the stock lower-left-front-**bottom**, which is
  lake Z −6.0, so the lake surface posts as Z **+6.000**. Depths are pinned to
  the stock bottom via `above_stock_bottom()`. Do not "fix" a depth by removing
  that conversion.
- **Never express the Parallel stepover as a cusp height**, and keep
  `minimumCuttingRadius` at 0 with `machineShallowAreas` off — all three are
  illegal or wrong for the tapered tool and Fusion inherits them between
  operations.
- **No 3D Pocket Clearing, no 3D Adaptive.** They hang or produce garbage on
  this mesh. 3D Parallel only.
- `04_SADDLE_SWALE` is reference geometry, not an operation. The swale is in the
  terrain and the Parallel pass cuts it.
- Fusion renames CAM parameters between versions. `set_param()` tries several
  names and reports failures rather than raising; check `cam_build_log.txt` and
  `cam_parameters_dump.txt` after a run.

## Testing

```bash
python bridge/tests/test_bridge.py     # no Fusion needed, opens no socket
python repair_terrain_stl.py cam/01-terrain.stl /tmp/out.stl
```

The repair script self-reports triangle counts, degeneracy, watertightness and
worst-case material per pass. A healthy run says `WATERTIGHT` with
`non-manifold edges 0`.
