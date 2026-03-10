import time

import hou
import viewerstate.utils as su


class State(object):
    """
    Performance-focused hover state:
    - One active pick mode at a time: point/edge/face
    - Lightweight hover overlays (single element)
    - Throttled Located handling
    """

    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer

        self.node = None
        self.geo = None
        self.stash_node = None
        self.input_node = None

        self.select_mode = "face"
        self.point_gadget = None
        self.edge_gadget = None
        self.face_gadget = None

        self.hover_point_ptnum = None
        self.hover_edge = None  # tuple(ptnum0, ptnum1)
        self.hover_face_primnum = None

        self.hover_point_drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Point,
            "hover_perf_point",
        )
        self.hover_point_drawable.setParams(
            {
                "color1": hou.Vector4(0.2, 0.95, 1.0, 1.0),
                "radius": 10.0,
                "style": hou.drawableGeometryPointStyle.RingsCircle,
            }
        )
        self.hover_point_drawable.show(False)

        self.hover_edge_drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Line,
            "hover_perf_edge",
        )
        self.hover_edge_drawable.setParams(
            {
                "color1": hou.Vector4(0.2, 0.9, 1.0, 1.0),
                "line_width": 4.0,
            }
        )
        self.hover_edge_drawable.show(False)

        self.hover_face_drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Face,
            "hover_perf_face",
        )
        self.hover_face_drawable.setParams({"color1": hou.Vector4(0.25, 0.7, 1.0, 0.24)})
        self.hover_face_drawable.show(False)

        self.base_drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Face,
            "hover_perf_base",
        )
        self.base_drawable.setParams({"color1": hou.Vector4(1.0, 0.85, 0.2, 0.06)})
        self.base_drawable.show(False)

        self._last_located_t = 0.0
        self._last_mouse = None
        self._located_interval = 0.02  # 50 Hz max
        self._mouse_delta2 = 4.0  # 2px squared

    def onEnter(self, kwargs):
        self.node = kwargs["node"]
        self._load_geo()
        self._init_gadgets()
        self._apply_mode_visibility()
        self._set_prompt()
        self._request_draw()

    def onExit(self, kwargs):
        self._clear_hover()
        self.base_drawable.show(False)
        self.hover_point_drawable.show(False)
        self.hover_edge_drawable.show(False)
        self.hover_face_drawable.show(False)

    def onDraw(self, kwargs):
        dh = kwargs["draw_handle"]
        self.base_drawable.draw(dh)
        self.hover_point_drawable.draw(dh)
        self.hover_edge_drawable.draw(dh)
        self.hover_face_drawable.draw(dh)

    def onMenuAction(self, kwargs):
        item = kwargs.get("menu_item")

        if item == "mode_point":
            self.select_mode = "point"
            self._apply_mode_visibility()
            self._clear_hover()
            self._set_prompt()
            self._request_draw()
            return True

        if item == "mode_edge":
            self.select_mode = "edge"
            self._apply_mode_visibility()
            self._clear_hover()
            self._set_prompt()
            self._request_draw()
            return True

        if item == "mode_face":
            self.select_mode = "face"
            self._apply_mode_visibility()
            self._clear_hover()
            self._set_prompt()
            self._request_draw()
            return True

        if item == "reload_geo":
            self._load_geo()
            self._refresh_gadget_geometry()
            self._clear_hover()
            self._request_draw()
            return True

        return False

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        reason = ui.reason()
        if reason != hou.uiEventReason.Located:
            return False

        if not self._should_process_located(ui):
            return True

        self._update_hover_from_context()
        return True

    def _should_process_located(self, ui_event):
        now = time.monotonic()
        mx = float(ui_event.device().mouseX())
        my = float(ui_event.device().mouseY())

        if self._last_mouse is not None:
            dx = mx - self._last_mouse[0]
            dy = my - self._last_mouse[1]
            if (dx * dx + dy * dy) < self._mouse_delta2 and (now - self._last_located_t) < self._located_interval:
                return False

        self._last_mouse = (mx, my)
        self._last_located_t = now
        return True

    def _load_geo(self):
        self.geo = None
        if self.node is None:
            return

        self.stash_node = self.node.node("stash1")
        self.input_node = self.node.node("INPUT")

        src = None
        if self.stash_node is not None:
            try:
                self.stash_node.cook(force=True)
                g = self.stash_node.geometry()
                if g is not None and (
                    int(g.intrinsicValue("pointcount")) > 0
                    or int(g.intrinsicValue("primitivecount")) > 0
                ):
                    src = g
            except Exception:
                src = None

        if src is None and self.input_node is not None:
            try:
                src = self.input_node.geometry()
            except Exception:
                src = None

        if src is None:
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

        try:
            self.point_gadget.setParams({"draw_color": [1, 1, 1, 0.08], "radius": 6.0})
            self.edge_gadget.setParams({"draw_color": [1, 1, 1, 0.08]})
            self.face_gadget.setParams({"draw_color": [1, 1, 1, 0.04]})
        except Exception:
            pass

        self._refresh_gadget_geometry()

    def _refresh_gadget_geometry(self):
        if self.geo is None:
            return
        try:
            if self.point_gadget is not None:
                self.point_gadget.setGeometry(self.geo)
            if self.edge_gadget is not None:
                self.edge_gadget.setGeometry(self.geo)
            if self.face_gadget is not None:
                self.face_gadget.setGeometry(self.geo)
            self.base_drawable.setGeometry(self.geo.freeze())
        except Exception:
            pass

    def _apply_mode_visibility(self):
        try:
            if self.point_gadget is not None:
                self.point_gadget.show(self.select_mode == "point")
            if self.edge_gadget is not None:
                self.edge_gadget.show(self.select_mode == "edge")
            if self.face_gadget is not None:
                self.face_gadget.show(self.select_mode == "face")
            self.base_drawable.show(self.select_mode == "face")
        except Exception:
            pass

    def _update_hover_from_context(self):
        sc = getattr(self, "state_context", None)
        if sc is None or self.geo is None:
            self._clear_hover()
            self._sync_hover_drawables()
            self._request_draw()
            return

        try:
            gadget = sc.gadget()
        except Exception:
            gadget = None

        hp = None
        he = None
        hf = None

        if self.select_mode == "point" and gadget == "point_gadget":
            try:
                ptnum = int(sc.component1())
                if ptnum >= 0 and self.geo.point(ptnum) is not None:
                    hp = ptnum
            except Exception:
                hp = None

        elif self.select_mode == "edge" and gadget == "edge_gadget":
            try:
                p0 = int(sc.component1())
                p1 = int(sc.component2())
                if p0 >= 0 and p1 >= 0:
                    he = (p0, p1)
            except Exception:
                he = None

        elif self.select_mode == "face" and gadget == "face_gadget":
            try:
                primnum = int(sc.component1())
                prim = self.geo.prim(primnum)
                if prim is not None and prim.numVertices() >= 3:
                    hf = primnum
            except Exception:
                hf = None

        changed = (
            hp != self.hover_point_ptnum
            or he != self.hover_edge
            or hf != self.hover_face_primnum
        )
        if not changed:
            return

        self.hover_point_ptnum = hp
        self.hover_edge = he
        self.hover_face_primnum = hf
        self._sync_hover_drawables()
        self._request_draw()

    def _sync_hover_drawables(self):
        point_geo = hou.Geometry()
        if self.hover_point_ptnum is not None:
            pt = self.geo.point(int(self.hover_point_ptnum))
            if pt is not None:
                p = point_geo.createPoint()
                p.setPosition(pt.position())
        self.hover_point_drawable.setGeometry(point_geo.freeze())
        self.hover_point_drawable.show(self.select_mode == "point" and self.hover_point_ptnum is not None)

        edge_geo = hou.Geometry()
        if self.hover_edge is not None:
            p0n, p1n = self.hover_edge
            p0 = self.geo.point(int(p0n))
            p1 = self.geo.point(int(p1n))
            if p0 is not None and p1 is not None:
                poly = edge_geo.createPolygon()
                poly.setIsClosed(False)
                a = edge_geo.createPoint()
                a.setPosition(p0.position())
                b = edge_geo.createPoint()
                b.setPosition(p1.position())
                poly.addVertex(a)
                poly.addVertex(b)
        self.hover_edge_drawable.setGeometry(edge_geo.freeze())
        self.hover_edge_drawable.show(self.select_mode == "edge" and self.hover_edge is not None)

        face_geo = hou.Geometry()
        if self.hover_face_primnum is not None:
            prim = self.geo.prim(int(self.hover_face_primnum))
            if prim is not None and prim.numVertices() >= 3:
                poly = face_geo.createPolygon()
                poly.setIsClosed(bool(prim.isClosed()))
                for v in prim.vertices():
                    src_pt = v.point()
                    dst_pt = face_geo.createPoint()
                    dst_pt.setPosition(src_pt.position())
                    poly.addVertex(dst_pt)
        self.hover_face_drawable.setGeometry(face_geo.freeze())
        self.hover_face_drawable.show(self.select_mode == "face" and self.hover_face_primnum is not None)

    def _clear_hover(self):
        self.hover_point_ptnum = None
        self.hover_edge = None
        self.hover_face_primnum = None
        self.hover_point_drawable.show(False)
        self.hover_edge_drawable.show(False)
        self.hover_face_drawable.show(False)

    def _set_prompt(self):
        try:
            self.scene_viewer.setPromptMessage(
                "HoverPerf: RMB menu -> Select Mode (Point/Edge/Face) | Reload Geo"
            )
        except Exception:
            pass

    def _request_draw(self):
        try:
            self.scene_viewer.curViewport().draw()
        except Exception:
            pass


def createViewerStateTemplate():
    state_typename = "hover_perf_state"
    state_label = "hover_perf_state"
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
        "Select Mode: Point",
        hotkey=su.defineHotkey(hotkeys, state_typename, "mode_point", "&"),
    )
    menu.addActionItem(
        "mode_edge",
        "Select Mode: Edge",
        hotkey=su.defineHotkey(hotkeys, state_typename, "mode_edge", "é"),
    )
    menu.addActionItem(
        "mode_face",
        "Select Mode: Face",
        hotkey=su.defineHotkey(hotkeys, state_typename, "mode_face", "\""),
    )
    menu.addSeparator()
    menu.addActionItem(
        "reload_geo",
        "Reload Geo",
        hotkey=su.defineHotkey(hotkeys, state_typename, "reload_geo", "\'"),
    )

    template.bindMenu(menu)
    template.bindHotkeyDefinitions(hotkeys)
    template.bindIcon("$SK_ICONS/devtools.svg")
    return template
