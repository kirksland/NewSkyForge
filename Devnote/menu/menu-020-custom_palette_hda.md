# Custom Palette HDA

## Purpose

Éditeur UI (PySide6) pour composer un menu SkyForge en glisser‑déposer.
Le résultat est stocké dans un JSON partagé par le menu “runtime”.

## Entry Points

- `show_palette_editor_hda()` : ouvre l’éditeur (ou le réactive).

## Config

Chemin : `"$HOUDINI_USER_PREF_DIR/skyforge_menu_hda.json"`

Valeurs par défaut :
- `menu`: liste d’actions.
- `sources.shelf_names`: shelves à scanner.
- `sources.tool_menu_prefixes`: préfixes `toolMenuLocations` à scanner.

## Catalog

La palette construit un catalogue depuis :
- HDAs présents dans le package SkyForge.
- Shelf tools (shelf + tool menu locations).

## UI Columns

- Menu (liste ordonnée, drag/drop).
- HDA (arbo par menu_path).
- Tools (arbo par menu_path).

## Notes

- Les actions sont stockées sous forme d’IDs (`hda:`, `shelf:`, etc.).
- Le JSON est la source de vérité pour `simple_menu_hda`.

## See Also

- [Index Menu](menu-000-index.md)
- [Forge Tools Overview](menu-010-forge_tools.md)
- [Simple Menu HDA](menu-030-simple_menu_hda.md)
