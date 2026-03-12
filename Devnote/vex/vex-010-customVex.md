# customVex.h

## Purpose

Bibliothèque VEX d’helpers pour parcourir des loops/rings via le half‑edge.
Elle sert à factoriser des fonctions réutilisables dans les wrangles.

## Contenu

- `rot_src(h)` : rotation “autour du vertex source” d’un half‑edge.
- `mark_stop(pt, reason, g_unshared, g_non4, g_deg)` : marque un point stop + code de raison.
- `walk_loop(prev, cur, outgrp, maxit, g_unshared, g_non4, g_deg, mark_cand_boundary)` :
  avance le long d’une edge‑loop et écrit un groupe d’arêtes.
- `walk_rail(hstart, outgrp, maxit)` :
  traverse un ring de quads et écrit un groupe d’arêtes.

## Résultats / Sorties

- Groupes d’arêtes via `setedgegroup`.
- Marquage debug via `setpointgroup` + attribut `stop_reason`.

## Include dans un Wrangle

1. Assure‑toi que `HOUDINI_VEX_PATH` contient le dossier `vex` du package.
2. Place les headers dans `vex/include/` (ex: `SkyForge/vex/include/customVex.h`).
3. Dans le VEX du wrangle, ajoute :

```c
#include "customVex.h"
```

## Exemple minimal

```c
#include "customVex.h"

int maxit = 1024;
int h = pointhedge(0, @ptnum, neighbour(0, @ptnum, 0));
int it = walk_rail(h, "rail_grp", maxit);
```

## Notes

- `walk_loop` suppose un contexte quad (valence 4) pour une loop “propre”.
- `walk_rail` ne traverse que des quads (`primvertexcount == 4`).
