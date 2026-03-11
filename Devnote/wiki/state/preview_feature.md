# Preview Feature

## Purpose

Shared preview service wrapper.
Draws hover/guide channels (points, edges, faces) in a centralized place.

## Inputs / Dependencies

- Requires a PreviewService (created if missing).
- Consumes `ctx.services["hit"]` for generic hover preview when enabled.

## Lifecycle

- on_enter: creates preview service and hover channels.
- on_exit: hides all channels.
- on_mouse_event: updates hover channels from `hit`.
- on_draw: draws all channels.

## Notes

- Typically used by states that rely on `hit_info` (legacy or non‑gadget).
- Point radius can be updated via `apply_point_radius(ctx)`.

## See Also

- [Channels](channels.md)
- [Tool Context](tool_context.md)
- [State Pipeline](state_pipeline.md)

## Navigation

- [State Index](index.md)
- [Wiki Index](../index.md)
