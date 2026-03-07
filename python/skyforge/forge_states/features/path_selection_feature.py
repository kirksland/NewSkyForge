import hou
import resourceutils as ru

from skyforge.forge_states.feature_base import ViewerFeature
from skyforge.forge_states.style import (
    LINE_WIDTH,
    COLOR_PREVIEW_YELLOW,
    COLOR_COMMITTED_ORANGE,
)


class PathSelectionFeature(ViewerFeature):
    name = "path_selection"

    def __init__(self):
        self.color_options = None
        self.hover_geo = None
        self.hover_drawable = None
        self.path_geo = None
        self.path_drawable = None

    def on_enter(self, ctx, kwargs):
        self.color_options = ru.ColorOptions(ctx.scene_viewer)
        self._init_drawables(ctx)
        ctx.ensure_mesh()
        ctx.load_selection_from_grstr()
        self.refresh_drawables(ctx)

    def on_exit(self, ctx, kwargs):
        self._hide_hover()
        self._hide_path()

    def on_draw(self, ctx, kwargs):
        handle = kwargs["draw_handle"]
        if self.path_drawable is not None:
            self.path_drawable.draw(handle)
        if self.hover_drawable is not None:
            self.hover_drawable.draw(handle)

    def on_mouse_event(self, ctx, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        reason = ui.reason()
        dev = ui.device()

        if reason == hou.uiEventReason.Located:
            hit = self._hit_edge(ctx, ui)
            if hit is None:
                ctx.hover_he = -1
                self._hide_hover()
                return False
            p0, p1 = hit
            he = ctx.edge_to_hedge(p0, p1)
            if he < 0:
                return False
            ctx.hover_he = he
            self._set_hover_edge(ctx, he)
            return False

        if reason != hou.uiEventReason.Start:
            return False
        if not dev.isLeftButton():
            return False

        hit = self._hit_edge(ctx, ui)
        if hit is None:
            # Empty click resets all selection state.
            ctx.clear_selection()
            ctx.sync_grstr_from_selection()
            self.refresh_drawables(ctx)
            return True

        p0, p1 = hit
        he = ctx.edge_to_hedge(p0, p1)
        if he < 0:
            return False

        if dev.isShiftKey():
            ctx.append_committed_hedge(he)
        else:
            ctx.set_committed_hedges([he])

        ctx.set_basegroup_from_hedge(he)
        ctx.sync_grstr_from_selection()
        self.refresh_drawables(ctx)
        return True

    def refresh_drawables(self, ctx):
        self._set_path(ctx, ctx.committed_hedges)
        if ctx.hover_he >= 0:
            self._set_hover_edge(ctx, ctx.hover_he)
        else:
            self._hide_hover()

    def _init_drawables(self, ctx):
        self.path_geo = hou.Geometry()
        self.path_drawable = hou.GeometryDrawable(
            ctx.scene_viewer,
            hou.drawableGeometryType.Line,
            "path_move_lab_committed",
            params={
                "style": hou.drawableGeometryLineStyle.Plain,
                "color1": COLOR_COMMITTED_ORANGE,
                "line_width": float(LINE_WIDTH),
            },
        )
        self.path_drawable.setGeometry(self.path_geo)
        self.path_drawable.show(False)

        self.hover_geo = hou.Geometry()
        self.hover_drawable = hou.GeometryDrawable(
            ctx.scene_viewer,
            hou.drawableGeometryType.Line,
            "path_move_lab_hover",
            params={
                "style": hou.drawableGeometryLineStyle.Plain,
                "color1": COLOR_PREVIEW_YELLOW,
                "line_width": float(LINE_WIDTH),
            },
        )
        self.hover_drawable.setGeometry(self.hover_geo)
        self.hover_drawable.show(False)

    def _set_path(self, ctx, hedges):
        if not hedges or ctx.edit_geo is None:
            self._hide_path()
            return

        geo = hou.Geometry()
        poly = geo.createPolygon()
        poly.setIsClosed(False)

        src0 = int(ctx.mesh.src(hedges[0]))
        pt0 = ctx.edit_geo.point(src0)
        if pt0 is None:
            self._hide_path()
            return

        first = geo.createPoint()
        first.setPosition(pt0.position())
        poly.addVertex(first)

        for he in hedges:
            dst = int(ctx.mesh.dst(he))
            pt = ctx.edit_geo.point(dst)
            if pt is None:
                continue
            p = geo.createPoint()
            p.setPosition(pt.position())
            poly.addVertex(p)

        if int(geo.intrinsicValue("pointcount")) < 2:
            self._hide_path()
            return

        self.path_geo = geo
        self.path_drawable.setGeometry(self.path_geo)
        self.path_drawable.show(True)

    def _set_hover_edge(self, ctx, hedge):
        if ctx.edit_geo is None:
            self._hide_hover()
            return
        p0 = int(ctx.mesh.src(hedge))
        p1 = int(ctx.mesh.dst(hedge))
        pt0 = ctx.edit_geo.point(p0)
        pt1 = ctx.edit_geo.point(p1)
        if pt0 is None or pt1 is None:
            self._hide_hover()
            return

        geo = hou.Geometry()
        poly = geo.createPolygon()
        poly.setIsClosed(False)
        a = geo.createPoint()
        a.setPosition(pt0.position())
        b = geo.createPoint()
        b.setPosition(pt1.position())
        poly.addVertex(a)
        poly.addVertex(b)

        self.hover_geo = geo
        self.hover_drawable.setGeometry(self.hover_geo)
        self.hover_drawable.show(True)

    def _hide_hover(self):
        if self.hover_drawable is not None:
            self.hover_drawable.show(False)

    def _hide_path(self):
        if self.path_drawable is not None:
            self.path_drawable.show(False)

    def _hit_edge(self, ctx, ui_event):
        if ctx.gi is None:
            return None

        rpos, rdir = ui_event.ray()
        if not ctx.gi.intersect(rpos, rdir):
            return None
        closest_edge = ctx.gi._closest_edge()
        if closest_edge is None:
            return None
        pts = closest_edge.points()
        if len(pts) < 2:
            return None
        return int(pts[0].number()), int(pts[1].number())
