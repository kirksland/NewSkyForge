# Devnote - 2026-03-10

## Sujet
API `HoverGadgetFeature` apres simplification du bootstrap (option B) avec integration dans:
- `viewerState/astar_hover_blend_test_state.py`

## Objectif
Avoir une feature hover/pick vraiment plug & play dans un state:
1. setup en un appel
2. boucle mouse event en un appel
3. draw en un appel
4. teardown en un appel

Sans perdre l'API bas niveau existante.

## API publique (haut niveau)
Fichier: `python/skyforge/forge_states/features/hover_gadget_feature.py`

### `attach(host, ctx, kwargs, geometry=None, mode=None)`
Fait le bootstrap complet:
- `bind_host(host)`
- resolution/assign geometry (argument explicite sinon `kwargs["node"].geometry()`)
- `set_mode(mode)` si fourni
- `on_enter(ctx, kwargs)`

Usage:
```python
self.hover_feature.attach(
    host=self,
    ctx=self.ctx,
    kwargs=kwargs,
    geometry=kwargs["node"].geometry(),
    mode="face_point",
)
```

### `tick(ctx, kwargs) -> (hover_payload, click_payload)`
Fait une iteration interaction:
- `on_mouse_event(ctx, kwargs)`
- retourne `get_hover()`
- retourne `consume_click()`

Usage:
```python
hover, click = self.hover_feature.tick(self.ctx, kwargs)
```

### `draw(ctx, kwargs)`
Alias de `on_draw(ctx, kwargs)`.

### `detach(ctx, kwargs)`
Alias de `on_exit(ctx, kwargs)`.

## API bas niveau (toujours disponible)
Aucune suppression:
- `bind_template(template)`
- `bind_host(state)`
- `set_geometry(geo)`
- `set_mode(mode)`
- `on_enter / on_mouse_event / on_draw / on_exit`
- `get_hover()`
- `consume_click()`
- `clear()`

## Payload retour
`hover_payload` (via `get_hover`) conserve le format:
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

`click_payload` est `None` ou un snapshot du hover au moment du clic LMB Start.

## Integration type dans un state
Extrait simplifie (pattern actuel):

```python
class State(object):
    def __init__(self, state_name, scene_viewer):
        self.scene_viewer = scene_viewer
        self.hover_feature = HoverGadgetFeature(enable_ray_filter=True)
        self.mode = "line"

    def onEnter(self, kwargs):
        self.hover_feature.attach(
            host=self,
            ctx=self.ctx,
            kwargs=kwargs,
            geometry=kwargs["node"].geometry(),
            mode=self.mode,
        )

    def onMouseEvent(self, kwargs):
        hover, click = self.hover_feature.tick(self.ctx, kwargs)
        # logique metier (A* start/end, write parm, etc.)
        return False

    def onDraw(self, kwargs):
        self.hover_feature.draw(self.ctx, kwargs)

    def onExit(self, kwargs):
        self.hover_feature.detach(self.ctx, kwargs)
```

## Cas A* (ce qu'on vient de valider)
Dans `astar_hover_blend_test_state.py`:
1. `tick()` fournit le hover courant pour preview edge
2. `click_payload` permet de distinguer et stocker:
- clic 1 -> `start_edge`
- clic 2 -> `end_edge`
3. la machine d'etat (`pick_start` / `pick_end`) reste dans le state metier
4. la feature reste responsable uniquement de hover/pick/preview

## Pourquoi ce decoupage est utile
- Le state ne gere plus le boilerplate gadget.
- La logique metier (A*, selection, param assignment) reste lisible.
- On peut encore basculer sur l'API bas niveau si un state a des besoins speciaux.

## Limites actuelles
1. La feature ne remplace pas la logique metier (state machine, validation domaine).
2. Le ray-filter est surtout pertinent pour point/edge visibles.
3. Les reglages couleur/params gadget restent sensibles et doivent etre testes par mode.

## Fichiers lies
- `python/skyforge/forge_states/features/hover_gadget_feature.py`
- `viewerState/astar_hover_blend_test_state.py`
- `viewerState/hover_gadget_feature_test_state.py`
- `viewerState/face_gadget_test_state.py` (reference comportement)
