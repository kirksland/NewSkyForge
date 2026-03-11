import hou

from skyforge.forge_states.tool_context import ToolContext
from skyforge.forge_states.base_state import BaseState
from skyforge.forge_states import constants as k
from skyforge.forge_states.features import (
    AstarTurnFeature,
    HoverGadgetFeature,
    TransversalLoopFeature,
)


class State(BaseState):
    HUD_TEMPLATE = {
        "title": "SkyForge Modular",
        "desc": "edge workflow",
        "icon": "$SK_ICONS/devtools.svg",
        "rows": [
            {"id": "loop_mode", "label": "Loop Mode", "key": "R / Q / X"},
            {"id": "loop_mode_g", "type": "choicegraph", "count": 2},
            {"id": "out_mode", "label": "Output", "key": "1 / 2 / 3"},
            {"id": "out_mode_g", "type": "choicegraph", "count": 3},
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
        self.hover_feature = HoverGadgetFeature(enable_ray_filter=True)
        self.astar_feature = AstarTurnFeature()
        self.loop_feature = TransversalLoopFeature()
        self.register_feature("hover_gadget", self.hover_feature)
        self.register_feature("astar_turn", self.astar_feature)
        self.register_feature("transversal_loop", self.loop_feature)

        self._shift_a_active = False
        self._output_mode = k.OUTPUT_MODE_EDGE

    def onEnter(self, kwargs):
        self.ctx.set_node(kwargs["node"])
        self.ctx.ensure_geo()
        self.ctx.ensure_mesh()
        self.astar_feature.on_enter(self.ctx, kwargs)
        self.loop_feature.on_enter(self.ctx, kwargs)
        self.hover_feature.attach(
            host=self,
            ctx=self.ctx,
            kwargs=kwargs,
            geometry=self.ctx.geometry,
            mode=HoverGadgetFeature.MODE_LINE,
        )
        self.astar_feature.clear_preview(self.ctx)
        self._apply_output_mode()
        self._setup_hud()
        self._update_hud()

    def onExit(self, kwargs):
        self.hover_feature.detach(self.ctx, kwargs)
        self.astar_feature.on_exit(self.ctx, kwargs)
        self.loop_feature.on_exit(self.ctx, kwargs)

    def onDraw(self, kwargs):
        self.hover_feature.draw(self.ctx, kwargs)
        self.astar_feature.on_draw(self.ctx, kwargs)

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

        if key in ("1", "2", "3"):
            self._output_mode = {
                "1": k.OUTPUT_MODE_EDGE,
                "2": k.OUTPUT_MODE_POINT,
                "3": k.OUTPUT_MODE_PRIM,
            }[key]
            self._apply_output_mode()
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
        hover, _click = self.hover_feature.tick(self.ctx, kwargs)
        dev = ui.device()
        reason = ui.reason()
        he = self._hover_hedge(hover)
        edge = hover.get("edge") if hover.get("visible") else None

        # SHIFT+A hover => preview A*
        if reason == hou.uiEventReason.Located:
            if self._shift_a_active and self._is_shift_down(dev):
                if he < 0:
                    self.astar_feature.clear_preview(self.ctx)
                    return False
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

        if he < 0 or edge is None:
            self._reset_all()
            self._update_hud()
            return True

        p0, p1 = int(edge[0]), int(edge[1])
        shift = self.is_shift_down(dev)

        # Shift+A + LMB => commit astar to grstr
        if is_lmb and shift and self._shift_a_active:
            committed = self.astar_feature.commit_from_base_to_he(self.ctx, he)
            self._update_hud()
            return bool(committed)

        # Shift + MMB => loop commit to grstr
        if is_mmb and shift:
            consumed = bool(self.loop_feature.commit_loop_from_he(self.ctx, he))
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

    def _apply_output_mode(self):
        self.astar_feature.set_output_mode(self._output_mode)
        self.loop_feature.set_output_mode(self._output_mode)

    def _update_hud(self):
        mode = getattr(self.loop_feature, "mode", k.LOOP_MODE_ROLL)
        mode_label = "Roll" if mode == k.LOOP_MODE_ROLL else "Quad"
        mode_idx = 0 if mode == k.LOOP_MODE_ROLL else 1
        out_label = {
            k.OUTPUT_MODE_EDGE: "Edge",
            k.OUTPUT_MODE_POINT: "Point",
            k.OUTPUT_MODE_PRIM: "Prim",
        }.get(self._output_mode, "Edge")
        out_idx = {
            k.OUTPUT_MODE_EDGE: 0,
            k.OUTPUT_MODE_POINT: 1,
            k.OUTPUT_MODE_PRIM: 2,
        }.get(self._output_mode, 0)
        astar_label = "On" if self._shift_a_active else "Off"
        values = {
            "loop_mode": mode_label,
            "loop_mode_g": mode_idx,
            "out_mode": out_label,
            "out_mode_g": out_idx,
            "astar_state": astar_label,
        }
        try:
            self.scene_viewer.hudInfo(hud_values=values)
        except Exception:
            pass

    def _is_shift_down(self, dev):
        # Compatibility shim for older internal calls.
        return self.is_shift_down(dev)

    def _hover_hedge(self, hover):
        if not hover or not hover.get("visible"):
            return -1
        edge = hover.get("edge")
        if edge is None:
            return -1
        return self.ctx.edge_to_hedge(int(edge[0]), int(edge[1]))


def createViewerStateTemplate():
    state_typename = "pyd_loop_modular"
    state_label = "pyd_loop_modular"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    HoverGadgetFeature.bind_template(template)
    template.bindIcon("$SK_ICONS/devtools.svg")

    return template
