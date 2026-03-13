## Feature Pipeline Audit (2026-03-13)

Scope: forge_states features + FeatureHub ordering and hover service behavior.

### Summary
- Added `provides/requires` metadata for features and topo ordering in FeatureHub.
- Hover now writes `ctx.services["hover"]` automatically (opt-out available).
- Identified missing dependency modeling and a few implicit services.

### Implemented Changes
- `ViewerFeature` has default `provides` / `requires` (empty).
- `FeatureHub` orders features via topological sort of `provides/requires` with stable fallback.
- `HoverGadgetFeature` now `provides = ("hover",)` and writes hover to `ctx` by default.
- `AstarTurnFeature` and `TransversalLoopFeature` now `requires = ("hover",)`.

### Feature-by-Feature Notes
- HoverGadgetFeature
  - Provides `hover`.
  - Depends on `state_context` + gadget bindings + geometry.
  - Emits click payload via `consume_click()` (no commit payload).

- AstarTurnFeature
  - Requires `hover`.
  - Implicitly depends on `ctx.mesh` + `ctx.geometry`.
  - Returns payload `{mode, group}` on commit.
  - Requires `onKeyTransitEvent` routing to avoid sticky Shift+A.

- TransversalLoopFeature
  - Requires `hover`.
  - Implicitly depends on `ctx.mesh` + `ctx.geometry`.
  - Returns payload `{mode, group}` on commit (Shift+MMB).

- HoverMoveFeature
  - Implicitly depends on `hover`, `ctx.edit_geo`, `ctx.tool_mode`.
  - No payload (direct action).
  - Missing requires declaration, ordering is still manual.

- HoverDrawFeature
  - Implicitly depends on `hover`, `ctx.edit_geo`, `preview`, `ctx.tool_mode`.
  - No payload.
  - Missing requires declaration, ordering is still manual.

- PreviewFeature
  - Manages `preview` service but does not declare `provides`.
  - When `enable_hover=True`, depends on `ctx.services["hit"]`.
  - `hit` is currently produced only by some states (not a feature).

### Frictions / Gaps
- Missing `provides/requires` on several features.
- Dependencies on `mesh`, `edit_geo`, `tool_mode`, `hit` are implicit.
- Preview hover channels are tied to `hit` which is not feature-owned.

### Proposed Follow-ups
- Add provides/requires tokens for:
  - `PreviewFeature` -> provides `preview`, requires `edit_geo` if hover enabled.
  - `HoverMoveFeature` -> requires `hover`, `edit_geo`, `tool_mode`.
  - `HoverDrawFeature` -> requires `hover`, `edit_geo`, `preview`, `tool_mode`.
- Consider a small `HitFeature` that writes `ctx.set_service("hit", ...)` to remove state coupling.
- Standardize token names (`hover`, `hit`, `preview`, `mesh`, `edit_geo`, `tool_mode`) in one place.
