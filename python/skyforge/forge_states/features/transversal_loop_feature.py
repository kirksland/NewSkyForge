import re
import hou

from ..feature_base import ViewerFeature
from ..preview_service import PreviewService
from ..constants import (
    LINE_WIDTH,
    COLOR_PREVIEW_YELLOW,
    COLOR_COMMITTED_ORANGE,
    LOOP_MODE_ROLL,
    LOOP_MODE_QUAD,
    GROUP_PARM_NAMES,
    OUTPUT_MODE_EDGE,
    CH_LOOP_PREVIEW,
    CH_LOOP_COMMITTED,
)


class TransversalLoopFeature(ViewerFeature):
    name = "transversal_loop"

    def __init__(self):
        self.preview = None
        self.ch_preview = CH_LOOP_PREVIEW
        self.ch_committed = CH_LOOP_COMMITTED
        self.mode = LOOP_MODE_ROLL  # transversal or quad
        self.output_mode = OUTPUT_MODE_EDGE

    def on_enter(self, ctx, kwargs):
        self.preview = ctx.get_service("preview")
        if self.preview is None:
            # Keep external injection support: only create service when absent.
            self.preview = PreviewService(ctx.scene_viewer, prefix="transversal_loop")
            ctx.set_service("preview", self.preview)
        if self.preview is None:
            return
        self.preview.ensure_line_channel(
            self.ch_preview,
            COLOR_PREVIEW_YELLOW,
            line_width=float(LINE_WIDTH),
        )
        self.preview.ensure_line_channel(
            self.ch_committed,
            COLOR_COMMITTED_ORANGE,
            line_width=float(LINE_WIDTH),
        )
        print("[SkyForge] TransversalLoopFeature mode:", self.mode, "(R=roll, Q=quad, X=toggle)")

    def on_exit(self, ctx, kwargs):
        self._hide_preview(ctx)
        self._hide_committed(ctx)

    def on_draw(self, ctx, kwargs):
        preview = self.preview or ctx.get_service("preview")
        if preview is None:
            return
        draw_handle = kwargs.get("draw_handle")
        if draw_handle is None:
            return
        preview.draw_all(draw_handle)

    def on_key_event(self, ctx, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        dev = ui.device()
        if dev.isAutoRepeat():
            return False

        key = (dev.keyString() or "").lower()
        if key in ("r", "&"):
            self.mode = LOOP_MODE_ROLL
            print("[SkyForge] Transversal loop mode -> roll")
            return True
        if key == "q":
            self.mode = LOOP_MODE_QUAD
            print("[SkyForge] Transversal loop mode -> quad")
            return True
        if key == "x":
            self.mode = LOOP_MODE_QUAD if self.mode == LOOP_MODE_ROLL else LOOP_MODE_ROLL
            print("[SkyForge] Transversal loop mode ->", self.mode)
            return True
        return False

    # Public API used by pyd_loop_modular orchestrator
    def clear_preview(self, ctx):
        self._hide_preview(ctx)

    def reset_all(self, ctx):
        self._reset_session(ctx)

    def set_output_mode(self, mode):
        self.output_mode = (mode or OUTPUT_MODE_EDGE).lower().strip()

    def set_basegroup_from_edge(self, ctx, p0, p1):
        self._set_basegroup_from_points(ctx, p0, p1)

    def preview_edge(self, ctx, p0, p1):
        he = ctx.edge_to_hedge(p0, p1)
        if he < 0:
            self._hide_preview(ctx)
            return False

        self._set_basegroup_from_points(ctx, p0, p1)
        self._set_preview_path(ctx, [he])
        return True

    def preview_loop_from_he(self, ctx, he):
        if he < 0:
            self._hide_preview(ctx)
            return False
        path = self._compute_loop(ctx, int(he))
        if not path:
            self._hide_preview(ctx)
            return False
        self._set_preview_path(ctx, path)
        return True

    def preview_loop_from_edge(self, ctx, p0, p1):
        he = ctx.edge_to_hedge(p0, p1)
        return self.preview_loop_from_he(ctx, he)

    def preview_from_hover(self, ctx, hover):
        he = self._hedge_from_hover(ctx, hover)
        return self.preview_loop_from_he(ctx, he)

    def commit_loop_from_he(self, ctx, he):
        if he < 0:
            return False
        p0 = int(ctx.mesh.src(int(he)))
        p1 = int(ctx.mesh.dst(int(he)))
        self._set_basegroup_from_points(ctx, p0, p1)
        path = self._compute_loop(ctx, int(he))
        if not path:
            self._hide_preview(ctx)
            return False
        self._set_committed_path(ctx, path)
        if ctx.parm_string is not None:
            ctx.parm_string.set(ctx.hedges_to_group_string_mode(path, self.output_mode))
        return True

    def commit_loop_from_edge(self, ctx, p0, p1):
        he = ctx.edge_to_hedge(p0, p1)
        return self.commit_loop_from_he(ctx, he)

    def commit_from_hover(self, ctx, hover):
        he = self._hedge_from_hover(ctx, hover)
        return self.commit_loop_from_he(ctx, he)

    def on_selection(self, ctx, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None or not self._is_shift_down(ui.device()):
            return False

        selection = kwargs.get("selection")
        if not selection:
            return False

        selstrs = selection.selectionStrings(True, False)
        if not selstrs:
            return False

        pair = self._first_edgepair_in_selection(selstrs)
        if pair is None:
            return False

        # Selection sync only: set basegroup from first selected edge.
        # Loop commit is handled by explicit mouse chord (Shift + MMB).
        self._set_basegroup_from_points(ctx, pair[0], pair[1])
        return False

    def on_mouse_event(self, ctx, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        if ui.reason() != hou.uiEventReason.Start:
            return False

        dev = ui.device()
        is_lmb = bool(dev.isLeftButton())
        is_mmb = bool(dev.isMiddleButton())
        if not (is_lmb or is_mmb):
            return False

        # Loops are momentary: only act while Shift is held.
        if not self._is_shift_down(dev):
            return False

        pair = self._hit_edge(ctx, ui)
        if pair is None:
            self._reset_session(ctx)
            return True

        p0, p1 = pair
        self._set_basegroup_from_points(ctx, p0, p1)

        # Shift + LMB => basegroup only
        if is_lmb:
            return True

        # Shift + MMB => compute loop and commit grstr
        he = ctx.edge_to_hedge(p0, p1)
        if he < 0:
            return True
        path = self._compute_loop(ctx, he)
        if not path:
            self._hide_preview(ctx)
            return True

        self._set_committed_path(ctx, path)
        if ctx.parm_string is not None:
            ctx.parm_string.set(ctx.hedges_to_group_string_mode(path, self.output_mode))
        return True

    def _compute_loop(self, ctx, he):
        if self.mode == LOOP_MODE_QUAD:
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

    def _hide_preview(self, ctx):
        if self.preview is None:
            return
        self.preview.hide(self.ch_preview)
        self._request_draw(ctx)

    def _hide_committed(self, ctx):
        if self.preview is None:
            return
        self.preview.hide(self.ch_committed)
        self._request_draw(ctx)

    def _set_preview_path(self, ctx, hedges):
        self._set_path(ctx, hedges, committed=False)

    def _set_committed_path(self, ctx, hedges):
        self._set_path(ctx, hedges, committed=True)

    def _set_path(self, ctx, hedges, committed):
        if self.preview is None:
            return
        channel = self.ch_committed if committed else self.ch_preview
        if not hedges or ctx.geometry is None:
            self.preview.hide(channel)
            self._request_draw(ctx)
            return
        self.preview.set_line_from_hedges(
            channel,
            ctx.geometry,
            ctx.mesh,
            hedges,
            segments=True,
        )
        self._request_draw(ctx)

    def _request_draw(self, ctx):
        try:
            ctx.scene_viewer.curViewport().draw()
        except Exception:
            pass

    def _hit_edge(self, ctx, ui_event):
        hit = ctx.hit_edge(ui_event)
        if hit is None:
            return None
        return int(hit[0]), int(hit[1])

    def _set_basegroup_from_points(self, ctx, p0, p1):
        ctx.set_basegroup_from_points(p0, p1)

    def _reset_session(self, ctx):
        self._hide_preview(ctx)
        self._hide_committed(ctx)
        ctx.clear_group_parms(GROUP_PARM_NAMES)

    def _is_shift_down(self, dev):
        try:
            return bool(dev.isShiftKey())
        except Exception:
            key = (dev.keyString() or "").lower()
            return "shift" in key

    def _hedge_from_hover(self, ctx, hover):
        if not hover or not hover.get("visible"):
            return -1
        edge = hover.get("edge")
        if edge is None:
            return -1
        return ctx.edge_to_hedge(int(edge[0]), int(edge[1]))
