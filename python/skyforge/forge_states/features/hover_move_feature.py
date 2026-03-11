import hou
import curveutils as cu

from skyforge import forge_mesh as mesh
from ..feature_base import ViewerFeature


class HoverMoveFeature(ViewerFeature):
    """
    Hover-driven move feature using HoverGadgetFeature payload.

    - LMB drag moves hovered point/edge/face.
    - Uses curveutils.curve3DPicker for view-plane ray drag.
    - No persistent selection: acts on current hover only.
    """

    name = "hover_move"

    def __init__(self):
        self.debug = False
        self.picker = cu.curve3DPicker(cu.curve3DPicker.MODE_VIEWPLANE)
        self.drag_active = False
        self.drag_plane_origin = None
        self.last_world_pos = None
        self.drag_ptnums = []
        self._undo_opened = False

    def on_enter(self, ctx, kwargs):
        self.picker.reset()
        self.picker.setPickMode(cu.curve3DPicker.MODE_VIEWPLANE)
        self._end_drag(ctx, commit=False)

    def on_exit(self, ctx, kwargs):
        self._end_drag(ctx, commit=False)

    def on_mouse_event(self, ctx, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        if ctx.edit_geo is None:
            return False

        reason = ui.reason()
        dev = ui.device()

        if reason == hou.uiEventReason.Start and dev.isLeftButton():
            return self._handle_start(ctx, ui, kwargs)

        if reason == hou.uiEventReason.Active and self.drag_active:
            return self._handle_active(ctx, ui)

        if reason == hou.uiEventReason.Changed and self.drag_active:
            self._handle_active(ctx, ui)
            self._end_drag(ctx, commit=True)
            return True

        return False

    def _handle_start(self, ctx, ui_event, kwargs):
        hover = self._get_hover(ctx, kwargs)
        ptnums, origin = self._hover_to_points_and_origin(ctx, hover)
        if not ptnums or origin is None:
            return False

        try:
            rpos, rdir = ui_event.ray()
        except Exception:
            return False

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
        self.drag_ptnums = list(ptnums)
        self.drag_active = True

        try:
            ctx.scene_viewer.beginStateUndo("Hover move")
            self._undo_opened = True
        except Exception:
            self._undo_opened = False

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

        mesh.apply_delta_to_points(ctx.edit_geo, self.drag_ptnums, delta)
        mesh.touch_point_positions(ctx.edit_geo)
        ctx.push_edit_geo()
        ctx.ensure_mesh(geo=ctx.edit_geo)

        self.last_world_pos = hou.Vector3(cur)
        return True

    def _end_drag(self, ctx, commit):
        if not self.drag_active:
            return
        self.drag_active = False
        self.drag_plane_origin = None
        self.last_world_pos = None
        self.drag_ptnums = []
        if commit and self._undo_opened:
            try:
                ctx.scene_viewer.endStateUndo()
            except Exception:
                pass
        self._undo_opened = False

    def _get_hover(self, ctx, kwargs):
        hover = kwargs.get("hover")
        if hover:
            return hover
        hover = ctx.get_service("hover")
        if hover:
            return hover
        return ctx.get_service("hover_payload")

    def _hover_to_points_and_origin(self, ctx, hover):
        if not hover or not hover.get("visible"):
            return [], None

        if ctx.edit_geo is None:
            return [], None

        ptnum = int(hover.get("point", -1))
        if ptnum >= 0:
            pt = ctx.edit_geo.point(ptnum)
            if pt is None:
                return [], None
            return [ptnum], pt.position()

        edge = hover.get("edge")
        if edge is not None:
            p0 = int(edge[0])
            p1 = int(edge[1])
            pt0 = ctx.edit_geo.point(p0)
            pt1 = ctx.edit_geo.point(p1)
            if pt0 is None or pt1 is None:
                return [], None
            origin = (pt0.position() + pt1.position()) * 0.5
            return [p0, p1], origin

        primnum = int(hover.get("prim", -1))
        if primnum >= 0:
            prim = ctx.edit_geo.prim(primnum)
            if prim is None:
                return [], None
            origin = mesh.prim_center(prim)
            pts = mesh.prim_points_unique(prim)
            return pts or [], origin

        return [], None
