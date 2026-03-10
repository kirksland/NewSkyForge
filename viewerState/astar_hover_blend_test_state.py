import hou
import viewerstate.utils as su

from skyforge.forge_states.base_state import BaseState
from skyforge.forge_states.tool_context import ToolContext
from skyforge.forge_states.features.astar_turn_feature import AstarTurnFeature
from skyforge.forge_states.features.hover_gadget_feature import HoverGadgetFeature


class State(BaseState):
    """
    Test state: blend HoverGadgetFeature + AstarTurnFeature.
    - Phase 1: pick start edge (LMB)
    - Phase 2: hover previews A* path, LMB picks end edge and commits
    """

    def __init__(self, state_name, scene_viewer):
        super().__init__(scene_viewer=scene_viewer, state_name=state_name)
        self.scene_viewer = scene_viewer
        self.state_name = state_name

        self.ctx = ToolContext(self.scene_viewer, state_name=self.state_name)
        self.hover_feature = HoverGadgetFeature(enable_ray_filter=True)
        self.astar_feature = AstarTurnFeature()

        self.phase = "pick_start"  # pick_start | pick_end

    def _set_prompt(self):
        hit = self.hover_feature.get_hover()
        hover_txt = "none"
        if hit.get("visible") and hit.get("edge") is not None:
            a, b = hit["edge"]
            hover_txt = "p{0}-p{1}".format(int(a), int(b))
        self.scene_viewer.setPromptMessage(
            "AstarHoverBlend | Phase: {0} | Hover Edge: {1} | LMB: set".format(
                self.phase,
                hover_txt,
            )
        )

    def _reset_session(self):
        self.astar_feature.reset_all(self.ctx)
        self.hover_feature.clear()
        self.phase = "pick_start"
        self._set_prompt()
        self.scene_viewer.curViewport().draw()

    def onEnter(self, kwargs):
        node = kwargs.get("node")
        self.ctx.set_node(node)
        self.ctx.geometry = node.geometry() if node is not None else None
        self.ctx.ensure_mesh(geo=self.ctx.geometry)

        self.astar_feature.on_enter(self.ctx, kwargs)

        self.hover_feature.bind_host(self)
        self.hover_feature.set_geometry(self.ctx.geometry)
        self.hover_feature.set_mode(HoverGadgetFeature.MODE_LINE)
        self.hover_feature.on_enter(self.ctx, kwargs)

        self.phase = "pick_start"
        self._set_prompt()

    def onExit(self, kwargs):
        self.hover_feature.on_exit(self.ctx, kwargs)
        self.astar_feature.on_exit(self.ctx, kwargs)

    def onMenuAction(self, kwargs):
        item = kwargs.get("menu_item")
        if item == "reset_session":
            self._reset_session()
            return True
        if item == "phase_pick_start":
            self.phase = "pick_start"
            self.astar_feature.clear_preview(self.ctx)
            self._set_prompt()
            self.scene_viewer.curViewport().draw()
            return True
        if item == "phase_pick_end":
            self.phase = "pick_end"
            self._set_prompt()
            self.scene_viewer.curViewport().draw()
            return True
        return False

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        # Keep topology fresh if geometry changes.
        self.ctx.ensure_mesh(geo=self.ctx.geometry)

        self.hover_feature.on_mouse_event(self.ctx, kwargs)
        hover = self.hover_feature.get_hover()

        # Live preview while selecting end edge.
        if self.phase == "pick_end":
            edge = hover.get("edge")
            if hover.get("visible") and edge is not None:
                he = self.ctx.edge_to_hedge(int(edge[0]), int(edge[1]))
                if he >= 0:
                    self.astar_feature.preview_from_base_to_he(self.ctx, he)
                else:
                    self.astar_feature.clear_preview(self.ctx)
            else:
                self.astar_feature.clear_preview(self.ctx)

        click = self.hover_feature.consume_click()
        if click and click.get("visible") and click.get("edge") is not None:
            p0, p1 = click["edge"]
            he = self.ctx.edge_to_hedge(int(p0), int(p1))
            if he >= 0:
                if self.phase == "pick_start":
                    # First click: initialize A* start edge (basegroup).
                    self.astar_feature.reset_all(self.ctx)
                    self.astar_feature.commit_from_base_to_he(self.ctx, he)
                    self.phase = "pick_end"
                else:
                    # Second click: commit path, then go back to start phase.
                    self.astar_feature.commit_from_base_to_he(self.ctx, he)
                    self.phase = "pick_start"

        self._set_prompt()
        return False

    def onDraw(self, kwargs):
        self.hover_feature.on_draw(self.ctx, kwargs)
        preview = self.ctx.get_service("preview")
        if preview is not None:
            preview.draw_all(kwargs["draw_handle"])


def createViewerStateTemplate():
    state_typename = "astar_hover_blend_test_state"
    state_label = "astar_hover_blend_test_state"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    HoverGadgetFeature.bind_template(template)

    hotkeys = hou.PluginHotkeyDefinitions()
    menu = hou.ViewerStateMenu(state_typename + "_menu", state_label)
    menu.addActionItem(
        "reset_session",
        "Reset Session",
        hotkey=su.defineHotkey(hotkeys, state_typename, "reset_session", "r"),
    )
    menu.addActionItem(
        "phase_pick_start",
        "Phase: Pick Start",
        hotkey=su.defineHotkey(hotkeys, state_typename, "phase_pick_start", "1"),
    )
    menu.addActionItem(
        "phase_pick_end",
        "Phase: Pick End",
        hotkey=su.defineHotkey(hotkeys, state_typename, "phase_pick_end", "2"),
    )
    template.bindMenu(menu)
    template.bindHotkeyDefinitions(hotkeys)
    template.bindIcon("$SK_ICONS/devtools.svg")
    return template
