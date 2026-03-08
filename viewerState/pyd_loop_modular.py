import hou

from skyforge.forge_states.tool_context import ToolContext
from skyforge.forge_states.base_state import BaseState
from skyforge.forge_states.features import AstarTurnFeature, TransversalLoopFeature, PreviewFeature


class State(BaseState):
    HUD_TEMPLATE = {
        "title": "SkyForge Modular",
        "desc": "edge workflow",
        "icon": "$SK_ICONS/devtools.svg",
        "rows": [
            {"id": "loop_mode", "label": "Loop Mode", "key": "R / Q / X"},
            {"id": "loop_mode_g", "type": "choicegraph", "count": 2},
            {"id": "astar_state", "label": "A* Preview", "key": "Shift + A"},
            {"type": "divider"},
            {"label": "Reset + Set Start", "key": "LMB"},
            {"label": "Set Basegroup + Append", "key": "Shift + LMB"},
            {"label": "Loop Commit", "key": "Shift + MMB"},
            {"label": "A* Commit", "key": "Shift + A + LMB"},
            {"label": "Reset All (empty click)", "key": "LMB / MMB"},
        ],
    }

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.scene_viewer = kwargs["scene_viewer"]
        self.state_name = kwargs.get("state_name", "pyd_loop_modular")
        super().__init__(scene_viewer=self.scene_viewer, state_name=self.state_name)

        self.ctx = ToolContext(self.scene_viewer, state_name=self.state_name)
        self.preview_feature = PreviewFeature(prefix="pyd_loop_modular", enable_hover=False)
        self.astar_feature = AstarTurnFeature()
        self.loop_feature = TransversalLoopFeature()
        self.register_feature("preview", self.preview_feature)
        self.register_feature("astar_turn", self.astar_feature)
        self.register_feature("transversal_loop", self.loop_feature)

        self._shift_a_active = False

    def onEnter(self, kwargs):
        self.ctx.set_node(kwargs["node"])
        self.ctx.ensure_geo()
        self.ctx.ensure_mesh()
        self.preview_feature.on_enter(self.ctx, kwargs)
        self.astar_feature.on_enter(self.ctx, kwargs)
        self.loop_feature.on_enter(self.ctx, kwargs)
        self.astar_feature.clear_preview(self.ctx)
        self._setup_hud()
        self._update_hud()

    def onExit(self, kwargs):
        self.astar_feature.on_exit(self.ctx, kwargs)
        self.loop_feature.on_exit(self.ctx, kwargs)
        self.preview_feature.on_exit(self.ctx, kwargs)

    def onDraw(self, kwargs):
        self.preview_feature.on_draw(self.ctx, kwargs)

    def onKeyEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        dev = ui.device()
        if dev.isAutoRepeat():
            return False

        key = self.key_string(dev)
        if key == "shift+a" or (key == "a" and self.is_shift_down(dev)):
            self._shift_a_active = True
            self._update_hud()
            return True

        # Loop mode keys (roll/quad)
        consumed = bool(self.loop_feature.on_key_event(self.ctx, kwargs))
        if consumed:
            self._update_hud()
        return consumed

    def onKeyTransitEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        dev = ui.device()
        if not dev.isKeyUp():
            return False

        key = self.key_string(dev)
        if key in ("shift", "a", "shift+a"):
            self._shift_a_active = False
            self.astar_feature.clear_preview(self.ctx)
            self._update_hud()
            return True
        return False

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        self.ctx.ensure_mesh()
        dev = ui.device()
        reason = ui.reason()

        # SHIFT+A hover => preview A*
        if reason == hou.uiEventReason.Located:
            if self._shift_a_active and self._is_shift_down(dev):
                hit = self.ctx.hit_edge(ui)
                if hit is None:
                    self.astar_feature.clear_preview(self.ctx)
                    return False
                _p0, _p1, he = hit
                self.astar_feature.preview_from_base_to_he(self.ctx, he)
                return False

            self.astar_feature.clear_preview(self.ctx)
            return False

        if reason != hou.uiEventReason.Start:
            return False

        is_lmb = bool(dev.isLeftButton())
        is_mmb = bool(dev.isMiddleButton())
        if not (is_lmb or is_mmb):
            return False

        hit = self.ctx.hit_edge(ui)
        if hit is None:
            self._reset_all()
            self._update_hud()
            return True

        p0, p1, he = hit
        shift = self.is_shift_down(dev)

        # Shift+A + LMB => commit astar to grstr
        if is_lmb and shift and self._shift_a_active:
            committed = self.astar_feature.commit_from_base_to_he(self.ctx, he)
            self._update_hud()
            return bool(committed)

        # Shift + MMB => loop commit to grstr
        if is_mmb and shift:
            consumed = bool(self.loop_feature.commit_loop_from_edge(self.ctx, p0, p1))
            self._update_hud()
            return consumed

        # Shift + LMB => set basegroup + append picked edge to grstr
        if is_lmb and shift:
            self.loop_feature.set_basegroup_from_edge(self.ctx, p0, p1)
            self.ctx.append_edge_to_grstr(p0, p1)
            self._update_hud()
            return True

        # LMB => reset basegroup/grstr then set basegroup (start edge)
        if is_lmb:
            self._reset_all()
            self.loop_feature.preview_edge(self.ctx, p0, p1)
            self._update_hud()
            return True

        return False

    def _reset_all(self):
        self.astar_feature.reset_all(self.ctx)
        self.loop_feature.reset_all(self.ctx)
        self._shift_a_active = False

    def _setup_hud(self):
        try:
            self.scene_viewer.hudInfo(template=self.HUD_TEMPLATE)
        except Exception:
            pass

    def _update_hud(self):
        mode = getattr(self.loop_feature, "mode", "roll")
        mode_label = "Roll" if mode == "roll" else "Quad"
        mode_idx = 0 if mode == "roll" else 1
        astar_label = "On" if self._shift_a_active else "Off"
        values = {
            "loop_mode": mode_label,
            "loop_mode_g": mode_idx,
            "astar_state": astar_label,
        }
        try:
            self.scene_viewer.hudInfo(hud_values=values)
        except Exception:
            pass

    def _is_shift_down(self, dev):
        # Compatibility shim for older internal calls.
        return self.is_shift_down(dev)


def createViewerStateTemplate():
    state_typename = "pyd_loop_modular"
    state_label = "pyd_loop_modular"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon("$SK_ICONS/devtools.svg")

    return template
