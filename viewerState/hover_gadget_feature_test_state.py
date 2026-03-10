import hou
import viewerstate.utils as su

from skyforge.forge_states.features import HoverGadgetFeature


class _Ctx(object):
    def __init__(self, scene_viewer):
        self.scene_viewer = scene_viewer


class State(object):
    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self.ctx = _Ctx(scene_viewer)

        self.node = None
        self.geometry = None
        self.mode = "face_point"

        self.hover_feature = HoverGadgetFeature(enable_ray_filter=True)
        self.hover_feature.bind_host(self)

    def _set_prompt(self):
        hit = self.hover_feature.get_hover()
        txt = "none"
        if hit.get("visible"):
            txt = "{0} c1={1} c2={2}".format(
                hit.get("gadget"), hit.get("c1"), hit.get("c2")
            )
        self.scene_viewer.setPromptMessage(
            "HoverFeatureTest | Mode: {0} | Hover: {1} | RMB: 1/2/3/4".format(
                self.mode, txt
            )
        )

    def onEnter(self, kwargs):
        self.node = kwargs.get("node")
        self.geometry = self.node.geometry() if self.node is not None else None
        if self.geometry is None:
            return

        self.hover_feature.bind_host(self)
        self.hover_feature.set_geometry(self.geometry)
        self.hover_feature.set_mode(self.mode)
        self.hover_feature.on_enter(self.ctx, kwargs)
        self._set_prompt()

    def onExit(self, kwargs):
        self.hover_feature.on_exit(self.ctx, kwargs)

    def onMenuAction(self, kwargs):
        item = kwargs.get("menu_item")
        if item == "mode_line":
            self.mode = "line"
        elif item == "mode_face":
            self.mode = "face"
        elif item == "mode_point":
            self.mode = "point"
        elif item == "mode_face_point":
            self.mode = "face_point"
        else:
            return False

        self.hover_feature.set_mode(self.mode)
        self._set_prompt()
        self.scene_viewer.curViewport().draw()
        return True

    def onMouseEvent(self, kwargs):
        self.hover_feature.on_mouse_event(self.ctx, kwargs)

        click = self.hover_feature.consume_click()
        if click and click.get("visible"):
            print(
                "[hover_feature_test] click",
                click.get("gadget"),
                click.get("c1"),
                click.get("c2"),
            )

        self._set_prompt()
        return False

    def onDraw(self, kwargs):
        self.hover_feature.on_draw(self.ctx, kwargs)


def createViewerStateTemplate():
    state_typename = "hover_gadget_feature_test_state"
    state_label = "hover_gadget_feature_test_state"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    HoverGadgetFeature.bind_template(template)

    hotkeys = hou.PluginHotkeyDefinitions()
    menu = hou.ViewerStateMenu(state_typename + "_menu", state_label)
    menu.addActionItem(
        "mode_line",
        "Mode: Line",
        hotkey=su.defineHotkey(hotkeys, state_typename, "mode_line", "1"),
    )
    menu.addActionItem(
        "mode_face",
        "Mode: Face",
        hotkey=su.defineHotkey(hotkeys, state_typename, "mode_face", "2"),
    )
    menu.addActionItem(
        "mode_point",
        "Mode: Point",
        hotkey=su.defineHotkey(hotkeys, state_typename, "mode_point", "3"),
    )
    menu.addActionItem(
        "mode_face_point",
        "Mode: Face+Point",
        hotkey=su.defineHotkey(hotkeys, state_typename, "mode_face_point", "4"),
    )
    template.bindMenu(menu)
    template.bindHotkeyDefinitions(hotkeys)
    template.bindIcon("$SK_ICONS/devtools.svg")
    return template
