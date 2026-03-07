import hou
import viewerstate.utils as su

from skyforge.forge_states.base_state import BaseState
from skyforge.forge_states.auto_axis_context import AutoAxisContext
from skyforge.forge_states.features.auto_axis_move_feature import AutoAxisMoveFeature
from skyforge.forge_states.features.auto_axis_hover_feature import AutoAxisHoverFeature


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

    STASH_NODE_NAME = "stash1"
    INPUT_NODE_NAME = "INPUT"
    ENABLE_HOVER_FEATURE = True
    ENABLE_MOVE_FEATURE = True

    def __init__(self, state_name, scene_viewer):
        super().__init__(scene_viewer=scene_viewer, state_name=state_name)
        self.ctx = AutoAxisContext(scene_viewer, state_name=state_name)

        self.move_feature = AutoAxisMoveFeature()
        self.hover_feature = AutoAxisHoverFeature()
        if self.ENABLE_MOVE_FEATURE:
            self.register_feature("move", self.move_feature)
        if self.ENABLE_HOVER_FEATURE:
            self.register_feature("hover", self.hover_feature)

        self.point_gadget = None
        self.edge_gadget = None
        self.face_gadget = None

    def onEnter(self, kwargs):
        self.ctx.set_node(kwargs["node"])
        self.ctx.load_point_radius_from_node()
        self.ctx.ensure_edit_geo(
            stash_node_name=self.STASH_NODE_NAME,
            input_node_name=self.INPUT_NODE_NAME,
        )
        self._init_gadgets()
        self._setup_hud()
        self._update_hud()
        if self.ENABLE_MOVE_FEATURE:
            self.call_feature(self.move_feature, "on_enter", self.ctx, kwargs)
        if self.ENABLE_HOVER_FEATURE:
            self.call_feature(self.hover_feature, "on_enter", self.ctx, kwargs)

    def onExit(self, kwargs):
        if self.ENABLE_MOVE_FEATURE:
            self.call_feature(self.move_feature, "on_exit", self.ctx, kwargs)
        if self.ENABLE_HOVER_FEATURE:
            self.call_feature(self.hover_feature, "on_exit", self.ctx, kwargs)

    def onMouseEvent(self, kwargs):
        self.ctx.set_service("state_context", self._state_context())
        if self.ENABLE_MOVE_FEATURE:
            return bool(self.call_feature(self.move_feature, "on_mouse_event", self.ctx, kwargs))
        return False

    def onDraw(self, kwargs):
        state_context = self._state_context()
        self.ctx.set_service("state_context", state_context)
        if state_context is None:
            return
        try:
            if state_context.isPicking():
                return
        except Exception:
            pass

        # Keep sync behavior centralized in state for now.
        move_interacting = False
        if self.ENABLE_MOVE_FEATURE:
            move_interacting = bool(self.call_feature(self.move_feature, "is_interacting"))
        changed = self.ctx.sync_edit_geo(force=False, allow_sync=(not move_interacting))
        if changed:
            self._refresh_gadgets_geometry()
            if self.ENABLE_HOVER_FEATURE:
                self.call_feature(self.hover_feature, "refresh_geometry", self.ctx)

        handle = kwargs["draw_handle"]
        if self.ctx.select_mode == "POINT" and self.point_gadget is not None:
            self.point_gadget.draw(handle)
        elif self.ctx.select_mode == "EDGE" and self.edge_gadget is not None:
            self.edge_gadget.draw(handle)
        elif self.ctx.select_mode == "FACE" and self.face_gadget is not None:
            self.face_gadget.draw(handle)

        if self.ENABLE_HOVER_FEATURE:
            self.call_feature(self.hover_feature, "on_draw", self.ctx, kwargs)
        if self.ENABLE_MOVE_FEATURE:
            self.call_feature(self.move_feature, "on_draw", self.ctx, kwargs)

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

    def _init_gadgets(self):
        self.point_gadget = self._get_state_gadget("point_gadget")
        self.edge_gadget = self._get_state_gadget("edge_gadget")
        self.face_gadget = self._get_state_gadget("face_gadget")

        if self.point_gadget is not None:
            self.point_gadget.setParams({"draw_color": [1, 1, 1, 0.0], "radius": self.ctx.point_radius})
            self.point_gadget.show(True)
        if self.edge_gadget is not None:
            self.edge_gadget.setParams({"draw_color": [1, 1, 1, 0.0]})
            self.edge_gadget.show(True)
        if self.face_gadget is not None:
            self.face_gadget.setParams({"draw_color": [1, 1, 1, 0.0]})
            self.face_gadget.show(True)

        self._refresh_gadgets_geometry()
        if self.ENABLE_HOVER_FEATURE:
            self.call_feature(self.hover_feature, "refresh_geometry", self.ctx)

    def _get_state_gadget(self, name):
        try:
            return self.state_gadgets[name]
        except Exception:
            return None

    def _state_context(self):
        return getattr(self, "state_context", None)

    def _refresh_gadgets_geometry(self):
        geo = self.ctx.edit_geo
        if geo is None:
            return
        if self.point_gadget is not None:
            self.point_gadget.setGeometry(geo)
        if self.edge_gadget is not None:
            self.edge_gadget.setGeometry(geo)
        if self.face_gadget is not None:
            self.face_gadget.setGeometry(geo)

    def _setup_hud(self):
        try:
            self.scene_viewer.hudInfo(template=self.HUD_TEMPLATE)
        except Exception:
            pass

    def _update_hud(self):
        mode_order = ["LOCAL", "WORLD", "EDGE"]
        sel_order = ["POINT", "EDGE", "FACE"]
        tool_order = ["MOVE", "CUT"]

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

        if self.point_gadget is not None:
            self.point_gadget.setParams({"radius": float(self.ctx.point_radius)})

        if self.ENABLE_HOVER_FEATURE:
            self.call_feature(self.hover_feature, "apply_point_radius", self.ctx)

        self.ctx.save_point_radius_to_node()
        self._update_hud()

    def _cycle_mode(self):
        order = ["LOCAL", "WORLD", "EDGE"]
        self.ctx.mode = order[(order.index(self.ctx.mode) + 1) % len(order)] if self.ctx.mode in order else "LOCAL"

    def _cycle_select_mode(self):
        order = ["POINT", "EDGE", "FACE"]
        self.ctx.select_mode = (
            order[(order.index(self.ctx.select_mode) + 1) % len(order)]
            if self.ctx.select_mode in order else "POINT"
        )
        if self.ctx.tool_mode == "CUT":
            self.ctx.tool_mode = "MOVE"

    def _cycle_tool_mode(self):
        self.ctx.tool_mode = "CUT" if self.ctx.tool_mode == "MOVE" else "MOVE"
        if self.ctx.tool_mode == "CUT":
            self.ctx.select_mode = "EDGE"
        else:
            self.ctx.select_mode = "POINT"


def createViewerStateTemplate():
    state_typename = "AutoAxisModular"
    state_label = "AutoAxisModular"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon("$SK_ICONS/devtools.svg")

    template.bindGadget(hou.drawableGeometryType.Point, "point_gadget", label="Point")
    template.bindGadget(hou.drawableGeometryType.Face, "face_gadget", label="Face")
    template.bindGadget(hou.drawableGeometryType.Line, "edge_gadget", label="Edge")

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
