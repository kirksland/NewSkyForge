import hou
import curveutils as cu

DEBUG = False


class State(object):
    """
    Standalone viewer state (no framework):
    - Draw mode:
      - LMB: append point
      - Enter: switch to Edit mode
      - Backspace/Delete: remove last point
    - Edit mode:
      - LMB on point: select and start drag
      - Shift+LMB on point: toggle selection
      - LMB drag: move selected points
      - Delete: remove selected points
      - D: switch to Draw mode
    """

    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer

        self.node = None
        self.picker = cu.curve3DPicker(cu.curve3DPicker.MODE_VIEWPLANE)

        self.mode = "draw"
        self.points = []
        self.selected_indices = set()
        self.selected_edges = set()

        self.drag_active = False
        self.drag_plane_origin = None
        self.drag_start_world = None
        self.drag_start_positions = {}
        self.pick_radius_px = 14.0

        self.points_drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Point,
            "curveutils_basic_points",
        )
        self.points_drawable.setParams(
            {
                "color1": hou.Vector4(1.0, 0.75, 0.15, 1.0),
                "radius": 7.0,
                "style": hou.drawableGeometryPointStyle.SmoothCircle,
            }
        )
        self.points_drawable.show(False)
        self.edges_drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Line,
            "curveutils_basic_edges",
        )
        self.edges_drawable.setParams(
            {
                "color1": hou.Vector4(0.95, 0.85, 0.35, 1.0),
                "line_width": 2.0,
            }
        )
        self.edges_drawable.show(False)
        self.selected_drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Point,
            "curveutils_basic_points_selected",
        )
        self.selected_drawable.setParams(
            {
                "color1": hou.Vector4(1.0, 0.45, 0.1, 1.0),
                "radius": 9.0,
                "style": hou.drawableGeometryPointStyle.RingsCircle,
            }
        )
        self.selected_drawable.show(False)
        self.selected_edges_drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Line,
            "curveutils_basic_edges_selected",
        )
        self.selected_edges_drawable.setParams(
            {
                "color1": hou.Vector4(1.0, 0.4, 0.1, 1.0),
                "line_width": 4.0,
            }
        )
        self.selected_edges_drawable.show(False)

    def onEnter(self, kwargs):
        self.node = kwargs.get("node")
        self.picker.reset()
        self.picker.setPickMode(cu.curve3DPicker.MODE_VIEWPLANE)
        self._set_prompt()
        self._sync_drawables()
        self._request_draw()

    def onExit(self, kwargs):
        self.points_drawable.show(False)
        self.edges_drawable.show(False)
        self.selected_drawable.show(False)
        self.selected_edges_drawable.show(False)
        self.drag_active = False

    def onDraw(self, kwargs):
        draw_handle = kwargs["draw_handle"]
        self.edges_drawable.draw(draw_handle)
        self.selected_edges_drawable.draw(draw_handle)
        self.points_drawable.draw(draw_handle)
        self.selected_drawable.draw(draw_handle)

    def onKeyEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False
        dev = ui.device()
        if dev.isAutoRepeat():
            return False

        key = (dev.keyString() or "").lower()
        if key == "enter":
            self.mode = "edit"
            self._set_prompt()
            self._request_draw()
            return True

        if key == "d":
            self.mode = "draw"
            self.drag_active = False
            self._set_prompt()
            self._request_draw()
            return True

        if key in ("backspace", "del", "delete") and self.mode == "draw":
            if self.points:
                self.points.pop()
            self.selected_indices.clear()
            self.selected_edges.clear()
            self._sync_drawables()
            self._request_draw()
            return True

        if key in ("backspace", "del", "delete") and self.mode == "edit":
            self._delete_selected()
            self._sync_drawables()
            self._request_draw()
            return True

        return False

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        reason = ui.reason()
        dev = ui.device()

        if reason == hou.uiEventReason.Start and dev.isLeftButton():
            if self.mode == "draw":
                return self._handle_draw_start(ui)
            return self._handle_edit_start(ui)

        if reason in (hou.uiEventReason.Active, hou.uiEventReason.Located) and self.drag_active:
            return self._handle_active(ui)

        if reason == hou.uiEventReason.Changed and self.drag_active:
            self._handle_active(ui)
            self.drag_active = False
            self.drag_start_positions = {}
            return True

        return False

    def _handle_draw_start(self, ui_event):
        pos = self._pick_world_pos(ui_event, plane_orig=None)
        if pos is None:
            return False
        self.points.append(hou.Vector3(pos))
        self.selected_indices.clear()
        self._sync_drawables()
        self._request_draw()
        return True

    def _handle_edit_start(self, ui_event):
        if not self.points:
            return False
        idx = self._pick_nearest_point_index(ui_event, self.pick_radius_px)
        edge_idx = None
        if idx is None:
            edge_idx = self._pick_nearest_edge_index(ui_event, self.pick_radius_px)

        if idx is None and edge_idx is None:
            self.selected_indices.clear()
            self.selected_edges.clear()
            self._sync_drawables()
            self._request_draw()
            return False

        dev = ui_event.device()
        if idx is not None and dev.isShiftKey():
            if idx in self.selected_indices:
                self.selected_indices.discard(idx)
            else:
                self.selected_indices.add(idx)
            self._sync_edges_from_points()
            self._sync_drawables()
            self._request_draw()
            return True
        if edge_idx is not None and dev.isShiftKey():
            if edge_idx in self.selected_edges:
                self.selected_edges.discard(edge_idx)
                self.selected_indices.discard(edge_idx)
                self.selected_indices.discard(edge_idx + 1)
            else:
                self.selected_edges.add(edge_idx)
                self.selected_indices.add(edge_idx)
                self.selected_indices.add(edge_idx + 1)
            self._sync_drawables()
            self._request_draw()
            return True

        if idx is not None:
            self.selected_indices = {idx}
            self.selected_edges.clear()
            pivot = self.points[idx]
        else:
            self.selected_edges = {edge_idx}
            self.selected_indices = {edge_idx, edge_idx + 1}
            pivot = self.points[edge_idx]
        start_world = self._pick_world_pos(ui_event, plane_orig=pivot)
        if start_world is None:
            self._sync_drawables()
            self._request_draw()
            return True

        self.drag_active = True
        self.drag_plane_origin = hou.Vector3(pivot)
        self.drag_start_world = hou.Vector3(start_world)
        self.drag_start_positions = {
            i: hou.Vector3(self.points[i]) for i in self.selected_indices
        }
        self._sync_drawables()
        self._request_draw()
        return True

    def _handle_active(self, ui_event):
        if not self.drag_active or not self.selected_indices:
            return False

        cur = self._pick_world_pos(ui_event, plane_orig=self.drag_plane_origin)
        if cur is None or self.drag_start_world is None:
            return False

        delta = hou.Vector3(cur) - hou.Vector3(self.drag_start_world)
        for i in self.selected_indices:
            base = self.drag_start_positions.get(i)
            if base is None:
                continue
            self.points[i] = hou.Vector3(base + delta)
        self._sync_drawables()
        self._request_draw()
        return True

    def _pick_world_pos(self, ui_event, plane_orig=None):
        try:
            rpos, rdir = ui_event.ray()
        except Exception:
            return None
        try:
            pos = self.picker.intersect(
                self.scene_viewer,
                rpos,
                rdir,
                ui_event=ui_event,
                plane_orig=plane_orig,
            )
            return hou.Vector3(pos) if pos is not None else None
        except Exception:
            return None

    def _pick_nearest_point_index(self, ui_event, px_radius):
        vp = self.scene_viewer.curViewport()
        if vp is None or not self.points:
            return None

        mx = float(ui_event.device().mouseX())
        my = float(ui_event.device().mouseY())
        best_idx = None
        best_d2 = float(px_radius * px_radius)

        for i, p in enumerate(self.points):
            try:
                sx, sy = vp.mapToScreen(p)
            except Exception:
                continue
            dx = float(sx) - mx
            dy = float(sy) - my
            d2 = dx * dx + dy * dy
            if d2 <= best_d2:
                best_d2 = d2
                best_idx = i
        return best_idx

    def _delete_selected(self):
        if not self.selected_indices:
            return
        kept = []
        for i, p in enumerate(self.points):
            if i not in self.selected_indices:
                kept.append(p)
        self.points = kept
        self.selected_indices.clear()
        self.selected_edges.clear()
        self.drag_active = False
        self.drag_start_positions = {}

    def _sync_drawables(self):
        edge_geo = hou.Geometry()
        if len(self.points) >= 2:
            poly = edge_geo.createPolygon()
            poly.setIsClosed(False)
            for p in self.points:
                pt = edge_geo.createPoint()
                pt.setPosition(p)
                poly.addVertex(pt)
        self.edges_drawable.setGeometry(edge_geo.freeze())
        self.edges_drawable.show(len(self.points) >= 2)

        all_geo = hou.Geometry()
        for p in self.points:
            pt = all_geo.createPoint()
            pt.setPosition(p)
        self.points_drawable.setGeometry(all_geo.freeze())
        self.points_drawable.show(bool(self.points))

        sel_geo = hou.Geometry()
        for i in sorted(self.selected_indices):
            if i < 0 or i >= len(self.points):
                continue
            pt = sel_geo.createPoint()
            pt.setPosition(self.points[i])
        self.selected_drawable.setGeometry(sel_geo.freeze())
        self.selected_drawable.show(bool(self.selected_indices))

        sel_edge_geo = hou.Geometry()
        for edge_idx in sorted(self.selected_edges):
            if edge_idx < 0 or (edge_idx + 1) >= len(self.points):
                continue
            poly = sel_edge_geo.createPolygon()
            poly.setIsClosed(False)
            a = sel_edge_geo.createPoint()
            a.setPosition(self.points[edge_idx])
            b = sel_edge_geo.createPoint()
            b.setPosition(self.points[edge_idx + 1])
            poly.addVertex(a)
            poly.addVertex(b)
        self.selected_edges_drawable.setGeometry(sel_edge_geo.freeze())
        self.selected_edges_drawable.show(bool(self.selected_edges))

    def _set_prompt(self):
        try:
            if self.mode == "draw":
                self.scene_viewer.setPromptMessage(
                    "Draw: LMB add point | Enter edit | Delete remove last"
                )
            else:
                self.scene_viewer.setPromptMessage(
                    "Edit: LMB point/edge select+drag | Shift+LMB toggle | D draw | Delete remove selected"
                )
        except Exception:
            pass

    def _sync_edges_from_points(self):
        if len(self.selected_indices) < 2:
            self.selected_edges.clear()
            return
        edges = set()
        for i in range(len(self.points) - 1):
            if i in self.selected_indices and (i + 1) in self.selected_indices:
                edges.add(i)
        self.selected_edges = edges

    def _pick_nearest_edge_index(self, ui_event, px_radius):
        vp = self.scene_viewer.curViewport()
        if vp is None or len(self.points) < 2:
            return None

        mx = float(ui_event.device().mouseX())
        my = float(ui_event.device().mouseY())
        best_idx = None
        best_d2 = float(px_radius * px_radius)

        for i in range(len(self.points) - 1):
            a = self.points[i]
            b = self.points[i + 1]
            try:
                ax, ay = vp.mapToScreen(a)
                bx, by = vp.mapToScreen(b)
            except Exception:
                continue
            d2 = self._point_to_segment_d2(mx, my, float(ax), float(ay), float(bx), float(by))
            if d2 <= best_d2:
                best_d2 = d2
                best_idx = i
        return best_idx

    @staticmethod
    def _point_to_segment_d2(px, py, ax, ay, bx, by):
        abx = bx - ax
        aby = by - ay
        apx = px - ax
        apy = py - ay
        ab2 = abx * abx + aby * aby
        if ab2 <= 1e-12:
            dx = px - ax
            dy = py - ay
            return dx * dx + dy * dy
        t = (apx * abx + apy * aby) / ab2
        if t < 0.0:
            t = 0.0
        elif t > 1.0:
            t = 1.0
        cx = ax + t * abx
        cy = ay + t * aby
        dx = px - cx
        dy = py - cy
        return dx * dx + dy * dy

    def _request_draw(self):
        try:
            self.scene_viewer.curViewport().draw()
        except Exception:
            pass


def createViewerStateTemplate():
    state_typename = "curveutils_basic_state"
    state_label = "curveutils_basic_state"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon("$SK_ICONS/devtools.svg")
    return template
