import re
import time

import hou

from ..feature_base import ViewerFeature
from .. import preview_channels as ch
from ..constants import (
    LINE_WIDTH,
    COLOR_PREVIEW_YELLOW,
    COLOR_COMMITTED_ORANGE,
    PARM_BASEGROUP,
    GROUP_PARM_NAMES,
)


class AstarTurnFeature(ViewerFeature):
    name = "astar_turn"

    def __init__(self):
        self.start_he = -1
        self.hover_he = -1
        self.committed_hedges = []
        self.preview = None
        self.ch_preview = ch.CH_ASTAR_PREVIEW
        self.ch_committed = ch.CH_ASTAR_COMMITTED
        self._last_commit_edge = -1
        self._last_commit_t = 0.0

    def on_enter(self, ctx, kwargs):
        self.start_he = -1
        self.hover_he = -1
        self.preview = ctx.get_service("preview")
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
        self.committed_hedges = self._hedges_from_group_string(ctx, (ctx.parm_string.eval() if ctx.parm_string is not None else ""))
        if self.committed_hedges:
            self.start_he = self.committed_hedges[-1]
            self._set_committed_path(ctx, self.committed_hedges)

        bg = ctx.node.parm(PARM_BASEGROUP) if ctx.node is not None else None
        if bg is not None:
            p0, p1 = self._first_edge_from_group(ctx, bg.eval())
            if p0 >= 0:
                self.start_he = ctx.edge_to_hedge(p0, p1)

    def on_exit(self, ctx, kwargs):
        self._hide_preview(ctx)
        self._hide_committed(ctx)

    def on_draw(self, ctx, kwargs):
        return

    def on_key_event(self, ctx, kwargs):
        return False

    # Public API for orchestrator-driven interactions
    def clear_preview(self, ctx):
        self._hide_preview(ctx)

    def reset_all(self, ctx):
        self._reset_session(ctx)

    def preview_from_base_to_he(self, ctx, end_he):
        start_he = self._start_from_basegroup(ctx)
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
        start_he = self._start_from_basegroup(ctx)
        if start_he < 0 or end_he < 0:
            return False

        path = ctx.mesh.astar_turn(start_he, end_he)
        if not path:
            return False

        current = self._current_committed_from_parm(ctx)
        merged = self._merge_path(current, path)

        if ctx.parm_string is not None:
            ctx.parm_string.set(ctx.hedges_to_group_string(merged))

        self.committed_hedges = list(merged)
        self._set_committed_path(ctx, self.committed_hedges)
        self._hide_preview(ctx)

        # Chain behavior: next A* starts from the clicked edge.
        p0 = int(ctx.mesh.src(end_he))
        p1 = int(ctx.mesh.dst(end_he))
        self._set_basegroup_from_points(ctx, p0, p1)

        return True

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

        self.committed_hedges = self._current_committed_from_parm(ctx)
        self.start_he = he
        self._set_basegroup_from_points(ctx, p[0], p[1])
        self.hover_he = -1
        self._set_preview_path(ctx, self.committed_hedges)
        return False

    def on_mouse_event(self, ctx, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        reason = ui.reason()
        dev = ui.device()

        if reason not in (hou.uiEventReason.Start, hou.uiEventReason.Active, hou.uiEventReason.Located):
            return False

        if reason in (hou.uiEventReason.Start, hou.uiEventReason.Active) and not dev.isLeftButton():
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

        if self._is_duplicate_commit_click(he):
            return True

        if self.start_he < 0:
            # Try to recover start from current basegroup on demand.
            start_from_bg = self._start_from_basegroup(ctx)
            if start_from_bg >= 0:
                self.start_he = start_from_bg
            else:
                # No start yet: first click defines start edge.
                self.start_he = he
                self._set_basegroup_from_points(ctx, p0, p1)
                self.hover_he = -1
                self._set_preview_path(ctx, self.committed_hedges)
                return True

        path = ctx.mesh.astar_turn(self.start_he, he)
        if not path:
            return True

        current = self._current_committed_from_parm(ctx)
        self.committed_hedges = self._merge_path(current, path)
        if ctx.parm_string is not None:
            ctx.parm_string.set(ctx.hedges_to_group_string(self.committed_hedges))

        # Chain behavior: clicked edge becomes next start.
        self.start_he = he
        self._set_basegroup_from_points(ctx, p0, p1)
        self.hover_he = -1
        self._set_committed_path(ctx, self.committed_hedges)
        self._hide_preview(ctx)
        return True

    def _hit_edge(self, ctx, ui_event):
        hit = ctx.hit_edge(ui_event)
        if hit is None:
            return None
        return int(hit[0]), int(hit[1])

    def _first_edge_from_group(self, ctx, group_str):
        return ctx.first_edge_from_group_string(group_str)

    def _edgepair_from_selstr(self, selstr):
        m = re.search(r"p(\d+)-(\d+)", selstr or "")
        if m:
            return int(m.group(1)), int(m.group(2))

        nums = re.findall(r"\d+", selstr or "")
        if len(nums) >= 2:
            return int(nums[0]), int(nums[1])
        return None

    def _hide_preview(self, ctx):
        self.preview.hide(self.ch_preview)
        self._request_draw(ctx)

    def _set_preview_path(self, ctx, hedges):
        self._set_path_to_drawable(ctx, hedges, is_committed=False)

    def _set_committed_path(self, ctx, hedges):
        self._set_path_to_drawable(ctx, hedges, is_committed=True)

    def _set_path_to_drawable(self, ctx, hedges, is_committed):
        ch = self.ch_committed if is_committed else self.ch_preview
        if not hedges or ctx.geometry is None:
            self.preview.hide(ch)
            self._request_draw(ctx)
            return
        self.preview.set_line_from_hedges(ch, ctx.geometry, ctx.mesh, hedges, segments=False)
        self._request_draw(ctx)

    def _hide_committed(self, ctx):
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

    def _hedges_from_group_string(self, ctx, group_str):
        return ctx.hedges_from_group_string(group_str)

    def _current_committed_from_parm(self, ctx):
        if ctx.parm_string is None:
            return list(self.committed_hedges)
        try:
            text = ctx.parm_string.eval()
        except Exception:
            text = ""
        parsed = self._hedges_from_group_string(ctx, text)
        if parsed:
            return parsed
        return list(self.committed_hedges)

    def _is_duplicate_commit_click(self, he):
        t = time.monotonic()
        if he == self._last_commit_edge and (t - self._last_commit_t) < 0.2:
            return True
        self._last_commit_edge = he
        self._last_commit_t = t
        return False

    def _start_from_basegroup(self, ctx):
        if ctx.node is None:
            return -1
        parm = ctx.node.parm(PARM_BASEGROUP)
        if parm is None:
            return -1

        p0, p1 = self._first_edge_from_group(ctx, parm.eval())
        if p0 < 0:
            return -1
        return ctx.edge_to_hedge(p0, p1)

    def _set_basegroup_from_points(self, ctx, p0, p1):
        ctx.set_basegroup_from_points(p0, p1)

    def _reset_session(self, ctx):
        self.start_he = -1
        self.hover_he = -1
        self.committed_hedges = []
        self._hide_preview(ctx)
        self._hide_committed(ctx)
        ctx.clear_group_parms(GROUP_PARM_NAMES)
