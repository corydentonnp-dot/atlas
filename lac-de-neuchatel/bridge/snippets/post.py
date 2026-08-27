# Post every operation to a single GRBL file.
#   python fusion_cli.py exec -f snippets/post.py --timeout 600
import os
import adsk.cam

OUTPUT = r"C:\Users\YOU\Documents\atlas\lac-de-neuchatel\cam"
PROGRAM = "1001"
POST = "grbl.cps"

if cam is None:
    result = "No CAM product in this document."
else:
    post_path = os.path.join(cam.genericPostFolder, POST)
    if not os.path.isfile(post_path):
        candidate = os.path.join(cam.personalPostFolder, POST)
        post_path = candidate if os.path.isfile(candidate) else None

    if post_path is None:
        result = {"error": "%s not found in either post folder" % POST,
                  "generic": cam.genericPostFolder,
                  "personal": cam.personalPostFolder}
    else:
        os.makedirs(OUTPUT, exist_ok=True)
        post_input = adsk.cam.PostProcessInput.create(
            PROGRAM, post_path, OUTPUT,
            adsk.cam.PostOutputUnitOptions.DocumentUnitsOutput)
        post_input.isOpenInEditor = False
        cam.postProcessAll(post_input)

        written = os.path.join(OUTPUT, PROGRAM + ".nc")
        result = {
            "post": post_path,
            "output": written,
            "exists": os.path.isfile(written),
            "bytes": os.path.getsize(written) if os.path.isfile(written) else 0,
        }
