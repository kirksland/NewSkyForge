import re

import hou

from skyforge.forge_states.feature_base import ViewerFeature


class TransversalLoopFeature(ViewerFeature):
    name = "transversal_loop"

    def __init__(self):
        self.preview_geo = None
        self.preview_drawable = None
        self.mode = "roll"  # "roll" (transversal) or "quad"

    def on_enter(self, ctx, kwargs):
        self._init_preview(ctx)
        print("[SkyForge] TransversalLoopFeature mode:", self.mode, "(R=roll, Q=quad, X=toggle)")

    def on_exit(self, ctx, kwargs):
        self._hide_preview(ctx)

    def on_draw(self, ctx, kwargs):
        if self.preview_drawable is not None:
            self.preview_drawable.draw(kwargs["draw_handle"])

    def on_key_event(self, ctx, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        dev = ui.device()
        if dev.isAutoRepeat():
            return False

        key = (dev.keyString() or "").lower()
        if key == "&":
            self.mode = "roll"
            print("[SkyForge] Transversal loop mode -> roll")
            return True
        if key == "q":
            self.mode = "quad"
            print("[SkyForge] Transversal loop mode -> quad")
            return True
        if key == "x":
            self.mode = "quad" if self.mode == "roll" else "roll"
            print("[SkyForge] Transversal loop mode ->", self.mode)
            return True
        return False

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

        self._set_basegroup_from_points(ctx, pair[0], pair[1])
        path = self._compute_loop(ctx, he)
        if not path:
            self._hide_preview(ctx)
            return False

        self._set_preview_path(ctx, path)

        if ctx.parm_string is not None:
            ctx.parm_string.set(ctx.hedges_to_group_string(path))

        return False

    def on_mouse_event(self, ctx, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        if ui.reason() != hou.uiEventReason.Start:
            return False

        dev = ui.device()
        if not dev.isLeftButton():
            return False

        pair = self._hit_edge(ctx, ui)
        if pair is None:
            return False

        p0, p1 = pair
        he = ctx.edge_to_hedge(p0, p1)
        if he < 0:
            return True

        self._set_basegroup_from_points(ctx, p0, p1)
        path = self._compute_loop(ctx, he)
        if not path:
            self._hide_preview(ctx)
            return True

        self._set_preview_path(ctx, path)
        if ctx.parm_string is not None:
            ctx.parm_string.set(ctx.hedges_to_group_string(path))
        return True

    def _compute_loop(self, ctx, he):
        if self.mode == "quad":
            return ctx.mesh.edge_loop_quad(he, 10000, 1)
        return ctx.mesh.edge_loop_roll(he, 10000, 1)

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
        seg_count = 0
        for he in hedges:
            src = int(ctx.mesh.src(he))
            dst = int(ctx.mesh.dst(he))
            psrc = ctx.geometry.point(src)
            pt = ctx.geometry.point(dst)
            if psrc is None or pt is None:
                continue

            # Draw each loop edge as an independent segment to avoid
            # visual connectors between non-consecutive loop members.
            poly = geo.createPolygon()
            poly.setIsClosed(False)

            p0 = geo.createPoint()
            p0.setPosition(psrc.position())
            poly.addVertex(p0)

            p1 = geo.createPoint()
            p1.setPosition(pt.position())
            poly.addVertex(p1)
            seg_count += 1

        if seg_count == 0:
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
        return pts[0].number(), pts[1].number()

    def _set_basegroup_from_points(self, ctx, p0, p1):
        if ctx.node is None:
            return
        parm = ctx.node.parm("basegroup")
        if parm is None:
            return
        parm.set(f"p{int(p0)}-{int(p1)}")
