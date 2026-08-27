# Change one parameter on one operation, then regenerate just that operation.
# This is the tight loop: tweak, regenerate, look, tweak again.
#
#   python fusion_cli.py exec -f snippets/set_parameter.py --timeout 300
#
# Edit the three values below.
import time
import adsk.core

OPERATION = "3 Parallel"      # operation display name
PARAMETER = "stepover"        # parameter name (see snippets/list_operations.py)
VALUE = "0.12 mm"             # expression, units included

target = None
if cam is None:
    result = "No CAM product in this document."
else:
    for setup in cam.setups:
        for op in setup.operations:
            if op.name == OPERATION:
                target = op
                break

    if target is None:
        names = [op.name for s in cam.setups for op in s.operations]
        result = {"error": "no operation called %r" % OPERATION,
                  "available": names}
    else:
        param = target.parameters.itemByName(PARAMETER)
        if param is None:
            result = {"error": "no parameter called %r on %r"
                               % (PARAMETER, OPERATION)}
        else:
            before = param.expression
            param.expression = VALUE

            collection = adsk.core.ObjectCollection.create()
            collection.add(target)
            future = cam.generateToolpath(target)

            deadline = time.time() + 280
            while time.time() < deadline:
                try:
                    if future.isGenerationCompleted:
                        break
                except Exception:
                    break
                adsk.doEvents()
                time.sleep(0.25)

            result = {
                "operation": OPERATION,
                "parameter": PARAMETER,
                "before": before,
                "after": param.expression,
                "toolpath_valid": target.isToolpathValid,
            }
