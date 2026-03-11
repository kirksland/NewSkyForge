# State Pipeline

## Purpose

Describe what the viewer state owns in the modular pipeline.

## State Responsibilities

- Create and own ToolContext.
- Build and order features.
- Enforce input ordering (hover first, actions after).
- Aggregate HUD fragments from features.
- Manage entry/exit lifecycle.

## Minimal Order (Typical)

1. onEnter: ctx.set_node(), ctx.ensure_edit_geo(), ctx.ensure_mesh(), feature.attach / hub.enter.
2. onMouseEvent: ensure geo + mesh, hover feature first, action features after, publish outputs in ctx.services.
3. onDraw: draw hover guides, draw feature previews, update HUD.
4. onExit: detach features, hide channels.

## Feature Registry

BaseState exposes:
- register_feature(name, feature)
- get_feature(name)

## Notes

- The state is the only place allowed to decide ordering.
- If you need deterministic inputs, do not rely on FeatureHub defaults.

## See Also

- [Concepts](concepts.md)
- [Dispatcher](dispatcher.md)
- [Tool Context](tool_context.md)
- [Implementation Overview](implementation.md)

## Navigation

- [State Index](index.md)
- [Wiki Index](../index.md)
