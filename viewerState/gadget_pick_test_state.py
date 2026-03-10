import hou
import viewerstate.utils as su


class State(object):
    """Minimal gadget pick test: point/edge/face only."""

    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self.node = None
        self.geo = None

        self.select_mode = "face"  # point | edge | face
        self.last_pick = None

        self.point_gadget = None
        self.edge_gadget = None
        self.face_gadget = None

        self.base_point_drawable = hou.GeometryDrawable(
            self.scene_viewer, hou.drawableGeometryType.Point, "gadget_pick_test_base_point"
        )
        self.base_point_drawable.setParams(
            {
                "color1": hou.Vector4(1.0, 0.85, 0.25, 1.0),
                "radius": 5.0,
                "style": hou.drawableGeometryPointStyle.SmoothCircle,
            }
        )
        self.base_point_drawable.show(False)

        self.base_edge_drawable = hou.GeometryDrawable(
            self.scene_viewer, hou.drawableGeometryType.Line, "gadget_pick_test_base_edge"
        )
        self.base_edge_drawable.setParams(
            {"color1": hou.Vector4(1.0, 0.85, 0.25, 1.0), "line_width": 2.0}
        )
        self.base_edge_drawable.show(False)

        self.base_face_drawable = hou.GeometryDrawable(
            self.scene_viewer, hou.drawableGeometryType.Face, "gadget_pick_test_base_face"
        )
        self.base_face_drawable.setParams({"color1": hou.Vector4(1.0, 0.85, 0.25, 0.18)})
        self.base_face_drawable.show(False)

    def onEnter(self, kwargs):
        self.node = kwargs.get("node")
        self._load_geo()
        self._init_gadgets()
        self._apply_mode()
        self._set_prompt()
        self._request_draw()

    def onResume(self, kwargs):
        self._set_prompt()
        self._request_draw()

    def onExit(self, kwargs):
        self.base_point_drawable.show(False)
        self.base_edge_drawable.show(False)
        self.base_face_drawable.show(False)

    def onDraw(self, kwargs):
        dh = kwargs["draw_handle"]
        self.base_face_drawable.draw(dh)
        self.base_edge_drawable.draw(dh)
        self.base_point_drawable.draw(dh)

    def onMenuAction(self, kwargs):
        item = kwargs.get("menu_item")
        if item == "mode_point":
            self.select_mode = "point"
        elif item == "mode_edge":
            self.select_mode = "edge"
        elif item == "mode_face":
            self.select_mode = "face"
        elif item == "reload_geo":
            self._load_geo()
            self._refresh_gadgets()
        else:
            return False

        self._apply_mode()
        self._set_prompt()
        self._request_draw()
        return True

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        reason = ui.reason()
        if reason not in (hou.uiEventReason.Located, hou.uiEventReason.Start):
            return False

        sc = getattr(self, "state_context", None)
        if sc is None:
            return False

        try:
            gadget = sc.gadget()
        except Exception:
            return False

        if gadget == "point_gadget":
            c1 = int(sc.component1())
            pick = ("point", c1)
        elif gadget == "edge_gadget":
            c1 = int(sc.component1())
            c2 = int(sc.component2())
            pick = ("edge", c1, c2)
        elif gadget == "face_gadget":
            c1 = int(sc.component1())
            pick = ("face", c1)
        else:
            pick = None

        if pick != self.last_pick:
            self.last_pick = pick
            if pick is not None:
                print("[gadget_pick_test]", pick)
                self.scene_viewer.setPromptMessage(
                    "Mode: {0} | Hover: {1}".format(self.select_mode, pick)
                )
        return False

    def _load_geo(self):
        self.geo = None
        if self.node is None:
            return

        try:
            src = self.node.geometry()
        except Exception:
            src = None
        if src is None:
            return

        g = hou.Geometry()
        g.merge(src)
        self.geo = g

    def _init_gadgets(self):
        try:
            self.point_gadget = self.state_gadgets["point_gadget"]
            self.edge_gadget = self.state_gadgets["edge_gadget"]
            self.face_gadget = self.state_gadgets["face_gadget"]
        except Exception:
            self.point_gadget = None
            self.edge_gadget = None
            self.face_gadget = None
            return

        self._refresh_gadgets()

    def _refresh_gadgets(self):
        if self.geo is None:
            return
        try:
            self.point_gadget.setGeometry(self.geo)
            self.edge_gadget.setGeometry(self.geo)
            self.face_gadget.setGeometry(self.geo)
            frozen = self.geo.freeze()
            self.base_point_drawable.setGeometry(frozen)
            self.base_edge_drawable.setGeometry(frozen)
            self.base_face_drawable.setGeometry(frozen)
            # Slightly visible for debugging.
            self.point_gadget.setParams({"draw_color": [1, 1, 1, 0.08], "radius": 6.0})
            self.edge_gadget.setParams({"draw_color": [1, 1, 1, 0.08]})
            self.face_gadget.setParams({"draw_color": [1, 1, 1, 0.04]})
        except Exception:
            pass

    def _apply_mode(self):
        try:
            if self.point_gadget is not None:
                self.point_gadget.show(self.select_mode == "point")
            if self.edge_gadget is not None:
                self.edge_gadget.show(self.select_mode == "edge")
            if self.face_gadget is not None:
                self.face_gadget.show(self.select_mode == "face")
            self.base_point_drawable.show(self.select_mode == "point")
            self.base_edge_drawable.show(self.select_mode == "edge")
            self.base_face_drawable.show(self.select_mode == "face")
        except Exception:
            pass

    def _set_prompt(self):
        try:
            self.scene_viewer.setPromptMessage(
                "GadgetPickTest | Mode: {0} | RMB menu: point/edge/face, reload".format(
                    self.select_mode
                )
            )
        except Exception:
            pass

    def _request_draw(self):
        try:
            self.scene_viewer.curViewport().draw()
        except Exception:
            pass


def createViewerStateTemplate():
    state_typename = "gadget_pick_test_state"
    state_label = "gadget_pick_test_state"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindGadget(hou.drawableGeometryType.Point, "point_gadget", label="Point")
    template.bindGadget(hou.drawableGeometryType.Line, "edge_gadget", label="Edge")
    template.bindGadget(hou.drawableGeometryType.Face, "face_gadget", label="Face")

    hotkeys = hou.PluginHotkeyDefinitions()
    menu = hou.ViewerStateMenu(state_typename + "_menu", state_label)
    menu.addActionItem(
        "mode_point",
        "Mode: Point",
        hotkey=su.defineHotkey(hotkeys, state_typename, "mode_point", "1"),
    )
    menu.addActionItem(
        "mode_edge",
        "Mode: Edge",
        hotkey=su.defineHotkey(hotkeys, state_typename, "mode_edge", "2"),
    )
    menu.addActionItem(
        "mode_face",
        "Mode: Face",
        hotkey=su.defineHotkey(hotkeys, state_typename, "mode_face", "3"),
    )
    menu.addSeparator()
    menu.addActionItem(
        "reload_geo",
        "Reload Geo",
        hotkey=su.defineHotkey(hotkeys, state_typename, "reload_geo", "r"),
    )
    template.bindMenu(menu)
    template.bindHotkeyDefinitions(hotkeys)
    template.bindIcon("$SK_ICONS/devtools.svg")
    return template
