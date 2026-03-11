# Hover Move Feature

## Purpose

Moves hovered points/edges/faces using a view‑plane drag.
Consumes the hover payload provided by hover_gadget.

## Inputs / Dependencies

- Requires `ctx.edit_geo` (editable geometry).
- Requires hover payload stored in `ctx.services["hover"]` or passed via kwargs.
- Active only when `ctx.tool_mode == MOVE`.

## Lifecycle

- on_enter: resets picker and drag state.
- on_exit: ends drag.
- on_mouse_event: LMB drag to move.

## Behavior

- LMB Start: resolves hover -> points + origin, starts drag.
- Active/Changed: applies delta to affected points.
- Uses `curveutils.curve3DPicker` for ray/plane movement.

## Notes

- No persistent selection. Each drag acts on the current hover target.

## See Also

- [Hover Gadget Feature](hover_gadget_feature.md)
- [Tool Context](tool_context.md)
- [State Pipeline](state_pipeline.md)

## Navigation

- [State Index](index.md)
- [Wiki Index](../index.md)
