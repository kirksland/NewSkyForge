# Devnote - 2026-03-10

## Titre
Wiki d'integration: `HoverGadgetFeature` + `AstarTurnFeature`

## Fichiers de reference
- `python/skyforge/forge_states/features/hover_gadget_feature.py`
- `python/skyforge/forge_states/features/astar_turn_feature.py`
- `viewerState/astar_hover_blend_test_state.py`
- `viewerState/face_gadget_test_state.py` (state labo de reference)

## But
Construire un state qui:
1. recupere l'edge hover via gadget (`c1/c2`)
2. choisit un `start edge` au clic
3. previsualise le chemin A* vers l'edge hover
4. commit le chemin au clic suivant (`end edge`)

Le tout en restant modulaire via features.

---

## 1) API utile de `HoverGadgetFeature`

### Creation
```python
hover_feature = HoverGadgetFeature(enable_ray_filter=True)
```

### Setup
```python
hover_feature.bind_host(self)           # self = state (pour state_context + state_gadgets)
hover_feature.set_geometry(self.ctx.geometry)
hover_feature.set_mode(HoverGadgetFeature.MODE_LINE)
hover_feature.on_enter(self.ctx, kwargs)
```

### Runtime
```python
hover_feature.on_mouse_event(self.ctx, kwargs)
hover = hover_feature.get_hover()
click = hover_feature.consume_click()
```

### Draw
```python
hover_feature.on_draw(self.ctx, kwargs)
```

### Payload hover
`get_hover()` retourne:
```python
{
  "gadget": str|None,
  "c1": int,
  "c2": int,
  "visible": bool,
  "point": int,       # -1 si N/A
  "edge": (int,int)|None,
  "prim": int,        # -1 si N/A
}
```

### Click payload
`consume_click()` retourne le dernier payload clique (LMB Start), puis reset interne.

---

## 2) API utile de `AstarTurnFeature`

### Setup
```python
preview_feature.on_enter(ctx, kwargs)  # requis: service preview
astar_feature.on_enter(ctx, kwargs)
```

### Operations principales
```python
astar_feature.preview_from_base_to_he(ctx, end_he)
astar_feature.commit_from_base_to_he(ctx, end_he)
astar_feature.clear_preview(ctx)
astar_feature.reset_all(ctx)
```

### Entree attendue
- `end_he` = half-edge id valide
- conversion depuis hover edge:
```python
he = ctx.edge_to_hedge(c1, c2)
```

---

## 3) Pattern d'orchestration (state machine)

### Phases
- `pick_start`
- `pick_end`

### Flux
1. `pick_start`: clic edge -> initialise `basegroup`/start via `commit_from_base_to_he`, puis phase `pick_end`
2. `pick_end`: hover edge -> `preview_from_base_to_he`
3. `pick_end`: clic edge -> `commit_from_base_to_he`, puis retour `pick_start` (ou chain mode si voulu)

### Pourquoi cette approche
- simple a raisonner
- aucun mode clavier obligatoire
- start/end clairement differencies

---

## 4) Implementation de reference

State de test cree:
- `viewerState/astar_hover_blend_test_state.py`
- typename: `astar_hover_blend_test_state`

Ce state montre:
1. setup features (`PreviewFeature`, `HoverGadgetFeature`, `AstarTurnFeature`)
2. map hover edge -> hedge
3. preview live en phase end
4. commit en 2 clics
5. menu debug:
- `Reset Session` (`r`)
- `Phase: Pick Start` (`1`)
- `Phase: Pick End` (`2`)

---

## 5) Integration dans un autre state

Checklist minimale:
1. creer `ctx` (`ToolContext`) + `PreviewFeature` + `HoverGadgetFeature` + `AstarTurnFeature`
2. dans `onEnter`:
- `ctx.set_node(node)`
- `ctx.geometry = node.geometry()`
- `ctx.ensure_mesh(geo=ctx.geometry)`
- `preview_feature.on_enter(...)`
- `astar_feature.on_enter(...)`
- `hover_feature.bind_host(self)`
- `hover_feature.set_geometry(ctx.geometry)`
- `hover_feature.set_mode(MODE_LINE)` (ou selon besoin)
- `hover_feature.on_enter(...)`
3. dans `onMouseEvent`:
- `hover_feature.on_mouse_event(...)`
- lire `hover = get_hover()`
- si phase end et hover edge visible: `preview_from_base_to_he(...)`
- lire `click = consume_click()` pour set start/commit end
4. dans `onDraw`:
- `hover_feature.on_draw(...)`
- `preview_feature.on_draw(...)`
5. dans `onExit`:
- `hover_feature.on_exit(...)`
- `astar_feature.on_exit(...)`
- `preview_feature.on_exit(...)`

---

## 6) Frictions connues

1. Mapping edge->hedge
- toujours passer par `ctx.edge_to_hedge(c1, c2)` (gere l'ordre inverse).

2. Hover non visible
- ne pas preview/commit si `hover["visible"]` est `False`.

3. State context hors gadget cible
- `hover_feature` retourne proprement no-hit; bien gerer reset preview.

4. Face transitions (historique)
- le comportement stable de reference reste celui valide dans `face_gadget_test_state`.
- pour le blend A* line, rester en `MODE_LINE` evite ces effets secondaires.

---

## 7) Snippet minimal (edge start/end)

```python
hover_feature.on_mouse_event(ctx, kwargs)
hover = hover_feature.get_hover()

if phase == "pick_end":
    edge = hover.get("edge")
    if hover.get("visible") and edge is not None:
        he = ctx.edge_to_hedge(edge[0], edge[1])
        if he >= 0:
            astar_feature.preview_from_base_to_he(ctx, he)
    else:
        astar_feature.clear_preview(ctx)

click = hover_feature.consume_click()
if click and click.get("visible") and click.get("edge") is not None:
    p0, p1 = click["edge"]
    he = ctx.edge_to_hedge(p0, p1)
    if he >= 0 and phase == "pick_start":
        astar_feature.reset_all(ctx)
        astar_feature.commit_from_base_to_he(ctx, he)
        phase = "pick_end"
    elif he >= 0:
        astar_feature.commit_from_base_to_he(ctx, he)
        phase = "pick_start"
```

---

## 8) Etat actuel
- Blend test fonctionne en pratique dans `astar_hover_blend_test_state`.
- Base modulaire valide pour brancher d'autres features (selection, move, tool chains).
- Prochaine extension logique: mode chain (rester en `pick_end` apres commit).

