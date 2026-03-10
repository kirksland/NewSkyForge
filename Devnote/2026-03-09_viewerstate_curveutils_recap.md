# Devnote - 2026-03-09

## Contexte
Objectif du jour: repartir d'un viewer state simple (sans framework) pour dessiner/editer une courbe, puis etendre a point/edge/face avec persistance `INPUT -> stash1`.

Fichier principal travaille:
- `viewerState/curveutils_basic_state.py`

## Ce qu'on a essaye
1. Base minimale `curveutils`:
- placement d'un point
- drag du point
- clear

2. Passage a une version multi-points:
- mode draw / mode edit
- selection de points
- drag de selection
- suppression selection

3. Ajout des edges:
- draw des segments
- selection edge
- drag edge (deplace ses points)

4. Chargement de la geo du node:
- d'abord `node.geometry()`
- puis correction pour privilegier `INPUT`

5. Integration du workflow stash (Houdini):
- session editable basee sur `stash1`
- init depuis `stash1` sinon `INPUT`
- push de l'edit geo vers `stash1`
- correction "push une seule fois" via snapshot geo frais a chaque commit

6. Ajout des faces:
- selection/drag face
- overlay face selectionnee
- tentative gadgets + fallback raycast

7. Stabilisation ergonomique:
- mode de selection explicite (point/edge/face)
- un seul gadget actif a la fois
- action menu + hotkeys de menu
- overlays hover edge/face

8. Tentative optimisation dense mesh:
- reduction des fallbacks Python
- throttling hover
- rollback partiel apres regressions

## Ce qui marche bien maintenant
1. Points et edges: comportement globalement stable.
2. Workflow `stash1` actif (edit + push).
3. Menu d'actions pour modes/select.
4. Overlay selection (point/edge/face) present.

## Ce qui reste sensible
1. Selection/hover face encore variable selon contexte.
2. Performance degradee quand mesh dense + hover frequent.
3. Risque de regressions des qu'on melange trop de strategies de pick en meme temps.

## Lecons du jour
1. Faire une seule strate de pick par mode (eviter melange gadget + fallback agressif partout).
2. Prioriser la stabilite avant optimisation.
3. Tester incrementalement, une modif ergonomie/perf a la fois.
4. Garder l'architecture simple tant que le comportement n'est pas verrouille.

## Plan propose pour la suite
1. Geler une baseline stable (point/edge/face minimal).
2. Instrumenter legerement le pick face (debug court, temporaire) pour comprendre les cas ratés.
3. Ensuite seulement, optimiser:
- gadget-only strict par mode
- hover incremental
- eventuellement couche proxy/mapping si necessaire sur tres gros meshes.

