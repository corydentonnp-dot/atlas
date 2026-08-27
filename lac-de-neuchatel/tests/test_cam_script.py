"""
Tests for LacDeNeuchatel_CAM.py that do not need Fusion.

    python3 tests/test_cam_script.py

Fusion is stubbed by tests/adsk.py, so this only covers the pure logic: the Z
datum conversion, the broken-mesh guard, headless dialog safety and the tool
JSON. The parts that actually call the CAM API cannot be tested without Fusion
and are checked by the script's own log at run time.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, PROJECT)

import adsk  # noqa: E402  installs the stub
import LacDeNeuchatel_CAM as M  # noqa: E402

CAM_DIR = os.path.join(PROJECT, "cam")
results = []


def check(label, condition, detail=""):
    results.append(bool(condition))
    if condition:
        print("  pass  %s" % label)
    else:
        print("  FAIL  %s   %s" % (label, detail))


# --------------------------------------------------------------------------
# The single most dangerous number in the job. Build-sheet Z is in the lake
# datum; the WCS is at the stock bottom, 6 mm lower. Getting this wrong cuts
# through the spoilboard.
print("Z datum conversion")
check("groove  -0.50 -> 5.50", M.above_stock_bottom(-0.5) == 5.5)
check("stones  -1.50 -> 4.50", M.above_stock_bottom(-1.5) == 4.5)
check("basins  -2.00 -> 4.00", M.above_stock_bottom(-2.0) == 4.0)
check("parallel -3.00 -> 3.00", M.above_stock_bottom(-3.0) == 3.0)
check("face    +3.40 -> 9.40", M.above_stock_bottom(3.4) == 9.4)
check("model base is -6.0", M.CONFIG["model_base_z"] == -6.0)
check("stock bottom maps to 0", M.above_stock_bottom(M.CONFIG["model_base_z"]) == 0)

print("\nunit-tagged expressions")
check("_mm formats mm", M._mm(5.5) == "5.500000 mm", M._mm(5.5))
check("_mm handles negatives", M._mm(-3) == "-3.000000 mm", M._mm(-3))

# --------------------------------------------------------------------------
print("\nbroken-mesh guard")
broken = os.path.join(CAM_DIR, "01-terrain.stl")
fixed = os.path.join(CAM_DIR, "01-terrain-FIXED.stl")

if os.path.isfile(broken):
    ok, message = M.verify_mesh_file(broken)
    check("rejects the supplied broken mesh", ok is False, message)
    check("explains how to fix it", "repair_terrain_stl" in message, message)
else:
    print("  skip  broken mesh not present")

if os.path.isfile(fixed):
    ok, message = M.verify_mesh_file(fixed)
    check("accepts the repaired mesh", ok is True, message)
else:
    print("  skip  repaired mesh not present -- run repair_terrain_stl.py")

ok, message = M.verify_mesh_file(os.path.join(CAM_DIR, "does-not-exist.stl"))
check("missing file reported, not raised", ok is False, message)

# --------------------------------------------------------------------------
# Modal dialogs hold Fusion's main thread, which is the thread FusionBridge
# answers on, so a headless run must never raise one.
print("\nheadless safety")


class FakeUI:
    def __init__(self):
        self.shown = []

    def messageBox(self, *args):
        self.shown.append(args)


class FakeApp:
    def __init__(self):
        self.logged = []

    def log(self, message):
        self.logged.append(message)


check("show_dialog defaults to True", M.CONFIG["show_dialog"] is True)

ui, app = FakeUI(), FakeApp()
M.CONFIG["show_dialog"] = False
M.notify(ui, app, "headless")
check("no modal raised when headless", len(ui.shown) == 0, ui.shown)
check("still written to the Fusion log", len(app.logged) == 1, app.logged)

M.CONFIG["show_dialog"] = True
M.notify(ui, app, "interactive")
check("modal raised when interactive", len(ui.shown) == 1, ui.shown)

M.notify(None, None, "nothing to talk to")
check("tolerates missing ui and app", True)
M.CONFIG["show_dialog"] = True

# --------------------------------------------------------------------------
print("\ntool definitions")
t1 = M.tapered_mill_json(M.CONFIG["T1"])
check("T1 is a tapered mill", t1["type"] == "tapered mill", t1["type"])
check("T1 tip diameter 1.588", t1["geometry"]["DC"] == 1.588)
check("T1 corner radius 0.794", t1["geometry"]["RE"] == 0.794)
check("T1 taper stored in radians (5.5 deg)",
      abs(math.degrees(t1["geometry"]["TA"]) - 5.5) < 1e-9,
      t1["geometry"]["TA"])
check("T1 corner radius is half the tip, ie a true ball",
      abs(t1["geometry"]["RE"] * 2 - t1["geometry"]["DC"]) < 1e-9)
check("T1 spindle 18000", t1["start-values"]["presets"][0]["n"] == 18000)
check("T1 plunge 500", t1["start-values"]["presets"][0]["v_f_plunge"] == 500)
check("T1 serialises to JSON", bool(json.dumps(t1)))

t2 = M.flat_mill_json(M.CONFIG["T2"])
check("T2 is a flat end mill", t2["type"] == "flat end mill", t2["type"])
check("T2 diameter 6.35", t2["geometry"]["DC"] == 6.35)
check("T2 serialises to JSON", bool(json.dumps(t2)))
check("tool numbers differ", t1["post-process"]["number"]
      != t2["post-process"]["number"])

# --------------------------------------------------------------------------
print("\nbuild-sheet agreement")
check("stock is 140 x 80 x 12",
      (M.CONFIG["stock"]["x"], M.CONFIG["stock"]["y"], M.CONFIG["stock"]["z"])
      == (140.0, 80.0, 12.0))
check("parallel stepover 0.15", M.CONFIG["parallel"]["stepover"] == 0.15)
check("parallel angle 0", M.CONFIG["parallel"]["angle_deg"] == 0.0)
check("groove bottom -0.50", M.CONFIG["groove"]["bottom_z"] == -0.50)
check("stones bottom -1.50", M.CONFIG["stones"]["bottom_z"] == -1.50)
check("basins bottom -2.00", M.CONFIG["basins"]["bottom_z"] == -2.00)
check("swale is not an operation layer",
      not any("SWALE" in name.upper()
              for group in M.CONFIG["layers"].values() for name in group))
check("three stone layers", len(M.CONFIG["layers"]["stones"]) == 3)
check("three lake layers", len(M.CONFIG["layers"]["lakes"]) == 3)
check("five groove layers", len(M.CONFIG["layers"]["grooves"]) == 5)

passed = sum(results)
print("\n%d passed, %d failed" % (passed, len(results) - passed))
sys.exit(0 if all(results) else 1)
