import hou
import viewerstate.utils as su

from skyforge.forge_states.base_state import BaseState
from skyforge.forge_states.path_move_context import PathMoveContext
from skyforge.forge_states.features.path_selection_feature import PathSelectionFeature
from skyforge.forge_states.features.path_move_feature import PathMoveFeature


class State(BaseState):
    HUD_TEMPLATE = {
        "title": "Path Move Lab",
        "desc": "modular architecture test",
        "icon": "$SK_ICONS/devtools.svg",
        "rows": [
            {"id": "move", "label": "Move Tool", "key": "G", "value": "Off"},
            {"id": "edges", "label": "Selected Edges", "value": "0"},
            {"id": "points", "label": "Selected Points", "value": "0"},
            {"type": "divider"},
            {"label": "Select Edge", "key": "LMB"},
            {"label": "Append Edge", "key": "Shift + LMB"},
            {"label": "Reset Selection", "key": "LMB (empty)"},
            {"label": "Move Selection", "key": "G + LMB drag"},
        ],
    }

    STASH_NODE_NAME = "stash1"
    INPUT_NODE_NAME = "INPUT"

    def __init__(self, state_name, scene_viewer):
        super().__init__(scene_viewer=scene_viewer, state_name=state_name)
        self.ctx = PathMoveContext(scene_viewer=scene_viewer, state_name=state_name)

        self.path_feature = PathSelectionFeature()
        self.move_feature = PathMoveFeature()
        self.register_feature("path_selection", self.path_feature)
        self.register_feature("path_move", self.move_feature)

    def onEnter(self, kwargs):
        self.ctx.set_node(kwargs["node"])
        self.ctx.ensure_edit_geo(
            stash_node_name=self.STASH_NODE_NAME,
            input_node_name=self.INPUT_NODE_NAME,
        )
        self.ctx.ensure_mesh()
        self.call_feature(self.path_feature, "on_enter", self.ctx, kwargs)
        self.call_feature(self.move_feature, "on_enter", self.ctx, kwargs)
        self._setup_hud()
        self._update_hud()

    def onExit(self, kwargs):
        self.call_feature(self.move_feature, "on_exit", self.ctx, kwargs)
        self.call_feature(self.path_feature, "on_exit", self.ctx, kwargs)

    def onKeyEvent(self, kwargs):
        consumed = bool(self.call_feature(self.move_feature, "on_key_event", self.ctx, kwargs))
        if consumed:
            self._update_hud()
        return consumed

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        self.ctx.set_service("state_context", getattr(self, "state_context", None))
        self.ctx.ensure_mesh()

        # Move has priority when enabled to avoid selection/move event conflicts.
        consumed_move = bool(self.call_feature(self.move_feature, "on_mouse_event", self.ctx, kwargs))
        if consumed_move:
            self._update_hud()
            return True

        consumed_path = bool(self.call_feature(self.path_feature, "on_mouse_event", self.ctx, kwargs))
        if consumed_path:
            self._update_hud()
        return consumed_path

    def onMenuAction(self, kwargs):
        action = kwargs.get("menu_item")
        if action != "toggle_move":
            return False
        if bool(self.move_feature.enabled):
            self.call_feature(self.move_feature, "deactivate", self.ctx)
        else:
            self.move_feature.enabled = True
        self._update_hud()
        return True

    def onDraw(self, kwargs):
        state_context = getattr(self, "state_context", None)
        try:
            if state_context is not None and state_context.isPicking():
                return
        except Exception:
            pass

        is_interacting = bool(self.call_feature(self.move_feature, "is_interacting"))
        changed = self.ctx.sync_edit_geo(force=False, allow_sync=(not is_interacting))
        if changed:
            self.ctx.ensure_mesh()
            self.call_feature(self.path_feature, "refresh_drawables", self.ctx)
            self._update_hud()

        self.call_feature(self.path_feature, "on_draw", self.ctx, kwargs)
        self.call_feature(self.move_feature, "on_draw", self.ctx, kwargs)

    def _setup_hud(self):
        try:
            self.scene_viewer.hudInfo(template=self.HUD_TEMPLATE)
        except Exception:
            pass

    def _update_hud(self):
        move_state = "On" if bool(getattr(self.move_feature, "enabled", False)) else "Off"
        values = {
            "move": move_state,
            "edges": str(len(self.ctx.committed_hedges)),
            "points": str(len(self.ctx.selected_ptnums)),
        }
        try:
            self.scene_viewer.hudInfo(hud_values=values)
        except Exception:
            pass


def createViewerStateTemplate():
    state_typename = "pyd_path_move_lab"
    state_label = "pyd_path_move_lab"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon("$SK_ICONS/devtools.svg")

    hotkey_definitions = hou.PluginHotkeyDefinitions()
    menu = hou.ViewerStateMenu(state_typename + "_menu", state_label)
    menu.addActionItem(
        "toggle_move",
        "Toggle Move Tool",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "toggle_move", "g"),
    )
    template.bindMenu(menu)
    template.bindHotkeyDefinitions(hotkey_definitions)
    return template
