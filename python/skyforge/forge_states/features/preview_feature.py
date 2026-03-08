import hou
import resourceutils as ru

from skyforge.forge_states.feature_base import ViewerFeature
from skyforge.forge_states.preview_service import PreviewService


class PreviewFeature(ViewerFeature):
    """
    Shared preview feature.
    - Owns PreviewService lifecycle.
    - Optionally manages generic point/edge/face hover channels.
    - Draws all channels in one place.
    """

    name = "preview"

    def __init__(self, prefix="preview", enable_hover=False):
        self.prefix = prefix
        self.enable_hover = bool(enable_hover)
        self.preview = None
        self.color_options = None

        self.ch_edge = "hover_edge"
        self.ch_point_rest = "point_rest"
        self.ch_point_hover = "hover_point"
        self.ch_face = "hover_face"

    def on_enter(self, ctx, kwargs):
        """Create/reuse preview service and initialize optional hover channels."""
        self.preview = ctx.get_service("preview")
        if self.preview is None:
            self.preview = PreviewService(ctx.scene_viewer, prefix=self.prefix)
            ctx.set_service("preview", self.preview)

        if self.enable_hover:
            self.color_options = ru.ColorOptions(ctx.scene_viewer)
            self._init_hover_channels(ctx)
            self.refresh_geometry(ctx)
            self.apply_point_radius(ctx)

    def on_exit(self, ctx, kwargs):
        """Hide all channels when feature exits."""
        if self.preview is not None:
            self.preview.hide_all()

    def on_mouse_event(self, ctx, kwargs):
        """
        Update generic hover channels from standardized `ctx.services['hit']`.
        No-op when hover mode is disabled.
        """
        if not self.enable_hover or self.preview is None:
            return False

        hit = ctx.get_service("hit")
        if not hit:
            self._hide_hover_channels()
            return False

        mode = getattr(ctx, "select_mode", "EDGE")

        if mode == "POINT":
            self.preview.hide(self.ch_edge)
            self.preview.hide(self.ch_face)
            self._set_rest_points(ctx)

            ptnum = int(hit.get("point", -1))
            if ptnum >= 0:
                self.preview.set_points(self.ch_point_hover, ctx.edit_geo, [ptnum])
            else:
                self.preview.hide(self.ch_point_hover)
            return False

        if mode == "EDGE":
            self.preview.hide(self.ch_point_rest)
            self.preview.hide(self.ch_point_hover)
            self.preview.hide(self.ch_face)

            edge = hit.get("edge")
            if edge is None or ctx.edit_geo is None:
                self.preview.hide(self.ch_edge)
                return False

            p0, p1 = int(edge[0]), int(edge[1])
            pt0 = ctx.edit_geo.point(p0)
            pt1 = ctx.edit_geo.point(p1)
            if pt0 is None or pt1 is None:
                self.preview.hide(self.ch_edge)
                return False
            self.preview.set_line_segment_world(self.ch_edge, pt0.position(), pt1.position())
            return False

        # FACE
        self.preview.hide(self.ch_point_rest)
        self.preview.hide(self.ch_point_hover)
        self.preview.hide(self.ch_edge)
        primnum = int(hit.get("prim", -1))
        if primnum >= 0:
            self.preview.set_faces(self.ch_face, ctx.edit_geo, [primnum])
        else:
            self.preview.hide(self.ch_face)
        return False

    def on_draw(self, ctx, kwargs):
        """Draw all preview channels."""
        if self.preview is not None:
            self.preview.draw_all(kwargs["draw_handle"])

    def refresh_geometry(self, ctx):
        """Refresh geometry-driven channels after stash sync."""
        if not self.enable_hover:
            return
        self._set_rest_points(ctx)

    def apply_point_radius(self, ctx):
        """Update point hover/rest channel radii from context values."""
        if not self.enable_hover or self.preview is None:
            return
        r = float(getattr(ctx, "point_radius", 5.0))
        extra = float(getattr(ctx, "point_hover_extra", 2.0))
        self.preview.set_point_channel_params(self.ch_point_rest, radius=r)
        self.preview.set_point_channel_params(self.ch_point_hover, radius=r + extra)

    def _init_hover_channels(self, ctx):
        """Initialize default hover channels and visual styles."""
        col_hover = self.color_options.colorFromName("PickedHandleColor")
        col_rest = self.color_options.colorFromName("HandleZAxisColor")

        self.preview.ensure_line_channel(self.ch_edge, col_hover, line_width=3.0)
        self.preview.ensure_point_channel(
            self.ch_point_rest,
            col_rest,
            radius=float(ctx.point_radius),
            style=hou.drawableGeometryPointStyle.SmoothCircle,
        )
        self.preview.ensure_point_channel(
            self.ch_point_hover,
            col_hover,
            radius=float(ctx.point_radius + ctx.point_hover_extra),
            style=hou.drawableGeometryPointStyle.SmoothCircle,
        )
        self.preview.ensure_face_channel(
            self.ch_face,
            col_hover,
            style=hou.drawableGeometryFaceStyle.Plain,
        )

    def _set_rest_points(self, ctx):
        """Populate the persistent 'rest points' channel with all points."""
        if self.preview is None or ctx.edit_geo is None:
            return
        npts = int(ctx.edit_geo.intrinsicValue("pointcount"))
        if npts <= 0:
            self.preview.hide(self.ch_point_rest)
            return
        self.preview.set_points(self.ch_point_rest, ctx.edit_geo, range(npts))

    def _hide_hover_channels(self):
        """Hide all generic hover channels."""
        if self.preview is None:
            return
        self.preview.hide(self.ch_edge)
        self.preview.hide(self.ch_point_rest)
        self.preview.hide(self.ch_point_hover)
        self.preview.hide(self.ch_face)
