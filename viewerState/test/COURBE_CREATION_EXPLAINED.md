# 🎨 Comment les Courbes Sont Créées dans `curve_state_test.py`

## 📋 Architecture Générale

```
CurveState (État principal)
    ├── ReferenceCurve (gère la géométrie live)
    ├── DrawableManager (affiche les points et courbes)
    ├── Modes (Edit, Draw, Orient)
    │   └── Opérations interactives (PointAddOperation, PointMoveOperation, etc.)
    └── Sélection (points sélectionnés)
```

---

## 🎯 Flux de Création d'une Courbe (mode Draw)

### **1. Utilisateur clique en mode Draw**

```plaintext
L'événement souris est reçu par CurveState.onMouseEvent()
    └─> Active le mode Draw
        └─> Crée/active une PointAddOperation
            └─> Se met en état "ChooseLocAddMode"
```

### **2. Positionnement du premier point**

**Classe impliquée :** `PointAddOperation.ChooseLocAddMode`

```python
# Utilisateur clique sur une position en 3D
onMouseEvent(kwargs)
    └─> pickPosition()  # Récupère la position 3D du clic
    └─> Si drag : 
        ├─> self.pos0 = position de départ (point)
        ├─> self.pos1 = position en drag (tangente)
        └─> _handleTangentsCase() ou _handleNoTangentsCase()
    └─> Transition vers SegmentAddMode ou TangentsSegmentAddMode
```

### **3. Ajout du deuxième point et suivants**

**Classe impliquée :** `PointAddOperation.SegmentAddMode` ou `TangentsSegmentAddMode`

```python
# Pour chaque point ajouté
onMouseEvent(kwargs)
    └─> pickPosition()  # Nouvelle position 3D
    └─> Stocke les positions dans self.drawn_points []
    └─> Vérifie si fuse/branchement/fermeture nécessaire
    └─> commitSegment() OU attendre le prochain clic
```

### **4. Commit du segment (ajout réel à la géométrie)**

```python
commitSegment()
    ├─> setupCommitSegment()  # Format les points
    │   └─> self.parent._setParm(ADDPTS_PARM, "x,y,z x,y,z ...")
    │
    ├─> preCommitSegmentOps()  # Opérations avant (si needed)
    │
    ├─> parent.node.parm(OPTYPE_PARM).set(OPTYPE_APPENDPT)  # Ou PREPENDPT
    │   # Cela déclenche le HDA/SOP qui crée réellement les points
    │
    ├─> La géométrie est mise à jour dans Houdini
    │   └─> ReferenceCurve met à jour son cache
    │   └─> DrawableManager se met à jour pour afficher les nouveaux points
    │
    └─> postCommitSegmentOps()  # Opérations après (fuse, branch, etc.)
```

---

## 🔑 Paramètres Clés Utilisés

| Paramètre | Signification | Exemple |
|-----------|---------------|---------|
| `ADDPTS_PARM` | Points à ajouter (format: "x,y,z x,y,z ...") | `"1.0,2.0,3.0 4.0,5.0,6.0"` |
| `OPTYPE_PARM` | Type d'opération | `OPTYPE_APPENDPT`, `OPTYPE_PREPENDPT` |
| `ACTIVEPRIM_PARM` | Primitive active (courbe) | Index primitif |
| `PARMPOINTS_PARM` | Points de la courbe stockés | Historique des opérations |
| `CORNERPTS_PARM` | Points cassés (broken) | Numéros de points |
| `SMOOTHPTS_PARM` | Points lissés | Numéros de points |

---

## 💾 Où la Courbe Est Réellement Créée

### **Dans le HDA (nicht dans Python)**

La vraie création géométrique se fait dans un **HDA (Houdini Digital Asset)** qui :

1. **Lit les paramètres** (ADDPTS_PARM, OPTYPE_PARM, etc.)
2. **Exécute les opérations SOP** (Procedural Geometry Operations)
3. **Crée/Modifie la géométrie** (crée les primitives Bezier/NURBS)
4. **Retourne la géométrie** au système Houdini

```python
# C'est un appel indirect via les paramètres du node
node.parm("optype").set(OPTYPE_APPENDPT)
node.parm("addpts").set("1,2,3 4,5,6")
# → Le HDA écoute ces changements et crée les points !
```

---

## 🎬 Les Modes de Dessin

### **Mode 1 : ChooseLocAddMode**  
✅ Utilisateur choisit la position du premier point  
✅ Peut faire un drag pour définir une tangente  

### **Mode 2 : SegmentAddMode / TangentsSegmentAddMode**  
✅ Ajoute les points suivants au segment  
✅ Gère les fusions/branchements  
✅ Peut fermer la courbe (snap)  

### **Mode 3 : Retour à ChooseLocAddMode (ou terminaison)**  
✅ Prêt pour un nouveau segment  
✅ Ou retour au mode Edit  

---

## 🎪 Sous-Modes Spécialisés Dans PointAddOperation

```python
class PointAddOperation:
    ├─ BaseAddMode (classe de base)
    │   ├─ ChooseLocAddMode (choisit le point de départ)
    │   ├─ SegmentAddMode (base pour ajouter à un segment)
    │   │   ├─ ClickSegmentAddMode (clic pour chaque point)
    │   │   ├─ AutoClickSegmentAddMode (auto-interpolation Bezier)
    │   │   └─ TangentsSegmentAddMode (drag pour tangentes)
    │   └─ ArcSegmentAddMode (clic-clic pour spécifier un arc)
    │
    └─ DrawTool (c'est une opération, pas un mode)
```

---

## 📊 Diagramme du Workflow Complet

```
┌─ CurveState.onMouseEvent(kwargs)
│
└─> Mode Draw actif
    │
    ├─> PointAddOperation.onMouseEvent(kwargs)
    │   │
    │   ├─ currentMode = ChooseLocAddMode OR SegmentAddMode
    │   │
    │   ├─ _mode.onMouseEvent(kwargs)
    │   │   │
    │   │   ├─ pickPosition(kwargs)        # Récupère X,Y,Z
    │   │   ├─ Check snap to existing pts
    │   │   └─ Update drawn_points[]
    │   │
    │   └─ if drag_finished:
    │       └─> commitSegment()
    │           ├─ Set ADDPTS_PARM
    │           ├─ Set OPTYPE_PARM = OPTYPE_APPENDPT
    │           ├─ HDA lit params → crée points
    │           ├─ ReferenceCurve met à jour cache
    │           └─ Drawables se redessinent
    │
    └─> Évènements suivants (souris, clavier, etc.)
        continuent dans la même logique
```

---

## 📝 Exemple: Ajouter Manuellement 3 Points

```python
# Depuis le Python dans `curve_state_simplified.py` :

state = SimpleCurveState(scene_viewer)

# Point 1
state.add_point_at(hou.Vector3(0, 0, 0))

# Point 2
state.add_point_at(hou.Vector3(1, 0, 0))

# Point 3
state.add_point_at(hou.Vector3(1, 1, 0))

# → La courbe est créée par les appels `commitSegment()` 
#   qui ont mis à jour les paramètres du node
```

---

## 🔗 Fichiers Clés du Système Houdini

| Fichier | Rôle |
|---------|------|
| `drawops.py` | Contient `PointAddOperation` et `DrawTool` |
| `editops.py` | Contient `PointMoveOperation` |
| `baseoperation.py` | Classe de base `BaseOperation` |
| `drawablemanager.py` | Gère l'affichage (Drawables) |
| `referencegeo.py` | Classe `ReferenceCurve` - gère la géométrie |
| `constants.py` | Définit tous les paramètres et codes |

---

## 🚀 Résumé Rapide

**La création d'une courbe = Suite d'appels à `commitSegment()`**

1. Utilisateur clique/drag dans le viewport
2. `PointAddOperation` capte les events
3. Accumule les positions dans `drawn_points[]`
4. Quand l'utilisateur relâche/valide → `commitSegment()`
5. `commitSegment()` met à jour les paramètres du Node
6. Le **HDA exécute son SOP** → crée réellement les points
7. `ReferenceCurve` se met à jour
8. `DrawableManager` se redessine
9. Retour à l'étape 1 pour le point suivant

C'est un **cycle interactif** de clic → visualisation → clic → etc.
