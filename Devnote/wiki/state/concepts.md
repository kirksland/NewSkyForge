# Concepts

## Purpose

Liste centrale des concepts clés qui font fonctionner le pipeline des viewer states modulaires.

## Feature

Petite unité d’interaction ciblée avec des hooks optionnels :
- on_enter, on_exit, on_draw
- on_mouse_event, on_key_event
- handle_menu_action

## Dispatcher

FeatureHub est le dispatcher ordonné qui transmet les callbacks du viewer state.
Il est best‑effort et ne propage jamais d’exception à l’appelant.

## Context

ToolContext est le bus de données runtime partagé.
Il met en cache la géométrie, gère les sessions d’édition via stash et stocke les services.

## Services

Les services sont des objets partagés et nommés dans `ctx.services`.
C’est le seul moyen supporté pour partager des données entre features.

## Hover First

Le hover est le signal de base. Les features d’action dépendent des sorties du hover.
Toujours mettre à jour le hover avant les features d’action dans onMouseEvent.

## Preview Channels

Les channels du PreviewService sont des drawables nommés.
Ils sont légers à mettre à jour et doivent être cachés à la sortie.

## Topology Awareness

`ensure_mesh()` ne reconstruit que lors d’un changement de topologie.
Il faut l’appeler dès que la topologie a pu changer.

## Commit Discipline

Ne jamais modifier la géométrie directement sans push/commit.
Toujours valider les changements via `ctx.push_edit_geo()`.

## See Also

- [State Pipeline](state_pipeline.md)
- [Tool Context](tool_context.md)
- [Dispatcher](dispatcher.md)
- [Channels](channels.md)

## Navigation

- [State Index](index.md)
- [Wiki Index](../index.md)
