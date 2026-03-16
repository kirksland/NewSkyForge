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

    # ------------------------------------------------------------------
    # Context bootstrap (uniform)
    # ------------------------------------------------------------------
    def bind_context(self, ctx, kwargs, ensure_geo=True, ensure_mesh=True, geo=None):
        """
        Standard context bootstrap for states.
        - bind node
        - expose host
        - optionally ensure geometry and mesh
        """
        if ctx is None:
            return None
        node = kwargs.get("node") if isinstance(kwargs, dict) else None
        if node is not None:
            try:
                ctx.set_node(node)
            except Exception:
                pass
        try:
            ctx.set_service("host", self)
        except Exception:
            pass
        if ensure_geo:
            try:
                ctx.ensure_geo()
            except Exception:
                pass
        if ensure_mesh:
            try:
                ctx.ensure_mesh(geo=geo if geo is not None else getattr(ctx, "geometry", None))
            except Exception:
                pass
        try:
            self.ensure_preview(ctx)
        except Exception:
            pass
        return ctx

    def ensure_preview(self, ctx, prefix=None):
        if ctx is None:
            return None
        try:
            preview = ctx.get_service("preview")
        except Exception:
            preview = None
        if preview is not None:
            return preview
        try:
            from .preview_service import PreviewService
            pref = prefix if prefix is not None else (self.state_name or "preview")
            preview = PreviewService(ctx.scene_viewer, prefix=str(pref))
            ctx.set_service("preview", preview)
            return preview
        except Exception:
            return None

    def enter_with_hud(self, hub, ctx, kwargs, base_template=None, update=True):
        """
        Standard hub enter + HUD apply/update for states.
        """
        if hub is None:
            return False
        try:
            hub.enter(ctx, kwargs)
        except Exception:
            pass
        if base_template is not None:
            try:
                hub.apply_hud(self.scene_viewer, base_template=base_template)
            except Exception:
                pass
        if update:
            try:
                hub.update_hud(self.scene_viewer, ctx)
            except Exception:
                pass
        return True
