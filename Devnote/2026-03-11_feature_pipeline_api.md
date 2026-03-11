# Devnote - 2026-03-11

## Sujet
API pipeline features (hover + A* + transversal loop) apres migration draw par channels.

## Objectif
Documenter le contrat d'integration actuel pour:
- `HoverGadgetFeature`
- `AstarTurnFeature`
- `TransversalLoopFeature`

Et clarifier le point important: draw cible par channels (plus de `draw_all` implicite dans ces features).

## Architecture rapide
1. `HoverGadgetFeature` gere hover/pick gadget et renvoie un payload normalise.
2. `AstarTurnFeature` et `TransversalLoopFeature` utilisent un `PreviewService` partage.
3. Chaque feature dessine uniquement ses channels via `preview.draw_channels(...)`.

## PreviewService (nouveau contrat draw)
Fichier: `python/skyforge/forge_states/preview_service.py`

Methodes utiles:
- `draw_channel(handle, name)`
- `draw_channels(handle, names)`
- `draw_all(handle)` (debug/global uniquement)

Regle:
- Dans les features metier, preferer `draw_channels` avec les channels possedes par la feature.

## HoverGadgetFeature API
Fichier: `python/skyforge/forge_states/features/hover_gadget_feature.py`

### Setup
- `HoverGadgetFeature.bind_template(template)`
- `attach(host, ctx, kwargs, geometry=None, mode=None)`

### Runtime
- `tick(ctx, kwargs) -> (hover_payload, click_payload)`
- `draw(ctx, kwargs)`
- `detach(ctx, kwargs)`

### Etat / utilitaires
- `set_mode(mode)`
- `set_geometry(geo)`
- `get_hover()`
- `consume_click()`
- `clear()`

### Payload hover
```python
{
  "gadget": str | None,
  "c1": int,
  "c2": int,
  "visible": bool,
  "point": int,
  "edge": (int, int) | None,
  "prim": int,
}
```

## AstarTurnFeature API
Fichier: `python/skyforge/forge_states/features/astar_turn_feature.py`

Channels possedes:
- `CH_ASTAR_PREVIEW`
- `CH_ASTAR_COMMITTED`

Methodes d'orchestration:
- `on_enter(ctx, kwargs)`
- `on_draw(ctx, kwargs)` -> draw seulement ses channels
- `on_exit(ctx, kwargs)`
- `preview_from_base_to_he(ctx, end_he)`
- `commit_from_base_to_he(ctx, end_he)`
- `clear_preview(ctx)`
- `reset_all(ctx)`
- `set_output_mode(mode)`

## TransversalLoopFeature API
Fichier: `python/skyforge/forge_states/features/transversal_loop_feature.py`

Channels possedes:
- `CH_LOOP_PREVIEW`
- `CH_LOOP_COMMITTED`

Methodes d'orchestration (pipeline moderne):
- `on_enter(ctx, kwargs)`
- `on_draw(ctx, kwargs)` -> draw seulement ses channels
- `on_exit(ctx, kwargs)`
- `preview_loop_from_he(ctx, he)`
- `commit_loop_from_he(ctx, he)`
- `preview_from_hover(ctx, hover)`
- `commit_from_hover(ctx, hover)`
- `clear_preview(ctx)`
- `reset_all(ctx)`
- `set_output_mode(mode)`

Note:
- La methode `on_mouse_event` legacy existe encore pour compat, mais le pipeline recommande passe par `HoverGadgetFeature` + appels explicites `*_from_he` / `*_from_hover`.

## Integration type dans un state
```python
self.hover_feature.attach(host=self, ctx=self.ctx, kwargs=kwargs, geometry=self.ctx.geometry, mode="line")
self.astar_feature.on_enter(self.ctx, kwargs)
self.loop_feature.on_enter(self.ctx, kwargs)

hover, click = self.hover_feature.tick(self.ctx, kwargs)
# convert hover -> he puis appeler A* / loop selon tool mode

self.hover_feature.draw(self.ctx, kwargs)
self.astar_feature.on_draw(self.ctx, kwargs)
self.loop_feature.on_draw(self.ctx, kwargs)
```

## Point d'attention
- Si le state n'appelle pas `feature.on_draw(...)`, les channels de cette feature ne sont pas visibles.
- Avantage: plus de double draw global involontaire entre features partageant le meme `PreviewService`.

## Fichiers concernes
- `python/skyforge/forge_states/preview_service.py`
- `python/skyforge/forge_states/features/hover_gadget_feature.py`
- `python/skyforge/forge_states/features/astar_turn_feature.py`
- `python/skyforge/forge_states/features/transversal_loop_feature.py`
- `viewerState/astar_hover_blend_test_state.py`
- `viewerState/pyd_loop_modular.py`
