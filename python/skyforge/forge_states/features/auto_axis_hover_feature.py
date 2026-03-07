import hou
import resourceutils as ru

from skyforge import forge_draw as draw
from skyforge.forge_states.feature_base import ViewerFeature


class AutoAxisHoverFeature(ViewerFeature):
    """
    Hover/overlay drawables for AutoAxis modular state.
    Migrated from legacy test_auto_axis_state hover rendering.
    """

    name = "auto_axis_hover"

    def __init__(self):
        self.color_options = None
        self.edge_hover = None
        self.point_rest = None
        self.point_hover = None
        self.face_hover = None

    def on_enter(self, ctx, kwargs):
        self.color_options = ru.ColorOptions(ctx.scene_viewer)
        self._init_edge_hover(ctx)
        self._init_point_hover(ctx)
        self._init_point_rest(ctx)
        self._init_face_hover(ctx)
        self.refresh_geometry(ctx)
        self._apply_point_radius(ctx)

    def on_exit(self, ctx, kwargs):
        self._hide_edge_hover()
        self._hide_point_hover()
        self._hide_face_hover()
        if self.point_rest is not None:
            self.point_rest.show(False)

    def on_draw(self, ctx, kwargs):
        state_context = ctx.get_service("state_context")
        if state_context is None:
            return

        try:
            if state_context.isPicking():
                return
        except Exception:
            pass

        handle = kwargs["draw_handle"]
        gadget_name = state_context.gadget()

        if ctx.select_mode == "POINT":
            if self.point_rest is not None:
                self.point_rest.draw(handle)
            if gadget_name == "point_gadget":
                self._update_point_hover(ctx, state_context.component1())
            else:
                self._hide_point_hover()
            self._hide_edge_hover()

        elif ctx.select_mode == "EDGE":
            self._hide_point_hover()
            self._hide_face_hover()
            if gadget_name == "edge_gadget":
                self._update_edge_hover_from_points(ctx, state_context.component1(), state_context.component2())
            else:
                self._hide_edge_hover()

        else:  # FACE
            self._hide_point_hover()
            self._hide_edge_hover()
            if gadget_name == "face_gadget":
                self._update_face_hover(ctx, state_context.component1())
            else:
                self._hide_face_hover()

        if self.edge_hover is not None:
            self.edge_hover.draw(handle)
        if self.point_hover is not None:
            self.point_hover.draw(handle)
        if self.face_hover is not None:
            self.face_hover.draw(handle)

    def refresh_geometry(self, ctx):
        geo = ctx.edit_geo
        if geo is None:
            return
        if self.point_rest is not None:
            self.point_rest.setGeometry(geo)
        if self.point_hover is not None:
            self.point_hover.setGeometry(geo)
        if self.face_hover is not None:
            self.face_hover.setGeometry(geo)

    def apply_point_radius(self, ctx):
        self._apply_point_radius(ctx)

    def _init_edge_hover(self, ctx):
        color = self.color_options.colorFromName("PickedHandleColor")
        self.edge_hover = draw.LineFX(ctx.scene_viewer, "auto_axis_mod_edge_hover", color, line_width=3.0)
        self.edge_hover.hide()

    def _init_point_hover(self, ctx):
        color = self.color_options.colorFromName("PickedHandleColor")
        self.point_hover = hou.GeometryDrawable(
            ctx.scene_viewer,
            hou.drawableGeometryType.Point,
            "auto_axis_mod_point_hover",
        )
        self.point_hover.setParams({
            "color1": color,
            "radius": float(ctx.point_radius + ctx.point_hover_extra),
            "style": hou.drawableGeometryPointStyle.SmoothCircle,
        })
        self.point_hover.show(False)

    def _init_point_rest(self, ctx):
        color = self.color_options.colorFromName("HandleZAxisColor")
        self.point_rest = hou.GeometryDrawable(
            ctx.scene_viewer,
            hou.drawableGeometryType.Point,
            "auto_axis_mod_point_rest",
        )
        self.point_rest.setParams({
            "color1": color,
            "radius": float(ctx.point_radius),
            "style": hou.drawableGeometryPointStyle.SmoothCircle,
        })
        self.point_rest.show(True)

    def _init_face_hover(self, ctx):
        color = self.color_options.colorFromName("PickedHandleColor")
        self.face_hover = hou.GeometryDrawable(
            ctx.scene_viewer,
            hou.drawableGeometryType.Face,
            "auto_axis_mod_face_hover",
        )
        self.face_hover.setParams({
            "color1": color,
            "style": hou.drawableGeometryFaceStyle.Plain,
        })
        self.face_hover.show(False)

    def _apply_point_radius(self, ctx):
        r = float(ctx.point_radius)
        if self.point_rest is not None:
            self.point_rest.setParams({"radius": r})
        if self.point_hover is not None:
            self.point_hover.setParams({"radius": r + float(ctx.point_hover_extra)})

    def _update_edge_hover_from_points(self, ctx, p0, p1):
        if self.edge_hover is None or ctx.edit_geo is None:
            return
        pt0 = ctx.edit_geo.point(p0)
        pt1 = ctx.edit_geo.point(p1)
        if pt0 is None or pt1 is None:
            self._hide_edge_hover()
            return
        self.edge_hover.set_line(pt0.position(), pt1.position())

    def _update_point_hover(self, ctx, ptnum):
        if self.point_hover is None or ctx.edit_geo is None:
            return
        pt = ctx.edit_geo.point(ptnum)
        if pt is None:
            self._hide_point_hover()
            return
        self.point_hover.setGeometry(ctx.edit_geo)
        self.point_hover.setParams({"indices": [int(ptnum)]})
        self.point_hover.show(True)

    def _hide_edge_hover(self):
        if self.edge_hover is not None:
            self.edge_hover.hide()

    def _hide_point_hover(self):
        if self.point_hover is not None:
            self.point_hover.show(False)

    def _update_face_hover(self, ctx, primnum):
        if self.face_hover is None or ctx.edit_geo is None:
            return
        prim = ctx.edit_geo.prim(primnum)
        if prim is None:
            self._hide_face_hover()
            return
        self.face_hover.setGeometry(ctx.edit_geo)
        self.face_hover.setParams({"indices": [int(primnum)]})
        self.face_hover.show(True)

    def _hide_face_hover(self):
        if self.face_hover is not None:
            self.face_hover.show(False)
