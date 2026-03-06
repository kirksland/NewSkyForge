import hou

from skyforge.forge_states.context import ViewerContext
from skyforge.forge_states.features import AstarTurnFeature, TransversalLoopFeature


class State(object):
    HUD_TEMPLATE = {
        "title": "SkyForge Modular Loop",
        "desc": "viewer state",
        "icon": "SOP_polyextrude",
        "rows": [
            {"id": "active_feature", "label": "Feature"},
            {"id": "active_feature_g", "type": "choicegraph", "count": 2},
            {"id": "loop_mode", "label": "Loop Mode", "key": "R / Q / X"},
            {"id": "loop_mode_g", "type": "choicegraph", "count": 2},
            {"type": "divider"},
            {"label": "Activate A* Turn", "key": "Shift + A"},
            {"label": "Activate Loops", "key": "Shift"},
            {"label": "A* Pick / Commit", "key": "LMB"},
            {"label": "Loop from picked edge", "key": "LMB"},
        ],
    }

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
        self._setup_hud()
        self._update_hud()
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
            self._update_hud()

            print("[SkyForge] Active modular feature:", self.active_feature_name)
            return True

        # Feature-local shortcuts
        on_key = getattr(self.active_feature, "on_key_event", None)
        if callable(on_key):
            consumed = bool(on_key(self.ctx, kwargs))
            if consumed:
                self._update_hud()
            return consumed
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
                self._update_hud()
                print("[SkyForge] Active modular feature:", self.active_feature_name)
            return True

        return False

    def _setup_hud(self):
        try:
            self.scene_viewer.hudInfo(template=self.HUD_TEMPLATE)
        except Exception:
            pass

    def _update_hud(self):
        feature_label = "A* Turn" if self.active_feature_name == "astar_turn" else "Transversal Loop"
        feature_index = 0 if self.active_feature_name == "astar_turn" else 1

        mode = getattr(self.features.get("transversal_loop"), "mode", "roll")
        mode_label = "Roll" if mode == "roll" else "Quad"
        mode_index = 0 if mode == "roll" else 1

        updates = {
            "active_feature": feature_label,
            "active_feature_g": feature_index,
            "loop_mode": mode_label,
            "loop_mode_g": mode_index,
        }

        try:
            self.scene_viewer.hudInfo(hud_values=updates)
        except Exception:
            pass


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
