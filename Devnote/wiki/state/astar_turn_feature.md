# A* Turn Feature

## Purpose

Provides A* edge path preview and commit on half‑edge meshes.
It writes committed paths into the node group string (`grstr`) and maintains a base edge (`basegroup`).

## Inputs / Dependencies

- Requires `ToolContext` with a valid `mesh`, `geometry`, and `parm_string`.
- Consumes edge hits via `ctx.hit_edge(...)` or a hover edge from the state.

## Lifecycle

- on_enter: builds preview channels, restores committed path from `grstr`, syncs `basegroup`.
- on_exit: hides preview and committed channels.
- on_draw: draws only the A* channels.

## Public API (state orchestration)
- `set_output_mode(mode)`: edge/point/prim encoding.
- `preview_from_base_to_he(ctx, end_he)`: live preview.
- `commit_from_base_to_he(ctx, end_he)`: commit to `grstr`.
- `clear_preview(ctx)` / `reset_all(ctx)`.

## Behavior Notes
- First click can define the start edge if none is set.
- Committed path is merged with existing chain in `grstr`.
- Uses `basegroup` to define the start of the A* path.
- Prevents duplicate commits on double‑click.

## Preview Channels

- `CH_ASTAR_PREVIEW` (live)
- `CH_ASTAR_COMMITTED` (committed)

## See Also

- [Channels](channels.md)
- [Preview Feature](preview_feature.md)
- [Tool Context](tool_context.md)

## Navigation

- [State Index](index.md)
- [Wiki Index](../index.md)
