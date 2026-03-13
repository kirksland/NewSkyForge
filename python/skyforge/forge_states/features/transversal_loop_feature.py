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
    OUTPUT_MODE_EDGE,
    OUTPUT_MODE_POINT,
    OUTPUT_MODE_PRIM,
    CH_LOOP_PREVIEW,
    CH_LOOP_COMMITTED,
)


class TransversalLoopFeature(ViewerFeature):
    """
    Transversal loop feature for edge-based loop preview/commit.

    Owns two preview channels:
    - `ch_preview`: live loop preview
    - `ch_committed`: committed loop (payload output)
    """
    name = "transversal_loop"
    requires = ("hover",)

    def __init__(self):
        """Initialize runtime mode, output mode, and preview channel names."""
        self.preview = None
        self.ch_preview = CH_LOOP_PREVIEW
        self.ch_committed = CH_LOOP_COMMITTED
        self.mode = LOOP_MODE_ROLL  # transversal or quad
        self.output_mode = OUTPUT_MODE_EDGE

    def on_enter(self, ctx, kwargs):
        """Initialize/reuse preview service and ensure loop channels exist."""
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


    def on_exit(self, ctx, kwargs):
        """Hide loop preview and committed channels."""
        self._hide_preview(ctx)
        self._hide_committed(ctx)

    def on_draw(self, ctx, kwargs):
        """Draw only loop owned channels on the shared preview service."""
        preview = self.preview or ctx.get_service("preview")
        if preview is None:
            return
        draw_handle = kwargs.get("draw_handle")
        if draw_handle is None:
            return
        preview.draw_channels(draw_handle, (self.ch_preview, self.ch_committed))

    def on_key_event(self, ctx, kwargs):
        return False

    # ------------------------------------------------------------------
    # Menu + hotkeys
    # ------------------------------------------------------------------
    @staticmethod
    def build_hotkeys(definitions, state_typename):
        """Register hotkey context + defaults for loop mode actions."""
        key_context = "h.pane.gview.state.sop.{0}".format(state_typename)
        key_category = "h.pane.gview.state.sop.{0}".format(state_typename)

        if not definitions.containsContext(key_context):
            definitions.addContext(
                key_context,
                "{0} Operation".format(state_typename),
                "Keys for {0} viewer state.".format(state_typename),
            )
        if not definitions.containsCommandCategory(key_category):
            definitions.addCommandCategory(
                key_category,
                "{0} Operation".format(state_typename),
                "Commands for {0} viewer state.".format(state_typename),
            )

        def _cmd(name, label, desc, default_keys):
            symbol = key_category + "." + name
            if not definitions.containsCommand(symbol):
                definitions.addCommand(symbol, label, desc)
            if default_keys:
                definitions.addDefaultBinding(key_context, symbol, default_keys)
            return symbol

        return {
            "loop_mode_roll": _cmd("loop_mode_roll", "Loop Mode: Roll", "Loop mode: roll", ["r"]),
            "loop_mode_quad": _cmd("loop_mode_quad", "Loop Mode: Quad", "Loop mode: quad", ["q"]),
            "loop_mode_toggle": _cmd("loop_mode_toggle", "Loop Mode: Toggle", "Loop mode: toggle", ["x"]),
        }

    @staticmethod
    def build_menu(state_typename, state_label=None, hotkeys=None):
        """Create a ViewerStateMenu with loop mode actions."""
        label = state_label or state_typename or "Loop"
        menu = hou.ViewerStateMenu(state_typename + "_loop_menu", label + " Loop")
        menu.addActionItem("loop_mode_roll", "Loop Mode: Roll", hotkeys.get("loop_mode_roll") if hotkeys else None)
        menu.addActionItem("loop_mode_quad", "Loop Mode: Quad", hotkeys.get("loop_mode_quad") if hotkeys else None)
        menu.addSeparator()
        menu.addActionItem("loop_mode_toggle", "Loop Mode: Toggle", hotkeys.get("loop_mode_toggle") if hotkeys else None)
        return menu

    @staticmethod
    def extend_menu(menu, hotkeys=None, add_separator=True):
        """Append loop mode actions to an existing ViewerStateMenu."""
        if menu is None:
            return None
        if add_separator:
            menu.addSeparator()
        menu.addActionItem("loop_mode_roll", "Loop Mode: Roll", hotkeys.get("loop_mode_roll") if hotkeys else None)
        menu.addActionItem("loop_mode_quad", "Loop Mode: Quad", hotkeys.get("loop_mode_quad") if hotkeys else None)
        menu.addActionItem("loop_mode_toggle", "Loop Mode: Toggle", hotkeys.get("loop_mode_toggle") if hotkeys else None)
        return menu

    @staticmethod
    def install_menu(template, state_typename, state_label=None):
        """Create and bind a loop mode menu + hotkeys onto the template."""
        hotkey_defs = hou.PluginHotkeyDefinitions()
        hotkeys = TransversalLoopFeature.build_hotkeys(hotkey_defs, state_typename)
        menu = TransversalLoopFeature.build_menu(state_typename, state_label, hotkeys=hotkeys)
        template.bindMenu(menu)
        template.bindHotkeyDefinitions(hotkey_defs)
        return menu

    def handle_menu_action(self, kwargs):
        action = kwargs.get("menu_item")
        if action == "loop_mode_roll":
            self.mode = LOOP_MODE_ROLL
            return True
        if action == "loop_mode_quad":
            self.mode = LOOP_MODE_QUAD
            return True
        if action == "loop_mode_toggle":
            self.mode = LOOP_MODE_QUAD if self.mode == LOOP_MODE_ROLL else LOOP_MODE_ROLL
            return True
        return False

    def on_menu_pre_open(self, kwargs):
        menu_id = kwargs.get("menu")
        if not menu_id or not str(menu_id).endswith("_loop_menu"):
            return False
        menu_item_states = kwargs.get("menu_item_states")
        if not isinstance(menu_item_states, dict):
            return False
        menu_item_states["loop_mode_roll"]["enable"] = True
        menu_item_states["loop_mode_quad"]["enable"] = True
        menu_item_states["loop_mode_toggle"]["enable"] = True
        return True

    # ------------------------------------------------------------------
    # HUD helpers (optional)
    # ------------------------------------------------------------------
    def hud_template(self):
        return [
            {"id": "loop_mode", "label": "Loop Mode"},
            {"id": "loop_mode_keys", "label": "Mode Keys"},
        ]

    def hud_values(self, ctx=None):
        label = "Roll" if self.mode == LOOP_MODE_ROLL else "Quad"
        keys_txt = "R / Q / X"
        return {
            "loop_mode": label,
            "loop_mode_keys": keys_txt,
        }

    # Public API used by pyd_loop_modular orchestrator
    def clear_preview(self, ctx):
        """Clear loop preview channel only."""
        self._hide_preview(ctx)

    def reset_all(self, ctx):
        """Reset loop session state and clear related group parms/channels."""
        self._reset_session(ctx)

    def set_output_mode(self, mode):
        """Set commit output mode: edge, point, or prim."""
        self.output_mode = (mode or OUTPUT_MODE_EDGE).lower().strip()

    def set_basegroup_from_edge(self, ctx, p0, p1):
        # Deprecated: kept for compatibility (no-op, no parm writes).
        self._set_basegroup_from_points(ctx, p0, p1)

    def preview_edge(self, ctx, p0, p1):
        he = ctx.edge_to_hedge(p0, p1)
        if he < 0:
            self._hide_preview(ctx)
            return False

        self._set_preview_path(ctx, [he])
        return True

    def preview_loop_from_he(self, ctx, he):
        """Compute and display loop preview for a target half-edge."""
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
        """Commit loop from target half-edge into parm string and channel."""
        if he < 0:
            return False
        path = self._compute_loop(ctx, int(he))
        if not path:
            self._hide_preview(ctx)
            return False
        self._set_committed_path(ctx, path)
        return self._payload_from_hedges(ctx, path)

    def commit_loop_from_edge(self, ctx, p0, p1):
        he = ctx.edge_to_hedge(p0, p1)
        return self.commit_loop_from_he(ctx, he)

    def commit_from_hover(self, ctx, hover):
        """Convenience wrapper to commit from normalized hover payload."""
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

        # Selection sync only (no parm writes in payload mode).
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

        # Auto output mode from hover payload when available.
        hover = ctx.get_service("hover") if hasattr(ctx, "get_service") else None
        if hover:
            auto_mode = self._output_mode_from_hover(hover)
            if auto_mode is not None:
                self.output_mode = auto_mode

        pair = self._hit_edge(ctx, ui)
        if pair is None:
            self._reset_session(ctx)
            return True
        p0, p1 = pair

        # Shift + LMB => anchor only (no commit)
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
        return self._payload_from_hedges(ctx, path)

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
        # Deprecated hook: no-op (payload-only mode, no parm writes).
        pass

    def _payload_from_hedges(self, ctx, hedges):
        group = ctx.hedges_to_group_string_mode(hedges, self.output_mode)
        return {
            "mode": self.output_mode,
            "group": group,
        }

    def _reset_session(self, ctx):
        self._hide_preview(ctx)
        self._hide_committed(ctx)

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

    def _output_mode_from_hover(self, hover):
        if not hover or not hover.get("visible"):
            return None
        if int(hover.get("prim", -1)) >= 0:
            return OUTPUT_MODE_PRIM
        if int(hover.get("point", -1)) >= 0:
            return OUTPUT_MODE_POINT
        if hover.get("edge") is not None:
            return OUTPUT_MODE_EDGE
        return None
