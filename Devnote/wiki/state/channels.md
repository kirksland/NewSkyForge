# Channels

## Purpose

Explain preview channels and how features share a PreviewService instance.

## PreviewService Overview

PreviewService owns named channels for drawables.
Each channel is one of:
- line
- point
- face

## Channel Lifecycle

- ensure_* creates or updates a channel (line/point/face).
- set_* updates the channel geometry or indices.
- hide hides a channel without deleting it.
- draw_* renders the channel on a draw handle.

## Shared Service Pattern

- The PreviewService is stored in `ctx.services["preview"]`.
- Features reuse the same service and define their own channel names.
- Channel names should be stable and unique within a state.

## Why Channels Matter

- They isolate visuals per feature without duplicating draw handles.
- They keep previews cheap: hide/show instead of rebuilding every frame.

## Notes

- A channel is not visible until it has geometry and is shown.
- Always hide channels on feature exit to avoid stale visuals.

## See Also

- [Preview Feature](preview_feature.md)
- [Hover Draw Feature](hover_draw_feature.md)
- [A* Turn Feature](astar_turn_feature.md)
- [Transversal Loop Feature](transversal_loop_feature.md)

## Navigation

- [State Index](index.md)
- [Wiki Index](../index.md)
