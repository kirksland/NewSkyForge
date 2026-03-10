import hou
import curveutils as cu

from ..feature_base import ViewerFeature
from .. import constants as k


class CurveDrawFeature(ViewerFeature):
    """
    Minimal curve drawing feature for modular composition tests.
    - DRAW mode: LMB appends a point at hit position.
    - Maintains a polyline preview + point preview channels.
    - Writes real points/prims in ctx.edit_geo so MoveFeature can edit them.
    """

    name = "curve_draw"

    def __init__(self):
        self.preview = None
        self.point_ids = []
        self.picker = cu.curve3DPicker(cu.curve3DPicker.MODE_VIEWPLANE)
        self.ch_points = k.CH_CURVE_POINTS
        self.ch_line = k.CH_CURVE_LINE

    def on_enter(self, ctx, kwargs):
        self.picker.reset()
        self.picker.setPickMode(cu.curve3DPicker.MODE_VIEWPLANE)
        self.preview = ctx.get_service("preview")
        if self.preview is None:
            return
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
        self._hide(ctx)

    def on_mouse_event(self, ctx, kwargs):
        if str(getattr(ctx, "tool_mode", "")).upper() != k.TOOL_MODE_DRAW:
            return False

        ui = kwargs.get("ui_event")
        if ui is None:
            return False
        if ui.reason() != hou.uiEventReason.Start:
            return False
        dev = ui.device()
        if not dev.isLeftButton():
            return False

        hit = ctx.get_service("hit") or {}
        hitpos = self._resolve_hit_position(ctx, ui, hit)
        if hitpos is None or ctx.edit_geo is None:
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
        ctx.push_edit_geo()
        ctx.ensure_mesh(geo=ctx.edit_geo)
        self._update_preview(ctx)
        self._request_draw(ctx)
        return True

    def clear_curve(self, ctx):
        self.point_ids = []
        self.picker.reset()
        self._hide(ctx)

    def refresh_after_sync(self, ctx):
        self._sync_valid_points(ctx)
        self._update_preview(ctx)

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
        try:
            ctx.scene_viewer.curViewport().draw()
        except Exception:
            pass

    def _request_draw(self, ctx):
        try:
            ctx.scene_viewer.curViewport().draw()
        except Exception:
            pass

    def _resolve_hit_position(self, ctx, ui_event, hit):
        """
        Resolve point placement via SideFX curve picker behavior.
        - mode: view plane
        - plane origin: last placed point when available
        - honors snapping / construction plane priorities
        """
        try:
            rpos, rdir = ui_event.ray()
        except Exception:
            return None

        plane_orig = self._last_point_position(ctx)
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

        # last-resort fallback to avoid dead clicks
        hp = hit.get("hitpos")
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
