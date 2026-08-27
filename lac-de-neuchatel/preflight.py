#!/usr/bin/env python3
"""
preflight.py -- is this machine ready to cut?

    python preflight.py            check everything
    python preflight.py --bridge   also try to reach Fusion

Checks, in the order they matter:
  1. Python is new enough
  2. the input files are present
  3. the terrain mesh is the repaired one, not the broken original
  4. the Fusion script and the FusionBridge add-in are installed
  5. optionally, that Fusion is running and the bridge answers

Every failure prints the exact command that fixes it. Nothing here touches
Fusion unless you pass --bridge.
"""

import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
CAM_DIR = os.path.join(HERE, "cam")

OK = "  ok    "
BAD = "  MISS  "
WARN = "  warn  "

problems = []


def report(good, label, detail="", fix=None):
    print(("%s%s" % (OK if good else BAD, label))
          + ("   %s" % detail if detail else ""))
    if not good and fix:
        problems.append((label, fix))
    return good


def fusion_api_dir():
    """Fusion's API folder for this OS, or None if Fusion cannot live here."""
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return None
        return os.path.join(appdata, "Autodesk", "Autodesk Fusion 360", "API")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Autodesk/"
                                  "Autodesk Fusion 360/API")
    return None


def mesh_health(path):
    """
    Sample the STL and report the share of triangles with no projected area.

    The broken export is ~100%; a healthy solid is only its vertical walls.
    """
    with open(path, "rb") as fh:
        fh.read(80)
        count = struct.unpack("<I", fh.read(4))[0]
        degenerate = checked = 0
        step = max(1, count // 4000)
        for i in range(count):
            data = fh.read(50)
            if len(data) < 50:
                break
            if i % step:
                continue
            v = struct.unpack("<12f", data[:48])
            x1, y1, x2, y2, x3, y3 = v[3], v[4], v[6], v[7], v[9], v[10]
            area = abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2.0
            checked += 1
            if area < 1e-9:
                degenerate += 1
    return count, (float(degenerate) / checked if checked else 1.0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge", action="store_true",
                        help="also check that Fusion is running and reachable")
    args = parser.parse_args()

    print("Lac de Neuchatel -- preflight")
    print("project: %s\n" % HERE)

    # 1 -------------------------------------------------------------------
    print("python")
    report(sys.version_info >= (3, 7),
           "python %d.%d" % sys.version_info[:2],
           fix="install Python 3.7 or newer and put it on PATH")

    # 2 -------------------------------------------------------------------
    print("\ninput files")
    wanted = {
        "01-terrain.stl": "the original mesh, kept for reference",
        "01-terrain-FIXED.stl": "the repaired mesh -- this is what gets carved",
        "02-sketch.dxf": "panel outline, grooves, lakes, stones",
        "04-build-sheet.txt": "authoritative dimensions",
    }
    for name, why in wanted.items():
        path = os.path.join(CAM_DIR, name)
        exists = os.path.isfile(path)
        detail = ("%.1f MB" % (os.path.getsize(path) / 1e6)) if exists else why
        if name == "01-terrain-FIXED.stl" and not exists:
            report(False, name, why,
                   fix="python repair_terrain_stl.py cam/01-terrain.stl "
                       "cam/01-terrain-FIXED.stl")
        else:
            report(exists, name, detail,
                   fix="restore %s from the repository" % name)

    # 3 -------------------------------------------------------------------
    print("\nterrain mesh")
    fixed = os.path.join(CAM_DIR, "01-terrain-FIXED.stl")
    if os.path.isfile(fixed):
        try:
            count, ratio = mesh_health(fixed)
            healthy = ratio < 0.5
            report(healthy,
                   "repaired mesh is a real surface",
                   "%d triangles, %.1f%% zero-area (walls)" % (count, 100 * ratio),
                   fix="re-run repair_terrain_stl.py; this file is still degenerate")
            if healthy and ratio > 0.05:
                print(WARN + "more zero-area triangles than expected "
                             "(~1.9%% is normal)")
        except Exception as exc:
            report(False, "repaired mesh readable", str(exc),
                   fix="re-run repair_terrain_stl.py")
    else:
        print(BAD + "no repaired mesh to check")

    original = os.path.join(CAM_DIR, "01-terrain.stl")
    if os.path.isfile(original):
        try:
            _, ratio = mesh_health(original)
            print(("%soriginal mesh still degenerate as expected  %.1f%% "
                   "-- never carve this one") % (OK, 100 * ratio))
        except Exception:
            pass

    # 4 -------------------------------------------------------------------
    print("\nfusion install")
    api = fusion_api_dir()
    if api is None:
        print(WARN + "not Windows or macOS -- Fusion 360 does not run here, "
                     "so the install checks are skipped")
    else:
        report(os.path.isdir(api), "Fusion API folder", api,
               fix="install Fusion 360, or run it once so it creates %s" % api)

        script = os.path.join(api, "Scripts", "LacDeNeuchatel_CAM",
                              "LacDeNeuchatel_CAM.py")
        report(os.path.isfile(script), "CAM script installed",
               script if os.path.isfile(script) else "not found",
               fix="run setup_windows.ps1, or copy LacDeNeuchatel_CAM.py into "
                   "<API>/Scripts/LacDeNeuchatel_CAM/")

        addin = os.path.join(api, "AddIns", "FusionBridge", "FusionBridge.py")
        report(os.path.isfile(addin), "FusionBridge add-in installed",
               addin if os.path.isfile(addin) else "not found",
               fix="run setup_windows.ps1, or copy bridge/FusionBridge into "
                   "<API>/AddIns/")

        token = os.path.join(api, "AddIns", "FusionBridge", "bridge-token.txt")
        if os.path.isfile(token):
            print(OK + "bridge token generated (add-in has run at least once)")
        else:
            print(WARN + "no bridge token yet -- start the add-in once in "
                         "Fusion: Utilities > Add-Ins > Add-Ins tab")

    # 5 -------------------------------------------------------------------
    if args.bridge:
        print("\nbridge")
        sys.path.insert(0, os.path.join(HERE, "bridge"))
        try:
            import fusion_cli
            tok = fusion_cli.find_token()
            if not tok:
                report(False, "bridge token found", "",
                       fix="start FusionBridge in Fusion once to generate it")
            else:
                answer = fusion_cli.request("http://127.0.0.1:8181/ping",
                                            tok, timeout=10)
                if answer.get("ok"):
                    info = answer.get("result") or {}
                    report(True, "Fusion is reachable",
                           "document=%s workspace=%s"
                           % (info.get("document"), info.get("workspace")))
                else:
                    report(False, "Fusion is reachable",
                           (answer.get("error") or "").splitlines()[0],
                           fix="open Fusion with a document, then "
                               "Utilities > Add-Ins > Add-Ins tab > "
                               "FusionBridge > Run")
        except Exception as exc:
            report(False, "bridge client usable", str(exc),
                   fix="check bridge/fusion_cli.py is present")

    # ---------------------------------------------------------------------
    print()
    if problems:
        print("%d thing%s to fix:\n" % (len(problems),
                                        "" if len(problems) == 1 else "s"))
        for label, fix in problems:
            print("  %s" % label)
            print("      %s\n" % fix)
        return 1

    print("Ready. Next: open Fusion, start FusionBridge, then")
    print("  cd bridge && python fusion_cli.py ping")
    return 0


if __name__ == "__main__":
    sys.exit(main())
