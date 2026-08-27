# What is Fusion currently looking at?
#   python fusion_cli.py exec -f snippets/status.py
import adsk.fusion
import adsk.cam

info = {
    "document": doc.name if doc else None,
    "workspace": ui.activeWorkspace.id if ui.activeWorkspace else None,
    "has_design": design is not None,
    "has_cam": cam is not None,
}

if design:
    root = design.rootComponent
    info["bodies"] = root.bRepBodies.count
    info["mesh_bodies"] = root.meshBodies.count
    info["sketches"] = [s.name for s in root.sketches]

if cam:
    info["setups"] = []
    for setup in cam.setups:
        info["setups"].append({
            "name": setup.name,
            "operations": [op.name for op in setup.operations],
        })

result = info
