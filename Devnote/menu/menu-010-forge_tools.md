# Forge Tools Overview

## Purpose

Vue d’ensemble du module Python `skyforge.forge_tools`, dédié à la construction et l’exécution de menus Houdini.

## Modules

- `custom_palette_hda.py` : éditeur UI pour composer un menu (drag/drop) et sauvegarder en JSON.
- `simple_menu_hda.py` : lecteur UI simple qui charge le JSON et exécute les actions.

## Data Flow

- `custom_palette_hda` écrit un JSON dans `CFG_PATH`.
- `simple_menu_hda` lit ce JSON et construit un menu exécutable.

## Config (JSON)

Chemin : `"$HOUDINI_USER_PREF_DIR/skyforge_menu_hda.json"`

Structure minimale :
- `menu`: liste d’actions (`shelf:`, `hda:`, `separator`, `header:`, `submenu_start:`, `submenu_end`).
- `sources`: listes de sources UI (shelves, toolMenuLocations).

## See Also

- [Index Menu](menu-000-index.md)
- [Custom Palette HDA](menu-020-custom_palette_hda.md)
- [Simple Menu HDA](menu-030-simple_menu_hda.md)
