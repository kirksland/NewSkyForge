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
            {"label": "A*", "key": "Shift + A + LMB"},
            {"label": "Loop", "key": "Shift + MMB"},
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
        self.hub.apply_hud(self.scene_viewer, base_template=self.HUD_TEMPLATE)
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
        self.hub.update_hud(self.scene_viewer, self.ctx)

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
            self.hub.update_hud(self.scene_viewer, self.ctx)
        return handled

    def onMenuPreOpen(self, kwargs):
        return bool(self.hub.menu_pre_open(self.ctx, kwargs, stop_on_consume=False))

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

    def _update_hud(self):
        try:
            self.hub.update_hud(self.scene_viewer, self.ctx)
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
