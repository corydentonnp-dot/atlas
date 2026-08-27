# Every operation, its tool, and the parameters that matter for this job.
# This is the fastest way to see what Fusion actually applied versus what the
# script asked for.
#   python fusion_cli.py exec -f snippets/list_operations.py
INTERESTING = (
    "tolerance", "stepover", "maximumStepover", "cuspHeight",
    "bottomHeight_offset", "bottomHeight_mode",
    "topHeight_offset", "topHeight_mode",
    "maximumStepdown", "stepdown",
    "minimumCuttingRadius", "machineShallowAreas", "doMachineShallowAreas",
    "machiningBoundary", "boundaryContainment", "toolContainment",
    "parallelAngle", "machiningAngle",
    "verticalStockToLeave", "horizontalStockToLeave",
)

out = []
if cam is None:
    result = "No CAM product in this document. Switch to Manufacture first."
else:
    for setup in cam.setups:
        entry = {"setup": setup.name, "operations": []}
        for op in setup.operations:
            row = {
                "name": op.name,
                "strategy": getattr(op, "strategy", None),
                "valid": op.isToolpathValid,
                "suppressed": op.isSuppressed,
            }
            try:
                row["tool"] = op.tool.parameters.itemByName(
                    "tool_description").value.value
            except Exception:
                row["tool"] = None

            params = {}
            for name in INTERESTING:
                try:
                    p = op.parameters.itemByName(name)
                    if p is None:
                        continue
                    try:
                        params[name] = p.expression
                    except Exception:
                        params[name] = str(p.value.value)
                except Exception:
                    continue
            row["parameters"] = params
            entry["operations"].append(row)
        out.append(entry)
    result = out
