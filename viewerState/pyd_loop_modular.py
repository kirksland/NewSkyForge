import hou

from skyforge.forge_states.context import ViewerContext
from skyforge.forge_states.features import AstarTurnFeature, TransversalLoopFeature


class State(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.scene_viewer = kwargs["scene_viewer"]

        self.ctx = ViewerContext(self.scene_viewer)
        self.features = {
            "astar_turn": AstarTurnFeature(),
            "transversal_loop": TransversalLoopFeature(),
        }
        self.active_feature_name = "transversal_loop"

    @property
    def active_feature(self):
        return self.features[self.active_feature_name]

    def onEnter(self, kwargs):
        self.ctx.set_node(kwargs["node"])
        self.ctx.ensure_mesh()
        self.active_feature.on_enter(self.ctx, kwargs)

    def onExit(self, kwargs):
        self.active_feature.on_exit(self.ctx, kwargs)

    def onMouseEvent(self, kwargs):
        self.ctx.ensure_mesh()
        return self.active_feature.on_mouse_event(self.ctx, kwargs)

    def onSelection(self, kwargs):
        self.ctx.ensure_mesh()
        return self.active_feature.on_selection(self.ctx, kwargs)

    def onStartSelection(self, kwargs):
        self.active_feature.on_start_selection(self.ctx, kwargs)

    def onStopSelection(self, kwargs):
        self.active_feature.on_stop_selection(self.ctx, kwargs)

    def onDraw(self, kwargs):
        self.active_feature.on_draw(self.ctx, kwargs)

    def onKeyEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        dev = ui.device()
        if dev.isAutoRepeat():
            return False

        key = (dev.keyString() or "").lower()

        # Global feature switch:
        # - Shift+A => astar_turn
        # - Shift alone => transversal_loop
        target = None
        if key == "shift+a":
            target = "astar_turn"
        elif key == "shift":
            target = "transversal_loop"

        if target is not None:
            if target == self.active_feature_name:
                return True

            old_feature = self.active_feature
            old_feature.on_exit(self.ctx, kwargs)

            self.active_feature_name = target
            self.active_feature.on_enter(self.ctx, kwargs)

            print("[SkyForge] Active modular feature:", self.active_feature_name)
            return True

        # Feature-local shortcuts
        on_key = getattr(self.active_feature, "on_key_event", None)
        if callable(on_key):
            return bool(on_key(self.ctx, kwargs))
        return False

    def onKeyTransitEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        dev = ui.device()
        key = (dev.keyString() or "").lower()

        # Momentary behavior:
        # return to loop mode when Shift is released.
        if dev.isKeyUp() and key == "shift":
            target = "transversal_loop"
            if self.active_feature_name != target:
                old_feature = self.active_feature
                old_feature.on_exit(self.ctx, kwargs)
                self.active_feature_name = target
                self.active_feature.on_enter(self.ctx, kwargs)
                print("[SkyForge] Active modular feature:", self.active_feature_name)
            return True

        return False


def createViewerStateTemplate():
    state_typename = "pyd_loop_modular"
    state_label = "pyd_loop_modular"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon("$SK_ICONS/devtools.svg")

    template.bindGeometrySelector(
        "SOP: Select an edge",
        quick_select=True,
        name="Modular Edge Selector",
        use_existing_selection=True,
        geometry_types=(hou.geometryType.Edges,),
        allow_other_sops=False,
    )

    return template
