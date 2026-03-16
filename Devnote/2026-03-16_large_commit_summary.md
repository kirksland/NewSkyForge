## Résumé Gros Commit (2026-03-16)

### Périmètre
Ce document capture l’état du “gros commit” après le travail sur le ViewerState Builder, la refonte du pipeline de features, l’automatisation HUD/menus, et les fixes hover/move. C’est un point d’étape sur ce qui a changé et pourquoi.

### Thèmes principaux
- Le ViewerState Builder a gagné une vraie connaissance du pipeline (HUD, menus, hotkeys, key events).
- Création de features ajoutée dans le Builder (génération de template + mise à jour auto de __init__.py).
- FeatureHub gère maintenant le filtrage HUD et le toggle HUD par feature.
- Intégration hover/move + edit_geo renforcée.
- Unification des constantes (modes select/tool) avec compat rétroactive.

---

## 1) ViewerState Builder (UI + génération)
Fichier : `SkyForge/python/skyforge/forge_tools/viewerState_builder.py`

### UI/UX
- Layout en 3 colonnes via `QSplitter` (colonnes redimensionnables).
- Colonne centrale en tabs Debug/Commit (contenu fake pour l’instant).
- Ajout d’une liste *ViewerStates* qui browse `$HPD/viewerState` et peut ouvrir les fichiers.
- Ajout d’une liste *Features* qui browse `$HPD/python/skyforge/forge_states/features` et peut ouvrir les fichiers.
- Bouton “Create Feature” pour générer un template de feature.
- Save UI avec champ de chemin + réutilisation du dernier chemin.
- Blocs features repliables, supprimables, et avec toggle HUD par feature.

### Changements de génération de code
Le state généré :
- Crée automatiquement un HUD minimal si des features exposent un HUD mais qu’il n’y a pas de `HUD_TEMPLATE`.
- Bind automatiquement `bind_template`, `build_menu`, `extend_menu`, et `build_hotkeys`.
- Inclut `onKeyEvent` et `onKeyTransitEvent` si les features les supportent.
- Ajoute un toggle HUD par feature (`feature.hud_enabled = False`).

### Générateur de template de feature
Le Builder peut générer un fichier feature avec :
- `provides` / `requires` valides
- Hooks (`on_enter`, `on_exit`, `on_mouse_event`, `on_key_event`, `on_draw`)
- `builder_schema`, `hud_template`, `hud_values`
- Bind optionnel des dépendances (`hover`, `preview`)
- Ajout automatique dans `features/__init__.py` + `__all__`

---

## 2) FeatureHub / HUD
Fichier : `SkyForge/python/skyforge/forge_states/feature_hub.py`

Changements :
- `hud_template()` et `hud_values()` ignorent les features avec `hud_enabled = False`.
- Les valeurs HUD sont filtrées sur les ids connus pour éviter les `KeyError`.

---

## 3) Fixes Hover / Move / Draw

### HoverMoveFeature
Fichier : `SkyForge/python/skyforge/forge_states/features/hover_move_feature.py`
- `on_enter()` appelle `ctx.ensure_edit_geo()` pour stabiliser le move sans boilerplate.
- Le check du mode utilise `k.TOOL_MOVE`.

### HoverDrawFeature
Fichier : `SkyForge/python/skyforge/forge_states/features/hover_draw_feature.py`
- Utilise `k.TOOL_DRAW` au lieu de `TOOL_MODE_DRAW`.

### HoverGadgetFeature
Fichier : `SkyForge/python/skyforge/forge_states/features/hover_gadget_feature.py`
- Ajout du flag `use_edit_geo` pour synchroniser les gadgets sur `edit_geo`.
- Ajout de `set_use_edit_geo(...)` + exposition dans `builder_schema()`.
- Si `use_edit_geo=True`, `on_enter()` assure `edit_geo` et `on_draw()` resynchronise la géométrie.

---

## 4) Unification des constantes (select/tool)
Fichier : `SkyForge/python/skyforge/forge_states/constants.py`

Ajouts :
- `SELECT_POINT / SELECT_EDGE / SELECT_FACE`
- `SELECT_ORDER`
- `TOOL_MOVE / TOOL_CUT / TOOL_DRAW`
- `TOOL_ORDER`

Compat rétroactive :
- `AUTO_AXIS_SELECT_ORDER = SELECT_ORDER`
- `AUTO_AXIS_TOOL_ORDER = (TOOL_MOVE, TOOL_CUT)`
- `TOOL_MODE_DRAW = TOOL_DRAW`

Aussi :
- `OUTPUT_MODE_FACE = OUTPUT_MODE_PRIM` (face == prim)

---

## 5) ToolContext : defaults mis à jour
Fichier : `SkyForge/python/skyforge/forge_states/tool_context.py`
- `select_mode` par défaut = `SELECT_ORDER[0]`.
- `tool_mode` par défaut = `TOOL_ORDER[0]`.

---

## 6) PreviewFeature : alignement select‑mode
Fichier : `SkyForge/python/skyforge/forge_states/features/preview_feature.py`
- Utilise les constantes unifiées (`SELECT_POINT`, `SELECT_EDGE`).

---

## 7) Viewer States touchés

### `my_state_draw.py`
- `ctx.ensure_edit_geo()` ajouté au onEnter (pour move).
- Resync de la géo du hover gadget sur `edit_geo` dans `onDraw`.

### `hover_curve_modular_state.py`
- Passage à `k.TOOL_DRAW` au lieu de `k.TOOL_MODE_DRAW`.

D’autres states avaient déjà été mis à jour pour utiliser `bind_context`, `enter_with_hud` et le routing via hub.

---

## 8) Fichiers de templates générés

### `new_feature.py` / `new_feature001.py`
- Générés par le système de template.
- `new_feature001.py` avait une syntaxe invalide, corrigée.
- À supprimer si non utilisés, en retirant aussi l’entrée dans `features/__init__.py`.

---

## Risques / Questions ouvertes
- Certaines features n’ont pas encore `builder_schema()`, donc peu d’actions exposées dans le Builder.
- Certains states utilisent encore des strings “POINT/EDGE/FACE” inline.
- Le générateur modifie `features/__init__.py`, possible source de conflits.

---

## Prochaines étapes (proposées)
1. Décider si `use_edit_geo` doit être auto‑activé dans le Builder quand HoverMoveFeature est sélectionné.
2. Finir la migration vers `SELECT_*` et `TOOL_*`.
3. Nettoyer les features générées par accident si non voulues.
