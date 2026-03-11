# Tool Context

## Purpose

Define the shared runtime context for modular viewer states.

## Core Responsibilities

- Hold the bound node and scene viewer.
- Cache geometry and topology helpers.
- Provide services for feature-to-feature communication.
- Manage editable stash geometry for commit workflows.

## Key Services

- `ctx.services["preview"]`: shared PreviewService.
- `ctx.services["hover"]`: normalized hover payload.
- `ctx.services["hit"]`: ray hit payload for non-gadget tools.
- `ctx.services["hover_payload"]`: feature-specific hover data.

## Geometry Flow

- `ensure_geo()` refreshes read-only geometry from the node.
- `ensure_mesh()` rebuilds intersector + half-edge mesh only when topology changes.
- `hit_info()` returns edge/point/prim + hit position in one payload.

## Editable Geometry Flow

- `ensure_edit_geo()` creates/reuses stash-backed editable geometry.
- `sync_edit_geo()` pulls changes when Houdini cooks or undo/redo occurs.
- `push_edit_geo()` commits the edited geometry back to the stash.

## Important Invariants

- Do not sync editable geometry mid-drag.
- Only commit changes through `ctx.push_edit_geo()`.
- Always refresh mesh after topology changes.

## See Also

- [Concepts](concepts.md)
- [Channels](channels.md)
- [Preview Feature](preview_feature.md)
- [State Pipeline](state_pipeline.md)

## Navigation

- [State Index](index.md)
- [Wiki Index](../index.md)
