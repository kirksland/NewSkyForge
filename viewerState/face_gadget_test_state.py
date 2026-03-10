"""
State:          Justi::pyd loop::1.0
State type:     justi::pyd_loop::1.0
Description:    Justi::pyd loop::1.0
Author:         justi
Date Created:   March 10, 2026 - 12:45:24
"""

import hou
import viewerstate.utils as su


class State(object):
    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self.geometry = None

        self.mode = "line"  # line | face | point | face_point

        self.line_gadget = None
        self.face_gadget = None
        self.point_gadget = None
        self.point_hover_gadget = None
        self.hover_point_id = None
        self.hover_edge = None

        self.cursor = su.CursorLabel(scene_viewer)
        self.hover_edge_drawable = hou.GeometryDrawable(
            scene_viewer,
            hou.drawableGeometryType.Line,
            "hover_edge_drawable",
        )
        self.hover_edge_drawable.setParams(
            {"color1": hou.Vector4(1.0, 1.0, 0.0, 1.0), "line_width": 4.0}
        )
        self.hover_edge_drawable.show(False)

    def _set_prompt(self):
        self.scene_viewer.setPromptMessage(
            "Gadget Test | Mode: {0} | RMB: Line/Face/Point/Face+Point".format(self.mode)
        )

    def _on_simple_click(self, gadget_name, c1, c2):
        msg = "[click] {0} c1={1} c2={2}".format(gadget_name, c1, c2)
        print(msg)
        self.scene_viewer.setPromptMessage(msg)

    def _is_point_visible_from_event(self, ui_event, ptnum):
        if self.geometry is None or ui_event is None:
            return False

        pt = self.geometry.point(int(ptnum))
        if pt is None:
            return False

        try:
            ray_origin, ray_dir = ui_event.ray()
        except Exception:
            return False

        ray_o = hou.Vector3(ray_origin)
        ray_d = hou.Vector3(ray_dir)
        try:
            if ray_d.length() <= 1e-12:
                return False
            ray_d = ray_d.normalized()
        except Exception:
            return False

        pt_pos = hou.Vector3(pt.position())
        t_point = (pt_pos - ray_o).dot(ray_d)
        if t_point < 0.0:
            return False

        hit_pos = hou.Vector3()
        hit_nml = hou.Vector3()
        hit_uvw = hou.Vector3()
        try:
            primnum = int(self.geometry.intersect(ray_o, ray_d, hit_pos, hit_nml, hit_uvw))
        except Exception:
            primnum = -1

        if primnum < 0:
            return True

        t_hit = (hou.Vector3(hit_pos) - ray_o).dot(ray_d)
        # Small tolerance to avoid jitter when point lies on first visible surface.
        return t_point <= (t_hit + 5e-3)

    def _is_edge_visible_from_event(self, ui_event, p0num, p1num):
        if self.geometry is None or ui_event is None:
            return False

        p0 = self.geometry.point(int(p0num))
        p1 = self.geometry.point(int(p1num))
        if p0 is None or p1 is None:
            return False

        try:
            ray_origin, ray_dir = ui_event.ray()
        except Exception:
            return False

        ray_o = hou.Vector3(ray_origin)
        ray_d = hou.Vector3(ray_dir)
        try:
            if ray_d.length() <= 1e-12:
                return False
            ray_d = ray_d.normalized()
        except Exception:
            return False

        mid = (hou.Vector3(p0.position()) + hou.Vector3(p1.position())) * 0.5
        t_edge = (mid - ray_o).dot(ray_d)
        if t_edge < 0.0:
            return False

        hit_pos = hou.Vector3()
        hit_nml = hou.Vector3()
        hit_uvw = hou.Vector3()
        try:
            primnum = int(self.geometry.intersect(ray_o, ray_d, hit_pos, hit_nml, hit_uvw))
        except Exception:
            primnum = -1

        if primnum < 0:
            return True

        t_hit = (hou.Vector3(hit_pos) - ray_o).dot(ray_d)
        return t_edge <= (t_hit + 5e-3)

    def _apply_mode_visibility(self):
        if self.line_gadget is not None:
            self.line_gadget.show(self.mode == "line")
        if self.face_gadget is not None:
            self.face_gadget.show(self.mode in ("face", "face_point"))

        if self.point_gadget is not None:
            self.point_gadget.show(self.mode in ("point", "face_point"))
        if self.point_hover_gadget is not None:
            self.point_hover_gadget.show(self.mode in ("point", "face_point"))

        if self.face_gadget is not None and self.mode not in ("face", "face_point"):
            self.face_gadget.setParams({"indices": []})
        if self.point_hover_gadget is not None and self.mode not in ("point", "face_point"):
            self.point_hover_gadget.setParams({"indices": []})
        if self.mode not in ("point", "face_point"):
            self.hover_point_id = None
        if self.mode != "line":
            self.hover_edge = None
            self.hover_edge_drawable.show(False)

    def onEnter(self, kwargs):
        node = kwargs["node"]
        self.geometry = node.geometry()

        self.line_gadget = self.state_gadgets["line_gadget"]
        self.line_gadget.setGeometry(self.geometry)
        self.line_gadget.setParams(
            {
                "draw_color": [0.0, 0.0, 0.0, 0.0],
                "locate_color": [1.0, 0.0, 0.0, 1.0],
                "pick_color": [1.0, 1.0, 0.0, 1.0],
                "line_width": 4.0,
            }
        )

        self.face_gadget = self.state_gadgets["face_gadget"]
        self.face_gadget.setGeometry(self.geometry)
        self.face_gadget.setParams(
            {
                "draw_color": [0.0, 0.0, 0.0, 0.0],
                "locate_color": [0.0, 0.0, 0.0, 0.0],
                "pick_color": [0.0, 0.0, 0.0, 0.0],
            }
        )

        self.point_gadget = self.state_gadgets["point_gadget"]
        self.point_gadget.setGeometry(self.geometry)
        self.point_gadget.setParams(
            {
                "draw_color": [0.0, 0.0, 0.0, 0.0],
                "locate_color": [0.0, 0.0, 0.0, 0.0],
                "pick_color": [0.0, 0.0, 0.0, 0.0],
                "radius": 3.0,
            }
        )

        self.point_hover_gadget = self.state_gadgets["point_hover_gadget"]
        self.point_hover_gadget.setGeometry(self.geometry)
        self.point_hover_gadget.setParams(
            {
                "draw_color": [1.0, 0.95, 0.25, 1.0],
                "locate_color": [1.0, 0.95, 0.25, 1.0],
                "pick_color": [1.0, 0.95, 0.25, 1.0],
                "radius": 7.0,
                "indices": [],
            }
        )

        self.cursor.show(False)
        self.hover_point_id = None
        self.hover_edge = None
        self._apply_mode_visibility()
        self._set_prompt()

    def onResume(self, kwargs):
        self._apply_mode_visibility()
        self._set_prompt()

    def onInterrupt(self, kwargs):
        self.cursor.show(False)
        self.hover_point_id = None
        self.hover_edge = None
        self.hover_edge_drawable.show(False)
        if self.line_gadget is not None:
            self.line_gadget.show(False)
        if self.face_gadget is not None:
            self.face_gadget.show(False)
        if self.point_gadget is not None:
            self.point_gadget.show(False)
        if self.point_hover_gadget is not None:
            self.point_hover_gadget.show(False)

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

        self.cursor.show(False)
        self.hover_point_id = None
        self.hover_edge = None
        self.hover_edge_drawable.show(False)
        self._apply_mode_visibility()
        self._set_prompt()
        self.scene_viewer.curViewport().draw()
        return True

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        self.cursor.setParams(kwargs)

        sc = getattr(self, "state_context", None)
        if sc is None:
            self.cursor.show(False)
            self.hover_point_id = None
            self.hover_edge = None
            self.hover_edge_drawable.show(False)
            if self.face_gadget is not None:
                self.face_gadget.setParams({"indices": []})
            if self.point_hover_gadget is not None:
                self.point_hover_gadget.setParams({"indices": []})
            return True

        try:
            gadget_name = sc.gadget()
        except Exception:
            gadget_name = None

        if self.mode == "line":
            active = {"line_gadget"}
        elif self.mode == "face":
            active = {"face_gadget"}
        elif self.mode == "point":
            active = {"point_gadget", "point_hover_gadget"}
        else:
            active = {"face_gadget", "point_gadget", "point_hover_gadget"}

        if gadget_name in active:
            try:
                label = sc.gadgetLabel()
                c1 = int(sc.component1())
                c2 = int(sc.component2())
            except Exception:
                label = str(gadget_name)
                c1 = -1
                c2 = -1

            if (
                ui is not None
                and ui.reason() == hou.uiEventReason.Start
                and ui.device().isLeftButton()
            ):
                self._on_simple_click(gadget_name, c1, c2)

            self.cursor.setLabel("{} : {} {}".format(label, c1, c2 if c2 > -1 else ""))
            self.cursor.show(True)

            if gadget_name == "face_gadget":
                self.hover_point_id = None
                self.hover_edge = None
                face_valid = (
                    c1 > -1
                    and self.geometry is not None
                    and self.geometry.prim(c1) is not None
                )
                if face_valid:
                    self.face_gadget.setParams({"indices": [c1]})
                else:
                    # Same mechanic: if nothing valid under cursor, clear all hover visuals.
                    self.face_gadget.setParams({"indices": []})
                    self.point_hover_gadget.setParams({"indices": []})
                self.point_hover_gadget.setParams({"indices": []})
            elif gadget_name in ("point_gadget", "point_hover_gadget"):
                self.hover_edge = None
                self.face_gadget.setParams({"indices": []})
                if c1 > -1 and self._is_point_visible_from_event(ui, c1):
                    self.hover_point_id = int(c1)
                    self.point_hover_gadget.setParams({"indices": [c1]})
                else:
                    self.hover_point_id = None
                    self.point_hover_gadget.setParams({"indices": []})
            elif gadget_name == "line_gadget":
                self.hover_point_id = None
                self.face_gadget.setParams({"indices": []})
                self.point_hover_gadget.setParams({"indices": []})
                if c1 > -1 and c2 > -1 and self._is_edge_visible_from_event(ui, c1, c2):
                    self.hover_edge = (int(c1), int(c2))
                else:
                    self.hover_edge = None
            else:
                self.hover_point_id = None
                self.hover_edge = None
                self.face_gadget.setParams({"indices": []})
                self.point_hover_gadget.setParams({"indices": []})
        else:
            self.cursor.show(False)
            self.hover_point_id = None
            self.hover_edge = None
            if self.face_gadget is not None:
                self.face_gadget.setParams({"indices": []})
            if self.point_hover_gadget is not None:
                self.point_hover_gadget.setParams({"indices": []})

        self.scene_viewer.curViewport().draw()
        return True

    def onDraw(self, kwargs):
        handle = kwargs["draw_handle"]

        if self.mode == "line":
            self.line_gadget.draw(handle)
        elif self.mode == "face":
            self.face_gadget.draw(handle)
        elif self.mode == "face_point":
            self.face_gadget.draw(handle)
            self.point_gadget.draw(handle)
            if self.hover_point_id is not None:
                self.point_hover_gadget.draw(handle)
        else:
            self.point_gadget.draw(handle)
            if self.hover_point_id is not None:
                self.point_hover_gadget.draw(handle)

        edge_geo = hou.Geometry()
        if self.mode == "line" and self.hover_edge is not None and self.geometry is not None:
            p0 = self.geometry.point(self.hover_edge[0])
            p1 = self.geometry.point(self.hover_edge[1])
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
        self.hover_edge_drawable.show(self.mode == "line" and self.hover_edge is not None)
        self.hover_edge_drawable.draw(handle)

        self.cursor.draw(handle)


def createViewerStateTemplate():
    state_typename = "face_gadget_test_state"
    state_label = "face_gadget_test_state"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)

    template.bindGadget(hou.drawableGeometryType.Line, "line_gadget", label="Line")
    template.bindGadget(hou.drawableGeometryType.Face, "face_gadget", label="Face")
    template.bindGadget(hou.drawableGeometryType.Point, "point_gadget", label="Point")
    template.bindGadget(hou.drawableGeometryType.Point, "point_hover_gadget", label="Point Hover")

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
    return template
