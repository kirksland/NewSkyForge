import re
import time

import hou

from ..feature_base import ViewerFeature
from ..preview_service import PreviewService
from ..constants import (
    LINE_WIDTH,
    COLOR_PREVIEW_YELLOW,
    COLOR_COMMITTED_ORANGE,
    OUTPUT_MODE_EDGE,
    CH_ASTAR_PREVIEW,
    CH_ASTAR_COMMITTED,
)


class AstarTurnFeature(ViewerFeature):
    """
    A* edge path feature.

    Owns two preview channels:
    - `ch_preview`: live path while hovering target edge
    - `ch_committed`: committed path (payload output)
    """
    name = "astar_turn"
    requires = ("hover",)

    def __init__(self):
        """Initialize runtime state, output mode, and preview channel names."""
        self.start_he = -1
        self.hover_he = -1
        self.committed_hedges = []
        self.output_mode = OUTPUT_MODE_EDGE
        self.preview = None
        self.ch_preview = CH_ASTAR_PREVIEW
        self.ch_committed = CH_ASTAR_COMMITTED
        self._last_commit_edge = -1
        self._last_commit_t = 0.0
        self._shift_a_active = False

    def on_enter(self, ctx, kwargs):
        """Initialize/reuse preview service and sync initial committed/base state."""
        self.start_he = -1
        self.hover_he = -1
        self.committed_hedges = []
        self.preview = ctx.get_service("preview")
        if self.preview is None:
            # Keep external injection support: only create service when absent.
            self.preview = PreviewService(ctx.scene_viewer, prefix="astar_turn")
            ctx.set_service("preview", self.preview)
        if self.preview is None:
            return
        self.preview.ensure_line_channel(
            self.ch_committed,
            COLOR_COMMITTED_ORANGE,
            line_width=float(LINE_WIDTH),
        )
        self.preview.ensure_line_channel(
            self.ch_preview,
            COLOR_PREVIEW_YELLOW,
            line_width=float(LINE_WIDTH),
        )
        if self.committed_hedges:
            self.start_he = self.committed_hedges[-1]
            self._set_committed_path(ctx, self.committed_hedges)

    def on_exit(self, ctx, kwargs):
        """Hide preview and committed channels."""
        self._hide_preview(ctx)
        self._hide_committed(ctx)

    def on_draw(self, ctx, kwargs):
        """Draw only A* owned channels on the shared preview service."""
        preview = self.preview or ctx.get_service("preview")
        if preview is None:
            return
        draw_handle = kwargs.get("draw_handle")
        if draw_handle is None:
            return
        preview.draw_channels(draw_handle, (self.ch_preview, self.ch_committed))

    def on_key_event(self, ctx, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        dev = ui.device()
        if dev.isAutoRepeat():
            return False

        key = (dev.keyString() or "").lower()
        if key == "shift+a" or (key == "a" and self._is_shift_down(dev)):
            self._shift_a_active = True
            return True
        return False

    def on_key_transit_event(self, ctx, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        dev = ui.device()
        if not dev.isKeyUp():
            return False

        key = (dev.keyString() or "").lower()
        if key in ("shift", "a", "shift+a"):
            self._shift_a_active = False
            self._hide_preview(ctx)
            return True
        return False

    # Public API for orchestrator-driven interactions
    def clear_preview(self, ctx):
        """Clear live preview channel only."""
        self._hide_preview(ctx)

    def reset_all(self, ctx):
        """Reset internal state and clear related channels."""
        self._reset_session(ctx)

    def set_output_mode(self, mode):
        """Set commit output mode: edge, point, or prim."""
        self.output_mode = (mode or OUTPUT_MODE_EDGE).lower().strip()

    def preview_single_edge(self, ctx, he):
        if he < 0:
            self._hide_preview(ctx)
            return False
        self._set_preview_path(ctx, [int(he)])
        return True

    def preview_from_base_to_he(self, ctx, end_he):
        """Compute and display A* path from current start edge to target half-edge."""
        start_he = self.start_he
        if start_he < 0 or end_he < 0 or start_he == end_he:
            self._hide_preview(ctx)
            return False

        path = ctx.mesh.astar_turn(start_he, end_he)
        if not path:
            self._hide_preview(ctx)
            return False

        self._set_preview_path(ctx, path)
        return True

    def commit_from_base_to_he(self, ctx, end_he):
        """Commit A* path and update chain start."""
        if end_he < 0:
            return False

        # First click in A* mode: define start edge and show a preview.
        if self.start_he < 0:
            p0 = int(ctx.mesh.src(end_he))
            p1 = int(ctx.mesh.dst(end_he))
            self.start_he = int(end_he)
            self.preview_single_edge(ctx, end_he)
            return self._payload_from_hedges(ctx, [int(end_he)])

        path = ctx.mesh.astar_turn(self.start_he, end_he)
        if not path:
            return False

        merged = self._merge_path(self.committed_hedges, path)

        commit_result = self._payload_from_hedges(ctx, merged)

        self.committed_hedges = list(merged)
        self._set_committed_path(ctx, self.committed_hedges)
        self._hide_preview(ctx)

        # Chain behavior: next A* starts from the clicked edge.
        p0 = int(ctx.mesh.src(end_he))
        p1 = int(ctx.mesh.dst(end_he))
        self.start_he = ctx.edge_to_hedge(p0, p1)

        return commit_result

    def on_selection(self, ctx, kwargs):
        selection = kwargs.get("selection")
        if not selection:
            return False

        selstrs = selection.selectionStrings(True, False)
        if not selstrs:
            return False

        p = self._edgepair_from_selstr(selstrs[0])
        if not p:
            return False

        he = ctx.edge_to_hedge(p[0], p[1])
        if he < 0:
            return False

        self.start_he = he
        self.hover_he = -1
        self._set_preview_path(ctx, self.committed_hedges)
        return False

    def on_mouse_event(self, ctx, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        reason = ui.reason()
        dev = ui.device()
        shift = self._is_shift_down(dev)

        # Auto output mode from hover payload when available.
        hover = ctx.get_service("hover") if hasattr(ctx, "get_service") else None
        if hover:
            auto_mode = self._output_mode_from_hover(hover)
            if auto_mode is not None:
                self.output_mode = auto_mode

        if reason not in (hou.uiEventReason.Start, hou.uiEventReason.Active, hou.uiEventReason.Located):
            return False

        if reason in (hou.uiEventReason.Start, hou.uiEventReason.Active) and not dev.isLeftButton():
            return False

        # When Shift+A is not held, keep showing the start edge if any.
        if reason == hou.uiEventReason.Located and not (self._shift_a_active and shift):
            if self.start_he >= 0:
                self.preview_single_edge(ctx, self.start_he)
            else:
                self._hide_preview(ctx)
            return False

        edge = self._hit_edge(ctx, ui)
        if edge is None:
            if reason == hou.uiEventReason.Located:
                self.hover_he = -1
                self._set_preview_path(ctx, self.committed_hedges)
            elif reason in (hou.uiEventReason.Start, hou.uiEventReason.Active):
                self._reset_session(ctx)
            return False

        p0, p1 = edge
        he = ctx.edge_to_hedge(p0, p1)
        if he < 0:
            return True

        if reason == hou.uiEventReason.Located:
            if not (self._shift_a_active and shift):
                return False
            if self.start_he < 0:
                self._set_preview_path(ctx, self.committed_hedges)
                return False
            if he == self.hover_he:
                return False

            self.hover_he = he
            if he == self.start_he:
                self._set_preview_path(ctx, self.committed_hedges)
                return False

            path = ctx.mesh.astar_turn(self.start_he, he)
            self._set_preview_path(ctx, path)
            return False

        # Start click without Shift+A: define start edge only.
        if not (self._shift_a_active and shift):
            self.start_he = he
            self.hover_he = -1
            self.preview_single_edge(ctx, he)
            return True

        if self._is_duplicate_commit_click(he):
            return True

        # Commit only when Shift+A is held.
        if self.start_he < 0:
            self.start_he = he
            self.preview_single_edge(ctx, he)
            return self._payload_from_hedges(ctx, [int(he)])

        path = ctx.mesh.astar_turn(self.start_he, he)
        if not path:
            return True

        self.committed_hedges = self._merge_path(self.committed_hedges, path)
        commit_result = self._payload_from_hedges(ctx, self.committed_hedges)

        # Chain behavior: clicked edge becomes next start.
        self.start_he = he
        self.hover_he = -1
        self._set_committed_path(ctx, self.committed_hedges)
        self._hide_preview(ctx)
        return commit_result

    def _hit_edge(self, ctx, ui_event):
        hit = ctx.hit_edge(ui_event)
        if hit is None:
            return None
        return int(hit[0]), int(hit[1])

    def _edgepair_from_selstr(self, selstr):
        m = re.search(r"p(\d+)-(\d+)", selstr or "")
        if m:
            return int(m.group(1)), int(m.group(2))

        nums = re.findall(r"\d+", selstr or "")
        if len(nums) >= 2:
            return int(nums[0]), int(nums[1])
        return None

    def _hide_preview(self, ctx):
        if self.preview is None:
            return
        self.preview.hide(self.ch_preview)
        self._request_draw(ctx)

    def _set_preview_path(self, ctx, hedges):
        self._set_path_to_drawable(ctx, hedges, is_committed=False)

    def _set_committed_path(self, ctx, hedges):
        self._set_path_to_drawable(ctx, hedges, is_committed=True)

    def _set_path_to_drawable(self, ctx, hedges, is_committed):
        if self.preview is None:
            return
        ch = self.ch_committed if is_committed else self.ch_preview
        if not hedges or ctx.geometry is None:
            self.preview.hide(ch)
            self._request_draw(ctx)
            return
        self.preview.set_line_from_hedges(ch, ctx.geometry, ctx.mesh, hedges, segments=False)
        self._request_draw(ctx)

    def _hide_committed(self, ctx):
        if self.preview is None:
            return
        self.preview.hide(self.ch_committed)
        self._request_draw(ctx)

    def _request_draw(self, ctx):
        try:
            ctx.scene_viewer.curViewport().draw()
        except Exception:
            pass

    def _merge_path(self, existing, incoming):
        if not incoming:
            return list(existing or [])
        if not existing:
            return list(incoming)

        out = list(existing)
        start = 0
        if out[-1] == incoming[0]:
            start = 1
        out.extend(incoming[start:])
        return out

    def _is_duplicate_commit_click(self, he):
        t = time.monotonic()
        if he == self._last_commit_edge and (t - self._last_commit_t) < 0.2:
            return True
        self._last_commit_edge = he
        self._last_commit_t = t
        return False

    def _payload_from_hedges(self, ctx, hedges):
        group = ctx.hedges_to_group_string_mode(hedges, self.output_mode)
        return {
            "mode": self.output_mode,
            "group": group,
        }

    def _reset_session(self, ctx):
        self.start_he = -1
        self.hover_he = -1
        self.committed_hedges = []
        self._hide_preview(ctx)
        self._hide_committed(ctx)

    def _is_shift_down(self, dev):
        try:
            return bool(dev.isShiftKey())
        except Exception:
            key = (dev.keyString() or "").lower()
            return "shift" in key

    def _output_mode_from_hover(self, hover):
        if not hover or not hover.get("visible"):
            return None
        if int(hover.get("prim", -1)) >= 0:
            return "prim"
        if int(hover.get("point", -1)) >= 0:
            return "point"
        if hover.get("edge") is not None:
            return "edge"
        return None
