# 🌌 SkyForge (Houdini)

**SkyForge** est un package Python pour **SideFX Houdini** orienté **outils interactifs dans le Scene Viewer** (Python Viewer States), avec une ambition principale : rendre la **modélisation** et surtout la **retopologie** plus **organique**, plus **instinctive**, directement dans le viewport.

> Projet en cours : pour l’instant, SkyForge pose surtout les **fondations** (architecture, modules, points d’entrée).  
> L’objectif final est d’en faire une **démo portfolio** centrée sur des outils de modélisation / retopo, et un mini **pipeline** (batch rendu, export USD, etc.).

---

## ✨ Vision

- **Retopo semi-auto** + outils interactifs
- Travail “au geste” : *clic/drag/snap/guide* dans le **Scene Viewer**
- Outils pensés comme des **Viewer States** (UX directe, fluide)
- Une base de code modulaire pour faire évoluer :
  - outils de modélisation / retopo
  - outils de rendu batch
  - export (USD, caches, etc.)

Référence d’intention : une approche dans la lignée d’outils de modélisation Houdini modernes (ex : plugin “Modeleur”-like), sans chercher à le reproduire, mais en visant la même sensation de **sculpt / sketch / retopo rapide** dans le viewport.

---

## ✅ État actuel

SkyForge est en phase **foundation** :
- structure de package `skyforge`
- organisation par sous-modules (core / mesh / motion / draw / store / tools)
- utilitaire de dev : **reload à chaud** pour itérer sans relancer Houdini

Les outils finaux (retopo, modelling) arrivent dans les prochaines itérations.

---


