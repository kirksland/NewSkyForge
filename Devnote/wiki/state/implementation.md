# Viewer State Implementation

## Goal

Define a consistent structure for states that compose multiple modules.
The state owns ordering, the context owns runtime data, modules do the work.

## Minimal Structure

1. Create context: initialize ToolContext and prepare editable geometry.
2. Attach hover/selection module: hover is the base interaction state.
3. Attach action modules: draw, move, commit, etc.
4. Enforce ordering in onMouseEvent: hover first, actions second.
5. Draw previews in onDraw.

## Dispatcher Usage

If you use FeatureHub:
- you can route events to modules automatically
- but you still decide the correct order of base interaction vs actions

## HUD

Modules can provide HUD fragments.
States aggregate them into the final HUD template and values.

## Notes

Do not sync editable geometry mid‑drag.
Only commit geometry changes through ctx.push_edit_geo().

## See Also

- [State Pipeline](state_pipeline.md)
- [Dispatcher](dispatcher.md)
- [Tool Context](tool_context.md)
- [Concepts](concepts.md)

## Navigation

- [State Index](index.md)
- [Wiki Index](../index.md)
