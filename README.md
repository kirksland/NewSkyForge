<img src="config/icons/newForge4-white.svg" alt="SkyForge Icon" width="350">

# SkyForge

Framework de developpement d'outils Houdini avances, centre sur la modularite des viewer states, la logique topo reusable, et une architecture propre pour iterer vite sans casser les outils existants.

---

## Intention du package

SkyForge n'essaie pas de remplacer Houdini.

SkyForge sert a construire, tester et faire evoluer des outils interactifs complexes avec une base technique stable:
- interactions viewport claires (viewer states)
- logique topo deterministic (Python/C++)
- services partages (preview, context runtime, stash/edit geo)
- UI tools (menus/palettes) pour exposer les workflows

Objectif: reduire le code ad-hoc et augmenter la reutilisation.

---

## Philosophie

1. Separation nette des responsabilites
- un state orchestre
- une feature fait une tache metier
- un service gere l'infra technique (ex: drawables)

2. Composition plutot que monolithe
- les outils se construisent en assemblant des features
- les features communiquent via un context commun standardise

3. Compatibilite progressive
- on peut migrer un outil par petites etapes
- on limite les regressions en gardant des couches simples et testables

4. Source de verite unique
- constantes centralisees
- channels preview centralises
- conversions topo centralisees

---

## Architecture (vue rapide)

### Viewer State Layer
Dans `viewerState/`:
- states orchestrateurs (`pyd_loop_modular`, `auto_axis_modular`, etc.)
- routing des events Houdini (key/mouse/draw)
- HUD et interactions utilisateur

### Modular Runtime Layer
Dans `python/skyforge/forge_states/`:
- `base_state.py`: orchestrateur minimal
- `tool_context.py`: contexte runtime partage (node, geo, mesh, hit, parms)
- `feature_base.py`: contrat de feature
- `preview_service.py`: drawables multi-channels
- `features/`: briques metier (A*, loop, move, curve draw...)
- `constants.py`: constantes runtime/style/channels

### Core Topology Layer
Dans `cpp/skyforge_core/` + binding Python:
- HalfEdgeMesh
- loops / A* turn
- helpers topologiques performants
- API stable exposee au Python

### Tool UI Layer
Dans `python/skyforge/forge_tools/`:
- menus et palettes d'outils (ex: custom palette, simple menu)

---

## Ce que ce repo apporte concretement

- prototypage rapide de nouvelles features viewport
- reuse de code entre plusieurs viewer states
- pipeline plus lisible pour passer de test -> outil robuste
- base evolutive pour modeling / retopo / operations topologiques

---

## Etat actuel

Le socle modulaire est actif et exploitable:
- features composables
- preview channels unifies
- context standardise
- tests de composition entre features deja en place (ex: A* -> Move)

La roadmap continue sur:
- enrichissement des features
- UX viewport
- robustesse des workflows multi-outils

---

## Documentation interne

- [Coding Convention](Coding-Conventions)
- [Roadmap](Roadmap)
- [MODULAR_STATE_API](MODULAR_STATE_API.md)
- [MODULAR_STATE_TUTORIAL](MODULAR_STATE_TUTORIAL.md)
- [WIKI_ASTAR_MOVE_COMPOSITION](WIKI_ASTAR_MOVE_COMPOSITION.md)
