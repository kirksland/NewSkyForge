## ViewerState Builder + Feature Pipeline Status (2026-03-15)

### Scope
This note captures the current state of the viewer-state pipeline refactor, the feature API, HUD handling, and the new ViewerState Builder tool. It summarizes what changed, what is stable, and what is still TODO.

### High-Level Architecture
- ViewerState owns the entry points and binds a `ToolContext`.
- `ToolContext` is the shared runtime bucket: geo, mesh, services, mode flags, and feature-owned data.
- `FeatureHub` is the dispatcher and ordering layer. It resolves `provides/requires`, manages HUD, and forwards events.
- Features are small modules, ideally with:
  - `provides` and `requires` lists.
  - `builder_schema()` to expose setup actions for the Builder UI.
  - Optional HUD rows and ctx services.

### BaseState API (global helpers)
`BaseState` now standardizes the boilerplate work most states were repeating.
- `bind_context(ctx, kwargs, ensure_geo=True, ensure_mesh=True)`
  - Sets `node`, `host`, `geometry`, `mesh` on the context.
  - Ensures `ToolContext` is ready for features (geometry and mesh are prepared).
- `enter_with_hud(hub, ctx, kwargs, scene_viewer, base_template=None)`
  - Calls `hub.enter(...)`
  - Applies HUD template and rows defined by features.
  - Reduces per-state HUD duplication.

### ToolContext Usage (runtime data)
- `ctx.set_node(node)` and `ctx.set_service("host", self)` are now standardized via `bind_context`.
- `ensure_geo()` and `ensure_mesh()` are now called by default in `bind_context`.
- Features read and write services via `ctx.set_service(...)` and `ctx.get_service(...)`.

### FeatureHub API (ordering + HUD)
`FeatureHub` now does more than call feature hooks.
- Ordering:
  - `provides/requires` are resolved in `_resolve_order`.
  - The order is deterministic and feature-driven.
- Event dispatch:
  - `mouse_collect(...)` aggregates feature payloads via the dispatcher.
- HUD:
  - `apply_hud(...)` builds the final HUD template from feature contributions.
  - `update_hud(...)` filters values to only existing HUD row ids.
  - This prevents `KeyError` when a feature does not provide a given HUD row.

### Features Updated
HoverGadgetFeature
- Writes hover data into `ctx` (service key `hover`) when enabled.
- Adds HUD rows for hover status and a hover mode choice graph.
- Auto-binds host from `ctx` on `on_enter`.
- New `builder_schema()`:
  - Setup actions: `set_mode`, `set_allowed_modes`.
  - Exposes mode selection for the Builder.

AstarTurnFeature
- Added `builder_schema()` with output mode config.

TransversalLoopFeature
- Added `builder_schema()` with `mode` and `output_mode`.
- Added `set_mode(...)` for runtime configuration.

PreviewFeature / PreviewService
- Already central to draw channels, now surfaced in diagrams and HUD flow.

### Viewer States Updated
States now use standardized plumbing.
- `astar_loop_payload_state.py`
  - Uses `bind_context` and `enter_with_hud`.
  - Uses hub dispatch to collect payloads.
  - Writes payload to `grstr` parm on selection.
  - No longer manually wires hover.
- Other states updated to inject host into ctx:
  - `dispatcher_modular_state.py`
  - `edit_modular_state.py`
  - `hover_curve_modular_state.py`
  - `auto_axis_modular_state.py`
  - `astar_hover_blend_test_state.py`

### ViewerState Builder Tool
File: `SkyForge/python/skyforge/forge_tools/viewerState_builder.py`

Purpose
- Build a new viewer state using the new pipeline.
- Pick features, configure init params and setup actions.
- Generate boilerplate state code into an embedded Python editor.

UI Layout
- 3 columns with a `QSplitter` for resizing.
- Column 1: Python editor (SideFX PythonEditor), Save, Reset Session.
- Column 2: Tabs for Debug / Commit (fake for now).
- Column 3: Feature picker and dynamic blocks.

Feature Blocks
- Each selected feature spawns a block.
- Blocks are collapsible and removable.
- `__init__ params` are read from `__init__` signature.
- `Setup actions` are read from `builder_schema()`.
- Each action renders with a matching widget type.

Code Generation
- `build_state_code(state_name, blocks)` outputs a template based on the new pipeline.
- `Append` option to keep previous code or replace.
- Generated code includes:
  - `ToolContext`
  - `FeatureHub`
  - `bind_context(...)`
  - `enter_with_hud(...)`
  - Hub-driven event flow and HUD updates.

Session Management
- The builder is stored as a singleton in `hou.session._py_scratchpad`.
- `Reset Session` clears the singleton and closes the window.

### Devnotes Updated
- `SkyForge/Devnote/2026-03-13_feature_pipeline_audit.md`
- `SkyForge/Devnote/2026-03-13_feature_pipeline_diagrams.md`

### Known Frictions
- Some features still lack `builder_schema()` and will show limited setup actions.
- The generated state still assumes the BaseState helpers exist and are used consistently.
- HUD templates are feature-driven; states should avoid hardcoding HUD rows.

### Next Steps (Proposed)
1. Add `builder_schema()` for remaining features.
2. Expose common per-feature helpers in schema (mode, filters, output modes).
3. Add actual debug/log output to the middle column.
4. Optional: add live validation (missing requires, invalid combos) in the Builder.
