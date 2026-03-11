# Hover Gadget Feature

## Purpose

Provides a single, normalized hover payload (point/edge/face) using Houdini gadgets.
This is the base interaction signal for the pipeline.

## Inputs / Dependencies

- Requires a state with `state_gadgets` and `state_context`.
- Requires geometry assigned via `set_geometry` or `attach`.

## Lifecycle

- on_enter: binds gadgets, applies geometry, setup params, applies mode visibility.
- on_exit: clears hover state and hides gadgets/drawables.
- on_mouse_event: reads gadget hover and updates payload.
- on_draw: draws active gadgets and optional edge guide.

## Hover Payload (normalized)

- `visible`: bool
- `point`: int (or -1)
- `edge`: (p0, p1) or None
- `prim`: int (or -1)

## Modes

- `MODE_POINT`, `MODE_LINE` (edge), `MODE_FACE`.
- `allowed_modes` can restrict the available modes.

## Menu + Hotkeys

- Provides `install_menu(...)` to bind a context menu and hotkeys.
- Default AZERTY bindings: `&` Point, `é` Edge, `"` Face.

## HUD

- Exposes `hud_template()` and `hud_values()` for mode and key hints.

## See Also

- [Dispatcher](dispatcher.md)
- [Tool Context](tool_context.md)
- [State Pipeline](state_pipeline.md)

## Navigation

- [State Index](index.md)
- [Wiki Index](../index.md)
