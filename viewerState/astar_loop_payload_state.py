import hou

from skyforge.forge_states.base_state import BaseState
from skyforge.forge_states.tool_context import ToolContext
from skyforge.forge_states.feature_hub import FeatureHub
from skyforge.forge_states.features import (
    HoverGadgetFeature,
    AstarTurnFeature,
    TransversalLoopFeature,
)


class State(BaseState):
    """
    Payload test state for A* and Loop features.
    If the target parm is missing, features return a payload:
      {"mode": "edge|point|prim", "group": "<string>"}
    """

    HUD_TEMPLATE = {
        "title": "AstarLoopPayload",
        "desc": "payload test (no parm required)",
        "icon": "$SK_ICONS/devtools.svg",
        "rows": [
            {"id": "hover_edge", "label": "Hover"},
            {"label": "A*", "key": "Shift + A + LMB"},
            {"label": "Loop", "key": "Shift + MMB"},
            {"id": "loop_mode", "label": "Mode", "key": "R / Q / X"},
            {"id": "loop_mode_g", "type": "choicegraph", "count": 2},
        ],
    }

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.scene_viewer = kwargs["scene_viewer"]
        self.state_name = kwargs.get("state_name", "astar_loop_payload_state")
        super().__init__(scene_viewer=self.scene_viewer, state_name=self.state_name)

        self.ctx = ToolContext(self.scene_viewer, state_name=self.state_name)
        self.hover_feature = HoverGadgetFeature(enable_ray_filter=True)
        self.astar_feature = AstarTurnFeature()
        self.loop_feature = TransversalLoopFeature()
        self.hub = FeatureHub([self.hover_feature, self.astar_feature, self.loop_feature])

    def onEnter(self, kwargs):
        self.ctx.set_node(kwargs["node"])
        self.ctx.ensure_geo()
        self.ctx.ensure_mesh(geo=self.ctx.geometry)
        self.hover_feature.bind_host(self)
        self.hover_feature.set_geometry(self.ctx.geometry)
        self.hover_feature.set_mode(HoverGadgetFeature.MODE_LINE)
        self.hub.enter(self.ctx, kwargs)
        self._setup_hud()
        self._update_hud()

    def onExit(self, kwargs):
        self.hub.exit(self.ctx, kwargs)

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        self.ctx.ensure_geo()
        self.ctx.ensure_mesh(geo=self.ctx.geometry)

        consumed, payload = self.hub.mouse_collect(
            self.ctx,
            kwargs,
            payload_picker=self._pick_payload,
            stop_on_consume=False,
        )
        if payload:
            self.ctx.set_service("selection_payload", payload)
            self._apply_payload_to_parms(payload)
            print("[SkyForge] Payload:", payload)
            return payload

        return consumed

    def onDraw(self, kwargs):
        self.hub.draw(self.ctx, kwargs)
        self._update_hud()

    def onKeyEvent(self, kwargs):
        if self.astar_feature.on_key_event(self.ctx, kwargs):
            return True
        return False

    def onKeyTransitEvent(self, kwargs):
        if self.astar_feature.on_key_transit_event(self.ctx, kwargs):
            return True
        return False

    def onMenuAction(self, kwargs):
        handled = bool(self.hub.menu(self.ctx, kwargs, stop_on_consume=False))
        if handled:
            self._update_hud()
        return handled

    def onMenuPreOpen(self, kwargs):
        handled = False
        if self.hover_feature.on_menu_pre_open(kwargs):
            handled = True
        if self.loop_feature.on_menu_pre_open(kwargs):
            handled = True
        return handled

    def _pick_payload(self, value):
        if isinstance(value, dict) and value.get("group"):
            return value
        return None

    def _apply_payload_to_parms(self, payload):
        if not isinstance(payload, dict):
            return
        group = payload.get("group")
        if not group:
            return
        try:
            if self.ctx.parm_string is not None:
                self.ctx.parm_string.set(str(group))
        except Exception:
            pass

    def _setup_hud(self):
        try:
            self.scene_viewer.hudInfo(template=self.HUD_TEMPLATE)
        except Exception:
            pass

    def _update_hud(self):
        try:
            hover = self.ctx.get_service("hover") or {}
            edge_txt = "-"
            if hover.get("visible") and hover.get("edge") is not None:
                a, b = hover["edge"]
                edge_txt = "p{0}-p{1}".format(int(a), int(b))

            mode = self.loop_feature.mode
            mode_txt = "Roll" if mode == "roll" else "Quad"
            mode_idx = 0 if mode == "roll" else 1

            values = {
                "hover_edge": edge_txt,
                "loop_mode": mode_txt,
                "loop_mode_g": mode_idx,
            }
            self.scene_viewer.hudInfo(hud_values=values)
        except Exception:
            pass



def createViewerStateTemplate():
    state_typename = "astar_loop_payload_state"
    state_label = "astar_loop_payload_state"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    HoverGadgetFeature.bind_template(template)
    hotkey_defs = hou.PluginHotkeyDefinitions()
    hover_hotkeys = HoverGadgetFeature.build_hotkeys(hotkey_defs, state_typename)
    loop_hotkeys = TransversalLoopFeature.build_hotkeys(hotkey_defs, state_typename)
    menu = HoverGadgetFeature.build_menu(state_typename, state_label, hotkeys=hover_hotkeys)
    TransversalLoopFeature.extend_menu(menu, hotkeys=loop_hotkeys, add_separator=True)
    template.bindMenu(menu)
    template.bindHotkeyDefinitions(hotkey_defs)
    template.bindIcon("$SK_ICONS/devtools.svg")
    return template
