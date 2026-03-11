# Dispatcher

## Purpose

Describe the FeatureHub dispatcher used to route viewer-state callbacks to features.

## What It Is

FeatureHub is a small, ordered dispatcher. It calls feature hooks if they exist:
- on_enter
- on_exit
- on_draw
- on_mouse_event
- on_key_event
- handle_menu_action

## Dispatch Rules

- Order matters. Features are called in the order provided to FeatureHub.
- Consumption is optional. `stop_on_consume=True` stops on first truthy return.
- Fail-safe. Exceptions are caught and ignored so one feature cannot crash the state.

## State Responsibilities

- The state still decides the ordering. FeatureHub does not reorder for you.
- The state decides which dispatcher handles which phase.
- The state decides where to store shared outputs in ctx.services.

## Typical Pattern

- Hover feature first to produce `ctx.services["hover"]`.
- Action features after hover.
- on_draw: draw hover first, then feature previews.

## Notes

- FeatureHub is intentionally minimal; it is not a dependency solver.
- If a feature must run before another, enforce that order in the FeatureHub list.

## See Also

- [State Pipeline](state_pipeline.md)
- [Concepts](concepts.md)
- [Hover Gadget Feature](hover_gadget_feature.md)
- [Preview Feature](preview_feature.md)

## Navigation

- [State Index](index.md)
- [Wiki Index](../index.md)
