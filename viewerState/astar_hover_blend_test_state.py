import hou
import viewerstate.utils as su

from skyforge.forge_states.base_state import BaseState
from skyforge.forge_states.tool_context import ToolContext
from skyforge.forge_states.features.astar_turn_feature import AstarTurnFeature
from skyforge.forge_states.features.hover_gadget_feature import HoverGadgetFeature
from skyforge.forge_states.features.transversal_loop_feature import TransversalLoopFeature


class State(BaseState):
    """
    Test state: blend HoverGadgetFeature + AstarTurnFeature + TransversalLoopFeature.
    - tool_mode=astar: LMB pick start/end edge (phase workflow)
    - tool_mode=loop: LMB set base edge, MMB commit transversal loop
    """

    def __init__(self, state_name, scene_viewer):
        super().__init__(scene_viewer=scene_viewer, state_name=state_name)
        self.scene_viewer = scene_viewer
        self.state_name = state_name

        self.ctx = ToolContext(self.scene_viewer, state_name=self.state_name)
        self.hover_feature = HoverGadgetFeature(enable_ray_filter=True)
        self.astar_feature = AstarTurnFeature()
        self.loop_feature = TransversalLoopFeature()

        self.tool_mode = "astar"  # astar | loop
        self.phase = "pick_start"  # pick_start | pick_end

    def _set_prompt(self):
        hit = self.hover_feature.get_hover()
        hover_txt = "none"
        if hit.get("visible") and hit.get("edge") is not None:
            a, b = hit["edge"]
            hover_txt = "p{0}-p{1}".format(int(a), int(b))
        if self.tool_mode == "astar":
            msg = "AstarHoverBlend | Tool: astar | Phase: {0} | Hover Edge: {1} | LMB: set".format(
                self.phase, hover_txt
            )
        else:
            mode_txt = "roll" if self.loop_feature.mode == "roll" else "quad"
            msg = (
                "AstarHoverBlend | Tool: loop ({0}) | Hover Edge: {1} | LMB: base | MMB: commit"
            ).format(mode_txt, hover_txt)
        self.scene_viewer.setPromptMessage(msg)

    def _reset_session(self):
        self.astar_feature.reset_all(self.ctx)
        self.loop_feature.reset_all(self.ctx)
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
        self.loop_feature.on_enter(self.ctx, kwargs)

        self.hover_feature.attach(
            host=self,
            ctx=self.ctx,
            kwargs=kwargs,
            geometry=self.ctx.geometry,
            mode=HoverGadgetFeature.MODE_LINE,
        )

        self.phase = "pick_start"
        self._set_prompt()

    def onExit(self, kwargs):
        self.hover_feature.detach(self.ctx, kwargs)
        self.loop_feature.on_exit(self.ctx, kwargs)
        self.astar_feature.on_exit(self.ctx, kwargs)

    def onKeyEvent(self, kwargs):
        consumed = bool(self.loop_feature.on_key_event(self.ctx, kwargs))
        if consumed:
            self._set_prompt()
            self.scene_viewer.curViewport().draw()
        return consumed


    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        # Keep topology fresh if geometry changes.
        self.ctx.ensure_mesh(geo=self.ctx.geometry)

        hover, click = self.hover_feature.tick(self.ctx, kwargs)
        he_hover = self._hover_hedge(hover)
        edge_hover = hover.get("edge") if hover.get("visible") else None

        if self.tool_mode == "astar":
            # Live preview while selecting end edge.
            if self.phase == "pick_end":
                if he_hover >= 0:
                    self.astar_feature.preview_from_base_to_he(self.ctx, he_hover)
                else:
                    self.astar_feature.clear_preview(self.ctx)

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
        else:
            # Loop tool: hover previews full loop path.
            if he_hover >= 0:
                self.loop_feature.preview_loop_from_he(self.ctx, he_hover)
            else:
                self.loop_feature.clear_preview(self.ctx)

            if ui.reason() == hou.uiEventReason.Start:
                dev = ui.device()
                edge_click = edge_hover
                he_click = he_hover if edge_click is not None else -1
                if he_click < 0 and edge_click is not None:
                    he_click = self.ctx.edge_to_hedge(int(edge_click[0]), int(edge_click[1]))

                if he_click >= 0 and edge_click is not None and dev.isLeftButton():
                    p0, p1 = edge_click
                    self.loop_feature.set_basegroup_from_edge(self.ctx, int(p0), int(p1))
                    self.loop_feature.preview_edge(self.ctx, int(p0), int(p1))
                elif he_click >= 0 and dev.isMiddleButton():
                    self.loop_feature.commit_loop_from_he(self.ctx, he_click)

        self._set_prompt()
        return False

    def onDraw(self, kwargs):
        self.hover_feature.draw(self.ctx, kwargs)
        self.astar_feature.on_draw(self.ctx, kwargs)
        self.loop_feature.on_draw(self.ctx, kwargs)
        

    def onMenuAction(self, kwargs):
        item = kwargs.get("menu_item")
        if item == "reset_session":
            self._reset_session()
            return True
        if item == "tool_astar":
            self.tool_mode = "astar"
            self.loop_feature.clear_preview(self.ctx)
            self._set_prompt()
            self.scene_viewer.curViewport().draw()
            return True
        if item == "tool_loop":
            self.tool_mode = "loop"
            self.astar_feature.clear_preview(self.ctx)
            self.phase = "pick_start"
            self._set_prompt()
            self.scene_viewer.curViewport().draw()
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
        if item == "loop_mode_roll":
            self.loop_feature.mode = "roll"
            self._set_prompt()
            self.scene_viewer.curViewport().draw()
            return True
        if item == "loop_mode_quad":
            self.loop_feature.mode = "quad"
            self._set_prompt()
            self.scene_viewer.curViewport().draw()
            return True
        return False

    def _hover_hedge(self, hover):
        if not hover or not hover.get("visible"):
            return -1
        edge = hover.get("edge")
        if edge is None:
            return -1
        return self.ctx.edge_to_hedge(int(edge[0]), int(edge[1]))


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
        "tool_astar",
        "Tool: A*",
        hotkey=su.defineHotkey(hotkeys, state_typename, "tool_astar", "a"),
    )
    menu.addActionItem(
        "tool_loop",
        "Tool: Loop",
        hotkey=su.defineHotkey(hotkeys, state_typename, "tool_loop", "l"),
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
    menu.addActionItem(
        "loop_mode_roll",
        "Loop Mode: Roll",
        hotkey=su.defineHotkey(hotkeys, state_typename, "loop_mode_roll", "q"),
    )
    menu.addActionItem(
        "loop_mode_quad",
        "Loop Mode: Quad",
        hotkey=su.defineHotkey(hotkeys, state_typename, "loop_mode_quad", "w"),
    )
    template.bindMenu(menu)
    template.bindHotkeyDefinitions(hotkeys)
    template.bindIcon("$SK_ICONS/devtools.svg")
    return template


