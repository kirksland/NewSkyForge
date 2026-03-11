Pipeline Viewer States: Architecture et mise en place (guide debutant)

Pourquoi ce pipeline existe
L'objectif est simple: rendre les viewer states predictibles, modulaires et faciles a faire evoluer.
On veut eviter les etats "magiques" ou tout est melange.
Le pipeline impose une structure claire pour:
- comprendre ce qui se passe
- ajouter une nouvelle interaction sans casser le reste
- garder une execution stable

Le modele mental
Imagine un atelier:
1. Le state est le chef d'atelier.
2. Le contexte est l'etabli (memoire de travail).
3. Les actions sont des outils qu'on branche sur l'etabli.
Le chef decide l'ordre, l'etabli garde les infos, les outils font le travail.

Architecture globale
Le pipeline se decoupe en 3 couches:
1. Orchestration (state)
2. Runtime (context)
3. Actions (briques modulaires)

1. Orchestration (state)
Le state est la seule piece qui connait Houdini.
Il ne fait pas le travail lui-meme, mais il decide quand le travail se fait.
Ses responsabilites:
- initialiser le contexte
- preparer la geometrie editable
- definir l'ordre d'execution
- deleguer les actions
- gerer le cycle de vie (enter, draw, event, exit)

2. Runtime (context)
Le contexte est une memoire partagée.
Il contient:
- le node
- le scene viewer
- la geo editable
- les services partages entre les briques
Il permet aux actions de communiquer sans se coupler directement entre elles.

3. Actions (briques modulaires)
Les actions sont des modules simples.
Chaque action fait une chose precise (ex: hover, move, preview, commit).
Le state choisit quelles actions sont actives.

Cycle d'execution (vue simple)
Chaque state suit toujours la meme logique:
1. Setup (onEnter)
   - creation du contexte
   - creation de la geo editable
   - initialisation des actions actives

2. Interaction (events)
   - lecture du contexte (hover, selection, etc.)
   - application d'une action a partir de cet etat

3. Rendu (onDraw)
   - dessins de guides ou previews

4. Cleanup (onExit)
   - detacher / nettoyer

Le principe cle: ordre et stabilite
Si une action depend d'une info, elle doit passer APRES la production de cette info.
C'est le state qui garantit cet ordre.
Exemple: une action de move doit passer apres la production d'un hover.

Dispatcher optionnel
Pour eviter de repeter les appels, on peut utiliser un dispatcher:
- il appelle automatiquement les hooks des actions
- il ne remplace pas l'orchestration
Le state reste responsable de l'ordre critique.

Mini tutorial: creer un nouveau state
1. Creer le contexte runtime.
2. Preparer la geo editable.
3. Brancher une action qui produit l'etat de base (hover/selection).
4. Brancher les actions qui consomment cet etat (move/commit/etc).
5. En event:
   - produire l'etat de base
   - appeler les actions dependantes
6. En draw:
   - afficher les feedbacks

Bonnes pratiques
- Garder le state fin: orchestration seulement.
- Garder les actions petites et testables.
- Centraliser la production d'un etat de base (hover/selection).
- Ne pas synchroniser la geo en plein drag.
- Donner un feedback clair a l'utilisateur (HUD, guides).

Ce document reste volontairement conceptuel.
Les details d'implementation sont documentes ailleurs.
