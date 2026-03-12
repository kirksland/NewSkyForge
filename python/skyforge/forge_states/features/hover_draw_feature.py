import hou
import curveutils as cu

from ..feature_base import ViewerFeature
from ..preview_service import PreviewService
from .. import constants as k


class HoverDrawFeature(ViewerFeature):
    """
    Hover-compatible curve draw feature.
    - DRAW mode: LMB adds a point, drag moves the last point.
    - Uses curveutils picker for ray/plane + snapping.
    """

    name = "hover_draw"

    def __init__(self):
        self.preview = None
        self.point_ids = []
        self.picker = cu.curve3DPicker(cu.curve3DPicker.MODE_VIEWPLANE)
        self.ch_points = k.CH_CURVE_POINTS
        self.ch_line = k.CH_CURVE_LINE
        self.drag_active = False
        self._last_ptnum = -1

    def on_enter(self, ctx, kwargs):
        self.picker.reset()
        self.picker.setPickMode(cu.curve3DPicker.MODE_VIEWPLANE)
        self.preview = ctx.get_service("preview")
        if self.preview is None:
            self.preview = PreviewService(ctx.scene_viewer, prefix="hover_draw")
            ctx.set_service("preview", self.preview)

        self.preview.ensure_point_channel(
            self.ch_points,
            k.COLOR_COMMITTED_ORANGE,
            radius=6.0,
            style=hou.drawableGeometryPointStyle.SmoothCircle,
        )
        self.preview.ensure_line_channel(
            self.ch_line,
            k.COLOR_COMMITTED_ORANGE,
            line_width=float(k.LINE_WIDTH),
        )
        self._sync_valid_points(ctx)
        self._update_preview(ctx)

    def on_exit(self, ctx, kwargs):
        self.drag_active = False
        self._last_ptnum = -1
        self._hide(ctx)

    def on_mouse_event(self, ctx, kwargs):
        if str(getattr(ctx, "tool_mode", "")).upper() != k.TOOL_MODE_DRAW:
            self.drag_active = False
            self._last_ptnum = -1
            return False

        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        if ctx.edit_geo is None:
            return False

        reason = ui.reason()
        dev = ui.device()

        if reason == hou.uiEventReason.Start and dev.isLeftButton():
            return self._start_draw(ctx, ui, kwargs)

        if reason == hou.uiEventReason.Active and self.drag_active:
            return self._update_drag(ctx, ui, kwargs)

        if reason == hou.uiEventReason.Changed and self.drag_active:
            self._update_drag(ctx, ui, kwargs)
            self.drag_active = False
            self._last_ptnum = -1
            return True

        return False

    def clear_curve(self, ctx):
        self.point_ids = []
        self.picker.reset()
        self._hide(ctx)

    def commit_curve(self, ctx):
        """
        Commit current curve and start a new one.
        Leaves existing geometry in place, resets active point ids.
        """
        self.point_ids = []
        self.drag_active = False
        self._last_ptnum = -1
        self._hide(ctx)

    def refresh_after_sync(self, ctx):
        self._sync_valid_points(ctx)
        self._update_preview(ctx)

    def _start_draw(self, ctx, ui_event, kwargs):
        hover = self._get_hover(ctx, kwargs)
        hitpos = self._resolve_hit_position(ctx, ui_event, hover)
        if hitpos is None:
            return False

        pt = ctx.edit_geo.createPoint()
        pt.setPosition(hitpos)
        ptnum = int(pt.number())

        if self.point_ids:
            pprev = ctx.edit_geo.point(int(self.point_ids[-1]))
            pcur = ctx.edit_geo.point(ptnum)
            if pprev is not None and pcur is not None:
                prim = ctx.edit_geo.createPolygon()
                prim.setIsClosed(False)
                prim.addVertex(pprev)
                prim.addVertex(pcur)

        self.point_ids.append(ptnum)
        self.drag_active = True
        self._last_ptnum = ptnum

        ctx.push_edit_geo()
        ctx.ensure_mesh(geo=ctx.edit_geo)
        self._update_preview(ctx)
        self._request_draw(ctx)
        return True

    def _update_drag(self, ctx, ui_event, kwargs):
        if self._last_ptnum < 0:
            return False

        hover = self._get_hover(ctx, kwargs)
        hitpos = self._resolve_hit_position(ctx, ui_event, hover)
        if hitpos is None:
            return False

        pt = ctx.edit_geo.point(int(self._last_ptnum))
        if pt is None:
            return False
        pt.setPosition(hitpos)

        ctx.push_edit_geo()
        ctx.ensure_mesh(geo=ctx.edit_geo)
        self._update_preview(ctx)
        self._request_draw(ctx)
        return True

    def _sync_valid_points(self, ctx):
        if ctx.edit_geo is None:
            self.point_ids = []
            return
        kept = []
        for ptnum in self.point_ids:
            if ctx.edit_geo.point(int(ptnum)) is not None:
                kept.append(int(ptnum))
        self.point_ids = kept

    def _update_preview(self, ctx):
        if self.preview is None or ctx.edit_geo is None:
            return
        if not self.point_ids:
            self._hide(ctx)
            return

        self.preview.set_points(self.ch_points, ctx.edit_geo, self.point_ids)

        positions = []
        for ptnum in self.point_ids:
            pt = ctx.edit_geo.point(int(ptnum))
            if pt is None:
                continue
            positions.append(pt.position())
        self.preview.set_polyline_world(self.ch_line, positions, closed=False)

    def _hide(self, ctx):
        if self.preview is None:
            return
        self.preview.hide(self.ch_points)
        self.preview.hide(self.ch_line)
        self._request_draw(ctx)

    def _request_draw(self, ctx):
        try:
            ctx.scene_viewer.curViewport().draw()
        except Exception:
            pass

    def _resolve_hit_position(self, ctx, ui_event, hover):
        try:
            rpos, rdir = ui_event.ray()
        except Exception:
            return None

        plane_orig = self._last_point_position(ctx)
        if plane_orig is None:
            plane_orig = self._hover_position(ctx, hover)

        try:
            pos = self.picker.intersect(
                ctx.scene_viewer,
                rpos,
                rdir,
                ui_event=ui_event,
                plane_orig=plane_orig,
            )
            if pos is not None:
                return hou.Vector3(pos)
        except Exception:
            pass

        hp = self._hover_position(ctx, hover)
        if hp is not None:
            return hou.Vector3(hp)

        try:
            return rpos + rdir * 1.0
        except Exception:
            return None

    def _last_point_position(self, ctx):
        if ctx.edit_geo is None or not self.point_ids:
            return None
        pt = ctx.edit_geo.point(int(self.point_ids[-1]))
        if pt is None:
            return None
        return hou.Vector3(pt.position())

    def _hover_position(self, ctx, hover):
        if not hover or not hover.get("visible") or ctx.edit_geo is None:
            return None

        ptnum = int(hover.get("point", -1))
        if ptnum >= 0:
            pt = ctx.edit_geo.point(ptnum)
            if pt is not None:
                return hou.Vector3(pt.position())

        edge = hover.get("edge")
        if edge is not None:
            p0 = ctx.edit_geo.point(int(edge[0]))
            p1 = ctx.edit_geo.point(int(edge[1]))
            if p0 is not None and p1 is not None:
                return (hou.Vector3(p0.position()) + hou.Vector3(p1.position())) * 0.5

        primnum = int(hover.get("prim", -1))
        if primnum >= 0:
            prim = ctx.edit_geo.prim(primnum)
            if prim is not None and prim.numVertices() > 0:
                center = hou.Vector3(0.0, 0.0, 0.0)
                n = 0
                for v in prim.vertices():
                    center += hou.Vector3(v.point().position())
                    n += 1
                if n > 0:
                    return center * (1.0 / float(n))

        return None

    def _get_hover(self, ctx, kwargs):
        hover = kwargs.get("hover")
        if hover:
            return hover
        hover = ctx.get_service("hover")
        if hover:
            return hover
        return None
