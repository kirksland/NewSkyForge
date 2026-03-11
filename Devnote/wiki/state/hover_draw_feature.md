# Hover Draw Feature

## Purpose

Draws a polyline by adding points with LMB, and dragging the last point.
Compatible with hover pipeline and curveutils snapping.

## Inputs / Dependencies

- Requires `ctx.edit_geo`.
- Uses hover payload as a base position when available.
- Active only when `ctx.tool_mode == DRAW`.

## Lifecycle

- on_enter: initializes picker and preview channels.
- on_exit: clears previews and drag state.
- on_mouse_event: LMB Start = append point, Drag = move last point.

## Behavior

- Each click creates a point and connects it to the previous one.
- Dragging updates the last point position.
- `commit_curve(ctx)` resets the active point list to start a new curve.

## Preview Channels

- `CH_CURVE_POINTS` (points)
- `CH_CURVE_LINE` (polyline)

## See Also

- [Channels](channels.md)
- [Preview Feature](preview_feature.md)
- [Tool Context](tool_context.md)

## Navigation

- [State Index](index.md)
- [Wiki Index](../index.md)
