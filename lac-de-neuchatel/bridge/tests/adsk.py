"""Minimal adsk stub that simulates Fusion's main-thread custom-event dispatch."""
import sys, types, threading

_registered = {}          # event id -> _CustomEvent


class _Args:
    def __init__(self, info):
        self.additionalInfo = info


class _CustomEvent:
    def __init__(self):
        self._handlers = []

    def add(self, h):
        self._handlers.append(h)

    def remove(self, h):
        if h in self._handlers:
            self._handlers.remove(h)


class _UI:
    def __init__(self):
        self.activeWorkspace = types.SimpleNamespace(id="FusionSolidEnvironment")

    def messageBox(self, *a, **k):
        raise AssertionError("messageBox must never be called from the bridge")


class _Doc:
    name = "TestDoc"

    class _Products:
        def itemByProductType(self, t):
            return None
    products = _Products()


class _App:
    version = "2.0.99999 (stub)"

    def __init__(self):
        self.userInterface = _UI()
        self.activeDocument = _Doc()
        self.logged = []
        # Simulates Fusion's single main thread: events run serialised, on a
        # thread that is NOT the HTTP worker thread.
        self._lock = threading.Lock()

    def log(self, m):
        self.logged.append(m)

    def registerCustomEvent(self, eid):
        if eid in _registered:
            raise RuntimeError("already registered")
        ev = _CustomEvent()
        _registered[eid] = ev
        return ev

    def unregisterCustomEvent(self, eid):
        if eid not in _registered:
            raise RuntimeError("not registered")
        del _registered[eid]

    def fireCustomEvent(self, eid, info):
        ev = _registered.get(eid)
        if ev is None:
            raise RuntimeError("no such event")

        def deliver():
            with self._lock:
                for h in list(ev._handlers):
                    h.notify(_Args(info))
        threading.Thread(target=deliver, daemon=True).start()


_APP = _App()


class _Castable:
    @staticmethod
    def cast(x):
        return None


def _mod(name):
    m = types.ModuleType(name)
    sys.modules[name] = m
    return m


core = _mod("adsk.core")
fusion = _mod("adsk.fusion")
cam = _mod("adsk.cam")

core.Application = types.SimpleNamespace(get=lambda: _APP)


class CustomEventHandler:
    def __init__(self):
        pass


core.CustomEventHandler = CustomEventHandler
fusion.Design = _Castable
cam.CAM = _Castable
