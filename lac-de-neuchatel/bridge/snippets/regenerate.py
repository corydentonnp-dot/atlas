# Regenerate every toolpath and report which ones came back valid.
#   python fusion_cli.py exec -f snippets/regenerate.py --timeout 900
import time
import adsk.core

if cam is None:
    result = "No CAM product in this document."
else:
    future = cam.generateAllToolpaths(False)

    # Fusion generates on background threads of its own, but we are already ON
    # the main thread here, so pump the event loop while we wait.
    deadline = time.time() + 800
    while time.time() < deadline:
        try:
            if future.isGenerationCompleted:
                break
        except Exception:
            break
        adsk.doEvents()
        time.sleep(0.25)

    rows = []
    for setup in cam.setups:
        for op in setup.operations:
            rows.append({"operation": op.name, "valid": op.isToolpathValid})

    result = {
        "completed": all(r["valid"] for r in rows),
        "operations": rows,
    }
