## PreviewService / PreviewFeature — Explication claire (2026-03-16)

### Objectif
Expliquer le rôle de **PreviewService**, **PreviewFeature**, et leurs interactions avec le **state**, le **ToolContext** et les autres features.

---

## 1) Les objets en jeu (qui fait quoi)

### ToolContext
Le sac commun du state.  
Il contient :
- `geometry` (lecture)
- `edit_geo` (édition)
- `services` (dictionnaire partagé)
- `hover`, `preview`, etc.

### PreviewService
Un **objet de dessin**.  
Il stocke des **channels** (line / points / faces).

**Image mentale** :  
> une “palette” de calques ; chaque calque = un channel de dessin.

### PreviewFeature
Une feature qui :
- crée le `PreviewService` si besoin
- **optionnellement** crée des channels de hover (si `enable_hover=True`)
- dessine tous les channels via `draw_all`

### Autres features (Astar / Loop / HoverDraw)
Elles **écrivent** dans les channels du PreviewService :
- elles ne dessinent pas directement
- elles alimentent les channels

---

## 2) Le flux typique (comment ça marche)

1. `PreviewFeature.on_enter()`  
   → crée `PreviewService` et le stocke dans `ctx.services["preview"]`.
2. `AstarTurnFeature` / `TransversalLoopFeature` / `HoverDrawFeature`  
   → récupèrent `ctx.get_service("preview")` et écrivent dans leurs channels.
3. `PreviewFeature.on_draw()`  
   → `preview.draw_all()` affiche tout.

Résultat : **un seul service**, plusieurs channels, et un rendu cohérent.

---

## 3) Modularité (pourquoi c’est bien)

### Modulaire parce que :
- chaque feature est indépendante
- elles passent par `ToolContext` pour communiquer
- elles n’ont pas besoin de se connaître directement

### Dépendances
Une feature peut déclarer :
- `requires = ("preview",)` : “j’ai besoin du service”
- `provides = ("preview",)` : “je crée le service”

Le **FeatureHub** peut trier l’ordre d’exécution quand ces tokens existent.

---

## 4) Le problème des “multiples PreviewService”

Si aucun `PreviewFeature` n’est présent, certaines features créent leur propre service :
- `AstarTurnFeature` peut créer `PreviewService(prefix="astar_turn")`
- `TransversalLoopFeature` peut créer `PreviewService(prefix="transversal_loop")`
- `HoverDrawFeature` peut créer `PreviewService(prefix="hover_draw")`

Conséquence :
- plusieurs services distincts dans le même state
- des channels séparés
- rendu moins cohérent (un service peut cacher, l’autre pas)

---

## 5) La version “propre”

**Un seul PreviewService partagé**.

Deux stratégies :
1. Toujours ajouter `PreviewFeature` dans les states qui utilisent preview.
2. Initialiser le PreviewService directement dans le state (ou BaseState).

Dans les deux cas :  
→ tous les channels sont centralisés.

---

## 6) enable_hover : rôle réel

`enable_hover=True` dans `PreviewFeature` :
- crée des channels de hover (edge/point/face)
- met à jour ces channels à partir de `ctx.services["hover"]`

`enable_hover=False` :
- pas de channels hover
- PreviewFeature sert seulement de **hub de dessin**.
