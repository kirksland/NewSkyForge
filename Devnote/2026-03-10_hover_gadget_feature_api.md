# Devnote - 2026-03-10

## Sujet
Implementation d'une feature plug & play de hover/pick gadget reutilisable dans les viewer states:
- `python/skyforge/forge_states/features/hover_gadget_feature.py`
- state de test: `viewerState/hover_gadget_feature_test_state.py`

## Objectif
Avoir un bloc reutilisable qui gere:
1. hover via `state_context` (`gadget`, `component1`, `component2`)
2. filtering de visibilite (ray) pour point/edge
3. preview hover (edge guide + point hover)
4. retour de payload unifie (pour selection, write parm, chain vers autre feature)
5. clic simple capture (LMB Start)

Sans recoder toute la mecanique dans chaque state.

## API de `HoverGadgetFeature`
### Construction
```python
HoverGadgetFeature(
    line_gadget="line_gadget",
    face_gadget="face_gadget",
    point_gadget="point_gadget",
    point_hover_gadget="point_hover_gadget",
    enable_ray_filter=True,
)
```

### Modes supportes
- `line`
- `face`
- `point`
- `face_point`

### Methodes publiques
1. `bind_template(template)`
- Bind les gadgets requis sur le `ViewerStateTemplate`.

2. `bind_host(state)`
- Branche la feature sur le state (acces `scene_viewer`, `state_gadgets`, `state_context`).

3. `set_geometry(geo)`
- Definit la geometrie source pour pick/visibilite.

4. `set_mode(mode)`
- Change le mode actif (`line`, `face`, `point`, `face_point`).

5. `on_enter(ctx, kwargs)`
- Setup complet (bind gadgets, geometry, params, visibilite mode).

6. `on_mouse_event(ctx, kwargs)`
- Lit le hover gadget courant.
- Applique les filtres visibility.
- Met a jour les overlays.
- Capture un clic simple (LMB Start) dans un buffer interne.

7. `on_draw(ctx, kwargs)`
- Draw gadgets actifs + preview edge hover.

8. `on_exit(ctx, kwargs)`
- Reset/hide.

9. `get_hover()`
- Retourne un dict normalise:
```python
{
  "gadget": str|None,
  "c1": int,
  "c2": int,
  "visible": bool,
  "point": int,    # -1 si N/A
  "edge": (int,int)|None,
  "prim": int,     # -1 si N/A
}
```

10. `consume_click()`
- Retourne le dernier payload clic capture (ou `None`) et le consomme.

11. `clear()`
- Reset explicite des etats hover/click + visuals.

## Integration type dans un state
```python
from skyforge.forge_states.features import HoverGadgetFeature

class State(object):
    def __init__(self, state_name, scene_viewer):
        self.scene_viewer = scene_viewer
        self.mode = "face_point"
        self.hover_feature = HoverGadgetFeature(enable_ray_filter=True)
        self.hover_feature.bind_host(self)

    def onEnter(self, kwargs):
        geo = kwargs["node"].geometry()
        self.hover_feature.bind_host(self)
        self.hover_feature.set_geometry(geo)
        self.hover_feature.set_mode(self.mode)
        self.hover_feature.on_enter(self.ctx, kwargs)

    def onMouseEvent(self, kwargs):
        self.hover_feature.on_mouse_event(self.ctx, kwargs)
        hover = self.hover_feature.get_hover()
        click = self.hover_feature.consume_click()
        return False

    def onDraw(self, kwargs):
        self.hover_feature.on_draw(self.ctx, kwargs)


def createViewerStateTemplate():
    template = hou.ViewerStateTemplate(...)
    template.bindFactory(State)
    HoverGadgetFeature.bind_template(template)
    return template
```

## Mecanique face (etat valide actuel)
- Le hover face est pilote par `face_gadget` + `indices`.
- Reset agressif applique quand pas de face valide:
```python
self.face_gadget.setParams({"indices": []})
```
- Les params auto de locate/pick face sont coupes pour eviter les cas de full overlay global pendant transitions.

## Diff principale avec `face_gadget_test_state`
- `face_gadget_test_state.py` est un state "lab" monolithique.
- `HoverGadgetFeature` encapsule la meme logique dans une API reutilisable.
- Le state test `hover_gadget_feature_test_state.py` montre une integration minimale en deleguant setup/hover/draw a la feature.

## Points de vigilance
1. Les params gadget (`draw_color`, `locate_color`, `pick_color`, `indices`) sont sensibles:
- un `locate_color` face non nul peut donner une teinte globale selon transitions.

2. Toujours reset les channels non actifs:
- face: `indices: []`
- point hover: `indices: []`

3. Filtre ray:
- utile pour point/edge "au travers".
- face actuellement geree par validite context + prim existence (comportement stable cote state lab).

## Fichiers concernes
- `python/skyforge/forge_states/features/hover_gadget_feature.py`
- `python/skyforge/forge_states/features/__init__.py`
- `viewerState/hover_gadget_feature_test_state.py`
- `viewerState/face_gadget_test_state.py` (reference labo)

## Etat actuel
- Feature operationnelle en test state.
- API utilisable pour brancher facilement hover/pick vers selection, parm set, ou chain vers autres features.
