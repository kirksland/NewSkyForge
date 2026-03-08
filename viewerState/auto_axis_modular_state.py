import hou
import viewerstate.utils as su

from skyforge.forge_states.base_state import BaseState
from skyforge.forge_states.tool_context import ToolContext
from skyforge.forge_states import constants as k
from skyforge.forge_states.features.move_feature import MoveFeature
from skyforge.forge_states.features.preview_feature import PreviewFeature


class State(BaseState):
    HUD_TEMPLATE = {
        "title": "AutoAxisModular",
        "desc": "tool",
        "icon": "SOP_edit",
        "rows": [
            {"id": "mode", "label": "Mode", "key": "M", "value": "LOCAL"},
            {"id": "mode_g", "type": "choicegraph", "count": 3},
            {"id": "selectmode", "label": "Select Mode", "key": "F", "value": "POINT"},
            {"id": "selectmode_g", "type": "choicegraph", "count": 3},
            {"id": "selecttool", "label": "Select Tool", "key": "C", "value": "MOVE"},
            {"id": "selecttool_g", "type": "choicegraph", "count": 2},
            {"id": "pointsize", "label": "Point Size", "key": "[ / ]", "value": "5.0"},
        ],
    }

    STASH_NODE_NAME = k.DEFAULT_STASH_NODE_NAME
    INPUT_NODE_NAME = k.DEFAULT_INPUT_NODE_NAME
    ENABLE_PREVIEW_FEATURE = True
    ENABLE_MOVE_FEATURE = True

    def __init__(self, state_name, scene_viewer):
        super().__init__(scene_viewer=scene_viewer, state_name=state_name)
        self.ctx = ToolContext(scene_viewer, state_name=state_name)

        self.move_feature = MoveFeature()
        self.preview_feature = PreviewFeature(prefix="auto_axis_mod", enable_hover=True)
        if self.ENABLE_MOVE_FEATURE:
            self.register_feature("move", self.move_feature)
        if self.ENABLE_PREVIEW_FEATURE:
            self.register_feature("preview", self.preview_feature)

    def onEnter(self, kwargs):
        self.ctx.set_node(kwargs["node"])
        self.ctx.load_point_radius_from_node()
        geo = self.ctx.ensure_edit_geo(
            stash_node_name=self.STASH_NODE_NAME,
            input_node_name=self.INPUT_NODE_NAME,
        )
        self.ctx.ensure_mesh(geo=geo)
        if self.ENABLE_PREVIEW_FEATURE:
            self.call_feature(self.preview_feature, "on_enter", self.ctx, kwargs)
        self._setup_hud()
        self._update_hud()
        if self.ENABLE_MOVE_FEATURE:
            self.call_feature(self.move_feature, "on_enter", self.ctx, kwargs)

    def onExit(self, kwargs):
        if self.ENABLE_MOVE_FEATURE:
            self.call_feature(self.move_feature, "on_exit", self.ctx, kwargs)
        if self.ENABLE_PREVIEW_FEATURE:
            self.call_feature(self.preview_feature, "on_exit", self.ctx, kwargs)

    def onMouseEvent(self, kwargs):
        ui_event = kwargs.get("ui_event")
        if ui_event is None:
            return False

        hit = self.ctx.hit_info(ui_event, geo=self.ctx.edit_geo)
        self.ctx.set_service("hit", hit)

        if self.ENABLE_PREVIEW_FEATURE:
            self.call_feature(self.preview_feature, "on_mouse_event", self.ctx, kwargs)
        if self.ENABLE_MOVE_FEATURE:
            return bool(self.call_feature(self.move_feature, "on_mouse_event", self.ctx, kwargs))
        return False

    def onDraw(self, kwargs):
        state_context = self._state_context()
        try:
            if state_context is not None and state_context.isPicking():
                return
        except Exception:
            pass

        # Keep sync behavior centralized in state for now.
        move_interacting = False
        if self.ENABLE_MOVE_FEATURE:
            move_interacting = bool(self.call_feature(self.move_feature, "is_interacting"))
        changed = self.ctx.sync_edit_geo(force=False, allow_sync=(not move_interacting))
        if changed:
            self.ctx.ensure_mesh(geo=self.ctx.edit_geo)
            if self.ENABLE_PREVIEW_FEATURE:
                self.call_feature(self.preview_feature, "refresh_geometry", self.ctx)

        if self.ENABLE_MOVE_FEATURE:
            self.call_feature(self.move_feature, "on_draw", self.ctx, kwargs)
        if self.ENABLE_PREVIEW_FEATURE:
            self.call_feature(self.preview_feature, "on_draw", self.ctx, kwargs)

    def onMenuAction(self, kwargs):
        action = kwargs.get("menu_item")
        if action == "cycle_mode":
            self._cycle_mode()
            self._update_hud()
            return True
        if action == "cycle_select":
            self._cycle_select_mode()
            self._update_hud()
            return True
        if action == "cycle_tool":
            self._cycle_tool_mode()
            self._update_hud()
            return True
        if action == "point_size_up":
            self._change_point_radius(self.ctx.point_radius_step)
            return True
        if action == "point_size_down":
            self._change_point_radius(-self.ctx.point_radius_step)
            return True
        return False

    def _state_context(self):
        return getattr(self, "state_context", None)

    def _setup_hud(self):
        try:
            self.scene_viewer.hudInfo(template=self.HUD_TEMPLATE)
        except Exception:
            pass

    def _update_hud(self):
        mode_order = list(k.AUTO_AXIS_MODE_ORDER)
        sel_order = list(k.AUTO_AXIS_SELECT_ORDER)
        tool_order = list(k.AUTO_AXIS_TOOL_ORDER)

        values = {
            "mode": self.ctx.mode,
            "mode_g": mode_order.index(self.ctx.mode) if self.ctx.mode in mode_order else 0,
            "selectmode": self.ctx.select_mode,
            "selectmode_g": sel_order.index(self.ctx.select_mode) if self.ctx.select_mode in sel_order else 0,
            "selecttool": self.ctx.tool_mode,
            "selecttool_g": tool_order.index(self.ctx.tool_mode) if self.ctx.tool_mode in tool_order else 0,
            "pointsize": "{:.1f}".format(float(self.ctx.point_radius)),
        }
        try:
            self.scene_viewer.hudInfo(hud_values=values)
        except Exception:
            pass

    def _change_point_radius(self, delta):
        prev = float(self.ctx.point_radius)
        cur = prev + float(delta)
        self.ctx.point_radius = max(self.ctx.point_radius_min, min(self.ctx.point_radius_max, cur))
        if abs(self.ctx.point_radius - prev) < 1e-6:
            return

        if self.ENABLE_PREVIEW_FEATURE:
            self.call_feature(self.preview_feature, "apply_point_radius", self.ctx)

        self.ctx.save_point_radius_to_node()
        self._update_hud()

    def _cycle_mode(self):
        order = list(k.AUTO_AXIS_MODE_ORDER)
        self.ctx.mode = order[(order.index(self.ctx.mode) + 1) % len(order)] if self.ctx.mode in order else k.AUTO_AXIS_MODE_ORDER[0]

    def _cycle_select_mode(self):
        order = list(k.AUTO_AXIS_SELECT_ORDER)
        self.ctx.select_mode = (
            order[(order.index(self.ctx.select_mode) + 1) % len(order)]
            if self.ctx.select_mode in order else k.AUTO_AXIS_SELECT_ORDER[0]
        )
        if self.ctx.tool_mode == k.AUTO_AXIS_TOOL_ORDER[1]:
            self.ctx.tool_mode = k.AUTO_AXIS_TOOL_ORDER[0]

    def _cycle_tool_mode(self):
        self.ctx.tool_mode = k.AUTO_AXIS_TOOL_ORDER[1] if self.ctx.tool_mode == k.AUTO_AXIS_TOOL_ORDER[0] else k.AUTO_AXIS_TOOL_ORDER[0]
        if self.ctx.tool_mode == k.AUTO_AXIS_TOOL_ORDER[1]:
            self.ctx.select_mode = k.AUTO_AXIS_SELECT_ORDER[1]
        else:
            self.ctx.select_mode = k.AUTO_AXIS_SELECT_ORDER[0]


def createViewerStateTemplate():
    state_typename = "AutoAxisModular"
    state_label = "AutoAxisModular"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon("$SK_ICONS/devtools.svg")

    hotkey_definitions = hou.PluginHotkeyDefinitions()
    menu = hou.ViewerStateMenu(state_typename + "_menu", state_label)

    menu.addActionItem(
        "cycle_mode",
        "Cycle Mode (Local/World/Edge)",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "cycle_mode", "m"),
    )
    menu.addActionItem(
        "cycle_select",
        "Cycle Select Mode (Point/Edge/Face)",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "cycle_select", "f"),
    )
    menu.addActionItem(
        "cycle_tool",
        "Cycle Tool Mode (Move/Cut)",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "cycle_tool", "c"),
    )
    menu.addActionItem(
        "point_size_up",
        "Point Size +",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "point_size_up", "]"),
    )
    menu.addActionItem(
        "point_size_down",
        "Point Size -",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "point_size_down", "["),
    )

    template.bindMenu(menu)
    template.bindHotkeyDefinitions(hotkey_definitions)
    return template
