import sys, types
def _mod(name):
    m = types.ModuleType(name); sys.modules[name] = m; return m
class _Any:
    def __getattr__(self, k): return _Any()
    def __call__(self, *a, **k): return _Any()
core = _mod('adsk.core'); fusion = _mod('adsk.fusion'); cam = _mod('adsk.cam')
for m in (core, fusion, cam):
    m.__getattr__ = lambda k: _Any()
    for n in ('Application','ObjectCollection','CAM','Design','MeshUnits',
              'CadContours2dParameterValue','OperationTypes','Tool',
              'PostProcessInput','PostOutputUnitOptions','DialogResults'):
        setattr(m, n, _Any())
def doEvents(): pass
