import hou
import curveutils as cu
import viewerstate.utils as su

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
        self.stash_node = None
        self.input_node = None
        self.picker = cu.curve3DPicker(cu.curve3DPicker.MODE_VIEWPLANE)

        self.mode = "draw"
        self.select_mode = "face"
        self.edit_geo = None
        self.points = []
        self.edges = []
        self.faces = {}
        self.model_to_ptnum = []
        self.ptnum_to_model_idx = {}
        self.edge_pair_to_index = {}
        self.selected_indices = set()
        self.selected_edges = set()
        self.selected_faces = set()

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
        self.selected_faces_drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Face,
            "curveutils_basic_faces_selected",
        )
        self.selected_faces_drawable.setParams({"color1": hou.Vector4(1.0, 0.45, 0.1, 0.28)})
        self.selected_faces_drawable.show(False)
        self.hover_edge_drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Line,
            "curveutils_basic_edges_hover",
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
            "curveutils_basic_faces_hover",
        )
        self.hover_face_drawable.setParams({"color1": hou.Vector4(0.25, 0.7, 1.0, 0.22)})
        self.hover_face_drawable.show(False)

        self.hover_edge_index = None
        self.hover_face_primnum = None

        self.point_gadget = None
        self.edge_gadget = None
        self.face_gadget = None

    def onEnter(self, kwargs):
        self.node = kwargs.get("node")
        self.picker.reset()
        self.picker.setPickMode(cu.curve3DPicker.MODE_VIEWPLANE)
        self._load_points_from_node_geometry()
        self._init_gadgets()
        self._set_prompt()
        self._sync_drawables()
        self._request_draw()

    def onExit(self, kwargs):
        self.points_drawable.show(False)
        self.edges_drawable.show(False)
        self.selected_drawable.show(False)
        self.selected_edges_drawable.show(False)
        self.selected_faces_drawable.show(False)
        self.hover_edge_drawable.show(False)
        self.hover_face_drawable.show(False)
        self.drag_active = False

    def onDraw(self, kwargs):
        draw_handle = kwargs["draw_handle"]
        self.edges_drawable.draw(draw_handle)
        self.hover_edge_drawable.draw(draw_handle)
        self.selected_edges_drawable.draw(draw_handle)
        self.hover_face_drawable.draw(draw_handle)
        self.selected_faces_drawable.draw(draw_handle)
        self.points_drawable.draw(draw_handle)
        self.selected_drawable.draw(draw_handle)
    def onMenuAction(self, kwargs):
        item = kwargs.get("menu_item")

        if item == "mode_draw":
            self.mode = "draw"
            self.drag_active = False
            self._clear_hover()
            self._set_prompt()
            self._request_draw()
            return True

        if item == "mode_edit":
            self.mode = "edit"
            self._clear_hover()
            self._set_prompt()
            self._request_draw()
            return True

        if item == "select_point":
            self.select_mode = "point"
            self._update_gadget_visibility()
            self._clear_hover()
            self._set_prompt()
            self._request_draw()
            return True

        if item == "select_edge":
            self.select_mode = "edge"
            self._update_gadget_visibility()
            self._clear_hover()
            self._set_prompt()
            self._request_draw()
            return True

        if item == "select_face":
            self.select_mode = "face"
            self._update_gadget_visibility()
            self._clear_hover()
            self._set_prompt()
            self._request_draw()
            return True

        if item == "reset_input":
            self._reset_from_input_geo()
            self._sync_drawables()
            self._set_prompt()
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
            # Always reset any stale drag state at click start.
            self.drag_active = False
            self.drag_start_positions = {}
            self._clear_hover()
            if self.mode == "draw":
                return self._handle_draw_start(ui)
            return self._handle_edit_start(ui)

        if reason == hou.uiEventReason.Located and (not self.drag_active):
            if self.mode == "edit":
                self._update_hover(ui)
                return True
            self._clear_hover()
            return False

        if reason in (hou.uiEventReason.Active, hou.uiEventReason.Located) and self.drag_active:
            return self._handle_active(ui)

        if reason == hou.uiEventReason.Changed and self.drag_active:
            self._handle_active(ui)
            self.drag_active = False
            self.drag_start_positions = {}
            self._write_points_to_edit_geo(push=True)
            return True

        return False

    def _handle_draw_start(self, ui_event):
        pos = self._pick_world_pos(ui_event, plane_orig=None)
        if pos is None:
            return False
        prev = len(self.points) - 1
        self.points.append(hou.Vector3(pos))
        self.model_to_ptnum.append(-1)
        cur = len(self.points) - 1
        if prev >= 0:
            self.edges.append((prev, cur))
            self._rebuild_edge_index_map()
        self.selected_indices.clear()
        self.selected_edges.clear()
        self.selected_faces.clear()
        self._append_point_to_edit_geo(pos, push=True)
        self._sync_drawables()
        self._request_draw()
        return True

    def _handle_edit_start(self, ui_event):
        if not self.points:
            return False
        pick_type, pick_value = self._pick_from_gadget()

        idx = None
        edge_idx = None
        face_primnum = None
        if self.select_mode == "face":
            # In face mode, prefer exact ray pick at click time.
            face_primnum = self._pick_face_by_ray(ui_event)
            if face_primnum is None and pick_type == "face":
                face_primnum = pick_value
        elif self.select_mode == "point":
            if pick_type == "point":
                idx = pick_value
            else:
                idx = self._pick_nearest_point_index(ui_event, self.pick_radius_px)
        else:  # edge mode
            if pick_type == "edge":
                edge_idx = pick_value
            else:
                edge_idx = self._pick_nearest_edge_index(ui_event, self.pick_radius_px)

        if idx is None and edge_idx is None and face_primnum is None:
            self.selected_indices.clear()
            self.selected_edges.clear()
            self.selected_faces.clear()
            self._sync_drawables()
            self._request_draw()
            # Consume in edit mode to prevent stale gadget interaction fallback.
            return True

        dev = ui_event.device()
        if face_primnum is not None and dev.isShiftKey():
            if face_primnum in self.selected_faces:
                self.selected_faces.discard(face_primnum)
            else:
                self.selected_faces.add(face_primnum)
            self._sync_selection_from_faces()
            self._sync_drawables()
            self._request_draw()
            return True

        if idx is not None and dev.isShiftKey():
            self.selected_faces.clear()
            if idx in self.selected_indices:
                self.selected_indices.discard(idx)
            else:
                self.selected_indices.add(idx)
            self._sync_edges_from_points()
            self._sync_drawables()
            self._request_draw()
            return True
        if edge_idx is not None and dev.isShiftKey():
            self.selected_faces.clear()
            if edge_idx in self.selected_edges:
                self.selected_edges.discard(edge_idx)
                if 0 <= edge_idx < len(self.edges):
                    a, b = self.edges[edge_idx]
                    self.selected_indices.discard(a)
                    self.selected_indices.discard(b)
            else:
                self.selected_edges.add(edge_idx)
                if 0 <= edge_idx < len(self.edges):
                    a, b = self.edges[edge_idx]
                    self.selected_indices.add(a)
                    self.selected_indices.add(b)
            self._sync_drawables()
            self._request_draw()
            return True

        if face_primnum is not None:
            self.selected_faces = {int(face_primnum)}
            self._sync_selection_from_faces()
            pivot = self._face_center(int(face_primnum))
        elif idx is not None:
            self.selected_indices = {idx}
            self.selected_edges.clear()
            self.selected_faces.clear()
            pivot = self.points[idx]
        else:
            self.selected_edges = {edge_idx}
            a, b = self.edges[edge_idx]
            self.selected_indices = {a, b}
            self.selected_faces.clear()
            pivot = self.points[a]
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
        self._write_points_to_edit_geo(push=False)
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
        if self.edit_geo is not None:
            if self.selected_faces:
                prims = []
                for primnum in sorted(self.selected_faces):
                    prim = self.edit_geo.prim(int(primnum))
                    if prim is not None:
                        prims.append(prim)
                if prims:
                    try:
                        self.edit_geo.deletePrims(prims, keep_points=False)
                    except TypeError:
                        self.edit_geo.deletePrims(prims)
                    except Exception:
                        pass
                    self._push_edit_geo_to_stash()
                    self._rebuild_model_from_edit_geo()
                    return

            if not self.selected_indices:
                return
            to_delete = []
            for idx in sorted(self.selected_indices):
                if idx < 0 or idx >= len(self.model_to_ptnum):
                    continue
                ptnum = self.model_to_ptnum[idx]
                if ptnum < 0:
                    continue
                pt = self.edit_geo.point(int(ptnum))
                if pt is not None:
                    to_delete.append(pt)
            if to_delete:
                try:
                    self.edit_geo.deletePoints(to_delete)
                except Exception:
                    pass
                self._push_edit_geo_to_stash()
                self._rebuild_model_from_edit_geo()
                return

        remap = {}
        kept = []
        for old_i, p in enumerate(self.points):
            if old_i in self.selected_indices:
                continue
            remap[old_i] = len(kept)
            kept.append(p)
        new_edges = []
        for a, b in self.edges:
            if a in self.selected_indices or b in self.selected_indices:
                continue
            if a not in remap or b not in remap:
                continue
            new_edges.append((remap[a], remap[b]))
        self.points = kept
        self.edges = new_edges
        self._rebuild_edge_index_map()
        self.selected_indices.clear()
        self.selected_edges.clear()
        self.selected_faces.clear()
        self.drag_active = False
        self.drag_start_positions = {}

    def _sync_drawables(self):
        self._refresh_gadgets_geometry()

        edge_geo = hou.Geometry()
        for a, b in self.edges:
            if a < 0 or b < 0 or a >= len(self.points) or b >= len(self.points):
                continue
            poly = edge_geo.createPolygon()
            poly.setIsClosed(False)
            pta = edge_geo.createPoint()
            pta.setPosition(self.points[a])
            ptb = edge_geo.createPoint()
            ptb.setPosition(self.points[b])
            poly.addVertex(pta)
            poly.addVertex(ptb)
        self.edges_drawable.setGeometry(edge_geo.freeze())
        show_edges = bool(self.edges) and (self.mode == "draw" or self.select_mode == "edge")
        self.edges_drawable.show(show_edges)

        all_geo = hou.Geometry()
        for p in self.points:
            pt = all_geo.createPoint()
            pt.setPosition(p)
        self.points_drawable.setGeometry(all_geo.freeze())
        show_points = bool(self.points) and (self.mode == "draw" or self.select_mode == "point")
        self.points_drawable.show(show_points)

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
            if edge_idx < 0 or edge_idx >= len(self.edges):
                continue
            a_idx, b_idx = self.edges[edge_idx]
            if (
                a_idx < 0
                or b_idx < 0
                or a_idx >= len(self.points)
                or b_idx >= len(self.points)
            ):
                continue
            poly = sel_edge_geo.createPolygon()
            poly.setIsClosed(False)
            a = sel_edge_geo.createPoint()
            a.setPosition(self.points[a_idx])
            b = sel_edge_geo.createPoint()
            b.setPosition(self.points[b_idx])
            poly.addVertex(a)
            poly.addVertex(b)
        self.selected_edges_drawable.setGeometry(sel_edge_geo.freeze())
        self.selected_edges_drawable.show(bool(self.selected_edges))

        sel_face_geo = hou.Geometry()
        for primnum in sorted(self.selected_faces):
            idxs = self.faces.get(int(primnum))
            if not idxs or len(idxs) < 3:
                continue
            poly = sel_face_geo.createPolygon()
            poly.setIsClosed(True)
            for idx in idxs:
                if idx < 0 or idx >= len(self.points):
                    continue
                pt = sel_face_geo.createPoint()
                pt.setPosition(self.points[idx])
                poly.addVertex(pt)
        self.selected_faces_drawable.setGeometry(sel_face_geo.freeze())
        self.selected_faces_drawable.show(bool(self.selected_faces))

        self._sync_hover_drawables()

    def _set_prompt(self):
        try:
            mode_hint = "Pick: 1 point / 2 edge / 3 face (current: {0})".format(self.select_mode)
            if self.mode == "draw":
                self.scene_viewer.setPromptMessage(
                    "Draw: LMB add point | Enter edit | I reset from INPUT | Delete remove last | " + mode_hint
                )
            else:
                self.scene_viewer.setPromptMessage(
                    "Edit: LMB select+drag | Shift+LMB toggle | I reset INPUT | D draw | Delete remove selected | " + mode_hint
                )
        except Exception:
            pass

    def _sync_edges_from_points(self):
        edges = set()
        for i, (a, b) in enumerate(self.edges):
            if a in self.selected_indices and b in self.selected_indices:
                edges.add(i)
        self.selected_edges = edges

    def _sync_selection_from_faces(self):
        pts = set()
        for primnum in self.selected_faces:
            for idx in self.faces.get(int(primnum), []):
                pts.add(int(idx))
        self.selected_indices = pts
        self._sync_edges_from_points()

    def _face_center(self, primnum):
        idxs = self.faces.get(int(primnum), [])
        if not idxs:
            return hou.Vector3(0.0, 0.0, 0.0)
        acc = hou.Vector3(0.0, 0.0, 0.0)
        n = 0
        for idx in idxs:
            if 0 <= idx < len(self.points):
                acc += self.points[idx]
                n += 1
        return acc * (1.0 / float(n)) if n > 0 else hou.Vector3(0.0, 0.0, 0.0)

    def _pick_from_gadget(self):
        sc = getattr(self, "state_context", None)
        if sc is None:
            return None, None
        try:
            gadget = sc.gadget()
        except Exception:
            return None, None

        if self.select_mode == "point" and gadget == "point_gadget":
            try:
                ptnum = int(sc.component1())
            except Exception:
                return None, None
            return "point", self.ptnum_to_model_idx.get(ptnum)

        if self.select_mode == "edge" and gadget == "edge_gadget":
            try:
                p0 = int(sc.component1())
                p1 = int(sc.component2())
            except Exception:
                return None, None
            a = self.ptnum_to_model_idx.get(p0)
            b = self.ptnum_to_model_idx.get(p1)
            if a is None or b is None:
                return None, None
            edge_idx = self.edge_pair_to_index.get(tuple(sorted((int(a), int(b)))))
            return ("edge", edge_idx) if edge_idx is not None else (None, None)

        if self.select_mode == "face" and gadget == "face_gadget":
            try:
                primnum = int(sc.component1())
            except Exception:
                return None, None
            if primnum in self.faces:
                return "face", primnum
            # Try to lazily map face from current edit_geo.
            if self._ensure_face_mapping_for_prim(primnum):
                return "face", primnum
            return None, None

        return None, None

    def _pick_face_by_ray(self, ui_event):
        if self.edit_geo is None:
            return None
        try:
            rpos, rdir = ui_event.ray()
        except Exception:
            return None
        pos = hou.Vector3()
        nml = hou.Vector3()
        uvw = hou.Vector3()
        try:
            primnum = int(self.edit_geo.intersect(rpos, rdir, pos, nml, uvw))
        except Exception:
            return None
        if primnum < 0:
            return None
        if primnum not in self.faces and not self._ensure_face_mapping_for_prim(primnum):
            return None
        return primnum

    def _ensure_face_mapping_for_prim(self, primnum):
        if self.edit_geo is None:
            return False
        prim = self.edit_geo.prim(int(primnum))
        if prim is None:
            return False
        try:
            verts = prim.vertices()
        except Exception:
            return False
        if not verts or len(verts) < 3:
            return False
        idxs = []
        for v in verts:
            try:
                ptnum = int(v.point().number())
            except Exception:
                continue
            idx = self.ptnum_to_model_idx.get(ptnum)
            if idx is None:
                continue
            idxs.append(int(idx))
        if len(idxs) < 3:
            return False
        self.faces[int(primnum)] = idxs
        return True

    def _pick_nearest_edge_index(self, ui_event, px_radius):
        vp = self.scene_viewer.curViewport()
        if vp is None or not self.edges:
            return None

        mx = float(ui_event.device().mouseX())
        my = float(ui_event.device().mouseY())
        best_idx = None
        best_d2 = float(px_radius * px_radius)

        for i, (a_idx, b_idx) in enumerate(self.edges):
            if (
                a_idx < 0
                or b_idx < 0
                or a_idx >= len(self.points)
                or b_idx >= len(self.points)
            ):
                continue
            a = self.points[a_idx]
            b = self.points[b_idx]
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

    def _update_hover(self, ui_event):
        hover_edge = None
        hover_face = None

        if self.select_mode == "edge":
            ptype, pval = self._pick_from_gadget()
            if ptype == "edge":
                hover_edge = pval
            else:
                hover_edge = self._pick_nearest_edge_index(ui_event, self.pick_radius_px)
        elif self.select_mode == "face":
            hover_face = self._pick_face_by_ray(ui_event)

        changed = (hover_edge != self.hover_edge_index) or (hover_face != self.hover_face_primnum)
        self.hover_edge_index = hover_edge
        self.hover_face_primnum = hover_face
        if changed:
            self._sync_hover_drawables()
            self._request_draw()

    def _clear_hover(self):
        self.hover_edge_index = None
        self.hover_face_primnum = None
        self.hover_edge_drawable.show(False)
        self.hover_face_drawable.show(False)

    def _sync_hover_drawables(self):
        he_geo = hou.Geometry()
        if self.hover_edge_index is not None:
            i = int(self.hover_edge_index)
            if 0 <= i < len(self.edges):
                a, b = self.edges[i]
                if 0 <= a < len(self.points) and 0 <= b < len(self.points):
                    poly = he_geo.createPolygon()
                    poly.setIsClosed(False)
                    pta = he_geo.createPoint()
                    pta.setPosition(self.points[a])
                    ptb = he_geo.createPoint()
                    ptb.setPosition(self.points[b])
                    poly.addVertex(pta)
                    poly.addVertex(ptb)
        self.hover_edge_drawable.setGeometry(he_geo.freeze())
        self.hover_edge_drawable.show(self.select_mode == "edge" and self.hover_edge_index is not None)

        hf_geo = hou.Geometry()
        if self.hover_face_primnum is not None:
            idxs = self.faces.get(int(self.hover_face_primnum))
            if idxs and len(idxs) >= 3:
                poly = hf_geo.createPolygon()
                poly.setIsClosed(True)
                for idx in idxs:
                    if 0 <= idx < len(self.points):
                        pt = hf_geo.createPoint()
                        pt.setPosition(self.points[idx])
                        poly.addVertex(pt)
        self.hover_face_drawable.setGeometry(hf_geo.freeze())
        self.hover_face_drawable.show(self.select_mode == "face" and self.hover_face_primnum is not None)

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

    def _load_points_from_node_geometry(self):
        self.points = []
        self.edges = []
        self.faces = {}
        self.model_to_ptnum = []
        self.ptnum_to_model_idx = {}
        self.edge_pair_to_index = {}
        self.selected_indices.clear()
        self.selected_edges.clear()
        self.selected_faces.clear()
        self.drag_active = False
        self.drag_start_positions = {}

        if self.node is None:
            return

        self.stash_node = self.node.node("stash1")
        self.input_node = self.node.node("INPUT")
        geo = self._ensure_edit_geo()
        if geo is None:
            return

        self._rebuild_model_from_edit_geo()

    def _ensure_edit_geo(self):
        src = None
        if self.stash_node is not None:
            try:
                self.stash_node.cook(force=True)
                g = self.stash_node.geometry()
                if self._geo_has_data(g):
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
            self.edit_geo = None
            return None

        g = hou.Geometry()
        g.merge(src)
        self.edit_geo = g

        if self.stash_node is not None and not self._stash_has_geo():
            self._push_edit_geo_to_stash()
        return self.edit_geo

    def _reset_from_input_geo(self):
        src = None
        if self.input_node is not None:
            try:
                src = self.input_node.geometry()
            except Exception:
                src = None
        if src is None and self.node is not None:
            try:
                src = self.node.geometry()
            except Exception:
                src = None
        if src is None:
            return
        g = hou.Geometry()
        g.merge(src)
        self.edit_geo = g
        self._push_edit_geo_to_stash()
        self._rebuild_model_from_edit_geo()

    def _rebuild_model_from_edit_geo(self):
        self.points = []
        self.edges = []
        self.faces = {}
        self.model_to_ptnum = []
        self.ptnum_to_model_idx = {}
        self.edge_pair_to_index = {}
        self.selected_indices.clear()
        self.selected_edges.clear()
        self.selected_faces.clear()

        if self.edit_geo is None:
            return

        try:
            pts = self.edit_geo.points()
        except Exception:
            pts = []
        if not pts:
            return

        try:
            pts_sorted = sorted(pts, key=lambda p: p.number())
        except Exception:
            pts_sorted = pts
        ptnum_to_idx = {}
        for i, pt in enumerate(pts_sorted):
            self.points.append(hou.Vector3(pt.position()))
            ptnum = int(pt.number())
            self.model_to_ptnum.append(ptnum)
            ptnum_to_idx[ptnum] = i
            self.ptnum_to_model_idx[ptnum] = i

        # Build unique edges from primitive vertex adjacency.
        edge_set = set()
        try:
            prims = self.edit_geo.prims()
        except Exception:
            prims = []
        for prim in prims:
            try:
                verts = prim.vertices()
            except Exception:
                continue
            if not verts or len(verts) < 2:
                continue
            idxs = []
            for v in verts:
                try:
                    ptn = int(v.point().number())
                except Exception:
                    ptn = None
                if ptn is None or ptn not in ptnum_to_idx:
                    continue
                idxs.append(ptnum_to_idx[ptn])
            try:
                primnum = int(prim.number())
            except Exception:
                primnum = -1
            if primnum >= 0 and len(idxs) >= 3:
                self.faces[primnum] = list(idxs)
            if len(idxs) < 2:
                continue
            for i in range(len(idxs) - 1):
                a = idxs[i]
                b = idxs[i + 1]
                if a == b:
                    continue
                edge_set.add(tuple(sorted((a, b))))
            try:
                is_closed = bool(prim.isClosed())
            except Exception:
                is_closed = False
            if is_closed and len(idxs) > 2:
                a = idxs[-1]
                b = idxs[0]
                if a != b:
                    edge_set.add(tuple(sorted((a, b))))

        self.edges = sorted(edge_set)
        self._rebuild_edge_index_map()

    def _rebuild_edge_index_map(self):
        self.edge_pair_to_index = {}
        for i, (a, b) in enumerate(self.edges):
            self.edge_pair_to_index[tuple(sorted((int(a), int(b))))] = int(i)

    def _write_points_to_edit_geo(self, push=False):
        if self.edit_geo is None:
            return
        for idx, pos in enumerate(self.points):
            if idx < 0 or idx >= len(self.model_to_ptnum):
                continue
            ptnum = self.model_to_ptnum[idx]
            if ptnum < 0:
                continue
            pt = self.edit_geo.point(int(ptnum))
            if pt is None:
                continue
            try:
                pt.setPosition(pos)
            except Exception:
                pass
        if push:
            self._push_edit_geo_to_stash()

    def _append_point_to_edit_geo(self, pos, push=False):
        if self.edit_geo is None:
            return
        try:
            pt = self.edit_geo.createPoint()
            pt.setPosition(pos)
            ptnum = int(pt.number())
            if self.model_to_ptnum:
                self.model_to_ptnum[-1] = ptnum
        except Exception:
            pass
        if push:
            self._push_edit_geo_to_stash()

    def _push_edit_geo_to_stash(self):
        if self.stash_node is None or self.edit_geo is None:
            return
        try:
            # Push a fresh geometry snapshot each time to avoid stale-object issues.
            snap = hou.Geometry()
            snap.merge(self.edit_geo)
            self.stash_node.parm("stash").set(snap)
            self.stash_node.cook(force=True)
            if self.node is not None:
                self.node.cook(force=True)
        except Exception:
            pass

    def _stash_has_geo(self):
        if self.stash_node is None:
            return False
        try:
            self.stash_node.cook(force=True)
            g = self.stash_node.geometry()
            return self._geo_has_data(g)
        except Exception:
            return False

    @staticmethod
    def _geo_has_data(geo):
        if geo is None:
            return False
        try:
            return (int(geo.intrinsicValue("pointcount")) > 0) or (
                int(geo.intrinsicValue("primitivecount")) > 0
            )
        except Exception:
            return False

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
            self.point_gadget.setParams({"draw_color": [1, 1, 1, 0.0], "radius": 7.0})
            self.edge_gadget.setParams({"draw_color": [1, 1, 1, 0.0]})
            self.face_gadget.setParams({"draw_color": [1, 1, 1, 0.0]})
        except Exception:
            pass
        self._update_gadget_visibility()
        self._refresh_gadgets_geometry()

    def _refresh_gadgets_geometry(self):
        if self.edit_geo is None:
            return
        try:
            if self.point_gadget is not None:
                self.point_gadget.setGeometry(self.edit_geo)
            if self.edge_gadget is not None:
                self.edge_gadget.setGeometry(self.edit_geo)
            if self.face_gadget is not None:
                self.face_gadget.setGeometry(self.edit_geo)
        except Exception:
            pass

    def _update_gadget_visibility(self):
        try:
            if self.point_gadget is not None:
                self.point_gadget.show(self.select_mode == "point")
            if self.edge_gadget is not None:
                self.edge_gadget.show(self.select_mode == "edge")
            if self.face_gadget is not None:
                self.face_gadget.show(self.select_mode == "face")
        except Exception:
            pass


def createViewerStateTemplate():
    state_typename = "curveutils_basic_state"
    state_label = "curveutils_basic_state"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindGadget(hou.drawableGeometryType.Point, "point_gadget", label="Point")
    template.bindGadget(hou.drawableGeometryType.Line, "edge_gadget", label="Edge")
    template.bindGadget(hou.drawableGeometryType.Face, "face_gadget", label="Face")

    hotkey_definitions = hou.PluginHotkeyDefinitions()
    menu = hou.ViewerStateMenu(state_typename + "_menu", state_label)
    menu.addActionItem(
        "mode_draw",
        "Mode: Draw",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "mode_draw", "d"),
    )
    menu.addActionItem(
        "mode_edit",
        "Mode: Edit",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "mode_edit", "m"),
    )
    menu.addSeparator()
    menu.addActionItem(
        "select_point",
        "Select: Point",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "select_point", "&"),
    )
    menu.addActionItem(
        "select_edge",
        "Select: Edge",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "select_edge", "é"),
    )
    menu.addActionItem(
        "select_face",
        "Select: Face",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "select_face", "\""),
    )
    menu.addSeparator()
    menu.addActionItem("reset_input", "Reset From INPUT")

    template.bindMenu(menu)
    template.bindHotkeyDefinitions(hotkey_definitions)
    template.bindIcon("$SK_ICONS/devtools.svg")
    return template
