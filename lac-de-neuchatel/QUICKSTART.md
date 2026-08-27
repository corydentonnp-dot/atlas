# Tomorrow, in order

Start to finish is about ten minutes, most of it Fusion loading.

---

## 1. Get the files (2 min)

```powershell
cd ~\Documents
git clone https://github.com/corydentonnp-dot/atlas.git
cd atlas
git checkout claude/fusion-relief-cutting-pc-3crxen
cd lac-de-neuchatel
```

No git? The [branch page](https://github.com/corydentonnp-dot/atlas/tree/claude/fusion-relief-cutting-pc-3crxen)
has **Code → Download ZIP**.

You need **Python 3** on PATH. If `python --version` fails, install from
[python.org](https://python.org/downloads) and tick *Add python.exe to PATH*.

---

## 2. Run setup (1 min)

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
```

Repairs the mesh, installs the CAM script and the bridge add-in into Fusion,
then runs preflight. Safe to re-run; it keeps your bridge token.

Everything should come back `ok`. Anything that doesn't prints the exact command
that fixes it.

---

## 3. Start the bridge in Fusion (2 min)

1. Open Fusion 360, open or create a design document.
2. `Utilities > Add-Ins > Add-Ins` tab → **FusionBridge** → **Run**.
   Tick *Run on Startup* so you never do this again.
3. Back in the terminal:

```powershell
cd bridge
python fusion_cli.py ping
```

Expected:

```json
{ "version": "2.0.x", "document": "Untitled", "workspace": "FusionSolidEnvironment" }
```

**If ping fails**, it is one of three things, in likelihood order: Fusion isn't
open, the add-in isn't running, or no document is open. The error message says
which.

---

## 4. Run the tests once (10 sec)

```powershell
cd ..
python tests\test_cam_script.py
python bridge\tests\test_bridge.py
```

Expect **40 passed, 0 failed** and **45 passed, 0 failed**. Neither needs Fusion.

The second one has not had a clean end-to-end run — the sandbox it was written
in blocks executing a module that opens a server socket. If anything fails there,
tell me the output before using the bridge.

---

## 5. Hand it to Claude Code

```powershell
cd ~\Documents\atlas
claude
```

`lac-de-neuchatel/CLAUDE.md` tells Claude Code the bridge exists, how to call it,
and the traps in this job. Reasonable openers:

> run preflight and tell me if anything is off

> ping Fusion, then show me what's in the document

> build the CAM setup and report which parameters Fusion rejected

From there it's a loop: it edits `LacDeNeuchatel_CAM.py`, runs
`snippets/build_cam.py`, reads the errors back, fixes, re-runs. No Fusion
restart, no dialogs.

---

## Before you cut

Nothing above has touched real Fusion yet, so treat the first build as a dry run.

- [ ] `cam_build_log.txt` — read the "PARAMETERS THAT COULD NOT BE SET" list.
      Fusion renames CAM parameters between versions; anything listed is a
      one-line fix using `cam_parameters_dump.txt`.
- [ ] **Stock** — open the Setup, confirm the model sits on the *bottom* of the
      140 × 80 × 12 box with all 2.82 mm of spare above it. Everything keys off
      this.
- [ ] **Count T1's flutes.** The build sheet is unsure whether the SC64 has 2 or
      4. Fix `CONFIG["T1"]["flutes"]`. Affects the displayed chipload only.
- [ ] **Simulate all five operations.** Especially Parallel — that's the one
      that carves the map.
- [ ] **Read the first 20 lines of the `.nc`.** Want `G21` (mm) and `G90`
      (absolute).
- [ ] **Zero Z on the spoilboard, not the panel.** The WCS is at the stock
      bottom, so the lake surface is Z **+6.000** and the groove cuts at
      **+5.500**. None of the build-sheet Z numbers appear in the G-code. This
      is the single easiest way to ruin the blank.
- [ ] **Tool change** between ops 2 and 3 posts as `M6` and stops. GRBL won't do
      it for you — confirm gSender pauses, and re-zero Z on T1 before resuming.

---

## If something is wrong

Everything is on the branch, so nothing is lost. Useful context to send me:

- `cam/cam_build_log.txt` — what the script did and what it couldn't set
- `cam/cam_parameters_dump.txt` — the real parameter names on your Fusion build
- output of `python preflight.py --bridge`

With the bridge up I can diagnose directly instead of guessing, which is the
whole reason it exists.

**And do not sand the terrain.**
