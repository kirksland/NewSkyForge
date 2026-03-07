import hou

from skyforge import forge_mesh as mesh
from skyforge import forge_draw as draw
from skyforge.forge_states.feature_base import ViewerFeature


class PathMoveFeature(ViewerFeature):
    name = "path_move"

    def __init__(self):
        self.enabled = False
        self._dragging = False
        self._undo_opened = False

        self._pivot = None
        self._plane_n = None
        self._start_hit = None
        self._start_positions = {}
        self._selected_points = []

        self.guide = None
        self.guide_len = 0.35

    def on_enter(self, ctx, kwargs):
        color = hou.Color((0.85, 0.95, 1.0))
        self.guide = draw.LineFX(ctx.scene_viewer, "path_move_lab_guide", color, line_width=2.0)
        self.guide.hide()
        self._reset_runtime(close_undo=False, scene_viewer=ctx.scene_viewer)

    def on_exit(self, ctx, kwargs):
        self._reset_runtime(close_undo=True, scene_viewer=ctx.scene_viewer)
        self.enabled = False
        if self.guide is not None:
            self.guide.hide()

    def on_key_event(self, ctx, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False
        dev = ui.device()
        if dev.isAutoRepeat():
            return False

        key = ""
        try:
            key = (dev.keyString() or "").lower()
        except Exception:
            key = ""

        if key != "g":
            return False

        self.enabled = (not self.enabled)
        if not self.enabled:
            self._reset_runtime(close_undo=True, scene_viewer=ctx.scene_viewer)
        return True

    def on_draw(self, ctx, kwargs):
        if self.guide is not None:
            self.guide.draw(kwargs["draw_handle"])

    def deactivate(self, ctx):
        self.enabled = False
        self._reset_runtime(close_undo=True, scene_viewer=ctx.scene_viewer)

    def on_mouse_event(self, ctx, kwargs):
        if not self.enabled:
            return False

        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        reason = ui.reason()
        dev = ui.device()
        if reason not in (hou.uiEventReason.Start, hou.uiEventReason.Active, hou.uiEventReason.Changed):
            return False
        if not dev.isLeftButton():
            return False

        if reason == hou.uiEventReason.Start:
            return self._start_drag(ctx, ui)
        return self._update_drag(ctx, ui, reason)

    def is_interacting(self):
        return bool(self._dragging or self._undo_opened)

    def _start_drag(self, ctx, ui_event):
        if ctx.edit_geo is None:
            return False
        if not ctx.selected_ptnums:
            return False

        points = []
        start_positions = {}
        for pn in ctx.selected_ptnums:
            pt = ctx.edit_geo.point(int(pn))
            if pt is None:
                continue
            points.append(int(pn))
            start_positions[int(pn)] = hou.Vector3(pt.position())

        if not points:
            return False

        pivot = hou.Vector3(0.0, 0.0, 0.0)
        for pn in points:
            pivot += start_positions[pn]
        pivot /= float(len(points))

        rpos, rdir = ui_event.ray()
        plane_n = hou.Vector3(rdir)
        if plane_n.length() < 1e-8:
            return False
        plane_n = plane_n.normalized()

        start_hit = self._ray_plane_hit(rpos, rdir, pivot, plane_n)
        if start_hit is None:
            return False

        self._selected_points = points
        self._start_positions = start_positions
        self._pivot = pivot
        self._plane_n = plane_n
        self._start_hit = start_hit
        self._dragging = True

        try:
            ctx.scene_viewer.beginStateUndo("Path Move")
            self._undo_opened = True
        except Exception:
            self._undo_opened = False

        self._update_guide(hou.Vector3(0.0, 0.0, 0.0))
        return True

    def _update_drag(self, ctx, ui_event, reason):
        if not self._dragging:
            return False

        rpos, rdir = ui_event.ray()
        hit = self._ray_plane_hit(rpos, rdir, self._pivot, self._plane_n)
        if hit is None:
            if reason == hou.uiEventReason.Changed:
                self._reset_runtime(close_undo=True, scene_viewer=ctx.scene_viewer)
            return False

        delta = hit - self._start_hit
        for pn in self._selected_points:
            pt = ctx.edit_geo.point(int(pn))
            if pt is None:
                continue
            pt.setPosition(self._start_positions[pn] + delta)

        mesh.touch_point_positions(ctx.edit_geo)
        ctx.push_edit_geo()
        self._update_guide(delta)

        if reason == hou.uiEventReason.Changed:
            self._reset_runtime(close_undo=True, scene_viewer=ctx.scene_viewer)
        return True

    def _update_guide(self, delta):
        if self.guide is None or self._pivot is None:
            return
        if delta.length() < 1e-9:
            self.guide.hide()
            return
        v = delta.normalized() * self.guide_len
        self.guide.set_line(self._pivot, self._pivot + v)

    def _ray_plane_hit(self, ray_origin, ray_dir, plane_point, plane_normal):
        denom = float(ray_dir.dot(plane_normal))
        if abs(denom) < 1e-8:
            return None
        t = float((plane_point - ray_origin).dot(plane_normal) / denom)
        if t < 0.0:
            return None
        return ray_origin + ray_dir * t

    def _reset_runtime(self, close_undo, scene_viewer):
        self._dragging = False
        self._pivot = None
        self._plane_n = None
        self._start_hit = None
        self._start_positions = {}
        self._selected_points = []
        if self.guide is not None:
            self.guide.hide()

        if close_undo and self._undo_opened:
            try:
                scene_viewer.endStateUndo()
            except Exception:
                pass
            self._undo_opened = False
