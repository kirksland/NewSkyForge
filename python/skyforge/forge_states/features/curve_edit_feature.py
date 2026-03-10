import hou
import curveutils as cu

from skyforge.forge_motion.axis_auto import world_to_screen
from ..feature_base import ViewerFeature
from .. import constants as k


class CurveEditFeature(ViewerFeature):
    """
    Safe curve edit feature (no ViewerStateDragger usage).
    - LMB in MOVE mode: select nearest curve point and start drag
    - Shift+LMB: toggle multi-selection then drag selection
    - Drag computed with ray/plane intersection
    """

    name = "curve_edit"

    def __init__(self):
        self.preview = None
        self.channel_selected = "curve_selected_test"
        self.selected = []

        self.drag_active = False
        self.drag_plane_origin = None
        self.drag_plane_normal = None
        self.last_world_pos = None

    def on_enter(self, ctx, kwargs):
        self.preview = ctx.get_service("preview")
        if self.preview is not None:
            self.preview.ensure_point_channel(
                self.channel_selected,
                k.COLOR_PREVIEW_YELLOW,
                radius=8.0,
                style=hou.drawableGeometryPointStyle.SmoothCircle,
            )
        self._update_preview(ctx)

    def on_exit(self, ctx, kwargs):
        self._end_drag(ctx, commit=False)
        if self.preview is not None:
            self.preview.hide(self.channel_selected)

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
        self.selected = []
        self._update_preview(ctx)

    def _handle_start(self, ctx, ui_event):
        curve_ids = [int(i) for i in (ctx.get_service("curve_point_ids") or [])]
        if not curve_ids or ctx.edit_geo is None:
            self.clear_selection(ctx)
            return False

        picked = self._pick_nearest_screen_point(ctx, ui_event, curve_ids, px_threshold=20.0)
        shift = self._is_shift_down(ui_event.device())

        if picked < 0:
            if not shift:
                self.clear_selection(ctx)
            return False

        if shift:
            if picked in self.selected:
                self.selected = [p for p in self.selected if p != picked]
            else:
                self.selected.append(picked)
        else:
            self.selected = [picked]

        self._filter_selection(ctx)
        self._update_preview(ctx)
        if not self.selected:
            return True

        origin = self._centroid(ctx, self.selected)
        if origin is None:
            return True

        try:
            rpos, rdir = ui_event.ray()
        except Exception:
            return True

        normal = cu.getViewDirection(ctx.scene_viewer)
        if normal.length() < 1e-8:
            normal = hou.Vector3(rdir)
        if normal.length() < 1e-8:
            return True
        normal = normal.normalized()

        wpos = self._intersect_ray_plane(rpos, rdir, origin, normal)
        if wpos is None:
            return True

        self.drag_plane_origin = hou.Vector3(origin)
        self.drag_plane_normal = hou.Vector3(normal)
        self.last_world_pos = hou.Vector3(wpos)
        self.drag_active = True
        try:
            ctx.scene_viewer.beginStateUndo("Curve edit drag")
        except Exception:
            pass
        return True

    def _handle_active(self, ctx, ui_event):
        try:
            rpos, rdir = ui_event.ray()
        except Exception:
            return False

        cur = self._intersect_ray_plane(
            rpos,
            rdir,
            self.drag_plane_origin,
            self.drag_plane_normal,
        )
        if cur is None or self.last_world_pos is None:
            return True

        delta = hou.Vector3(cur) - hou.Vector3(self.last_world_pos)
        if delta.lengthSquared() <= 1e-14:
            return True

        self._translate_selected(ctx, delta)
        self.last_world_pos = hou.Vector3(cur)
        return True

    def _handle_changed(self, ctx, ui_event):
        # Apply one last drag step on mouse up.
        self._handle_active(ctx, ui_event)
        self._end_drag(ctx, commit=True)
        return True

    def _translate_selected(self, ctx, delta):
        if ctx.edit_geo is None:
            return
        for ptnum in self.selected:
            pt = ctx.edit_geo.point(int(ptnum))
            if pt is None:
                continue
            pt.setPosition(pt.position() + delta)

        ctx.push_edit_geo()
        ctx.ensure_mesh(geo=ctx.edit_geo)
        self._update_preview(ctx)
        self._request_draw(ctx)

    def _pick_nearest_screen_point(self, ctx, ui_event, ptnums, px_threshold=20.0):
        if ctx.edit_geo is None:
            return -1
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
        for ptnum in ptnums:
            pt = ctx.edit_geo.point(int(ptnum))
            if pt is None:
                continue
            acc += pt.position()
            n += 1
        if n <= 0:
            return None
        return acc / float(n)

    def _intersect_ray_plane(self, rpos, rdir, plane_origin, plane_normal):
        if plane_origin is None or plane_normal is None:
            return None
        try:
            n = hou.Vector3(plane_normal).normalized()
            d = float(rdir.dot(n))
            if abs(d) < 1e-8:
                return None
            t = float((hou.Vector3(plane_origin) - rpos).dot(n)) / d
            if t < 0.0:
                return None
            return rpos + rdir * t
        except Exception:
            return None

    def _filter_selection(self, ctx):
        if ctx.edit_geo is None:
            self.selected = []
            return
        self.selected = [int(p) for p in self.selected if ctx.edit_geo.point(int(p)) is not None]

    def _update_preview(self, ctx):
        if self.preview is None:
            return
        if ctx.edit_geo is None or not self.selected:
            self.preview.hide(self.channel_selected)
            return
        self.preview.set_points(self.channel_selected, ctx.edit_geo, self.selected)

    def _request_draw(self, ctx):
        try:
            ctx.scene_viewer.curViewport().draw()
        except Exception:
            pass

    def _end_drag(self, ctx, commit):
        if not self.drag_active:
            return
        self.drag_active = False
        self.drag_plane_origin = None
        self.drag_plane_normal = None
        self.last_world_pos = None
        if commit:
            try:
                ctx.scene_viewer.endStateUndo()
            except Exception:
                pass

    def _is_shift_down(self, dev):
        try:
            return bool(dev.isShiftKey())
        except Exception:
            key = (dev.keyString() or "").lower()
            return "shift" in key
