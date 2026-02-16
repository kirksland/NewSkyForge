"""Viewer state used to test auto-axis transform and loop-cut interactions.

The state edits a local `hou.Geometry`, keeps it synced with an internal stash SOP,
and updates viewer gadgets/drawables as edits happen.
"""

import hou
import viewerstate.utils as su
import resourceutils as ru

from skyforge.forge_draw import LineFX
from skyforge.forge_mesh import (
    prim_points_unique,
    prim_center,
    connected_neighbors,
    edge_midpoint,
    edge_tangent,
    apply_delta_to_points,
    touch_point_positions,
    edge_t_from_mouse_ray,
    canonicalize_edge_and_t,
    format_cut_spec,
    set_spec_parm,
    clear_spec_parm,
)
from skyforge.forge_motion import (
    pick_axis_from_mouse,
    axes_for_space,
)
from skyforge.forge_store import ForgeStashSession


class State(object):
    """Interactive SOP viewer state with move/cut tools and stash-backed edits."""

    HUD_TEMPLATE = {
        "title": "AutoAxisTest", "desc": "tool", "icon": "SOP_edit",
        "rows": [
            {"id": "mode", "label": "Mode", "key": "M", "value": "LOCAL"},
            {"id": "mode_g", "type": "choicegraph", "count": 3},

            {"id": "selectmode", "label": "Select Mode", "key": "F", "value": "POINT"},
            {"id": "selectmode_g", "type": "choicegraph", "count": 3},

            {"id": "selecttool", "label": "Select Tool", "key": "C", "value": "MOVE"},
            {"id": "selecttool_g", "type": "choicegraph", "count": 2},
        ]
    }

    # ---- HDA parms ----
    LOOPCUT_SPEC_PARM = "edgeloop_spec"   # string parm: p<a>-<b>:<t>
    LOOPCUT_ENABLE_PARM = None            # optional toggle/switch parm, or None

    # ---- HDA internal SOP used for baking preview ----
    CACHE_NODE = "cache_geo"              # NULL/OUT at end of chain to capture preview geo
    STASH_RESET_PARM = "stashinput"       # button parm that resets stash from INPUT
    STASH_NODE_NAME = "stash1"
    INPUT_NODE_NAME = "INPUT"

    def __init__(self, state_name, scene_viewer):
        """Build state runtime data; Houdini calls hooks later (onEnter/onDraw/...)."""
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self.dragger = hou.ViewerStateDragger("dragger")

        self._edit_geo = None

        # SINGLE MODE: LOCAL / WORLD / EDGE
        self.mode = "LOCAL"
        self._drag_mode_used = None

        # selection mode
        self.select_mode = "POINT"       # "POINT" / "EDGE" / "FACE"
        self._drag_select_used = None

        # tool mode (move/cut)
        self.tool_mode = "MOVE"          # "MOVE" / "CUT"

        self._is_dragging = False
        self._pending = False

        # --- CUT session ---
        self._cut_active = False
        self._cut_p0 = -1
        self._cut_p1 = -1
        self._cut_t = 0.5
        self._cut_mouse0 = None
        self._cut_t0 = 0.5

        # current selection
        self._ptnum = -1
        self._primnum = -1
        self._affected_ptnums = None     # list[int]

        self._edge_p0 = -1
        self._edge_p1 = -1

        self._origin = None
        self._start_mouse = None

        self._drag_axis = None
        self._undo_opened = False

        self.node = None
        self.color_options = ru.ColorOptions(self.scene_viewer)

        # --- drawables ---
        self.guide_len = 0.3
        self.guide_line = None
        self.edge_hover = None

        # --- store/session ---
        self.store = None

        # --- callback guard ---
        self._cb_registered = False

    # -------------------------------------------------------------------------
    # Loopcut helpers
    # -------------------------------------------------------------------------

    def _edge_t_from_mouse_ray(self, geo, a, b, ui_event):
        """Return t in [0,1] along edge a->b from mouse ray (closest ray/segment)."""
        return edge_t_from_mouse_ray(geo, a, b, ui_event)

    def _canonicalize_edge_and_t(self, a, b, t):
        """Force a<b so the spec string is stable; invert t when swapping."""
        return canonicalize_edge_and_t(a, b, t)


    def _format_cut_spec(self, a, b, t):
        """Encode one cut as a stable `p<a>-<b>:<t>` string."""
        return format_cut_spec(a, b, t)

    def _commit_loopcut_spec(self, spec, append=False, undoable=True):
        if self.node is None:
            return
        set_spec_parm(
            self.node,
            self.LOOPCUT_SPEC_PARM,
            spec,
            append=append,
            enable_parm_name=self.LOOPCUT_ENABLE_PARM,
            undo_label="Loop Cut Spec",
            undoable=undoable,
        )

    def _reset_cut_session(self):
        """Clear transient cut-drag state."""
        self._cut_active = False
        self._cut_p0 = -1
        self._cut_p1 = -1
        self._cut_mouse0 = None
        self._cut_t0 = 0.5
        self._cut_t = 0.5

    def _bake_from_cache_geo(self):
        """
        Bake the current preview (cache_geo output) into stash:
        - cook cache node
        - replace store.edit_geo + push to stash
        - clear edgeloop_spec so we can accumulate cuts
        """

        if self.node is None or self.store is None:
            return

        cache = self.node.node(self.CACHE_NODE)
        if cache is None:
            # Uncomment if you want explicit feedback:
            # print(f"[AutoAxisTest] Missing CACHE_NODE: {self.CACHE_NODE}")
            return

        try:
            cache.cook(force=True)
            cooked = cache.geometry()
        except:
            return

        # Copy into a fresh geometry (avoid holding a live cooked ref)
        new_geo = hou.Geometry()
        new_geo.merge(cooked)

        # Replace edit geo and push to stash
        self.store.edit_geo = new_geo
        self._edit_geo = new_geo
        self._refresh_gadgets_geometry()
        self.store.push()

        # Clear spec after bake
        parm = self.node.parm(self.LOOPCUT_SPEC_PARM)
        if parm is not None:
            clear_spec_parm(self.node, self.LOOPCUT_SPEC_PARM)

    # -------------------------------------------------------------------------
    # HUD
    # -------------------------------------------------------------------------

    def _cycle_mode(self):
        """Cycle transform space mode LOCAL -> WORLD -> EDGE."""
        order = ["LOCAL", "WORLD", "EDGE"]
        try:
            i = order.index(self.mode)
        except ValueError:
            i = 0
        self.mode = order[(i + 1) % len(order)]

    def _cycle_select_mode(self):
        """Cycle selection mode POINT -> EDGE -> FACE."""
        order = ["POINT", "EDGE", "FACE"]
        try:
            i = order.index(self.select_mode)
        except ValueError:
            i = 0
        self.select_mode = order[(i + 1) % len(order)]

    def _cycle_tool_mode(self):
        """Cycle tool mode MOVE <-> CUT and enforce CUT prerequisites."""
        order = ["MOVE", "CUT"]
        try:
            i = order.index(self.tool_mode)
        except ValueError:
            i = 0
        self.tool_mode = order[(i + 1) % len(order)]

        # NEW: when entering CUT, force EDGE selection mode
        if self.tool_mode == "CUT":
            self.select_mode = "EDGE"
            self._drag_select_used = None   # safety: cancel cached drag select mode
            # optional: cancel pending move drag
            if self._pending or self._is_dragging or self._undo_opened:
                self._cleanup_drag()
            # optional: reset cut session if you use it
            if hasattr(self, "_reset_cut_session"):
                self._reset_cut_session()
        else:
            # When returning to MOVE, restore point selection by default.
            self.select_mode = "POINT"
            self._drag_select_used = None

        self._hud_update()


    def _hud_update(self):
        """Push current mode values to the viewer HUD."""
        try:
            mode_order = ["LOCAL", "WORLD", "EDGE"]
            mode_idx = mode_order.index(self.mode) if self.mode in mode_order else 0

            sel_order = ["POINT", "EDGE", "FACE"]
            sel_idx = sel_order.index(self.select_mode) if self.select_mode in sel_order else 0

            tool_order = ["MOVE", "CUT"]
            tool_idx = tool_order.index(self.tool_mode) if self.tool_mode in tool_order else 0

            updates = {
                "mode": self.mode,
                "mode_g": mode_idx,
                "selectmode": self.select_mode,
                "selectmode_g": sel_idx,
                "selecttool": self.tool_mode,
                "selecttool_g": tool_idx,
            }
            try:
                self.scene_viewer.hudInfo(hud_values=updates)
            except TypeError:
                self.scene_viewer.hudInfo(values=updates)
        except:
            pass

    # -------------------------------------------------------------------------
    # Drawables (LineFX)
    # -------------------------------------------------------------------------

    def _init_guide_line(self):
        """Create guide drawable used during axis drag."""
        color = self.color_options.colorFromName("PickedHandleColor")
        self.guide_line = LineFX(self.scene_viewer, "auto_axis_guide_line", color, line_width=2.0)
        self.guide_line.hide()

    def _update_guide_line(self, origin, axis_dir):
        """Update guide drawable from origin along selected axis."""
        if self.guide_line is None:
            return
        if origin is None or axis_dir is None or axis_dir.length() < 1e-6:
            self.guide_line.hide()
            return
        a = axis_dir.normalized()
        self.guide_line.set_line(origin, origin + a * self.guide_len)

    def _hide_guide_line(self):
        """Hide axis guide drawable."""
        if self.guide_line is not None:
            self.guide_line.hide()

    def _init_edge_hover(self):
        """Create edge-hover drawable."""
        color = self.color_options.colorFromName("PickedHandleColor")
        self.edge_hover = LineFX(self.scene_viewer, "auto_axis_edge_hover", color, line_width=3.0)
        self.edge_hover.hide()

    def _update_edge_hover_from_points(self, p0, p1):
        """Draw hovered edge segment using two point indices."""
        if self.edge_hover is None or self._edit_geo is None:
            return
        pt0 = self._edit_geo.point(p0)
        pt1 = self._edit_geo.point(p1)
        if pt0 is None or pt1 is None:
            self.edge_hover.hide()
            return
        self.edge_hover.set_line(pt0.position(), pt1.position())

    def _hide_edge_hover(self):
        """Hide edge-hover drawable."""
        if self.edge_hover is not None:
            self.edge_hover.hide()

    # -------------------------------------------------------------------------
    # Axis / edge pick helpers
    # -------------------------------------------------------------------------

    def _pick_connected_edge_dir_from_point(self, origin, mouse_delta, ptnum):
        """Pick best connected-edge direction from a point using mouse direction."""
        if self._edit_geo is None:
            return None, 1.0

        nbrs = connected_neighbors(self._edit_geo, ptnum)
        if not nbrs:
            return None, 1.0

        edge_dirs = {}
        for idx, n in enumerate(nbrs):
            npt = self._edit_geo.point(n)
            if npt is None:
                continue
            v = npt.position() - origin
            if v.length() > 1e-6:
                edge_dirs[f"E{idx}"] = v

        if not edge_dirs:
            return None, 1.0

        key, sign = pick_axis_from_mouse(self.scene_viewer, origin, mouse_delta, edge_dirs)
        if key is None:
            return None, 1.0

        return edge_dirs[key].normalized(), sign

    def _pick_axis_for_selected_edge(self, origin, mouse_delta, p0, p1):
        """Pick edge tangent orientation from mouse direction for selected edge."""
        t = edge_tangent(self._edit_geo, p0, p1)
        if t is None:
            return None, 1.0
        key, sign = pick_axis_from_mouse(self.scene_viewer, origin, mouse_delta, {"T": t})
        if key is None:
            return None, 1.0
        return t, sign

    def _world_axes(self):
        """Return fallback world-space axis vectors."""
        return {
            "X": hou.Vector3(1, 0, 0),
            "Y": hou.Vector3(0, 1, 0),
            "Z": hou.Vector3(0, 0, 1),
        }

    # -------------------------------------------------------------------------
    # Callbacks
    # -------------------------------------------------------------------------

    def _onHdaParmChanged(self, **kwargs):
        """React to HDA parm changes that should reset edit geo from INPUT/stash."""
        parm_tuple = kwargs.get("parm_tuple")
        if parm_tuple is None:
            return
        if parm_tuple.name() != self.STASH_RESET_PARM:
            return

        self._edit_geo = self.store.ensure_on_enter()
        self._refresh_gadgets_geometry()

    def _register_callbacks(self):
        """Attach node parm-change callback once per state entry."""
        if not self.node or self._cb_registered:
            return
        try:
            self.node.addEventCallback((hou.nodeEventType.ParmTupleChanged,), self._onHdaParmChanged)
            self._cb_registered = True
        except:
            self._cb_registered = False

    def _unregister_callbacks(self):
        """Detach node callback when state exits."""
        if not self.node or not self._cb_registered:
            return
        try:
            self.node.removeEventCallback((hou.nodeEventType.ParmTupleChanged,), self._onHdaParmChanged)
        except:
            pass
        self._cb_registered = False

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _refresh_gadgets_geometry(self):
        """Push current editable geometry to all registered gadgets."""
        if hasattr(self, "point_gadget") and self.point_gadget is not None:
            self.point_gadget.setGeometry(self._edit_geo)
        if hasattr(self, "face_gadget") and self.face_gadget is not None:
            self.face_gadget.setGeometry(self._edit_geo)
        if hasattr(self, "edge_gadget") and self.edge_gadget is not None:
            self.edge_gadget.setGeometry(self._edit_geo)

    def _init_gadgets(self):
        """Bind state gadgets once and initialize their visual params."""
        self.point_gadget = self.state_gadgets["point_gadget"]
        self.point_gadget.setParams({
            "draw_color": self.color_options.colorFromName("HandleZAxisColor", alpha_name="LocateAlpha"),
            "radius": 5.0
        })
        self.point_gadget.show(True)

        self.face_gadget = self.state_gadgets["face_gadget"]
        self.face_gadget.setParams({"draw_color": [1, 1, 1, 0.0]})
        self.face_gadget.show(True)

        self.edge_gadget = self.state_gadgets["edge_gadget"]
        self.edge_gadget.setParams({"draw_color": [1, 1, 1, 0.0]})
        self.edge_gadget.show(True)

        self._refresh_gadgets_geometry()

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def _cleanup_drag(self):
        """Close drag/undo state and reset drag-related caches."""
        self._pending = False
        try:
            self.dragger.endDrag()
        except:
            pass

        self._hide_guide_line()
        self._hide_edge_hover()

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

        if self._undo_opened:
            try:
                self.scene_viewer.endStateUndo()
            except:
                pass
            self._undo_opened = False

    def _finalize_active_interaction_for_mode_change(self):
        """Commit/interrupt active interactions before switching modes."""
        # If a CUT drag is active, commit preview into stash before leaving CUT flow.
        if self.tool_mode == "CUT" and self._cut_active:
            self._bake_from_cache_geo()
            self._reset_cut_session()

        # For MOVE drag (or any open drag/undo), interrupt cleanly.
        if self._pending or self._is_dragging or self._undo_opened:
            self._cleanup_drag()

    # -------------------------------------------------------------------------
    # Viewer state hooks
    # -------------------------------------------------------------------------

    def onEnter(self, kwargs):
        """Initialize state resources when the viewer state is entered."""
        self.node = kwargs["node"]

        self.scene_viewer.hudInfo(template=State.HUD_TEMPLATE)
        self._hud_update()

        self.store = ForgeStashSession(
            self.node,
            stash_node_name=self.STASH_NODE_NAME,
            input_node_name=self.INPUT_NODE_NAME,
        )
        self._edit_geo = self.store.ensure_on_enter()

        clear_spec_parm(self.node, self.LOOPCUT_SPEC_PARM)

        self._init_guide_line()
        self._init_edge_hover()
        self._init_gadgets()

        self._register_callbacks()

    def onExit(self, kwargs):
        """Release callbacks and temporary state when leaving the viewer state."""
        self._cleanup_drag()
        self._reset_cut_session()
        self._unregister_callbacks()
        self._hide_guide_line()
        self._hide_edge_hover()

    def onMouseEvent(self, kwargs):
        """Main mouse interaction handler for move and cut tools."""
        ui_event = kwargs["ui_event"]
        reason = ui_event.reason()

        # current mouse
        try:
            mx, my = ui_event.device().mouseX(), ui_event.device().mouseY()
            cur_mouse = hou.Vector2(mx, my)
        except:
            return False

        # Which gadget should be active for this select_mode?
        gad = self.state_context.gadget()
        if self.select_mode == "POINT":
            ok = (gad == "point_gadget")
        elif self.select_mode == "EDGE":
            ok = (gad == "edge_gadget")
        else:
            ok = (gad == "face_gadget")

        # If not picking our gadget, cleanup move drag if needed and allow Houdini to handle
        if not ok:
            if self._pending or self._undo_opened or self._is_dragging:
                self._cleanup_drag()

            if self.tool_mode == "CUT" and self._cut_active and reason == hou.uiEventReason.Changed:
                self._reset_cut_session()

            return False

        if self._edit_geo is None:
            return False

        # ---------------------------------------------------------------------
        # CUT TOOL MODE: drag t + COMMIT on release (bake from cache_geo)
        # ---------------------------------------------------------------------
        if self.tool_mode == "CUT":
            # Make sure move drag isn't active
            if self._pending or self._is_dragging or self._undo_opened:
                self._cleanup_drag()

            if self.select_mode != "EDGE":
                self._reset_cut_session()
                return True

            if reason == hou.uiEventReason.Start:
                self._cut_active = True
                self._cut_mouse0 = cur_mouse

                self._cut_p0 = self.state_context.component1()
                self._cut_p1 = self.state_context.component2()

                self._cut_t0 = self._edge_t_from_mouse_ray(self._edit_geo, self._cut_p0, self._cut_p1, ui_event)
                self._cut_t = self._cut_t0

                a, b, t = self._canonicalize_edge_and_t(self._cut_p0, self._cut_p1, self._cut_t)
                spec = self._format_cut_spec(a, b, t)
                self._commit_loopcut_spec(spec, append=False, undoable=False)  # preview (no undo spam)
                return True
            

            if reason in (hou.uiEventReason.Active, hou.uiEventReason.Changed):
                if not self._cut_active:
                    return True

                self._cut_t = self._edge_t_from_mouse_ray(self._edit_geo, self._cut_p0, self._cut_p1, ui_event)

                a, b, t = self._canonicalize_edge_and_t(self._cut_p0, self._cut_p1, self._cut_t)
                spec = self._format_cut_spec(a, b, t)
                self._commit_loopcut_spec(spec, append=False, undoable=False)  # preview live (no undo spam)

                if reason == hou.uiEventReason.Changed:
                    # COMMIT: one undo step for the whole cut
                    with hou.undos.group("Loop Cut"):
                        self._bake_from_cache_geo()
                    self._reset_cut_session()

                return True

            return True

        # ---------------------------------------------------------------------
        # MOVE TOOL MODE (existing behavior)
        # ---------------------------------------------------------------------

        if reason == hou.uiEventReason.Start:
            self._pending = True
            self._start_mouse = cur_mouse

            self._drag_mode_used = self.mode
            self._drag_select_used = self.select_mode
            self._is_dragging = False

            self._drag_axis = None
            self._affected_ptnums = None

            if self.select_mode == "POINT":
                ptnum = self.state_context.component1()
                pt = self._edit_geo.point(ptnum)
                if pt is None:
                    return False
                self._ptnum = ptnum
                self._origin = pt.position()
                self._affected_ptnums = [ptnum]

            elif self.select_mode == "EDGE":
                p0 = self.state_context.component1()
                p1 = self.state_context.component2()
                pt0 = self._edit_geo.point(p0)
                pt1 = self._edit_geo.point(p1)
                if pt0 is None or pt1 is None:
                    return False
                self._edge_p0 = p0
                self._edge_p1 = p1
                self._origin = (pt0.position() + pt1.position()) * 0.5
                self._affected_ptnums = [p0, p1]

            else:  # FACE
                primnum = self.state_context.component1()
                prim = self._edit_geo.prim(primnum)
                if prim is None:
                    return False
                self._primnum = primnum
                self._origin = prim_center(prim)
                self._affected_ptnums = prim_points_unique(prim)

            self._hide_guide_line()

            try:
                self.scene_viewer.beginStateUndo("Auto drag")
                self._undo_opened = True
            except:
                self._undo_opened = False

            return True

        elif reason in (hou.uiEventReason.Active, hou.uiEventReason.Changed):
            if self._pending:
                md = cur_mouse - self._start_mouse

                mode = self._drag_mode_used or self.mode
                sel = self._drag_select_used or self.select_mode
                origin = self._origin

                if sel == "FACE" and mode == "EDGE":
                    mode = "LOCAL"

                if mode == "EDGE":
                    if sel == "POINT":
                        edge_dir, sign = self._pick_connected_edge_dir_from_point(origin, md, self._ptnum)
                        if edge_dir is not None:
                            self._drag_axis = edge_dir * sign
                        else:
                            origin2, axes = axes_for_space(
                                self._edit_geo, "LOCAL", "POINT", self._ptnum, self._primnum, prim_center
                            )
                            if origin2 is not None and axes is not None:
                                origin = origin2
                            choice, sign = pick_axis_from_mouse(self.scene_viewer, origin, md, axes)
                            if choice is None and reason != hou.uiEventReason.Changed:
                                return True
                            if choice is None:
                                choice, sign = "Z", 1.0
                            self._drag_axis = axes[choice].normalized() * sign

                    elif sel == "EDGE":
                        t, sign = self._pick_axis_for_selected_edge(origin, md, self._edge_p0, self._edge_p1)
                        if t is None:
                            axes = self._world_axes()
                            choice, sign = pick_axis_from_mouse(self.scene_viewer, origin, md, axes)
                            if choice is None and reason != hou.uiEventReason.Changed:
                                return True
                            if choice is None:
                                choice, sign = "Z", 1.0
                            self._drag_axis = axes[choice].normalized() * sign
                        else:
                            self._drag_axis = t * sign

                    else:
                        origin, axes = axes_for_space(
                            self._edit_geo, "LOCAL", "FACE", self._ptnum, self._primnum, prim_center
                        )
                        if origin is None or axes is None:
                            return False
                        choice, sign = pick_axis_from_mouse(self.scene_viewer, origin, md, axes)
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
                            origin2, axes = axes_for_space(
                                self._edit_geo, "LOCAL", "POINT", pt_for_local, self._primnum, prim_center
                            )
                            if origin2 is None or axes is None:
                                axes = self._world_axes()
                    else:
                        origin, axes = axes_for_space(
                            self._edit_geo, mode, sel, self._ptnum, self._primnum, prim_center
                        )
                        if origin is None or axes is None:
                            return False

                    choice, sign = pick_axis_from_mouse(self.scene_viewer, origin, md, axes)
                    if choice is None and reason != hou.uiEventReason.Changed:
                        return True
                    if choice is None:
                        choice, sign = "Z", 1.0
                    self._drag_axis = axes[choice].normalized() * sign

                self._update_guide_line(origin, self._drag_axis)
                self.dragger.startDragAlongLine(ui_event, origin, self._drag_axis)
                self._pending = False
                self._is_dragging = True

            try:
                delta = self.dragger.drag(ui_event)["delta_position"]
            except:
                if reason == hou.uiEventReason.Changed:
                    self._cleanup_drag()
                return False

            apply_delta_to_points(self._edit_geo, self._affected_ptnums, delta)
            touch_point_positions(self._edit_geo)

            if self.store is not None:
                self.store.push()

            if self.select_mode == "POINT":
                pt = self._edit_geo.point(self._ptnum)
                if pt is not None:
                    self._update_guide_line(pt.position(), self._drag_axis)
            elif self.select_mode == "EDGE":
                mid = edge_midpoint(self._edit_geo, self._edge_p0, self._edge_p1)
                if mid is not None:
                    self._update_guide_line(mid, self._drag_axis)
            else:
                prim = self._edit_geo.prim(self._primnum)
                if prim is not None:
                    c = prim_center(prim)
                    if c is not None:
                        self._update_guide_line(c, self._drag_axis)

            if reason == hou.uiEventReason.Changed:
                self._cleanup_drag()

            return True

        return False

    def onDraw(self, kwargs):
        """Draw gadgets/overlays and pull stash updates when needed."""
        if self.state_context.isPicking():
            return

        # Sync from stash if changed (undo/redo/etc.)
        if self.store is not None:
            changed = self.store.sync_if_needed(force=False, allow_sync=(not self._pending and not self._is_dragging))
            if changed:
                self._edit_geo = self.store.edit_geo
                self._refresh_gadgets_geometry()
                self._hide_guide_line()
                self._hide_edge_hover()
                clear_spec_parm(self.node, self.LOOPCUT_SPEC_PARM)
                try:
                    self.scene_viewer.curViewport().draw()
                except:
                    pass

        handle = kwargs["draw_handle"]

        if self.select_mode == "POINT":
            if self.state_context.gadget() == "point_gadget":
                self.point_gadget.setParams({"indices": [self.state_context.component1()]})
            else:
                self.point_gadget.setParams({"indices": []})
            self.point_gadget.draw(handle)
            self._hide_edge_hover()

        elif self.select_mode == "EDGE":
            self.edge_gadget.draw(handle)
            if self.state_context.gadget() == "edge_gadget":
                p0 = self.state_context.component1()
                p1 = self.state_context.component2()
                self._update_edge_hover_from_points(p0, p1)
            else:
                self._hide_edge_hover()

        else:  # FACE
            if self.state_context.gadget() == "face_gadget":
                self.face_gadget.setParams({"indices": [self.state_context.component1()]})
            else:
                self.face_gadget.setParams({"indices": []})
            self.face_gadget.draw(handle)
            self._hide_edge_hover()

        if self.guide_line is not None:
            self.guide_line.draw(handle)
        if self.edge_hover is not None:
            self.edge_hover.draw(handle)

    def onMenuAction(self, kwargs):
        """Handle radial/context menu actions for mode switching."""
        menu_item = kwargs.get("menu_item")

        if menu_item == "cycle_mode":
            self._finalize_active_interaction_for_mode_change()
            self._cycle_mode()
            self._hud_update()
            return True

        if menu_item == "cycle_select":
            self._finalize_active_interaction_for_mode_change()
            self._cycle_select_mode()
            self._hud_update()
            return True

        if menu_item == "cycle_tool":
            self._finalize_active_interaction_for_mode_change()
            self._cycle_tool_mode()
            return True

        return False


def createViewerStateTemplate():
    """Register and return the viewer state template for Houdini."""
    state_typename = "AutoAxisTest"
    state_label = "AutoAxisTest"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)

    template.bindGadget(hou.drawableGeometryType.Point, "point_gadget", label="Point")
    template.bindGadget(hou.drawableGeometryType.Face, "face_gadget", label="Face")
    template.bindGadget(hou.drawableGeometryType.Line, "edge_gadget", label="Edge")

    hotkey_definitions = hou.PluginHotkeyDefinitions()
    menu = hou.ViewerStateMenu(state_typename + "_menu", state_label)

    menu.addActionItem(
        "cycle_mode",
        "Cycle Mode (Local/World/Edge)",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "cycle_mode", "m")
    )
    menu.addActionItem(
        "cycle_select",
        "Cycle Select Mode (Point/Edge/Face)",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "cycle_select", "f")
    )
    menu.addActionItem(
        "cycle_tool",
        "Cycle tool Mode (move/cut)",
        hotkey=su.defineHotkey(hotkey_definitions, state_typename, "cycle_tool", "c")
    )

    template.bindMenu(menu)
    template.bindHotkeyDefinitions(hotkey_definitions)
    return template


