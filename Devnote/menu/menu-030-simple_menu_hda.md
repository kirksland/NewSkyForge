# Simple Menu HDA

## Purpose

Menu léger qui lit le JSON produit par `custom_palette_hda` et exécute les actions.

## Entry Points

- `show()` : construit le QMenu et l’affiche.

## Actions Supportées

- `shelf:<tool_name>` : exécute un shelf tool.
- `hda:<node_type_name>` : crée un node HDA.
- `separator` : séparateur.
- `header:<text>` : label non cliquable.
- `submenu_start:<text>` / `submenu_end` : sous‑menus.

## SOP Handling

Pour les SOP HDAs :
- force une Scene Viewer context.
- injecte explicitement la sélection (current node puis display node).

## Error Handling

- `_safe_dispatch()` catch les exceptions et affiche un message Houdini.

## See Also

- [Index Menu](menu-000-index.md)
- [Forge Tools Overview](menu-010-forge_tools.md)
- [Custom Palette HDA](menu-020-custom_palette_hda.md)
