## Pipeline API — Référence complète (2026-03-16)

### Objectif
Documenter le pipeline “viewer state → tool context → features → hub”, avec l’API, les dépendances, et les contrats d’usage.

---

## 1) Vue globale (résumé)

**Viewer State**  
→ crée `ToolContext`  
→ instancie des **features**  
→ délègue à `FeatureHub` (dispatch + HUD + ordre)

**ToolContext**  
→ stocke toutes les données runtime (geo, edit_geo, services, modes)

**FeatureHub**  
→ ordonne par `provides/requires`  
→ dispatch les events  
→ gère HUD

**Features**  
→ unités modulaires  
→ écrivent/consomment des `services`  
→ peuvent exposer `builder_schema()` pour le Builder

---

## 2) ToolContext — API & Services

### Champs clés
- `node`: node Houdini bindé
- `geometry`: geo read‑only (node.geometry)
- `edit_geo`: geo editable (stash)
- `mesh`: HalfEdgeMesh (topologie)
- `gi`: GeometryIntersector (ray pick)
- `services`: dict partagé (ex: `hover`, `preview`, `selection_payload`, `host`)
- `mode`, `select_mode`, `tool_mode` (modes unifiés)

### Méthodes importantes
- `set_node(node)` → bind le node + cache les parms
- `set_service(name, value)` / `get_service(name)`
- `ensure_geo()` → refresh `geometry`
- `ensure_mesh(geo=None)` → rebuild GI + mesh si topo changée
- `ensure_edit_geo()` → stash editable (`edit_geo`)
- `push_edit_geo()` → push edit_geo dans stash

### Tokens de services standards
| Service | Type | Fournisseur attendu | Usage |
|---|---|---|---|
| `hover` | dict | HoverGadgetFeature | payload hover (edge/point/prim) |
| `preview` | PreviewService | BaseState (auto) | hub de drawables |
| `selection_payload` | dict | State / hub | payload de sélection |
| `host` | viewer state | BaseState | accès au state depuis feature |

---

## 3) BaseState — API standard

### `bind_context(ctx, kwargs, ensure_geo=True, ensure_mesh=True)`
Fait :
- bind `node`
- expose `host` dans `ctx.services`
- ensure `geometry` / `mesh`
- **crée PreviewService** si absent (via `ensure_preview`)

### `ensure_preview(ctx, prefix=None)`
Crée un `PreviewService` (si absent) et le stocke dans `ctx.services["preview"]`.

### `enter_with_hud(hub, ctx, kwargs, base_template=None, update=True)`
Appelle :
1. `hub.enter(...)`
2. `hub.apply_hud(...)`
3. `hub.update_hud(...)`

---

## 4) FeatureHub — API (dispatch + ordre)

### Ordre
Basé sur `provides` / `requires`.  
Si une feature consomme un token sans provider, l’ordre reste “best effort”.

### Dispatch
- `enter(ctx, kwargs)`
- `exit(ctx, kwargs)`
- `draw(ctx, kwargs)`
- `mouse(ctx, kwargs, stop_on_consume=False)`
- `mouse_collect(ctx, kwargs, payload_picker=None, stop_on_consume=False)`
- `key(ctx, kwargs, stop_on_consume=False)`
- `menu(ctx, kwargs, stop_on_consume=False)`
- `menu_pre_open(ctx, kwargs, stop_on_consume=False)`

### HUD
Chaque feature peut exposer :
- `hud_template()` → rows
- `hud_values(ctx)`

Le hub merge les rows, filtre les ids, et met à jour le HUD.

Option : une feature peut désactiver sa contribution HUD avec  
`feature.hud_enabled = False`.

---

## 5) Features — Contrat minimal

### Attributs
- `name`: id logique
- `provides = (...)`
- `requires = (...)`

### Hooks
Optionnels, appelés par le Hub :
- `on_enter(ctx, kwargs)`
- `on_exit(ctx, kwargs)`
- `on_mouse_event(ctx, kwargs)`
- `on_key_event(ctx, kwargs)`
- `on_draw(ctx, kwargs)`
- `on_menu_pre_open(kwargs)`
- `handle_menu_action(kwargs)`

### HUD (optionnel)
```
def hud_template(self): return [...]
def hud_values(self, ctx): return {...}
```

### Builder schema (optionnel)
```
@staticmethod
def builder_schema():
    return { "setup": [ ... ] }
```

---

## 6) Preview — API consolidée

### PreviewService (objet)
Contient des **channels** (line/points/faces).  
Les features écrivent dedans, puis le service dessine.

### PreviewFeature
Rôle :
- fournit/consomme `preview` (service central)
- option `enable_hover`: crée et met à jour les channels hover

### Channels majeurs
- Hover: `hover_edge`, `hover_point`, `hover_face`, `point_rest`
- Astar: `CH_ASTAR_PREVIEW`, `CH_ASTAR_COMMITTED`
- Loop: `CH_LOOP_PREVIEW`, `CH_LOOP_COMMITTED`
- Draw: `CH_CURVE_POINTS`, `CH_CURVE_LINE`

---

## 7) Hover — API consolidée

### HoverGadgetFeature
Fournit : `hover`  
Payload standard :
```
{
  "gadget": "...",
  "c1": int,
  "c2": int,
  "visible": bool,
  "point": int,
  "edge": (p0, p1),
  "prim": int
}
```

Options :
- `use_edit_geo`: resync gadgets sur edit_geo

---

## 8) Modes unifiés (select / tool)

### Select
- `SELECT_POINT`, `SELECT_EDGE`, `SELECT_FACE`
- `SELECT_ORDER`

### Tool
- `TOOL_MOVE`, `TOOL_CUT`, `TOOL_DRAW`
- `TOOL_ORDER`

Compat :
- `AUTO_AXIS_SELECT_ORDER`
- `AUTO_AXIS_TOOL_ORDER`
- `TOOL_MODE_DRAW`

---

## 9) Règles de stabilité (best practices)

1. **Le service `preview` doit être unique**
   → base state l’initialise automatiquement.
2. **Chaque feature doit déclarer ses `requires`**
   → sinon ordre et dépendances implicites.
3. **Le hover générique passe par `HoverGadgetFeature`**
   → et alimente `PreviewFeature(enable_hover=True)` si besoin.
