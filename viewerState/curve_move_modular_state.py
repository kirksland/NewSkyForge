import hou

from skyforge.forge_states.base_state import BaseState
from skyforge.forge_states.tool_context import ToolContext
from skyforge.forge_states import constants as k
from skyforge.forge_states.features.preview_feature import PreviewFeature
from skyforge.forge_states.features.move_feature import MoveFeature
from skyforge.forge_states.features.curve_draw_feature import CurveDrawFeature


class State(BaseState):
    HUD_TEMPLATE = {
        "title": "CurveMoveModular",
        "desc": "composition test",
        "icon": "$SK_ICONS/devtools.svg",
        "rows": [
            {"id": "tool_mode", "label": "Tool Mode", "key": "D / M"},
            {"id": "tool_mode_g", "type": "choicegraph", "count": 2},
            {"type": "divider"},
            {"label": "Append Point", "key": "LMB (Draw mode)"},
            {"label": "Move Points", "key": "LMB drag (Move mode)"},
            {"label": "Clear Preview IDs", "key": "C"},
        ],
    }

    STASH_NODE_NAME = k.DEFAULT_STASH_NODE_NAME
    INPUT_NODE_NAME = k.DEFAULT_INPUT_NODE_NAME

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.scene_viewer = kwargs["scene_viewer"]
        self.state_name = kwargs.get("state_name", "curve_move_modular")
        super().__init__(scene_viewer=self.scene_viewer, state_name=self.state_name)

        self.ctx = ToolContext(self.scene_viewer, state_name=self.state_name)
        self.preview_feature = PreviewFeature(prefix="curve_move_modular", enable_hover=True)
        self.move_feature = MoveFeature()
        self.curve_draw_feature = CurveDrawFeature()

        self.register_feature("preview", self.preview_feature)
        self.register_feature("move", self.move_feature)
        self.register_feature("curve_draw", self.curve_draw_feature)

    def onEnter(self, kwargs):
        self.ctx.set_node(kwargs["node"])
        geo = self.ctx.ensure_edit_geo(
            stash_node_name=self.STASH_NODE_NAME,
            input_node_name=self.INPUT_NODE_NAME,
        )
        self.ctx.ensure_mesh(geo=geo)
        self.ctx.select_mode = k.AUTO_AXIS_SELECT_ORDER[0]  # POINT
        self.ctx.tool_mode = k.TOOL_MODE_DRAW

        self.preview_feature.on_enter(self.ctx, kwargs)
        self.move_feature.on_enter(self.ctx, kwargs)
        self.curve_draw_feature.on_enter(self.ctx, kwargs)
        self._setup_hud()
        self._update_hud()

    def onExit(self, kwargs):
        self.curve_draw_feature.on_exit(self.ctx, kwargs)
        self.move_feature.on_exit(self.ctx, kwargs)
        self.preview_feature.on_exit(self.ctx, kwargs)

    def onMouseEvent(self, kwargs):
        ui_event = kwargs.get("ui_event")
        if ui_event is None:
            return False

        hit = self.ctx.hit_info(ui_event, geo=self.ctx.edit_geo)
        self.ctx.set_service("hit", hit)

        if self.call_feature(self.curve_draw_feature, "on_mouse_event", self.ctx, kwargs):
            return True

        self.call_feature(self.preview_feature, "on_mouse_event", self.ctx, kwargs)
        return bool(self.call_feature(self.move_feature, "on_mouse_event", self.ctx, kwargs))

    def onDraw(self, kwargs):
        move_interacting = bool(self.call_feature(self.move_feature, "is_interacting"))
        changed = self.ctx.sync_edit_geo(force=False, allow_sync=(not move_interacting))
        if changed:
            self.ctx.ensure_mesh(geo=self.ctx.edit_geo)
            self.call_feature(self.preview_feature, "refresh_geometry", self.ctx)
            self.call_feature(self.curve_draw_feature, "refresh_after_sync", self.ctx)

        self.call_feature(self.preview_feature, "on_draw", self.ctx, kwargs)

    def onKeyEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False
        dev = ui.device()
        if dev.isAutoRepeat():
            return False

        key = self.key_string(dev)
        if key == "d":
            self.ctx.tool_mode = k.TOOL_MODE_DRAW
            self._update_hud()
            return True
        if key == "m":
            self.ctx.tool_mode = k.AUTO_AXIS_TOOL_ORDER[0]  # MOVE
            self._update_hud()
            return True
        if key == "c":
            self.curve_draw_feature.clear_curve(self.ctx)
            return True
        return False

    def _setup_hud(self):
        try:
            self.scene_viewer.hudInfo(template=self.HUD_TEMPLATE)
        except Exception:
            pass

    def _update_hud(self):
        is_draw = str(self.ctx.tool_mode).upper() == k.TOOL_MODE_DRAW
        values = {
            "tool_mode": "DRAW" if is_draw else "MOVE",
            "tool_mode_g": 0 if is_draw else 1,
        }
        try:
            self.scene_viewer.hudInfo(hud_values=values)
        except Exception:
            pass


def createViewerStateTemplate():
    state_typename = "curve_move_modular"
    state_label = "curve_move_modular"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon("$SK_ICONS/devtools.svg")
    return template
