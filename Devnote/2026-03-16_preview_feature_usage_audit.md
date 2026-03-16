## Audit rapide — PreviewFeature & PreviewService (2026-03-16)

### Objectif
Cartographier qui utilise `PreviewFeature` / `PreviewService`, pourquoi, et par quels canaux.

---

## 1) Features qui consomment `preview`

### `PreviewFeature`
Fichier : `SkyForge/python/skyforge/forge_states/features/preview_feature.py`
Rôle :
- Crée/stocke le `PreviewService` dans `ctx.services["preview"]`.
- Dessine tous les channels via `draw_all`.
- **Option `enable_hover`** : crée les channels de hover (edge/point/face) et les met à jour.
Canaux utilisés :
- `hover_edge` (line)
- `point_rest` (points)
- `hover_point` (points)
- `hover_face` (faces)

---

### `HoverDrawFeature`
Fichier : `SkyForge/python/skyforge/forge_states/features/hover_draw_feature.py`
Rôle :
- Utilise `PreviewService` pour afficher un polyline + points pendant le draw.
Canaux :
- `CH_CURVE_POINTS`
- `CH_CURVE_LINE`
Notes :
- Crée son propre `PreviewService` si absent (`prefix="hover_draw"`), sinon réutilise.

---

### `TransversalLoopFeature`
Fichier : `SkyForge/python/skyforge/forge_states/features/transversal_loop_feature.py`
Rôle :
- Affiche preview + commit d’un loop.
Canaux :
- `CH_LOOP_PREVIEW`
- `CH_LOOP_COMMITTED`
Notes :
- Crée son propre `PreviewService` si absent (`prefix="transversal_loop"`), sinon réutilise.

---

### `AstarTurnFeature`
Fichier : `SkyForge/python/skyforge/forge_states/features/astar_turn_feature.py`
Rôle :
- Affiche preview + commit d’un path A*.
Canaux :
- `CH_ASTAR_PREVIEW`
- `CH_ASTAR_COMMITTED`
Notes :
- Crée son propre `PreviewService` si absent (`prefix="astar_turn"`), sinon réutilise.

---

## 2) Qui instancie `PreviewFeature` (côté states)

À vérifier dans chaque state : `PreviewFeature(enable_hover=...)` est utilisé quand on veut :
- un hub de drawables partagé
- ou un hover “dessiné” (enable_hover=True)

Le Builder permet d’ajouter `PreviewFeature` et de régler `enable_hover`.

---

## 3) “enable_hover” : mapping d’usage

### Quand `enable_hover = True`
`PreviewFeature` crée et met à jour les canaux :
`hover_edge`, `hover_point`, `hover_face`, `point_rest`
Il lit les infos hover depuis `ctx.get_service("hover")` (fallback).

### Quand `enable_hover = False`
`PreviewFeature` se limite à :
- fournir `PreviewService`
- dessiner les channels existants (`draw_all`)

---

## 4) Frictions constatées

1. **Aucun “hit” provider**
   - `PreviewFeature` lit `hover` en fallback (OK).
   - Il n’y a pas de `HitFeature` qui écrit `ctx.services["hit"]`.

2. **PreviewService créé à plusieurs endroits**
   - `PreviewFeature`, `HoverDrawFeature`, `AstarTurnFeature`, `TransversalLoopFeature`
     peuvent chacun créer un `PreviewService` si absent.
   - Risque : collisions de prefix si utilisés dans un même state sans PreviewFeature.

3. **Couplage au “hover”**
   - `PreviewFeature(enable_hover=True)` dépend du payload `hover` (HoverGadgetFeature).
   - Si HoverGadgetFeature n’est pas présent → pas de hover preview.

---

## 5) Reco rapides

1. Si un state utilise `HoverDrawFeature`, `AstarTurnFeature`, `TransversalLoopFeature`,
   alors `PreviewFeature` peut être ajouté pour centraliser le service et éviter les duplications.
2. Si on veut un hover preview générique, activer `PreviewFeature(enable_hover=True)`
   et s’assurer que `HoverGadgetFeature` écrit `hover`.
3. Optionnel : créer un `HitFeature` si tu veux un hit “ray‑pick” complet (sans gadgets).
