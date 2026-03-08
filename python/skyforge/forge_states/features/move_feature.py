import hou
import resourceutils as ru

from skyforge import forge_mesh as mesh
from skyforge import forge_motion as motion
from ..feature_base import ViewerFeature
from .. import preview_channels as ch
from .. import constants as k


class MoveFeature(ViewerFeature):
    """
    MOVE tool migration from legacy AutoAxis state.
    Handles point/edge/face drag with LOCAL/WORLD/EDGE axis picking.
    """

    name = "auto_axis_move"

    def __init__(self):
        self.enable_dragger = False
        self.enable_guide_line = True

        self.dragger = None
        self._dragger_active = False
        self.color_options = None
        self.preview = None
        self.guide_channel = ch.CH_MOVE_GUIDE
        self.guide_len = float(k.MOVE_GUIDE_LENGTH)

        self._pending = False
        self._is_dragging = False
        self._undo_opened = False

        self._drag_mode_used = None
        self._drag_select_used = None

        self._ptnum = -1
        self._primnum = -1
        self._affected_ptnums = None
        self._edge_p0 = -1
        self._edge_p1 = -1

        self._origin = None
        self._start_mouse = None
        self._last_mouse = None
        self._drag_axis = None

    def on_enter(self, ctx, kwargs):
        """Initialize drag runtime and guide preview channel."""
        self.dragger = hou.ViewerStateDragger("dragger") if self.enable_dragger else None
        self._dragger_active = False
        self.color_options = ru.ColorOptions(ctx.scene_viewer)
        self.preview = ctx.get_service("preview")
        if self.enable_guide_line and self.preview is not None:
            color = self.color_options.colorFromName("PickedHandleColor")
            self.preview.ensure_line_channel(self.guide_channel, color, line_width=float(k.MOVE_GUIDE_LINE_WIDTH))
        self._reset_runtime(close_undo=False, scene_viewer=ctx.scene_viewer)

    def on_exit(self, ctx, kwargs):
        """Stop active drag and hide guide visuals."""
        self._cleanup_drag(ctx, close_undo=True)
        self._hide_guide_line()

    def on_draw(self, ctx, kwargs):
        """No local draw: guide is rendered through PreviewFeature."""
        return

    def is_interacting(self):
        """Return True while a move drag/undo transaction is active."""
        return bool(self._pending or self._is_dragging or self._undo_opened)

    def on_mouse_event(self, ctx, kwargs):
        """Main move interaction entrypoint (start/update/finish)."""
        if ctx.tool_mode != "MOVE":
            return False

        ui_event = kwargs.get("ui_event")
        if ui_event is None:
            return False

        if ctx.edit_geo is None:
            return False

        reason = ui_event.reason()

        try:
            mx, my = ui_event.device().mouseX(), ui_event.device().mouseY()
            cur_mouse = hou.Vector2(mx, my)
        except Exception:
            return False

        if reason == hou.uiEventReason.Start:
            hit = ctx.get_service("hit") or {}
            return self._move_start(ctx, hit, cur_mouse)

        if reason in (hou.uiEventReason.Active, hou.uiEventReason.Changed):
            if not (self._pending or self._is_dragging or self._undo_opened):
                return False
            return self._move_update(ctx, ui_event, reason, cur_mouse)

        return False

    def _move_start(self, ctx, hit, cur_mouse):
        """Capture selection origin and open state undo."""
        self._pending = True
        self._start_mouse = cur_mouse
        self._last_mouse = cur_mouse
        self._drag_mode_used = ctx.mode
        self._drag_select_used = ctx.select_mode
        self._is_dragging = False
        self._drag_axis = None
        self._affected_ptnums = None

        # Optional external composition hook:
        # state can inject a custom set of points/origin for move start.
        override = ctx.get_service("move_override")
        if override:
            try:
                ptnums = [int(p) for p in (override.get("ptnums") or [])]
            except Exception:
                ptnums = []
            origin = override.get("origin")
            anchor = int(override.get("anchor_ptnum", ptnums[0] if ptnums else -1))
            sel = str(override.get("select_mode", "POINT")).upper()
            ctx.set_service("move_override", None)

            if not ptnums or origin is None:
                self._reset_runtime(close_undo=False, scene_viewer=ctx.scene_viewer)
                return False

            self._drag_select_used = sel
            self._ptnum = anchor
            self._affected_ptnums = ptnums
            self._origin = origin

            self._hide_guide_line()
            try:
                ctx.scene_viewer.beginStateUndo("AutoAxis move")
                self._undo_opened = True
            except Exception:
                self._undo_opened = False
            return True

        if ctx.select_mode == "POINT":
            ptnum = int(hit.get("point", -1))
            if ptnum < 0:
                self._reset_runtime(close_undo=False, scene_viewer=ctx.scene_viewer)
                return False
            pt = ctx.edit_geo.point(ptnum)
            if pt is None:
                self._reset_runtime(close_undo=False, scene_viewer=ctx.scene_viewer)
                return False
            self._ptnum = ptnum
            self._origin = pt.position()
            self._affected_ptnums = [ptnum]

        elif ctx.select_mode == "EDGE":
            edge = hit.get("edge")
            if edge is None:
                self._reset_runtime(close_undo=False, scene_viewer=ctx.scene_viewer)
                return False
            p0 = int(edge[0])
            p1 = int(edge[1])
            pt0 = ctx.edit_geo.point(p0)
            pt1 = ctx.edit_geo.point(p1)
            if pt0 is None or pt1 is None:
                self._reset_runtime(close_undo=False, scene_viewer=ctx.scene_viewer)
                return False
            self._edge_p0 = p0
            self._edge_p1 = p1
            self._origin = (pt0.position() + pt1.position()) * 0.5
            self._affected_ptnums = [p0, p1]

        else:  # FACE
            primnum = int(hit.get("prim", -1))
            if primnum < 0:
                self._reset_runtime(close_undo=False, scene_viewer=ctx.scene_viewer)
                return False
            prim = ctx.edit_geo.prim(primnum)
            if prim is None:
                self._reset_runtime(close_undo=False, scene_viewer=ctx.scene_viewer)
                return False
            self._primnum = primnum
            self._origin = mesh.prim_center(prim)
            self._affected_ptnums = mesh.prim_points_unique(prim)

        self._hide_guide_line()

        try:
            ctx.scene_viewer.beginStateUndo("AutoAxis move")
            self._undo_opened = True
        except Exception:
            self._undo_opened = False

        return True

    def _move_update(self, ctx, ui_event, reason, cur_mouse):
        """Resolve axis, apply delta on affected points, push to stash."""
        if self._pending:
            md = cur_mouse - self._start_mouse

            mode = self._drag_mode_used or ctx.mode
            sel = self._drag_select_used or ctx.select_mode
            origin = self._origin

            if sel == "FACE" and mode == "EDGE":
                mode = "LOCAL"

            if mode == "EDGE":
                if sel == "POINT":
                    edge_dir, sign = self._pick_connected_edge_dir_from_point(ctx, origin, md, self._ptnum)
                    if edge_dir is not None:
                        self._drag_axis = edge_dir * sign
                    else:
                        origin2, axes = motion.axes_for_space(ctx.edit_geo, "LOCAL", "POINT", self._ptnum, self._primnum, mesh.prim_center)
                        if origin2 is not None and axes is not None:
                            origin = origin2
                        choice, sign = motion.pick_axis_from_mouse(ctx.scene_viewer, origin, md, axes)
                        if choice is None and reason != hou.uiEventReason.Changed:
                            return True
                        if choice is None:
                            choice, sign = "Z", 1.0
                        self._drag_axis = axes[choice].normalized() * sign

                elif sel == "EDGE":
                    t, sign = self._pick_axis_for_selected_edge(ctx, origin, md, self._edge_p0, self._edge_p1)
                    if t is None:
                        axes = self._world_axes()
                        choice, sign = motion.pick_axis_from_mouse(ctx.scene_viewer, origin, md, axes)
                        if choice is None and reason != hou.uiEventReason.Changed:
                            return True
                        if choice is None:
                            choice, sign = "Z", 1.0
                        self._drag_axis = axes[choice].normalized() * sign
                    else:
                        self._drag_axis = t * sign

                else:
                    origin, axes = motion.axes_for_space(ctx.edit_geo, "LOCAL", "FACE", self._ptnum, self._primnum, mesh.prim_center)
                    if origin is None or axes is None:
                        return False
                    choice, sign = motion.pick_axis_from_mouse(ctx.scene_viewer, origin, md, axes)
                    if choice is None and reason != hou.uiEventReason.Changed:
                        return True
                    if choice is None:
                        choice, sign = "Z", 1.0
                    self._drag_axis = axes[choice].normalized() * sign

            else:
                if sel == "EDGE":
                    origin = self._origin
                    if mode == "WORLD":
                        axes = self._world_axes()
                    else:
                        pt_for_local = self._edge_p0
                        origin2, axes = motion.axes_for_space(ctx.edit_geo, "LOCAL", "POINT", pt_for_local, self._primnum, mesh.prim_center)
                        if origin2 is None or axes is None:
                            axes = self._world_axes()
                else:
                    origin, axes = motion.axes_for_space(ctx.edit_geo, mode, sel, self._ptnum, self._primnum, mesh.prim_center)
                    if origin is None or axes is None:
                        return False

                choice, sign = motion.pick_axis_from_mouse(ctx.scene_viewer, origin, md, axes)
                if choice is None and reason != hou.uiEventReason.Changed:
                    return True
                if choice is None:
                    choice, sign = "Z", 1.0
                self._drag_axis = axes[choice].normalized() * sign

            self._update_guide_line(origin, self._drag_axis)
            if self.dragger is None:
                self._pending = False
                self._is_dragging = True
                self._last_mouse = cur_mouse
                if reason == hou.uiEventReason.Changed:
                    self._cleanup_drag(ctx, close_undo=True)
                return True

            self.dragger.startDragAlongLine(ui_event, origin, self._drag_axis)
            self._dragger_active = True
            self._pending = False
            self._is_dragging = True

        if self.dragger is None or not self._dragger_active:
            delta = self._delta_from_mouse_without_dragger(ctx, cur_mouse)
            if delta is not None and delta.length() > 0.0:
                mesh.apply_delta_to_points(ctx.edit_geo, self._affected_ptnums, delta)
                mesh.touch_point_positions(ctx.edit_geo)
                ctx.push_edit_geo()
            if reason == hou.uiEventReason.Changed:
                self._cleanup_drag(ctx, close_undo=True)
            return True

        try:
            delta = self.dragger.drag(ui_event)["delta_position"]
        except Exception:
            if reason == hou.uiEventReason.Changed:
                self._cleanup_drag(ctx, close_undo=True)
            return False

        mesh.apply_delta_to_points(ctx.edit_geo, self._affected_ptnums, delta)
        mesh.touch_point_positions(ctx.edit_geo)
        ctx.push_edit_geo()

        sel = self._drag_select_used or ctx.select_mode
        if sel == "POINT":
            pt = ctx.edit_geo.point(self._ptnum)
            if pt is not None:
                self._update_guide_line(pt.position(), self._drag_axis)
        elif sel == "EDGE":
            mid = mesh.edge_midpoint(ctx.edit_geo, self._edge_p0, self._edge_p1)
            if mid is not None:
                self._update_guide_line(mid, self._drag_axis)
        else:
            prim = ctx.edit_geo.prim(self._primnum)
            if prim is not None:
                c = mesh.prim_center(prim)
                if c is not None:
                    self._update_guide_line(c, self._drag_axis)

        if reason == hou.uiEventReason.Changed:
            self._cleanup_drag(ctx, close_undo=True)

        return True

    def _update_guide_line(self, origin, axis_dir):
        """Update guide channel from origin and selected axis."""
        if not self.enable_guide_line or self.preview is None:
            return
        if origin is None or axis_dir is None or axis_dir.length() < 1e-6:
            self.preview.hide(self.guide_channel)
            return
        a = axis_dir.normalized()
        self.preview.set_line_segment_world(self.guide_channel, origin, origin + a * self.guide_len)

    def _hide_guide_line(self):
        """Hide move guide channel."""
        if self.preview is not None:
            self.preview.hide(self.guide_channel)

    def _cleanup_drag(self, ctx, close_undo):
        """Cleanup wrapper preserving undo close behavior."""
        self._reset_runtime(close_undo=close_undo, scene_viewer=ctx.scene_viewer)

    def _reset_runtime(self, close_undo, scene_viewer):
        """Reset transient drag state and optionally close state undo."""
        self._pending = False
        try:
            if self.dragger is not None and self._dragger_active:
                self.dragger.endDrag()
        except Exception:
            pass
        self._dragger_active = False

        self._hide_guide_line()

        self._is_dragging = False
        self._drag_mode_used = None
        self._drag_select_used = None
        self._drag_axis = None

        self._ptnum = -1
        self._primnum = -1
        self._affected_ptnums = None
        self._edge_p0 = -1
        self._edge_p1 = -1
        self._origin = None
        self._start_mouse = None
        self._last_mouse = None

        if close_undo and self._undo_opened:
            try:
                scene_viewer.endStateUndo()
            except Exception:
                pass
            self._undo_opened = False

    def _pick_connected_edge_dir_from_point(self, ctx, origin, mouse_delta, ptnum):
        """Pick best outgoing edge direction from point using mouse motion."""
        nbrs = mesh.connected_neighbors(ctx.edit_geo, ptnum)
        if not nbrs:
            return None, 1.0

        edge_dirs = {}
        for idx, n in enumerate(nbrs):
            npt = ctx.edit_geo.point(n)
            if npt is None:
                continue
            v = npt.position() - origin
            if v.length() > 1e-6:
                edge_dirs["E{0}".format(idx)] = v

        if not edge_dirs:
            return None, 1.0

        key, sign = motion.pick_axis_from_mouse(ctx.scene_viewer, origin, mouse_delta, edge_dirs)
        if key is None:
            return None, 1.0
        return edge_dirs[key].normalized(), sign

    def _pick_axis_for_selected_edge(self, ctx, origin, mouse_delta, p0, p1):
        """Pick tangent orientation for currently selected edge."""
        t = mesh.edge_tangent(ctx.edit_geo, p0, p1)
        if t is None:
            return None, 1.0
        key, sign = motion.pick_axis_from_mouse(ctx.scene_viewer, origin, mouse_delta, {"T": t})
        if key is None:
            return None, 1.0
        return t, sign

    def _world_axes(self):
        """Return canonical world axis dictionary."""
        return {
            "X": hou.Vector3(1, 0, 0),
            "Y": hou.Vector3(0, 1, 0),
            "Z": hou.Vector3(0, 0, 1),
        }

    def _delta_from_mouse_without_dragger(self, ctx, cur_mouse):
        """Fallback axis-projected delta when dragger is disabled."""
        if self._drag_axis is None or self._origin is None:
            self._last_mouse = cur_mouse
            return None

        if self._last_mouse is None:
            self._last_mouse = cur_mouse
            return None

        o2 = motion.world_to_screen(ctx.scene_viewer, self._origin)
        p2 = motion.world_to_screen(ctx.scene_viewer, self._origin + self._drag_axis.normalized() * 0.1)
        if o2 is None or p2 is None:
            self._last_mouse = cur_mouse
            return None

        axis2 = p2 - o2
        px = axis2.length()
        if px < 1e-6:
            self._last_mouse = cur_mouse
            return None

        step = cur_mouse - self._last_mouse
        self._last_mouse = cur_mouse

        dpx = step.dot(axis2.normalized())
        units_per_px = 0.1 / px
        dist = float(dpx * units_per_px)
        return self._drag_axis.normalized() * dist
