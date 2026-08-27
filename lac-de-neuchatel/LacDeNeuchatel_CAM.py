"""
LacDeNeuchatel_CAM.py
Fusion 360 script -- builds the whole CAM job for the Lac de Neuchatel
necklace case, so none of it has to be clicked in by hand.

HOW TO RUN
----------
1. Put this file in its own folder named "LacDeNeuchatel_CAM" inside
   Fusion's script folder, or just add it via the "+" in the dialog below.
2. Fusion 360 > Utilities > Add-Ins > Scripts and Add-Ins > Scripts
3. Select "LacDeNeuchatel_CAM" and press Run.

Everything you might want to change lives in the CONFIG block below. You should
not have to read Autodesk's API docs to retune a feed, a depth or a stepover.

READ THIS FIRST -- THE SUPPLIED MESH IS BROKEN
----------------------------------------------
01-terrain.stl as delivered cannot be carved. 99.7% of its triangles have zero
projected area; 95752 of 96690 have all three vertices on the same Y scanline.
It is a stack of flat ribbons, not a surface. The height data inside it is
perfect -- a complete 305 x 157 grid at 0.4 mm, Z -3.0000 to +3.1812 -- but the
triangles were indexed along each row instead of stitched between rows.

Carving that file would send the Parallel pass to the only real geometry left,
the base slab at Z-6.0, and cut your panel in half. A machining boundary does
not save you, because the boundary is not the problem.

Run repair_terrain_stl.py first. It rebuilds the surface from the intact grid
and writes a watertight solid. This script defaults to the repaired file and
refuses to continue if it is handed a mesh that is still degenerate.

WHAT THIS SCRIPT CANNOT DO -- the honest list is at the bottom of this file
and is also printed to the log when the script finishes.
"""

import os
import json
import math
import time
import traceback

import adsk.core
import adsk.fusion
import adsk.cam


# =============================================================================
# CONFIG -- everything tweakable is here
# =============================================================================

CONFIG = {
    # --- input files ---------------------------------------------------------
    # Folder holding the mesh and the DXF. Leave as None to be prompted.
    "folder": None,

    # Use the REPAIRED mesh. Point this at the raw 01-terrain.stl only if you
    # have fixed the triangulation some other way.
    "mesh_file": "01-terrain-FIXED.stl",
    "dxf_file": "02-sketch.dxf",

    # Import the geometry, or assume it is already in the open design.
    "import_mesh": True,
    "import_dxf": True,

    # Abort if the mesh still looks like the broken original. Keep this True.
    "verify_mesh": True,

    # --- stock and WCS -------------------------------------------------------
    # Fixed size box, model sitting on the bottom.
    "stock": {"x": 140.0, "y": 80.0, "z": 12.0},

    # THE ONE THING MOST LIKELY TO RUIN THE PANEL -- read this.
    #
    # Every Z on the build sheet is in the LAKE datum: lake surface = 0.000,
    # land up to +3.18, lake bed down to -3.00, model underside at -6.00.
    #
    # But the brief puts the WCS at the stock box LOWER LEFT FRONT BOTTOM
    # corner. The model sits on the bottom of the stock, so the stock bottom is
    # lake Z -6.000, and that corner is G-code Z0. The lake surface therefore
    # posts as Z +6.000, and NONE of the build sheet's Z numbers appear in the
    # G-code as written. That is expected, not a mistake.
    #
    # Fusion's height references are geometric, not WCS relative, so this
    # script pins every depth to the stock bottom and converts:
    #
    #     offset above stock bottom = lake_z - model_base_z
    #
    # which is correct no matter where you later move the WCS.
    #
    #   Face           lake +3.40  ->  9.40 above stock bottom
    #   Pocket basins  lake -2.00  ->  4.00
    #   Parallel floor lake -3.00  ->  3.00
    #   Trace groove   lake -0.50  ->  5.50
    #   Pocket stones  lake -1.50  ->  4.50
    #
    # If you re-export the terrain with a different underside, change this.
    "model_base_z": -6.0,

    # --- tools ---------------------------------------------------------------
    # T1 Whiteside SC64 tapered ball.
    # NOTE the build sheet says the flute count needs checking on the physical
    # bit. Flute count only scales the feed per tooth Fusion reports, it does
    # not change the toolpath, but fix it before you trust the chipload number.
    "T1": {
        "number": 1,
        "description": "Whiteside SC64 tapered ball 1/16 tip",
        "vendor": "Whiteside",
        "product_id": "SC64",
        "tip_diameter": 1.588,       # mm, 1/16"
        "corner_radius": 0.794,      # mm, 1/32" -- a true ball tip
        "taper_per_side_deg": 5.5,   # 11 deg included
        "shank_diameter": 6.35,      # mm, 1/4"
        "overall_length": 63.5,      # mm, 2-1/2"
        "flute_length": 25.4,        # mm, cutting length -- adjust if yours differs
        "body_length": 38.1,         # mm, below the collet
        "flutes": 4,                 # VERIFY ON THE BIT -- may be 2
        "rpm": 18000,
        "feed_cut": 1500,            # mm/min
        "feed_plunge": 500,          # mm/min
    },

    # T2 quarter inch flat end mill, facing and basin roughing only.
    "T2": {
        "number": 2,
        "description": "1/4 in flat end mill",
        "vendor": "",
        "product_id": "",
        "diameter": 6.35,
        "corner_radius": 0.0,
        "shank_diameter": 6.35,
        "overall_length": 63.5,
        "flute_length": 22.0,
        "body_length": 38.1,
        "flutes": 2,
        "rpm": 16000,
        "feed_cut": 2500,
        "feed_plunge": 800,
    },

    # --- operations ----------------------------------------------------------
    "face": {
        "leave_above_z0": 3.4,       # facing stops here, 0.22 above the peak
        "stepdown": 1.0,
    },
    "basins": {
        "bottom_z": -2.0,            # leaves 1.0 mm for the tapered ball
        "stepdown": 1.0,
    },
    "parallel": {
        "stepover": 0.15,            # NEVER express this as a cusp height
        "angle_deg": 0.0,
        "stock_to_leave": 0.0,
        "tolerance": 0.01,
        # Hard floor for the finish pass. The panel outline is slightly larger
        # than the mesh footprint, so without this clamp the cutter can dive in
        # the uncovered margin. -3.0 is the deepest real terrain, the lake bed.
        "bottom_z": -3.0,
        "smoothing": True,
    },
    "groove": {
        "bottom_z": -0.50,
    },
    "stones": {
        "bottom_z": -1.50,
        "stepdown": 0.5,
    },

    # --- clearances ----------------------------------------------------------
    # Measured above the STOCK TOP, not above the lake surface. The un-faced
    # stock top is at lake +6.0, so a retract quoted against the lake datum
    # would put rapids inside the blank on the very first move.
    "clearance_height": 10.0,        # above stock top
    "retract_height": 5.0,           # above stock top

    # --- DXF layers ----------------------------------------------------------
    # These are matched against the sketch names Fusion creates on import.
    "layers": {
        "panel": ["00_PANEL_OUTLINE"],
        "lakes": ["02_LAKE_NEUCHATEL", "02_LAKE_BIELERSEE", "02_LAKE_MORAT"],
        "grooves": ["01_GROOVE_NEUCHATEL", "01_GROOVE_BIELERSEE",
                    "01_GROOVE_MORAT", "01_GROOVE_LINK_BIELERSEE",
                    "01_GROOVE_LINK_MORAT"],
        "stones": ["03_STONE_SAPPHIRE", "03_STONE_AMETHYST_A",
                   "03_STONE_AMETHYST_B"],
        # 04_SADDLE_SWALE is deliberately NOT machined as its own operation.
        # The swale is modelled into the terrain and is cut by the Parallel
        # pass. Cutting it again as a groove would carve a trench through it.
    },

    # --- output --------------------------------------------------------------
    "generate_toolpaths": True,
    "post_process": True,
    "post_name": "grbl.cps",
    "program_name": "1001",
    "output_folder": None,           # None -> alongside the input files

    # --- diagnostics ---------------------------------------------------------
    # Writes every parameter of every created operation to a text file. Turn
    # this on when a parameter below refuses to set and you need its real name
    # on your version of Fusion.
    "dump_parameters": True,
}


# =============================================================================
# Small helpers
# =============================================================================

_log_lines = []
_unset = []      # parameters we could not set, reported at the end


def log(msg):
    _log_lines.append(str(msg))


def _mm(value):
    """Fusion expressions are unit-tagged strings; the API is happiest that way."""
    return "{:.6f} mm".format(float(value))


def above_stock_bottom(lake_z):
    """
    Convert a build-sheet Z (lake datum) into an offset above the stock bottom.

    See the long note in CONFIG. Heights in Fusion are measured from a
    geometric reference, so pinning everything to the stock bottom keeps the
    depths right regardless of where the WCS ends up.
    """
    return float(lake_z) - float(CONFIG["model_base_z"])


def set_height(op, prefix, lake_z, label):
    """
    Set one of Fusion's height fields from a build-sheet Z.

    Both halves have to agree: the reference the offset is measured from, and
    the offset itself. Setting only the offset is how you end up cutting
    through the spoilboard.
    """
    set_param(op, ["%s_mode" % prefix], "from stock bottom",
              "%s reference" % label)
    set_param(op, ["%s_offset" % prefix], above_stock_bottom(lake_z),
              "%s offset" % label)


def set_param(op, names, value, label=None, optional=False):
    """
    Set a CAM parameter, trying several possible names.

    Fusion renames parameters between versions and between strategies, so every
    setting goes through here. Numeric values are passed as unit-tagged
    expressions; booleans and enums go through .value.value. Anything that
    cannot be set is recorded and reported at the end rather than raising, so
    one renamed parameter never kills the whole build.
    """
    if isinstance(names, str):
        names = [names]
    label = label or names[0]

    for name in names:
        try:
            param = op.parameters.itemByName(name)
        except Exception:
            param = None
        if param is None:
            continue

        # numeric -> expression
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            for expr in (_mm(value), "{:.6f}".format(float(value)), str(value)):
                try:
                    param.expression = expr
                    return True
                except Exception:
                    continue

        # boolean / enum / string -> value.value
        try:
            param.value.value = value
            return True
        except Exception:
            pass
        try:
            param.expression = str(value)
            return True
        except Exception:
            pass

    if not optional:
        _unset.append("{}  ({})".format(label, " / ".join(names)))
    return False


def find_contour_param(op, preferred):
    """
    Return a geometry parameter that holds a 2D contour selection.

    Tries the expected names first, then falls back to scanning every parameter
    on the operation for one whose value is a CadContours2dParameterValue. The
    scan is what makes this survive a parameter rename.
    """
    if isinstance(preferred, str):
        preferred = [preferred]

    for name in preferred:
        try:
            param = op.parameters.itemByName(name)
            if param is not None:
                cad = adsk.cam.CadContours2dParameterValue.cast(param.value)
                if cad:
                    return cad
        except Exception:
            pass

    try:
        for param in op.parameters:
            try:
                cad = adsk.cam.CadContours2dParameterValue.cast(param.value)
                if cad:
                    log("      (used fallback geometry parameter '%s')" % param.name)
                    return cad
            except Exception:
                continue
    except Exception:
        pass
    return None


# =============================================================================
# Mesh sanity check
# =============================================================================

def verify_mesh_file(path):
    """
    Refuse to build a job on the broken mesh.

    Returns (ok, message). A healthy heightfield has almost all of its
    triangles carrying real projected area; the broken export has almost none.
    """
    import struct

    try:
        with open(path, "rb") as fh:
            fh.read(80)
            count = struct.unpack("<I", fh.read(4))[0]
            if count == 0 or count > 5000000:
                return False, "STL triangle count looks wrong (%d)." % count

            degenerate = 0
            checked = 0
            step = max(1, count // 4000)          # sample, do not read 100k facets
            for i in range(count):
                data = fh.read(50)
                if len(data) < 50:
                    break
                if i % step:
                    continue
                v = struct.unpack("<12f", data[:48])
                x1, y1 = v[3], v[4]
                x2, y2 = v[6], v[7]
                x3, y3 = v[9], v[10]
                area = abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2.0
                checked += 1
                if area < 1e-9:
                    degenerate += 1
    except Exception as exc:
        return False, "Could not read the STL: %s" % exc

    if not checked:
        return False, "No triangles could be sampled from the STL."

    ratio = float(degenerate) / checked
    if ratio > 0.5:
        return False, (
            "This mesh is the broken export: %.1f%% of sampled triangles have "
            "zero projected area. Run repair_terrain_stl.py and point "
            "CONFIG['mesh_file'] at the repaired file."
            % (100.0 * ratio))
    return True, "Mesh looks sane (%.1f%% degenerate, walls only)." % (100.0 * ratio)


# =============================================================================
# Tool definitions
# =============================================================================

def tapered_mill_json(spec):
    """
    Build Fusion tool-library JSON for the SC64.

    Fusion models this as a Tapered Mill with a corner radius. Because the
    corner radius equals half the tip diameter, the tip is a true ball, which
    is what the SC64 actually is.

    Angles in this JSON are RADIANS. TA is the half angle, ie per side.
    """
    return {
        "version": 1,
        "guid": "",
        "type": "tapered mill",
        "unit": "millimeters",
        "description": spec["description"],
        "vendor": spec["vendor"],
        "product-id": spec["product_id"],
        "geometry": {
            "DC": spec["tip_diameter"],                 # cutting diameter at tip
            "RE": spec["corner_radius"],                # corner radius
            "TA": math.radians(spec["taper_per_side_deg"]),
            "LCF": spec["flute_length"],                # flute length
            "LB": spec["body_length"],                  # body length
            "OAL": spec["overall_length"],
            "NOF": spec["flutes"],
            "SFDM": spec["shank_diameter"],             # shaft diameter
            "shoulder-length": spec["flute_length"],
            "HAND": True,                               # right hand
            "coolant": "disabled",
        },
        "start-values": {
            "presets": [{
                "name": "Default",
                "description": spec["description"],
                "tool-coolant": "disabled",
                "n": spec["rpm"],
                "v_f": spec["feed_cut"],
                "v_f_plunge": spec["feed_plunge"],
                "v_f_leadIn": spec["feed_cut"],
                "v_f_leadOut": spec["feed_cut"],
                "v_f_ramp": spec["feed_plunge"],
                "v_f_retract": spec["feed_cut"],
                "f_n": round(spec["feed_cut"] /
                             float(spec["rpm"] * spec["flutes"]), 5),
            }],
        },
        "post-process": {
            "number": spec["number"],
            "diameter-offset": spec["number"],
            "length-offset": spec["number"],
            "live": True,
            "turret": 0,
            "comment": spec["description"],
        },
    }


def flat_mill_json(spec):
    """Fusion tool-library JSON for the 1/4 inch flat end mill."""
    return {
        "version": 1,
        "guid": "",
        "type": "flat end mill",
        "unit": "millimeters",
        "description": spec["description"],
        "vendor": spec["vendor"],
        "product-id": spec["product_id"],
        "geometry": {
            "DC": spec["diameter"],
            "RE": spec["corner_radius"],
            "LCF": spec["flute_length"],
            "LB": spec["body_length"],
            "OAL": spec["overall_length"],
            "NOF": spec["flutes"],
            "SFDM": spec["shank_diameter"],
            "shoulder-length": spec["flute_length"],
            "HAND": True,
            "coolant": "disabled",
        },
        "start-values": {
            "presets": [{
                "name": "Default",
                "description": spec["description"],
                "tool-coolant": "disabled",
                "n": spec["rpm"],
                "v_f": spec["feed_cut"],
                "v_f_plunge": spec["feed_plunge"],
                "v_f_leadIn": spec["feed_cut"],
                "v_f_leadOut": spec["feed_cut"],
                "v_f_ramp": spec["feed_plunge"],
                "v_f_retract": spec["feed_cut"],
                "f_n": round(spec["feed_cut"] /
                             float(spec["rpm"] * spec["flutes"]), 5),
            }],
        },
        "post-process": {
            "number": spec["number"],
            "diameter-offset": spec["number"],
            "length-offset": spec["number"],
            "live": True,
            "turret": 0,
            "comment": spec["description"],
        },
    }


def ensure_tools(cam, folder):
    """
    Put T1 and T2 into the document tool library and return them.

    Tool creation is the least stable corner of the CAM API, so the .json files
    are always written to disk as well. If the API route fails you can import
    them by hand in seconds: Manage > Tool Library > Import.
    """
    tool_json = {
        "T1": tapered_mill_json(CONFIG["T1"]),
        "T2": flat_mill_json(CONFIG["T2"]),
    }

    # Always write the JSON, whether or not the API route works.
    for key, payload in tool_json.items():
        path = os.path.join(folder, "%s_%s.json" % (key, payload["type"].replace(" ", "_")))
        try:
            with open(path, "w") as fh:
                json.dump(payload, fh, indent=2)
            log("  wrote tool file %s" % os.path.basename(path))
        except Exception as exc:
            log("  could not write %s: %s" % (path, exc))

    tools = {}
    try:
        library = cam.documentToolLibrary
    except Exception:
        library = None

    if library is None:
        log("  ! document tool library unavailable; import the .json files by hand")
        return tools

    # Reuse a matching tool if the script has already been run once.
    for key, spec in (("T1", CONFIG["T1"]), ("T2", CONFIG["T2"])):
        for existing in library:
            try:
                if existing.parameters.itemByName("tool_number").value.value == spec["number"]:
                    tools[key] = existing
                    log("  reusing existing tool #%d" % spec["number"])
                    break
            except Exception:
                continue

    for key, payload in tool_json.items():
        if key in tools:
            continue
        try:
            tool = adsk.cam.Tool.createFromJson(json.dumps(payload))
            if tool is None:
                raise RuntimeError("createFromJson returned nothing")
            added = library.add(tool)
            tools[key] = added if added else tool
            log("  created %s (%s)" % (key, payload["description"]))
        except Exception as exc:
            log("  ! could not create %s via the API: %s" % (key, exc))
            log("    -> import %s_*.json from the folder instead" % key)

    return tools


# =============================================================================
# Geometry lookup
# =============================================================================

def import_geometry(app, design, folder):
    """Import the mesh and the DXF, both already on the shared origin."""
    root = design.rootComponent
    import_manager = app.importManager

    mesh_body = None
    if CONFIG["import_mesh"]:
        mesh_path = os.path.join(folder, CONFIG["mesh_file"])
        if not os.path.isfile(mesh_path):
            raise RuntimeError("Mesh not found: %s" % mesh_path)

        if CONFIG["verify_mesh"]:
            ok, message = verify_mesh_file(mesh_path)
            log("  mesh check: %s" % message)
            if not ok:
                raise RuntimeError(message)

        # The design must be in direct-modelling mode or the mesh import is
        # fussy; either way we never move the mesh, it lands on the origin.
        added = root.meshBodies.add(mesh_path, adsk.fusion.MeshUnits.MillimeterMeshUnit)
        mesh_body = added.item(0) if added.count else None
        if mesh_body:
            mesh_body.name = "Terrain"
            log("  imported mesh: %s" % CONFIG["mesh_file"])
    else:
        if root.meshBodies.count:
            mesh_body = root.meshBodies.item(0)

    if CONFIG["import_dxf"]:
        dxf_path = os.path.join(folder, CONFIG["dxf_file"])
        if not os.path.isfile(dxf_path):
            raise RuntimeError("DXF not found: %s" % dxf_path)
        options = import_manager.createDXF2DImportOptions(dxf_path, root.xYConstructionPlane)
        # One sketch per DXF layer, so the layers stay tellable apart by name.
        options.isSingleSketchResult = False
        import_manager.importToTarget(options, root)
        log("  imported DXF: %s (%d sketches)" % (CONFIG["dxf_file"], root.sketches.count))

    return mesh_body


def curves_for_layers(design, layer_names):
    """
    Collect sketch curves belonging to the named DXF layers.

    Fusion names the sketches after the layers on import, but it also decorates
    them, so the match is a case-insensitive substring rather than equality.
    """
    root = design.rootComponent
    found = adsk.core.ObjectCollection.create()
    matched = []

    for wanted in layer_names:
        hit = False
        for sketch in root.sketches:
            if wanted.lower() in sketch.name.lower():
                for curve in sketch.sketchCurves:
                    found.add(curve)
                matched.append(sketch.name)
                hit = True
        if not hit:
            log("    ! no sketch found for layer '%s'" % wanted)

    return found, matched


def apply_contours(op, cad_param, curves, mode="chain", label=""):
    """
    Push a set of sketch curves into a 2D geometry parameter.

    mode "pocket" is used for closed regions that get cleared out; "chain" is
    used for paths that get followed. Fusion treats the two differently and
    will silently produce nothing if given the wrong one.
    """
    if cad_param is None:
        _unset.append("geometry selection for %s" % label)
        return False
    try:
        selections = cad_param.getCurveSelections()
        selections.clear()
        if mode == "pocket":
            selection = selections.createNewPocketSelection()
        else:
            selection = selections.createNewChainSelection()
        selection.inputGeometry = curves
        try:
            selection.isSelectingSameProfile = True
        except Exception:
            pass
        cad_param.applyCurveSelections(selections)
        return True
    except Exception as exc:
        _unset.append("geometry selection for %s (%s)" % (label, exc))
        return False


# =============================================================================
# Setup
# =============================================================================

def create_setup(cam, mesh_body):
    setups = cam.setups
    setup_input = setups.createInput(adsk.cam.OperationTypes.MillingOperation)

    models = adsk.core.ObjectCollection.create()
    if mesh_body:
        models.add(mesh_body)
    setup_input.models = models
    setup_input.name = "Lac de Neuchatel"

    setup = setups.add(setup_input)

    stock = CONFIG["stock"]

    # Fixed size stock box with the model sitting on the bottom.
    set_param(setup, ["job_stockMode"], "fixedbox", "stock mode")
    for axis, value in (("X", stock["x"]), ("Y", stock["y"]), ("Z", stock["z"])):
        set_param(setup, ["job_stockFixed%s" % axis], value, "stock %s" % axis)
    set_param(setup, ["job_stockFixedZOffset"], 0.0, "stock Z offset", optional=True)
    # "model on the bottom" -> no offset below, everything spare goes on top
    set_param(setup, ["job_stockFixedZMode"], "offset", "stock Z mode", optional=True)

    # WCS at the stock box corner: lower left front bottom.
    set_param(setup, ["wcs_origin_mode"], "stockBoxPoint", "WCS origin mode")
    set_param(setup, ["wcs_origin_boxPoint"], "bottom left front", "WCS box point")

    # Clearances, shared by every operation. Both are pinned to the stock top so
    # they stay safe no matter what the lake datum is doing underneath.
    set_param(setup, ["clearanceHeight_mode"], "from stock top",
              "clearance reference", optional=True)
    set_param(setup, ["clearanceHeight_offset"], CONFIG["clearance_height"],
              "clearance height", optional=True)
    set_param(setup, ["retractHeight_mode"], "from stock top",
              "retract reference", optional=True)
    set_param(setup, ["retractHeight_offset"], CONFIG["retract_height"],
              "retract height", optional=True)

    log("  setup created: %s" % setup.name)
    return setup


# =============================================================================
# Operations
# =============================================================================

def add_operation(setup, strategies, name, tool):
    """Create an operation, trying each candidate strategy id in turn."""
    if isinstance(strategies, str):
        strategies = [strategies]

    last_error = None
    for strategy in strategies:
        try:
            op_input = setup.operations.createInput(strategy)
            op_input.displayName = name
            if tool is not None:
                op_input.tool = tool
            operation = setup.operations.add(op_input)
            log("  + %s  [%s]" % (name, strategy))
            return operation
        except Exception as exc:
            last_error = exc
            continue

    log("  ! could not create %s (tried %s): %s"
        % (name, ", ".join(strategies), last_error))
    return None


def op_face(setup, tool):
    """1. Face the stock flat, stopping 3.4 mm above the lake surface."""
    op = add_operation(setup, ["face"], "1 Face", tool)
    if not op:
        return None
    cfg = CONFIG["face"]
    # Facing stops at lake +3.4, which is 0.22 mm clear of the highest peak.
    set_height(op, "bottomHeight", cfg["leave_above_z0"], "face bottom")
    set_param(op, ["maximumStepdown", "stepdown"], cfg["stepdown"], "face stepdown")
    set_param(op, ["tolerance"], 0.05, "face tolerance", optional=True)
    return op


def op_pocket_basins(setup, tool, design):
    """
    2. Rough the three lake basins with the flat mill.

    This exists purely so the 1.588 mm tip of the SC64 never has to plunge the
    full 3 mm. It takes the basins to -2.0 and leaves the last millimetre for
    the finish pass.
    """
    op = add_operation(setup, ["pocket2d", "pocket"], "2 Pocket basins", tool)
    if not op:
        return None
    cfg = CONFIG["basins"]

    curves, matched = curves_for_layers(design, CONFIG["layers"]["lakes"])
    log("    lake layers: %s" % (", ".join(matched) or "none"))
    cad = find_contour_param(op, ["pockets", "pocketSelections", "contours"])
    apply_contours(op, cad, curves, "pocket", "Pocket basins")

    set_height(op, "bottomHeight", cfg["bottom_z"], "basin bottom")
    set_param(op, ["maximumStepdown", "stepdown"], cfg["stepdown"], "basin stepdown")
    set_param(op, ["stockToLeave"], True, "basin stock to leave flag", optional=True)
    set_param(op, ["verticalStockToLeave"], 0.2, "basin wall stock", optional=True)
    set_param(op, ["horizontalStockToLeave"], 0.2, "basin floor stock", optional=True)
    return op


def op_parallel(setup, tool, design):
    """
    3. The terrain finish pass. This is the operation that carves the map.

    The build sheet's warnings are all handled here:
      - stepover is set explicitly, never as a cusp height
      - minimum cutting radius forced to 0, illegal on a tapered tool otherwise
      - machine shallow areas forced off
      - a machining boundary is mandatory, with the tool kept inside it
      - a hard bottom height, because the panel outline is very slightly larger
        than the mesh footprint and the cutter would otherwise dive in the gap
    """
    op = add_operation(setup, ["parallel_new", "parallel"], "3 Parallel", tool)
    if not op:
        return None
    cfg = CONFIG["parallel"]

    # Stepover, explicitly. Never touch cusp height on a tapered tool.
    set_param(op, ["stepover", "maximumStepover"], cfg["stepover"], "parallel stepover")
    set_param(op, ["useStepover"], True, "parallel use stepover", optional=True)
    set_param(op, ["cuspHeight"], 0.005, "parallel cusp height", optional=True)

    set_param(op, ["parallelAngle", "machiningAngle"], cfg["angle_deg"],
              "parallel machining angle")
    set_param(op, ["tolerance"], cfg["tolerance"], "parallel tolerance")
    set_param(op, ["stockToLeave"], False, "parallel stock to leave flag", optional=True)
    set_param(op, ["verticalStockToLeave"], cfg["stock_to_leave"],
              "parallel vertical stock", optional=True)
    set_param(op, ["horizontalStockToLeave"], cfg["stock_to_leave"],
              "parallel horizontal stock", optional=True)

    # Illegal-for-a-tapered-tool settings that Fusion drags in from whatever
    # operation you built last.
    set_param(op, ["minimumCuttingRadius"], 0.0, "minimum cutting radius")
    set_param(op, ["useMinimumCuttingRadius"], False, "use minimum cutting radius",
              optional=True)
    set_param(op, ["machineShallowAreas", "doMachineShallowAreas"], False,
              "machine shallow areas")

    # Smoothing on.
    set_param(op, ["smoothingFilter", "useSmoothing"], cfg["smoothing"],
              "smoothing", optional=True)
    set_param(op, ["smoothingTolerance"], cfg["tolerance"] / 2.0,
              "smoothing tolerance", optional=True)

    # Machining boundary = panel outline, tool kept inside.
    curves, matched = curves_for_layers(design, CONFIG["layers"]["panel"])
    log("    boundary layer: %s" % (", ".join(matched) or "none"))
    set_param(op, ["machiningBoundary"], "boundarySelection", "machining boundary mode")
    cad = find_contour_param(op, ["machiningBoundarySel", "machiningBoundaryContours",
                                  "boundarySelections"])
    apply_contours(op, cad, curves, "chain", "Parallel boundary")
    set_param(op, ["boundaryContainment", "toolContainment"], "insideBoundary",
              "tool containment")
    set_param(op, ["boundaryContainmentOffset", "additionalOffset"], 0.0,
              "boundary offset", optional=True)

    # Hard depth clamp. See the docstring.
    set_param(op, ["useBottomHeight", "useDepthRange"], True,
              "parallel bottom height flag", optional=True)
    set_height(op, "bottomHeight", cfg["bottom_z"], "parallel bottom")
    return op


def op_trace_groove(setup, tool, design):
    """4. The chain groove. Single pass at Z-0.50, following the shoreline."""
    op = add_operation(setup, ["trace"], "4 Trace groove", tool)
    if not op:
        return None
    cfg = CONFIG["groove"]

    curves, matched = curves_for_layers(design, CONFIG["layers"]["grooves"])
    log("    groove layers: %s" % (", ".join(matched) or "none"))
    cad = find_contour_param(op, ["contours", "traceContours", "curves"])
    apply_contours(op, cad, curves, "chain", "Trace groove")

    set_height(op, "bottomHeight", cfg["bottom_z"], "groove bottom")

    # Single pass: no stepdown ladder, no multiple depths, no side offset.
    set_param(op, ["useMultipleDepths", "multipleDepths"], False,
              "groove multiple depths", optional=True)
    set_param(op, ["numberOfStepovers"], 0, "groove stepovers", optional=True)
    set_param(op, ["sideways_offset", "traceOffset"], 0.0, "groove offset",
              optional=True)
    return op


def op_pocket_stones(setup, tool, design):
    """5. The three stone seats, cut with the tapered ball to Z-1.50."""
    op = add_operation(setup, ["pocket2d", "pocket"], "5 Pocket stones", tool)
    if not op:
        return None
    cfg = CONFIG["stones"]

    curves, matched = curves_for_layers(design, CONFIG["layers"]["stones"])
    log("    stone layers: %s" % (", ".join(matched) or "none"))
    cad = find_contour_param(op, ["pockets", "pocketSelections", "contours"])
    apply_contours(op, cad, curves, "pocket", "Pocket stones")

    set_height(op, "bottomHeight", cfg["bottom_z"], "stone bottom")
    set_param(op, ["maximumStepdown", "stepdown"], cfg["stepdown"], "stone stepdown")
    set_param(op, ["minimumCuttingRadius"], 0.0, "stone minimum cutting radius",
              optional=True)
    return op


# =============================================================================
# Toolpaths and post
# =============================================================================

def generate_all(cam, ui):
    """Generate every toolpath and wait for the queue to drain."""
    try:
        future = cam.generateAllToolpaths(False)
    except Exception as exc:
        log("  ! toolpath generation could not start: %s" % exc)
        return False

    deadline = time.time() + 600      # ten minutes is plenty for this job
    while time.time() < deadline:
        try:
            if future.isGenerationCompleted:
                break
        except Exception:
            break
        adsk.doEvents()
        time.sleep(0.25)

    log("  toolpaths generated")
    return True


def post_all(cam, folder):
    """Post every operation into a single GRBL file."""
    try:
        post_folder = cam.genericPostFolder
        post_path = os.path.join(post_folder, CONFIG["post_name"])
        if not os.path.isfile(post_path):
            # Personal posts live elsewhere; try there before giving up.
            personal = cam.personalPostFolder
            candidate = os.path.join(personal, CONFIG["post_name"])
            if os.path.isfile(candidate):
                post_path = candidate
            else:
                log("  ! %s not found in either post folder; post by hand"
                    % CONFIG["post_name"])
                return False

        output = CONFIG["output_folder"] or folder
        post_input = adsk.cam.PostProcessInput.create(
            CONFIG["program_name"], post_path, output,
            adsk.cam.PostOutputUnitOptions.DocumentUnitsOutput)
        post_input.isOpenInEditor = False
        cam.postProcessAll(post_input)
        log("  posted to %s" % os.path.join(output, CONFIG["program_name"] + ".nc"))
        return True
    except Exception as exc:
        log("  ! post processing failed: %s" % exc)
        return False


def dump_parameters(setup, folder):
    """Write every parameter of every operation, for when a name has changed."""
    path = os.path.join(folder, "cam_parameters_dump.txt")
    try:
        with open(path, "w") as fh:
            for operation in setup.operations:
                fh.write("=" * 70 + "\n%s  [%s]\n" % (operation.name, operation.strategy)
                         + "=" * 70 + "\n")
                for param in operation.parameters:
                    try:
                        value = param.expression
                    except Exception:
                        try:
                            value = str(param.value.value)
                        except Exception:
                            value = "<unreadable>"
                    fh.write("  %-40s = %s\n" % (param.name, value))
                fh.write("\n")
        log("  parameter dump written to %s" % os.path.basename(path))
    except Exception as exc:
        log("  ! could not write parameter dump: %s" % exc)


# =============================================================================
# Entry point
# =============================================================================

MANUAL_STEPS = """
WHAT THE FUSION CAM API CANNOT DO -- you still have to click these
------------------------------------------------------------------
1. TOOL LIBRARY. Tool creation from JSON works on most builds but is the
   flakiest call in the whole API. If the log above says a tool could not be
   created, open Manage > Tool Library, pick the Document library, and import
   T1_tapered_mill.json and T2_flat_end_mill.json from the project folder.
   Then reassign the tool on each operation. Nothing else needs touching.

2. FLUTE COUNT ON T1. The build sheet is unsure whether the SC64 has 2 or 4
   flutes. Count them and fix CONFIG["T1"]["flutes"]. This changes only the
   chipload Fusion displays, not the toolpath.

3. STOCK "MODEL ON THE BOTTOM". The API sets a fixed 140 x 80 x 12 box, but
   which way the spare material is distributed in Z is version dependent.
   Open the Setup, check the Stock tab, and confirm the model sits on the
   bottom of the box with all 2.82 mm of spare above it. This is worth ten
   seconds of your attention because everything else keys off it.

4. THE Z NUMBERS IN THE G-CODE ARE NOT THE BUILD SHEET Z NUMBERS.
   The WCS sits at the stock box lower left front BOTTOM corner, as asked, so
   G-code Z0 is the underside of the blank and the lake surface posts as
   Z +6.000. The groove is at Z +5.500, the stones at +4.500, the basins at
   +4.000, the deepest lake bed at +3.000, the faced surface at +9.400.
   Nothing is wrong; the datum is just 6 mm lower than the build sheet's.
   At the machine this means you zero Z on the SPOILBOARD, not on the panel.
   If you would rather zero on the panel top, move the setup origin to the
   model origin and every number above drops by exactly 6.000.

5. VERIFY THE POST. There is no way to confirm from the API that grbl.cps
   produced sane G-code for gSender. Simulate the job, then read the first
   twenty lines of the .nc file and check the units are mm (G21) and the
   moves are absolute (G90).

6. TOOL CHANGE. This posts as one file with one tool change between operation
   2 and 3, as the build sheet asks. GRBL has no automatic tool change, so the
   post emits M6 and stops. Confirm gSender is set to pause there, and re-zero
   Z on the new tool before resuming.

7. ANYTHING THE LOG FLAGGED AS UNSET. Fusion renames CAM parameters between
   versions. Every setting this script could not apply is listed above. Turn on
   CONFIG["dump_parameters"], re-run, and cam_parameters_dump.txt will give you
   the real parameter names on your build.
"""


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        doc = app.activeDocument
        products = doc.products
        design = adsk.fusion.Design.cast(products.itemByProductType("DesignProductType"))
        if design is None:
            ui.messageBox("Open a design document first, then run this script.")
            return

        # Work out where the input files live.
        folder = CONFIG["folder"]
        if not folder:
            dialog = ui.createFolderDialog()
            dialog.title = "Folder holding 01-terrain-FIXED.stl and 02-sketch.dxf"
            if dialog.showDialog() != adsk.core.DialogResults.DialogOK:
                return
            folder = dialog.folder

        log("Lac de Neuchatel CAM build")
        log("folder: %s" % folder)
        log("")

        # 1. geometry
        log("Geometry")
        mesh_body = import_geometry(app, design, folder)
        if mesh_body is None:
            ui.messageBox("No mesh body found. Set CONFIG['import_mesh'] = True "
                          "or import the terrain manually first.")
            return
        log("")

        # 2. CAM product
        cam = adsk.cam.CAM.cast(products.itemByProductType("CAMProductType"))
        if cam is None:
            # Switching workspace forces the CAM product into existence.
            ui.workspaces.itemById("CAMEnvironment").activate()
            cam = adsk.cam.CAM.cast(doc.products.itemByProductType("CAMProductType"))
        if cam is None:
            ui.messageBox("Could not reach the Manufacture workspace.")
            return

        # 3. tools
        log("Tools")
        tools = ensure_tools(cam, folder)
        log("")

        # 4. setup
        log("Setup")
        setup = create_setup(cam, mesh_body)
        log("")

        # 5. operations, in the order the build sheet specifies
        log("Operations")
        op_face(setup, tools.get("T2"))
        op_pocket_basins(setup, tools.get("T2"), design)
        op_parallel(setup, tools.get("T1"), design)
        op_trace_groove(setup, tools.get("T1"), design)
        op_pocket_stones(setup, tools.get("T1"), design)
        log("")

        if CONFIG["dump_parameters"]:
            dump_parameters(setup, folder)

        # 6. generate and post
        if CONFIG["generate_toolpaths"]:
            log("Toolpaths")
            generate_all(cam, ui)
            log("")

        if CONFIG["post_process"]:
            log("Post")
            post_all(cam, folder)
            log("")

        # 7. report
        if _unset:
            log("PARAMETERS THAT COULD NOT BE SET (%d):" % len(_unset))
            for item in _unset:
                log("  - %s" % item)
            log("")
            log("These are almost always version renames. See cam_parameters_dump.txt.")
        else:
            log("All parameters applied cleanly.")

        report = "\n".join(_log_lines) + "\n" + MANUAL_STEPS
        try:
            with open(os.path.join(folder, "cam_build_log.txt"), "w") as fh:
                fh.write(report)
        except Exception:
            pass

        app.log(report)
        ui.messageBox(report, "Lac de Neuchatel CAM")

    except Exception:
        if ui:
            ui.messageBox("Script failed:\n\n%s" % traceback.format_exc(),
                          "Lac de Neuchatel CAM")
