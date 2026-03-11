## Pipeline Viewer States

Overview
This pipeline defines a predictable architecture for Houdini viewer states.
Its goals are:
- clear execution order
- modular, composable interactions
- minimal duplication across states

## Architecture
The system is organized in three layers:
1. Orchestration (state)
2. Runtime (context)
3. Actions (modules)

## Orchestration (State)
The state is responsible for:
- creating and owning the runtime context
- initializing editable geometry
- enforcing execution order
- delegating to action modules
- managing lifecycle (enter / draw / events / exit)

## Runtime (Context)
The context provides shared runtime data:
- scene viewer, node, and editable geometry
- shared services for cross‑module data exchange
It is the single source of truth for the current session.

Actions (Modules)
Action modules implement isolated behavior (hover, draw, move, commit, preview).
They are assembled by the state and executed in a defined order.

## Execution Flow
1. Setup (onEnter)
   - create context
   - create/editable geometry
   - initialize actions
2. Interaction (onMouseEvent / onKeyEvent)
   - compute base interaction state (hover/selection)
   - consume that state in action modules
3. Render (onDraw)
   - draw visual feedback and previews
4. Cleanup (onExit)
   - detach and clear runtime state

Ordering Rules
Ordering is critical:
- a module that consumes hover must run after hover is produced
- geometry sync must not interrupt a drag
The state guarantees this order.

## Optional Dispatcher
A dispatcher can be used to reduce boilerplate by routing events to modules.
It does not replace orchestration; the state still controls ordering.

## HUD Guidance
The pipeline supports modular HUD fragments.
Modules can expose small HUD fragments; states assemble them into a single HUD.

Recommended Workflow (New State)
1. Create context and editable geometry.
2. Attach a hover/selection module (base interaction state).
3. Attach action modules that consume that state.
4. Ensure correct ordering in onMouseEvent.
5. Provide minimal HUD guidance (mode + keys).

Notes
This document is intentionally high‑level.
Implementation details live in separate feature documentation.
