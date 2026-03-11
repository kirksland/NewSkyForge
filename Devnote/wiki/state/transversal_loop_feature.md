# Transversal Loop Feature

## Purpose

Computes and commits transversal edge loops (roll/quad).
Writes committed loop to `grstr`.

## Inputs / Dependencies

- Requires `ToolContext` with valid mesh and geometry.
- Consumes edge hits or hover edge.

## Lifecycle

- on_enter: sets up preview channels.
- on_exit: hides preview and committed channels.
- on_draw: draws loop preview/committed channels.

## Public API (state orchestration)
- `set_output_mode(mode)`: edge/point/prim encoding.
- `preview_loop_from_he(ctx, he)` / `commit_loop_from_he(ctx, he)`.
- `preview_from_hover(ctx, hover)` / `commit_from_hover(ctx, hover)`.
- `reset_all(ctx)` / `clear_preview(ctx)`.

## Behavior Notes
- Shift + MMB commits loop (if used via direct mouse handler).
- Supports roll/quad modes (R / Q / X).

## Preview Channels

- `CH_LOOP_PREVIEW` (live)
- `CH_LOOP_COMMITTED` (committed)

## See Also

- [Channels](channels.md)
- [Preview Feature](preview_feature.md)
- [Tool Context](tool_context.md)

## Navigation

- [State Index](index.md)
- [Wiki Index](../index.md)
