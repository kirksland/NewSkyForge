import hou
import curveutils as cu

from skyforge.forge_motion.axis_auto import world_to_screen
from ..feature_base import ViewerFeature
from .. import constants as k


class CurveUtilsEditFeature(ViewerFeature):
    """
    Unified edit feature built on curveutils.curve3DPicker.
    Supports dragging a selection interpreted as:
    - POINT: selected point ids
    - EDGE: selected edge point pairs
    - PRIM: selected primitive ids
    """

    name = "curveutils_edit"

    TARGET_POINT = "POINT"
    TARGET_EDGE = "EDGE"
    TARGET_PRIM = "PRIM"

    def __init__(self):
        self.preview = None
        self.channel_selected = "curveutils_selected_test"
        self.target = self.TARGET_POINT

        self.selected_points = []
        self.selected_edges = []
        self.selected_prims = []

        self.picker = cu.curve3DPicker(cu.curve3DPicker.MODE_VIEWPLANE)
        self.drag_active = False
        self.drag_plane_origin = None
        self.last_world_pos = None
        self.drag_ptnums = []

    def on_enter(self, ctx, kwargs):
        self.preview = ctx.get_service("preview")
        if self.preview is not None:
            self.preview.ensure_point_channel(
                self.channel_selected,
                k.COLOR_PREVIEW_YELLOW,
                radius=8.0,
                style=hou.drawableGeometryPointStyle.SmoothCircle,
            )
        self.picker.reset()
        self.picker.setPickMode(cu.curve3DPicker.MODE_VIEWPLANE)
        self._update_preview(ctx)

    def on_exit(self, ctx, kwargs):
        self._end_drag(ctx, commit=False)
        if self.preview is not None:
            self.preview.hide(self.channel_selected)

    def on_key_event(self, ctx, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False
        dev = ui.device()
        if dev.isAutoRepeat():
            return False

        key = (dev.keyString() or "").lower()
        if key == "&":
            self.target = self.TARGET_POINT
            return True
        if key == "é":
            self.target = self.TARGET_EDGE
            return True
        if key == "q":
            self.target = self.TARGET_PRIM
            return True
        return False

    def on_mouse_event(self, ctx, kwargs):
        if str(getattr(ctx, "tool_mode", "")).upper() != k.AUTO_AXIS_TOOL_ORDER[0]:
            self._end_drag(ctx, commit=False)
            return False

        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        reason = ui.reason()
        dev = ui.device()

        if reason == hou.uiEventReason.Start and dev.isLeftButton():
            return self._handle_start(ctx, ui)

        if reason == hou.uiEventReason.Active and self.drag_active:
            return self._handle_active(ctx, ui)

        if reason == hou.uiEventReason.Changed and self.drag_active:
            return self._handle_changed(ctx, ui)

        return False

    def refresh_after_sync(self, ctx):
        self._filter_selection(ctx)
        self._update_preview(ctx)

    def clear_selection(self, ctx):
        self.selected_points = []
        self.selected_edges = []
        self.selected_prims = []
        self._update_preview(ctx)

    def _handle_start(self, ctx, ui_event):
        if ctx.edit_geo is None:
            return False

        shift = self._is_shift_down(ui_event.device())
        hit = ctx.get_service("hit") or {}
        if not self._select_from_hit(ctx, ui_event, hit, shift):
            return False

        self.drag_ptnums = self._selection_to_ptnums(ctx)
        if not self.drag_ptnums:
            return True

        origin = self._centroid(ctx, self.drag_ptnums)
        if origin is None:
            return True

        try:
            rpos, rdir = ui_event.ray()
        except Exception:
            return True

        wpos = self.picker.intersect(
            ctx.scene_viewer,
            rpos,
            rdir,
            ui_event=ui_event,
            plane_orig=origin,
        )
        if wpos is None:
            return True

        self.drag_plane_origin = hou.Vector3(origin)
        self.last_world_pos = hou.Vector3(wpos)
        self.drag_active = True
        try:
            ctx.scene_viewer.beginStateUndo("CurveUtils edit drag")
        except Exception:
            pass
        return True

    def _handle_active(self, ctx, ui_event):
        try:
            rpos, rdir = ui_event.ray()
        except Exception:
            return False

        cur = self.picker.intersect(
            ctx.scene_viewer,
            rpos,
            rdir,
            ui_event=ui_event,
            plane_orig=self.drag_plane_origin,
        )
        if cur is None or self.last_world_pos is None:
            return True

        delta = hou.Vector3(cur) - hou.Vector3(self.last_world_pos)
        if delta.lengthSquared() <= 1e-14:
            return True
        self._translate_ptnums(ctx, self.drag_ptnums, delta)
        self.last_world_pos = hou.Vector3(cur)
        return True

    def _handle_changed(self, ctx, ui_event):
        self._handle_active(ctx, ui_event)
        self._end_drag(ctx, commit=True)
        return True

    def _end_drag(self, ctx, commit):
        if not self.drag_active:
            return
        self.drag_active = False
        self.drag_plane_origin = None
        self.last_world_pos = None
        self.drag_ptnums = []
        if commit:
            try:
                ctx.scene_viewer.endStateUndo()
            except Exception:
                pass

    def _translate_ptnums(self, ctx, ptnums, delta):
        if ctx.edit_geo is None:
            return
        for p in ptnums:
            pt = ctx.edit_geo.point(int(p))
            if pt is not None:
                pt.setPosition(pt.position() + delta)
        ctx.push_edit_geo()
        ctx.ensure_mesh(geo=ctx.edit_geo)
        self._update_preview(ctx)
        self._request_draw(ctx)

    def _select_from_hit(self, ctx, ui_event, hit, shift):
        if self.target == self.TARGET_POINT:
            return self._select_point(ctx, ui_event, hit, shift)
        if self.target == self.TARGET_EDGE:
            return self._select_edge(hit, shift)
        return self._select_prim(hit, shift)

    def _select_point(self, ctx, ui_event, hit, shift):
        curve_ids = [int(i) for i in (ctx.get_service("curve_point_ids") or [])]
        if not curve_ids or ctx.edit_geo is None:
            if not shift:
                self.clear_selection(ctx)
            return False

        picked = int(hit.get("point", -1))
        if picked not in curve_ids:
            picked = self._pick_nearest_screen_point(ctx, ui_event, curve_ids, px_threshold=20.0)
        if picked < 0:
            if not shift:
                self.clear_selection(ctx)
            return False

        if shift:
            if picked in self.selected_points:
                self.selected_points = [p for p in self.selected_points if p != picked]
            else:
                self.selected_points.append(picked)
        else:
            self.selected_points = [picked]
            self.selected_edges = []
            self.selected_prims = []
        self._filter_selection(ctx)
        self._update_preview(ctx)
        return True

    def _select_edge(self, hit, shift):
        edge = hit.get("edge")
        if edge is None:
            if not shift:
                self.selected_edges = []
                self.selected_points = []
                self.selected_prims = []
            return False
        pair = (int(edge[0]), int(edge[1]))
        key = tuple(sorted(pair))
        if shift:
            cur = [tuple(sorted(e)) for e in self.selected_edges]
            if key in cur:
                self.selected_edges = [e for e in self.selected_edges if tuple(sorted(e)) != key]
            else:
                self.selected_edges.append(pair)
        else:
            self.selected_edges = [pair]
            self.selected_points = []
            self.selected_prims = []
        return True

    def _select_prim(self, hit, shift):
        prim = int(hit.get("prim", -1))
        if prim < 0:
            if not shift:
                self.selected_prims = []
                self.selected_points = []
                self.selected_edges = []
            return False
        if shift:
            if prim in self.selected_prims:
                self.selected_prims = [p for p in self.selected_prims if p != prim]
            else:
                self.selected_prims.append(prim)
        else:
            self.selected_prims = [prim]
            self.selected_points = []
            self.selected_edges = []
        return True

    def _selection_to_ptnums(self, ctx):
        if ctx.edit_geo is None:
            return []
        seen = set()
        out = []

        for p in self.selected_points:
            ip = int(p)
            if ip not in seen and ctx.edit_geo.point(ip) is not None:
                seen.add(ip)
                out.append(ip)

        for a, b in self.selected_edges:
            for ip in (int(a), int(b)):
                if ip not in seen and ctx.edit_geo.point(ip) is not None:
                    seen.add(ip)
                    out.append(ip)

        for primnum in self.selected_prims:
            prim = ctx.edit_geo.prim(int(primnum))
            if prim is None:
                continue
            for pt in prim.points():
                ip = int(pt.number())
                if ip not in seen:
                    seen.add(ip)
                    out.append(ip)
        return out

    def _pick_nearest_screen_point(self, ctx, ui_event, ptnums, px_threshold=20.0):
        try:
            mx = float(ui_event.device().mouseX())
            my = float(ui_event.device().mouseY())
        except Exception:
            return -1
        best = -1
        best_d2 = float(px_threshold) * float(px_threshold)
        for ptnum in ptnums:
            pt = ctx.edit_geo.point(int(ptnum))
            if pt is None:
                continue
            sp = world_to_screen(ctx.scene_viewer, pt.position())
            if sp is None:
                continue
            dx = float(sp.x()) - mx
            dy = float(sp.y()) - my
            d2 = dx * dx + dy * dy
            if d2 <= best_d2:
                best_d2 = d2
                best = int(ptnum)
        return best

    def _centroid(self, ctx, ptnums):
        if ctx.edit_geo is None:
            return None
        acc = hou.Vector3(0.0, 0.0, 0.0)
        n = 0
        for p in ptnums:
            pt = ctx.edit_geo.point(int(p))
            if pt is None:
                continue
            acc += pt.position()
            n += 1
        if n <= 0:
            return None
        return acc / float(n)

    def _filter_selection(self, ctx):
        if ctx.edit_geo is None:
            self.clear_selection(ctx)
            return
        self.selected_points = [int(p) for p in self.selected_points if ctx.edit_geo.point(int(p)) is not None]
        kept_edges = []
        for a, b in self.selected_edges:
            if ctx.edit_geo.point(int(a)) is not None and ctx.edit_geo.point(int(b)) is not None:
                kept_edges.append((int(a), int(b)))
        self.selected_edges = kept_edges
        self.selected_prims = [int(pr) for pr in self.selected_prims if ctx.edit_geo.prim(int(pr)) is not None]

    def _update_preview(self, ctx):
        if self.preview is None:
            return
        if ctx.edit_geo is None:
            self.preview.hide(self.channel_selected)
            return
        pts = self._selection_to_ptnums(ctx)
        if not pts:
            self.preview.hide(self.channel_selected)
            return
        self.preview.set_points(self.channel_selected, ctx.edit_geo, pts)

    def _request_draw(self, ctx):
        try:
            ctx.scene_viewer.curViewport().draw()
        except Exception:
            pass

    def _is_shift_down(self, dev):
        try:
            return bool(dev.isShiftKey())
        except Exception:
            key = (dev.keyString() or "").lower()
            return "shift" in key
