import re

import hou

from skyforge.forge_states.feature_base import ViewerFeature


class TransversalLoopFeature(ViewerFeature):
    name = "transversal_loop"

    def __init__(self):
        self.preview_geo = None
        self.preview_drawable = None

    def on_enter(self, ctx, kwargs):
        self._init_preview(ctx)

    def on_exit(self, ctx, kwargs):
        self._hide_preview(ctx)

    def on_draw(self, ctx, kwargs):
        if self.preview_drawable is not None:
            self.preview_drawable.draw(kwargs["draw_handle"])

    def on_selection(self, ctx, kwargs):
        selection = kwargs.get("selection")
        if not selection:
            return False

        selstrs = selection.selectionStrings(True, False)
        if not selstrs:
            return False

        pair = self._first_edgepair_in_selection(selstrs)
        if pair is None:
            return False

        he = ctx.edge_to_hedge(pair[0], pair[1])
        if he < 0:
            return False

        path = ctx.mesh.edge_loop_roll(he, 10000, 1)
        if not path:
            self._hide_preview(ctx)
            return False

        self._set_preview_path(ctx, path)

        if ctx.parm_string is not None:
            ctx.parm_string.set(ctx.hedges_to_group_string(path))

        return False

    def _first_edgepair_in_selection(self, selstrs):
        # Use the very first edge token found in the selection strings.
        for s in selstrs:
            if not s:
                continue

            m = re.search(r"p(\d+)-(\d+)", s)
            if m:
                return int(m.group(1)), int(m.group(2))

            m2 = re.search(r"(\d+)\s*-\s*(\d+)", s)
            if m2:
                return int(m2.group(1)), int(m2.group(2))
        return None

    def _init_preview(self, ctx):
        self.preview_geo = hou.Geometry()
        self.preview_drawable = hou.GeometryDrawable(
            ctx.scene_viewer,
            hou.drawableGeometryType.Line,
            "pyd_loop_modular_transversal_preview",
            params={
                "style": hou.drawableGeometryLineStyle.Plain,
                "color1": (1.0, 1.0, 0.0, 1.0),
                "line_width": 3.0,
            },
        )
        self.preview_drawable.setGeometry(self.preview_geo)
        self.preview_drawable.show(False)

    def _hide_preview(self, ctx):
        if self.preview_drawable is not None:
            self.preview_drawable.show(False)
            self._request_draw(ctx)

    def _set_preview_path(self, ctx, hedges):
        if not hedges or ctx.geometry is None:
            self._hide_preview(ctx)
            return

        geo = hou.Geometry()
        poly = geo.createPolygon()
        poly.setIsClosed(False)

        src0 = int(ctx.mesh.src(hedges[0]))
        pt0 = ctx.geometry.point(src0)
        if pt0 is None:
            self._hide_preview(ctx)
            return

        p = geo.createPoint()
        p.setPosition(pt0.position())
        poly.addVertex(p)

        for he in hedges:
            dst = int(ctx.mesh.dst(he))
            pt = ctx.geometry.point(dst)
            if pt is None:
                continue
            p = geo.createPoint()
            p.setPosition(pt.position())
            poly.addVertex(p)

        if geo.intrinsicValue("pointcount") < 2:
            self._hide_preview(ctx)
            return

        self.preview_geo = geo
        self.preview_drawable.setGeometry(self.preview_geo)
        self.preview_drawable.show(True)
        self._request_draw(ctx)

    def _request_draw(self, ctx):
        try:
            ctx.scene_viewer.curViewport().draw()
        except Exception:
            pass
