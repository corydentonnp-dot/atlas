# Lac de Neuchâtel necklace case — Fusion 360 CAM

A Fusion 360 script that builds the entire CAM job for the relief carving, plus
a repair tool for the terrain mesh.

```
lac-de-neuchatel/
├── LacDeNeuchatel_CAM.py     the Fusion script — run from Scripts and Add-Ins
├── repair_terrain_stl.py     run this FIRST, outside Fusion
├── CLAUDE.md                 project notes for Claude Code
├── README.md
├── bridge/                   drive Fusion from the command line — see bridge/README.md
└── cam/
    ├── 01-terrain.stl        as supplied — do not carve this
    ├── 01-terrain-FIXED.stl  repaired, watertight, use this
    ├── 02-sketch.dxf
    └── 04-build-sheet.txt
```

**Driving Fusion from outside.** `bridge/` holds a Fusion add-in that opens a
token-protected localhost endpoint, so Claude Code (or any script) can run
Python inside Fusion and read the result back — edit, rebuild, regenerate,
re-post without touching a dialog. Setup and the security model are in
[bridge/README.md](bridge/README.md).

---

## Read this before anything else: the supplied STL cannot be carved

`01-terrain.stl` is not a surface. It is a stack of flat ribbons.

| | supplied | repaired |
|---|---|---|
| triangles | 96 690 | 97 608 |
| **zero projected area in XY** | **96 376 (99.7 %)** | 1 840 (walls only, 1.9 %) |
| all three vertices on one Y row | 95 752 | 0 |
| projected surface area | **24.96 mm²** | **7 587.84 mm²** |
| panel area for reference | 7 587.84 mm² | 7 587.84 mm² |
| watertight | no | yes, 0 non-manifold edges of 146 412 |

The exporter walked each DEM scanline and emitted triangles from three
consecutive points *along that row* instead of stitching each row to the next.
It got the triangle count exactly right and the indexing exactly wrong.

**What would have happened.** A 3D Parallel pass over that mesh has no surface
to follow. The only real geometry left in the file is the base slab at Z −6.0,
so the cutter goes there — the "machines the whole stock down to the model base"
failure the notes warn about. A machining boundary does not save you, because
the boundary is not the cause. This would have destroyed the blank, the bit, or
both, roughly forty minutes into a two-hour job.

**The good news.** The height data inside the file is perfect: a complete
305 × 157 grid at 0.4 mm pitch, Z −3.0000 to +3.1812, zero missing points, zero
conflicting samples. Exactly the ±3.18 / −3.00 the build sheet specifies. Only
the triangulation was wrong, and the wall and base triangles were already
correct. So it is fully recoverable.

```bash
python3 repair_terrain_stl.py cam/01-terrain.stl cam/01-terrain-FIXED.stl
```

No dependencies. It rebuilds the top surface from the intact grid, keeps the
skirt walls, and re-fans the base so the solid closes. The Fusion script
defaults to the repaired file and **refuses to run** on a mesh that is still
degenerate, so this cannot be forgotten.

The repaired heightfield was rendered back to an image and matches the
reference terrain picture — three lake basins in the right places, cross-checked
against the lake outlines in the DXF.

---

## Running the CAM script

1. Open a Fusion design document.
2. `Utilities > Add-Ins > Scripts and Add-Ins > Scripts`, add
   `LacDeNeuchatel_CAM.py`, Run.
3. Pick the `cam/` folder when prompted, or set `CONFIG["folder"]` to skip the
   dialog.

Everything tunable is in the `CONFIG` block at the top — feeds, depths,
stepovers, layer names, tool geometry. You should not need the API docs to
change a number.

It builds, in order:

| # | operation | tool | depth (build-sheet datum) |
|---|---|---|---|
| 1 | Face | T2 | stops at +3.40 |
| 2 | Pocket basins | T2 | −2.00, 1 mm stepdown |
| 3 | Parallel | T1 | terrain, 0.15 mm stepover, 0° |
| 4 | Trace groove | T1 | −0.50, single pass |
| 5 | Pocket stones | T1 | −1.50 |

Then generates all toolpaths and posts everything as one GRBL file.

### The three known traps, handled

- **Stepover is always set explicitly, never as a cusp height.** Cusp height is
  additionally forced to a non-zero value so an inherited 0 cannot poison the
  operation.
- **`Minimum Cutting Radius` forced to 0** and **`Machine Shallow Areas` forced
  off** on the Parallel pass — both illegal for a tapered tool and both things
  Fusion drags in from whatever operation you built last.
- **A machining boundary is always applied** (panel outline, tool inside).

No 3D Pocket Clearing, no 3D Adaptive, as instructed.

`04_SADDLE_SWALE` is deliberately **not** machined as its own operation. The
swale is modelled into the terrain and gets cut by the Parallel pass; running a
groove down it as well would carve a trench through real drainage.

---

## The Z datum — the most dangerous number in this job

Every Z on the build sheet is in the **lake datum**: lake surface 0.000, land to
+3.18, lake bed to −3.00, model underside −6.00.

But the WCS goes at the stock box **lower-left-front-bottom** corner, as
specified. The model sits on the bottom of a 12 mm stock box, so that corner is
lake Z −6.000 — and **the lake surface posts as G-code Z +6.000.**

| operation | build sheet Z | posted G-code Z |
|---|---|---|
| Face | +3.40 | **+9.400** |
| Pocket basins | −2.00 | **+4.000** |
| Trace groove | −0.50 | **+5.500** |
| Pocket stones | −1.50 | **+4.500** |
| Parallel floor clamp | −3.00 | **+3.000** |

Nothing is wrong here, but **not one build-sheet number appears in the G-code**.
At the machine this means you zero Z on the **spoilboard**, not on the panel. If
you would rather zero on the panel top, move the setup origin to the model
origin and every number above drops by exactly 6.000.

The script pins every depth to the *stock bottom* and converts
(`offset = lake_z − model_base_z`). Fusion's height references are geometric
rather than WCS-relative, so the cuts land correctly wherever you later move the
WCS.

Clearance and retract are pinned to the **stock top** for the same reason: the
un-faced stock top is at lake +6.0, so a 5 mm retract quoted against the lake
datum would put the first rapid *inside* the blank.

---

## One addition to the spec

The Parallel pass gets a **hard floor at lake Z −3.00** (the deepest real lake
bed). The panel outline in the DXF is 122.34 × 63.00 but the mesh footprint is
only 121.60 × 62.40, so the boundary is larger than the model by 0.74 mm in X
and 0.60 mm in Y. In that uncovered margin there is no surface to follow and the
cutter can dive. The clamp costs nothing — no real terrain reaches −3.00 — and
closes the gap. Change it via `CONFIG["parallel"]["bottom_z"]`.

---

## Numbers that were checked against the geometry, not just copied

- **Groove cove width.** SC64 ball tip at 0.50 mm depth cuts **1.475 mm** wide.
  Build sheet says 1.48 for 1.2 mm chain. Confirmed.
- **Stone seats.** All three stones sit essentially on the shoreline datum
  (terrain +0.000, +0.008, +0.020), so each is a 1.50 mm deep cut. The tapered
  ball is 1.73 mm wide at that depth, inside the 3.0 mm amethyst circles with
  0.63 mm clearance per side. Both amethysts and the 7.0 mm sapphire clear.
- **Basin roughing.** Lake beds bottom out at −3.000. Roughing to −2.00 leaves
  at most 1.00 mm for the tapered ball, exactly as intended.
- **Stone positions and diameters** in the DXF match the build sheet to the
  micron.
- **Material per Parallel pass**: worst case **0.309 mm**, from the steepest
  Y-adjacent rise in the DEM (0.823 mm across 0.4 mm of grid) scaled to the
  0.15 mm stepover. The build sheet says 0.27 mm. Slightly optimistic but the
  same order — no cause for concern with a tapered ball in maple, and worth
  knowing if you ever raise the stepover.

---

## What the Fusion CAM API cannot do — you still click these

1. **Tool library.** Creating tools from JSON works on most builds but is the
   flakiest call in the API. The script always writes `T1_tapered_mill.json` and
   `T2_flat_end_mill.json` to the folder regardless, so if the log says the API
   route failed: `Manage > Tool Library > Document library > Import`, then
   reassign the tool on each operation.
2. **Flute count on T1.** The build sheet is unsure whether the SC64 has 2 or 4
   flutes. Count them and fix `CONFIG["T1"]["flutes"]`. It changes only the
   chipload Fusion displays, not the toolpath.
3. **Stock "model on the bottom".** The API sets the fixed 140 × 80 × 12 box,
   but how the spare 2.82 mm is distributed in Z is version-dependent. Open the
   Setup and confirm the model sits on the bottom. Everything else keys off this.
4. **Post verification.** There is no way to confirm from the API that
   `grbl.cps` produced sane output for gSender. Simulate, then read the first
   twenty lines of the `.nc` and check for G21 (mm) and G90 (absolute).
5. **Tool change.** GRBL has no automatic tool change, so the post emits M6 and
   stops between operations 2 and 3. Confirm gSender pauses there, and re-zero Z
   on the new tool before resuming.
6. **Parameter names.** Fusion renames CAM parameters between versions and
   between strategies. Every setting goes through a resilient setter that tries
   several names and *reports what it could not apply* rather than dying
   silently. If anything is listed as unset, leave `CONFIG["dump_parameters"]`
   on and re-run — `cam_parameters_dump.txt` will give you the real names on
   your build, and the fix is a one-line edit.

Because these scripts could not be executed against a live Fusion install here,
treat the first run as a dry run: check the log the script pops up, confirm the
five operations exist with the right tools and depths, and simulate before you
cut. The mesh repair, the tool JSON, the datum arithmetic and the geometry
checks above were all verified directly and are not guesses.

**And do not sand the terrain.**
