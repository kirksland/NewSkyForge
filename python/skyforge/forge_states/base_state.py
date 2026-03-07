class BaseState:
    """
    Minimal reusable orchestrator base for modular viewer states.

    It is intentionally light: existing states can adopt it progressively.
    """

    def __init__(self, scene_viewer, state_name=""):
        self.scene_viewer = scene_viewer
        self.state_name = state_name or ""
        self.features = {}

    # ------------------------------------------------------------------
    # Feature registry helpers
    # ------------------------------------------------------------------
    def register_feature(self, name, feature):
        if not name or feature is None:
            return
        self.features[str(name)] = feature

    def get_feature(self, name):
        return self.features.get(str(name))

    # ------------------------------------------------------------------
    # Safe dispatch helpers
    # ------------------------------------------------------------------
    def call_feature(self, feature, method_name, *args, **kwargs):
        if feature is None:
            return None
        method = getattr(feature, method_name, None)
        if not callable(method):
            return None
        try:
            return method(*args, **kwargs)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Input helpers
    # ------------------------------------------------------------------
    def key_string(self, device):
        try:
            return (device.keyString() or "").lower()
        except Exception:
            return ""

    def is_shift_down(self, device):
        try:
            return bool(device.isShiftKey())
        except Exception:
            return "shift" in self.key_string(device)
