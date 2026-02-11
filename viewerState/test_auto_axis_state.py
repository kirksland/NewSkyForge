import hou
import viewerstate.utils as su
import resourceutils as ru


class State(object):
    HUD_TEMPLATE = {
        "title": "AutoAxisTest", "desc": "tool", "icon": "SOP_edit",
        "rows": [
            {"id": "mode", "label": "Mode", "key": "M", "value": "LOCAL"},
            {"id": "mode_g", "type": "choicegraph", "count": 3},

            {"id": "selectmode", "label": "Select Mode", "key": "F", "value": "POINT"},
            {"id": "selectmode_g", "type": "choicegraph", "count": 3},
        ]
    }

    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self.dragger = hou.ViewerStateDragger("dragger")

        self._src_geo = None
        self._edit_geo = None

        # SINGLE MODE: LOCAL / WORLD / EDGE
        self.mode = "LOCAL"
        self._drag_mode_used = None

        # selection mode
        self.select_mode = "POINT"       # "POINT" / "EDGE" / "FACE"
        self._drag_select_used = None

        self._is_dragging = False
        self._pending = False

        # current selection
        self._ptnum = -1
        self._primnum = -1
        self._affected_ptnums = None     # list[int]

        self._edge_p0 = -1
        self._edge_p1 = -1

        self._origin = None
        self._start_mouse = None

        self._choice = None
        self._sign = 1.0
        self._drag_axis = None

        self._undo_opened = False

        self.node = None
        self.stash = None

        self.color_options = ru.ColorOptions(self.scene_viewer)

        # --- guide line drawable ---
        self.guide_len = 0.3
        self.guide_line_geo = None
        self.guide_line_pts = None
        self.guide_line_prim = None
        self.guide_line_drawable = None

        # --- edge hover drawable (single highlighted edge) ---
        self.edge_hover_geo = None
        self.edge_hover_pts = None
        self.edge_hover_prim = None
        self.edge_hover_drawable = None

        # --- callback guard ---
        self._cb_registered = False

        # --- stash sync signature (for undo/redo, external recook, etc.) ---
        self._stash_sig = None

    # -------------------------------------------------------------------------
    # HUD
    # -------------------------------------------------------------------------

    def _cycle_mode(self):
        order = ["LOCAL", "WORLD", "EDGE"]
        try:
            i = order.index(self.mode)
        except ValueError:
            i = 0
        self.mode = order[(i + 1) % len(order)]

    def _cycle_select_mode(self):
        order = ["POINT", "EDGE", "FACE"]
        try:
            i = order.index(self.select_mode)
        except ValueError:
            i = 0
        self.select_mode = order[(i + 1) % len(order)]

    def _hud_update(self):
        try:
            mode_order = ["LOCAL", "WORLD", "EDGE"]
            mode_idx = mode_order.index(self.mode) if self.mode in mode_order else 0

            sel_order = ["POINT", "EDGE", "FACE"]
            sel_idx = sel_order.index(self.select_mode) if self.select_mode in sel_order else 0

            updates = {
                "mode": self.mode,
                "mode_g": mode_idx,
                "selectmode": self.select_mode,
                "selectmode_g": sel_idx,
            }
            try:
                self.scene_viewer.hudInfo(hud_values=updates)
            except TypeError:
                self.scene_viewer.hudInfo(values=updates)
        except:
            pass

    # -------------------------------------------------------------------------
    # Edge hover highlight (single edge)
    # -------------------------------------------------------------------------

    def _init_edge_hover(self):
        self.edge_hover_geo = hou.Geometry()
        self.edge_hover_pts = [self.edge_hover_geo.createPoint(), self.edge_hover_geo.createPoint()]

        self.edge_hover_prim = self.edge_hover_geo.createPolygon()
        self.edge_hover_prim.setIsClosed(False)
        self.edge_hover_prim.addVertex(self.edge_hover_pts[0])
        self.edge_hover_prim.addVertex(self.edge_hover_pts[1])

        self.edge_hover_drawable = hou.GeometryDrawable(
            self.scene_viewer, hou.drawableGeometryType.Line, "auto_axis_edge_hover"
        )
        self.edge_hover_drawable.setGeometry(self.edge_hover_geo)
        self.edge_hover_drawable.setParams({
            "color1": self.color_options.colorFromName("PickedHandleColor"),
            "line_width": 3.0
        })
        self.edge_hover_drawable.show(False)

    def _update_edge_hover_from_points(self, p0, p1):
        if self.edge_hover_drawable is None or self._edit_geo is None:
            return

        pt0 = self._edit_geo.point(p0)
        pt1 = self._edit_geo.point(p1)
        if pt0 is None or pt1 is None:
            self.edge_hover_drawable.show(False)
            return

        self.edge_hover_pts[0].setPosition(pt0.position())
        self.edge_hover_pts[1].setPosition(pt1.position())

        P = self.edge_hover_geo.findPointAttrib("P")
        if P is not None:
            P.incrementDataId()
        self.edge_hover_geo.incrementModificationCounter()

        self.edge_hover_drawable.show(True)

    def _hide_edge_hover(self):
        if self.edge_hover_drawable is not None:
            self.edge_hover_drawable.show(False)

    # -------------------------------------------------------------------------
    # Selection / affected points
    # -------------------------------------------------------------------------

    def _prim_points_unique(self, prim):
        if prim is None:
            return []
        seen = set()
        out = []
        for p in prim.points():
            n = p.number()
            if n in seen:
                continue
            seen.add(n)
            out.append(n)
        return out

    def _prim_center(self, prim):
        if prim is None:
            return None
        pts = prim.points()
        if not pts:
            return None
        c = hou.Vector3(0, 0, 0)
        for p in pts:
            c += p.position()
        return c / float(len(pts))

    # -------------------------------------------------------------------------
    # Local frames
    # -------------------------------------------------------------------------

    def _frame_from_normal(self, origin, N):
        if N is None or N.length() < 1e-6:
            N = hou.Vector3(0, 1, 0)
        N = N.normalized()

        ref = hou.Vector3(0, 1, 0)
        if abs(ref.dot(N)) > 0.95:
            ref = hou.Vector3(1, 0, 0)

        T = ref - ref.dot(N) * N
        if T.length() < 1e-6:
            ref = hou.Vector3(0, 0, 1)
            T = ref - ref.dot(N) * N
        T = T.normalized()

        B = N.cross(T).normalized()
        return origin, T, B, N

    def _point_frame_from_avg_normal(self, ptnum):
        pt = self._edit_geo.point(ptnum)
        if pt is None:
            return None

        origin = pt.position()
        N = hou.Vector3()
        for poly in pt.prims():
            try:
                N += poly.normal()
            except:
                pass
        if N.length() < 1e-6:
            N = hou.Vector3(0, 1, 0)

        return self._frame_from_normal(origin, N)

    def _prim_frame_from_normal(self, primnum):
        prim = self._edit_geo.prim(primnum) if self._edit_geo else None
        if prim is None:
            return None

        origin = self._prim_center(prim)
        if origin is None:
            return None

        try:
            N = prim.normal()
        except:
            N = hou.Vector3(0, 1, 0)

        return self._frame_from_normal(origin, N)

    def _get_axes_for_space(self, space, sel):
        """
        space: "LOCAL" or "WORLD"
        sel: "POINT" or "FACE"
        Return (origin, axes_dict)
        """
        if self._edit_geo is None:
            return None, None

        if sel == "FACE":
            prim = self._edit_geo.prim(self._primnum)
            origin = self._prim_center(prim) if prim else None
            if origin is None:
                return None, None
            if space == "WORLD":
                return origin, {
                    "X": hou.Vector3(1, 0, 0),
                    "Y": hou.Vector3(0, 1, 0),
                    "Z": hou.Vector3(0, 0, 1),
                }
            frame = self._prim_frame_from_normal(self._primnum)
            if frame is None:
                return origin, {
                    "X": hou.Vector3(1, 0, 0),
                    "Y": hou.Vector3(0, 1, 0),
                    "Z": hou.Vector3(0, 0, 1),
                }
            o, T, B, N = frame
            return o, {"X": T, "Y": B, "Z": N}

        # POINT
        pt = self._edit_geo.point(self._ptnum)
        origin = pt.position() if pt else None
        if origin is None:
            return None, None

        if space == "WORLD":
            return origin, {
                "X": hou.Vector3(1, 0, 0),
                "Y": hou.Vector3(0, 1, 0),
                "Z": hou.Vector3(0, 0, 1),
            }

        frame = self._point_frame_from_avg_normal(self._ptnum)
        if frame is None:
            return origin, {
                "X": hou.Vector3(1, 0, 0),
                "Y": hou.Vector3(0, 1, 0),
                "Z": hou.Vector3(0, 0, 1),
            }
        o, T, B, N = frame
        return o, {"X": T, "Y": B, "Z": N}

    # -------------------------------------------------------------------------
    # EDGE helpers
    # -------------------------------------------------------------------------

    def _connected_neighbors(self, ptnum):
        """Neighbors around a point (by polygon adjacency)."""
        if self._edit_geo is None:
            return []
        pt = self._edit_geo.point(ptnum)
        if pt is None:
            return []

        nbrs = set()
        for prim in pt.prims():
            pts = prim.points()
            try:
                i = pts.index(pt)
            except ValueError:
                continue
            if len(pts) < 2:
                continue
            nbrs.add(pts[(i - 1) % len(pts)].number())
            nbrs.add(pts[(i + 1) % len(pts)].number())
        return sorted(nbrs)

    def _pick_edge_from_mouse(self, origin, mouse_delta, ptnum):
        """EDGE mode when sel==POINT: pick the best-connected edge direction."""
        nbrs = self._connected_neighbors(ptnum)
        if not nbrs:
            return None, 1.0

        edge_dirs = {}
        for idx, n in enumerate(nbrs):
            npt = self._edit_geo.point(n)
            if npt is None:
                continue
            v = npt.position() - origin
            if v.length() > 1e-6:
                edge_dirs[f"E{idx}"] = v

        if not edge_dirs:
            return None, 1.0

        key, sign = self._pick_axis_from_mouse(origin, mouse_delta, edge_dirs)
        if key is None:
            return None, 1.0

        return edge_dirs[key].normalized(), sign

    def _edge_midpoint(self, p0, p1):
        pt0 = self._edit_geo.point(p0) if self._edit_geo else None
        pt1 = self._edit_geo.point(p1) if self._edit_geo else None
        if pt0 is None or pt1 is None:
            return None
        return (pt0.position() + pt1.position()) * 0.5

    def _edge_tangent(self, p0, p1):
        pt0 = self._edit_geo.point(p0) if self._edit_geo else None
        pt1 = self._edit_geo.point(p1) if self._edit_geo else None
        if pt0 is None or pt1 is None:
            return None
        v = pt1.position() - pt0.position()
        if v.length() < 1e-6:
            return None
        return v.normalized()

    def _pick_edge_axis_for_selected_edge(self, origin, mouse_delta, p0, p1):
        """EDGE mode when sel==EDGE: use the tangent of the selected edge."""
        t = self._edge_tangent(p0, p1)
        if t is None:
            return None, 1.0
        key, sign = self._pick_axis_from_mouse(origin, mouse_delta, {"T": t})
        if key is None:
            return None, 1.0
        return t, sign

    # -------------------------------------------------------------------------
    # Stash sync (undo/redo safe)
    # -------------------------------------------------------------------------

    def _geo_signature(self, geo):
        if geo is None:
            return None
        try:
            pc = int(geo.intrinsicValue("pointcount"))
            prc = int(geo.intrinsicValue("primitivecount"))
        except:
            pc, prc = -1, -1

        pid = None
        try:
            P = geo.findPointAttrib("P")
            if P is not None:
                pid = P.dataId()
        except:
            pid = None

        return (pc, prc, pid)

    def _sync_from_stash_if_needed(self, force=False):
        if self.stash is None:
            return
        if self._pending or self._is_dragging:
            return

        try:
            self.stash.cook(force=True)
            stash_geo = self.stash.geometry()
        except:
            return

        sig = self._geo_signature(stash_geo)
        if (not force) and (sig == self._stash_sig):
            return

        self._stash_sig = sig
        self._init_editable_geo_from(stash_geo)

        if hasattr(self, "point_gadget") and self.point_gadget is not None:
            self.point_gadget.setGeometry(self._edit_geo)
        if hasattr(self, "face_gadget") and self.face_gadget is not None:
            self.face_gadget.setGeometry(self._edit_geo)
        if hasattr(self, "edge_gadget") and self.edge_gadget is not None:
            self.edge_gadget.setGeometry(self._edit_geo)

        self._hide_guide_line()
        self._hide_edge_hover()
        try:
            self.scene_viewer.curViewport().draw()
        except:
            pass

    # -------------------------------------------------------------------------
    # Stash helpers / editable geo
    # -------------------------------------------------------------------------

    def _stash_has_geo(self):
        if self.stash is None:
            return False
        try:
            self.stash.cook(force=True)
            g = self.stash.geometry()
            if g is None:
                return False
            return (g.intrinsicValue("pointcount") > 0) or (g.intrinsicValue("primitivecount") > 0)
        except:
            return False

    def _get_stash_geo(self):
        if self.stash is None:
            return None
        try:
            self.stash.cook(force=True)
            return self.stash.geometry()
        except:
            return None

    def _init_editable_geo_from(self, src_geo):
        self._edit_geo = hou.Geometry()
        if src_geo is not None:
            self._edit_geo.merge(src_geo)

    def _push_edit_geo_to_stash(self):
        if self.stash is None or self._edit_geo is None:
            return
        try:
            self.stash.parm("stash").set(self._edit_geo)
            self.stash.cook(force=True)
            if self.node is not None:
                self.node.cook(force=True)
        except:
            pass

    def _ensure_editable_geo_on_enter(self):
        input_node = self.node.node("INPUT") if self.node else None

        if self._stash_has_geo():
            self._src_geo = self._get_stash_geo()
            self._init_editable_geo_from(self._src_geo)
        else:
            self._src_geo = input_node.geometry() if input_node else None
            self._init_editable_geo_from(self._src_geo)
            self._push_edit_geo_to_stash()

        try:
            self._stash_sig = self._geo_signature(self._get_stash_geo())
        except:
            self._stash_sig = None

    # -------------------------------------------------------------------------
    # Callbacks (kept)
    # -------------------------------------------------------------------------

    def _onHdaParmChanged(self, **kwargs):
        pass

    def _register_callbacks(self):
        if not self.node or self._cb_registered:
            return
        try:
            self.node.addEventCallback((hou.nodeEventType.ParmTupleChanged,), self._onHdaParmChanged)
            self._cb_registered = True
        except:
            self._cb_registered = False

    def _unregister_callbacks(self):
        if not self.node or not self._cb_registered:
            return
        try:
            self.node.removeEventCallback((hou.nodeEventType.ParmTupleChanged,), self._onHdaParmChanged)
        except:
            pass
        self._cb_registered = False

    # -------------------------------------------------------------------------
    # Guide line
    # -------------------------------------------------------------------------

    def _init_guide_line(self):
        self.guide_line_geo = hou.Geometry()
        self.guide_line_pts = [self.guide_line_geo.createPoint(), self.guide_line_geo.createPoint()]

        self.guide_line_prim = self.guide_line_geo.createPolygon()
        self.guide_line_prim.setIsClosed(False)
        self.guide_line_prim.addVertex(self.guide_line_pts[0])
        self.guide_line_prim.addVertex(self.guide_line_pts[1])

        self.guide_line_drawable = hou.GeometryDrawable(
            self.scene_viewer, hou.drawableGeometryType.Line, "auto_axis_guide_line"
        )
        self.guide_line_drawable.setGeometry(self.guide_line_geo)
        self.guide_line_drawable.setParams({
            "color1": self.color_options.colorFromName("PickedHandleColor"),
            "line_width": 2.0
        })
        self.guide_line_drawable.show(False)

    def _update_guide_line(self, origin, axis_dir):
        if self.guide_line_drawable is None:
            return
        if origin is None or axis_dir is None or axis_dir.length() < 1e-6:
            self.guide_line_drawable.show(False)
            return

        a = axis_dir.normalized()
        self.guide_line_pts[0].setPosition(origin)
        self.guide_line_pts[1].setPosition(origin + a * self.guide_len)

        P = self.guide_line_geo.findPointAttrib("P")
        if P is not None:
            P.incrementDataId()
        self.guide_line_geo.incrementModificationCounter()

        self.guide_line_drawable.show(True)

    def _hide_guide_line(self):
        if self.guide_line_drawable is not None:
            self.guide_line_drawable.show(False)

    # -------------------------------------------------------------------------
    # Screen projection + pick
    # -------------------------------------------------------------------------

    def _world_to_screen(self, pos):
        vp = self.scene_viewer.curViewport()
        try:
            x, y = vp.worldToScreen(pos)
            return hou.Vector2(x, y)
        except:
            try:
                return vp.mapToScreen(pos)
            except:
                return None

    def _pick_axis_from_mouse(self, origin, mouse_delta, axes):
        if mouse_delta.length() < 2.0:
            return None, 1.0

        o2 = self._world_to_screen(origin)
        if o2 is None:
            return None, 1.0

        md = mouse_delta.normalized()

        best_name = None
        best_score = -1.0
        best_sign = 1.0

        for name, axis in axes.items():
            if axis is None or axis.length() < 1e-6:
                continue

            p2 = self._world_to_screen(origin + axis.normalized() * 0.1)
            if p2 is None:
                continue

            v2 = p2 - o2
            if v2.length() < 1e-6:
                continue

            d = md.dot(v2.normalized())
            score = abs(d)
            if score > best_score:
                best_score = score
                best_name = name
                best_sign = 1.0 if d >= 0.0 else -1.0

        return best_name, best_sign

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def _cleanup_drag(self):
        self._pending = False
        try:
            self.dragger.endDrag()
        except:
            pass

        self._hide_guide_line()
        self._hide_edge_hover()

        self._is_dragging = False
        self._drag_mode_used = None
        self._drag_select_used = None

        self._drag_axis = None
        self._choice = None
        self._sign = 1.0

        self._ptnum = -1
        self._primnum = -1
        self._affected_ptnums = None

        self._edge_p0 = -1
        self._edge_p1 = -1

        self._origin = None
        self._start_mouse = None

        if self._undo_opened:
            try:
                self.scene_viewer.endStateUndo()
            except:
                pass
            self._undo_opened = False

    # -------------------------------------------------------------------------
    # Viewer state hooks
    # -------------------------------------------------------------------------

    def onEnter(self, kwargs):
        self.node = kwargs["node"]
        self.stash = self.node.node("stash1")

        self.scene_viewer.hudInfo(template=State.HUD_TEMPLATE)
        self._hud_update()

        self._ensure_editable_geo_on_enter()
        self._sync_from_stash_if_needed(force=True)

        self._init_guide_line()
        self._init_edge_hover()

        # --- gadgets ---
        self.point_gadget = self.state_gadgets["point_gadget"]
        self.point_gadget.setGeometry(self._edit_geo)
        self.point_gadget.setParams({
            "draw_color": self.color_options.colorFromName("HandleZAxisColor", alpha_name="LocateAlpha"),
            "radius": 5.0
        })
        self.point_gadget.show(True)

        self.face_gadget = self.state_gadgets["face_gadget"]
        self.face_gadget.setGeometry(self._edit_geo)
        self.face_gadget.setParams({
            "draw_color": self.color_options.colorFromName("HandleXAxisColor", alpha_name="LocateAlpha"),
        })
        self.face_gadget.show(True)

        self.edge_gadget = self.state_gadgets["edge_gadget"]
        self.edge_gadget.setGeometry(self._edit_geo)
        # IMPORTANT: keep invisible so Houdini doesn't draw ALL edges
        self.edge_gadget.setParams({
            "draw_color": [1, 1, 1, 0.0],
        })
        self.edge_gadget.show(True)

        self._register_callbacks()

    def onExit(self, kwargs):
        self._cleanup_drag()
        self._unregister_callbacks()
        self._hide_guide_line()
        self._hide_edge_hover()

    def onMouseEvent(self, kwargs):
        ui_event = kwargs["ui_event"]
        reason = ui_event.reason()

        # Only react if correct gadget for current selection mode
        gad = self.state_context.gadget()
        if self.select_mode == "POINT":
            ok = (gad == "point_gadget")
        elif self.select_mode == "EDGE":
            ok = (gad == "edge_gadget")
        else:  # FACE
            ok = (gad == "face_gadget")

        if not ok:
            if self._pending or self._undo_opened or self._is_dragging:
                self._cleanup_drag()
            return False

        if self._edit_geo is None:
            return False

        # mouse pos
        try:
            mx, my = ui_event.device().mouseX(), ui_event.device().mouseY()
            cur_mouse = hou.Vector2(mx, my)
        except:
            return False

        if reason == hou.uiEventReason.Start:
            self._pending = True
            self._start_mouse = cur_mouse

            # snapshot modes for this drag
            self._drag_mode_used = self.mode
            self._drag_select_used = self.select_mode
            self._is_dragging = False

            self._choice = None
            self._sign = 1.0
            self._drag_axis = None
            self._affected_ptnums = None

            # capture selection
            if self.select_mode == "POINT":
                ptnum = self.state_context.component1()
                pt = self._edit_geo.point(ptnum)
                if pt is None:
                    return False
                self._ptnum = ptnum
                self._origin = pt.position()

            elif self.select_mode == "EDGE":
                p0 = self.state_context.component1()
                p1 = self.state_context.component2()

                pt0 = self._edit_geo.point(p0)
                pt1 = self._edit_geo.point(p1)
                if pt0 is None or pt1 is None:
                    return False

                self._edge_p0 = p0
                self._edge_p1 = p1
                self._affected_ptnums = [p0, p1]
                self._origin = (pt0.position() + pt1.position()) * 0.5

            else:  # FACE
                primnum = self.state_context.component1()
                prim = self._edit_geo.prim(primnum)
                if prim is None:
                    return False
                self._primnum = primnum
                self._origin = self._prim_center(prim)
                self._affected_ptnums = self._prim_points_unique(prim)

            self._hide_guide_line()

            try:
                self.scene_viewer.beginStateUndo("Auto drag")
                self._undo_opened = True
            except:
                self._undo_opened = False

            return True

        elif reason in [hou.uiEventReason.Active, hou.uiEventReason.Changed]:
            if self._pending:
                md = cur_mouse - self._start_mouse

                mode = self._drag_mode_used or self.mode
                sel = self._drag_select_used or self.select_mode
                origin = self._origin

                # If FACE + mode EDGE -> fallback LOCAL
                if sel == "FACE" and mode == "EDGE":
                    mode = "LOCAL"

                if mode == "EDGE":
                    if sel == "POINT":
                        edge_dir, sign = self._pick_edge_from_mouse(origin, md, self._ptnum)
                        if edge_dir is not None:
                            self._drag_axis = edge_dir * sign
                        else:
                            # fallback LOCAL
                            origin2, axes = self._get_axes_for_space("LOCAL", "POINT")
                            if origin2 is not None and axes is not None:
                                origin = origin2
                            choice, sign = self._pick_axis_from_mouse(origin, md, axes)
                            if choice is None and reason != hou.uiEventReason.Changed:
                                return True
                            if choice is None:
                                choice, sign = "Z", 1.0
                            self._drag_axis = axes[choice].normalized() * sign

                    elif sel == "EDGE":
                        t, sign = self._pick_edge_axis_for_selected_edge(origin, md, self._edge_p0, self._edge_p1)
                        if t is None:
                            # fallback WORLD
                            axes = {"X": hou.Vector3(1, 0, 0), "Y": hou.Vector3(0, 1, 0), "Z": hou.Vector3(0, 0, 1)}
                            choice, sign = self._pick_axis_from_mouse(origin, md, axes)
                            if choice is None and reason != hou.uiEventReason.Changed:
                                return True
                            if choice is None:
                                choice, sign = "Z", 1.0
                            self._drag_axis = axes[choice].normalized() * sign
                        else:
                            self._drag_axis = t * sign

                    else:  # FACE (edge mode fallback local)
                        origin, axes = self._get_axes_for_space("LOCAL", "FACE")
                        if origin is None or axes is None:
                            return False
                        choice, sign = self._pick_axis_from_mouse(origin, md, axes)
                        if choice is None and reason != hou.uiEventReason.Changed:
                            return True
                        if choice is None:
                            choice, sign = "Z", 1.0
                        self._drag_axis = axes[choice].normalized() * sign

                else:
                    # mode LOCAL / WORLD
                    if sel == "EDGE":
                        origin = self._origin
                        if mode == "WORLD":
                            axes = {"X": hou.Vector3(1, 0, 0), "Y": hou.Vector3(0, 1, 0), "Z": hou.Vector3(0, 0, 1)}
                        else:
                            # simple fallback: local based on p0
                            self._ptnum = self._edge_p0
                            origin2, axes = self._get_axes_for_space("LOCAL", "POINT")
                            if origin2 is None or axes is None:
                                axes = {"X": hou.Vector3(1, 0, 0), "Y": hou.Vector3(0, 1, 0), "Z": hou.Vector3(0, 0, 1)}
                    else:
                        origin, axes = self._get_axes_for_space(mode, sel)
                        if origin is None or axes is None:
                            return False

                    choice, sign = self._pick_axis_from_mouse(origin, md, axes)
                    if choice is None and reason != hou.uiEventReason.Changed:
                        return True
                    if choice is None:
                        choice, sign = "Z", 1.0
                    self._drag_axis = axes[choice].normalized() * sign

                self._update_guide_line(origin, self._drag_axis)
                self.dragger.startDragAlongLine(ui_event, origin, self._drag_axis)
                self._pending = False
                self._is_dragging = True

            # Apply delta
            try:
                delta = self.dragger.drag(ui_event)["delta_position"]
            except:
                if reason == hou.uiEventReason.Changed:
                    self._cleanup_drag()
                return False

            # Apply delta based on selection
            if self.select_mode == "POINT":
                pt = self._edit_geo.point(self._ptnum)
                if pt is not None:
                    pt.setPosition(pt.position() + delta)

            elif self.select_mode == "EDGE":
                if self._affected_ptnums:
                    for pn in self._affected_ptnums:
                        p = self._edit_geo.point(pn)
                        if p is not None:
                            p.setPosition(p.position() + delta)

            else:  # FACE
                if self._affected_ptnums:
                    for pn in self._affected_ptnums:
                        p = self._edit_geo.point(pn)
                        if p is not None:
                            p.setPosition(p.position() + delta)

            # refresh geo + stash
            P = self._edit_geo.findPointAttrib("P")
            if P is not None:
                P.incrementDataId()
            self._edit_geo.incrementModificationCounter()

            self._push_edit_geo_to_stash()
            try:
                self._stash_sig = self._geo_signature(self._get_stash_geo())
            except:
                pass

            # update guide origin
            if self.select_mode == "POINT":
                pt = self._edit_geo.point(self._ptnum)
                if pt is not None:
                    self._update_guide_line(pt.position(), self._drag_axis)

            elif self.select_mode == "EDGE":
                mid = self._edge_midpoint(self._edge_p0, self._edge_p1)
                if mid is not None:
                    self._update_guide_line(mid, self._drag_axis)

            else:  # FACE
                prim = self._edit_geo.prim(self._primnum)
                if prim is not None:
                    c = self._prim_center(prim)
                    if c is not None:
                        self._update_guide_line(c, self._drag_axis)

            if reason == hou.uiEventReason.Changed:
                self._cleanup_drag()

            return True

        return False

    def onDraw(self, kwargs):
        if self.state_context.isPicking():
            return

        self._sync_from_stash_if_needed(force=False)
        handle = kwargs["draw_handle"]

        # --- Hover highlight ONLY ---
        if self.select_mode == "POINT":
            if self.state_context.gadget() == "point_gadget":
                self.point_gadget.setParams({"indices": [self.state_context.component1()]})
            else:
                self.point_gadget.setParams({"indices": []})
            self.point_gadget.draw(handle)
            self._hide_edge_hover()

        elif self.select_mode == "EDGE":
            # draw gadget (invisible) for picking
            self.edge_gadget.draw(handle)

            # draw only the hovered edge
            if self.state_context.gadget() == "edge_gadget":
                p0 = self.state_context.component1()
                p1 = self.state_context.component2()
                self._update_edge_hover_from_points(p0, p1)
            else:
                self._hide_edge_hover()

        else:  # FACE
            if self.state_context.gadget() == "face_gadget":
                self.face_gadget.setParams({"indices": [self.state_context.component1()]})
            else:
                self.face_gadget.setParams({"indices": []})
            self.face_gadget.draw(handle)
            self._hide_edge_hover()

        if self.guide_line_drawable is not None:
            self.guide_line_drawable.draw(handle)

        if self.edge_hover_drawable is not None:
            self.edge_hover_drawable.draw(handle)

    def onMenuAction(self, kwargs):
        menu_item = kwargs.get("menu_item")

        if menu_item == "cycle_mode":
            if self._pending or self._is_dragging:
                return True
            self._cycle_mode()
            self._hud_update()
            return True

        if menu_item == "cycle_select":
            if self._pending or self._is_dragging:
                return True
            self._cycle_select_mode()
            self._hud_update()
            return True

        return False


def createViewerStateTemplate():
    state_typename = "AutoAxisTest"
    state_label = "AutoAxisTest"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)

    # gadgets
    template.bindGadget(hou.drawableGeometryType.Point, "point_gadget", label="Point")
    template.bindGadget(hou.drawableGeometryType.Face, "face_gadget", label="Face")
    template.bindGadget(hou.drawableGeometryType.Line, "edge_gadget", label="Edge")

    # hotkeys / menu actions
    hotkey_definitions = hou.PluginHotkeyDefinitions()
    menu = hou.ViewerStateMenu(state_typename + "_menu", state_label)

    menu.addActionItem(
        "cycle_mode",
        "Cycle Mode (Local/World/Edge)",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "cycle_mode", "m")
    )
    menu.addActionItem(
        "cycle_select",
        "Cycle Select Mode (Point/Edge/Face)",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "cycle_select", "f")
    )

    template.bindMenu(menu)
    template.bindHotkeyDefinitions(hotkey_definitions)
    return template
