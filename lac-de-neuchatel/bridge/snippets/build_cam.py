# Run the whole CAM build headless, through the bridge.
#
#   python fusion_cli.py exec -f snippets/build_cam.py --timeout 900
#
# Toolpath generation and posting are slow, so give this a generous timeout.
# EDIT PROJECT to point at your lac-de-neuchatel folder.
import importlib.util
import os
import sys

PROJECT = r"C:\Users\YOU\Documents\atlas\lac-de-neuchatel"

script_path = os.path.join(PROJECT, "LacDeNeuchatel_CAM.py")
if not os.path.isfile(script_path):
    result = "Not found: %s -- edit PROJECT at the top of this snippet." % script_path
else:
    # Load it fresh every time so edits on disk take effect without restarting
    # Fusion. This is the whole point of driving it from outside.
    spec = importlib.util.spec_from_file_location("LacDeNeuchatel_CAM", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["LacDeNeuchatel_CAM"] = module
    spec.loader.exec_module(module)

    # Headless: no modal dialogs, and the folder must be given up front.
    module.CONFIG["show_dialog"] = False
    module.CONFIG["folder"] = os.path.join(PROJECT, "cam")

    result = module.run(None)
