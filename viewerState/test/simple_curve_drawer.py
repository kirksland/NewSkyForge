"""
SimpleCurveDrawer: Un state minimaliste pour dessiner des courbes dans Houdini.

Fonctionnalités:
  - Placer des points avec left-click dans le viewport
  - Déplacer les points avec middle-click
  - Afficher les points en temps réel (drawables)
  - Créer une courbe Bezier simple

Usage:
  state = SimpleCurveDrawer(scene_viewer, node)
  # Utilisateur clique dans viewport → points ajoutés
  # Utilisateur drag middle-click → points déplacés
"""

from typing import Optional, List, Tuple
import hou

from curvestate import drawops, editops, drawablemanager, constants


class SimpleCurveDrawer:
    """
    État minimaliste pour dessiner et éditer des courbes interactives.
    
    Points clés:
    - Gère les drawable (affichage des points)
    - Gère l'ajout de points (left-click)
    - Gère le déplacement (middle-click)
    """

    def __init__(self, scene_viewer: hou.SceneViewer, node: hou.Node):
        """
        Initialise le drawer.
        
        Args:
            scene_viewer: SCeneViewer Houdini pour le rendu
            node: Le SOP node qui contient la géométrie
        """
        self.scene_viewer = scene_viewer
        self.node = node  # Le node Houdini (HDA)
        
        # ===== DRAWABLE MANAGER (pour afficher les points) =====
        self._drawable_manager = drawablemanager.DrawableInteractionManager(
            "drawable_manager", self.scene_viewer, self
        )
        
        # Lier les callbacks des drawables aux méthodes de this state
        self._setup_drawable_callbacks()
        
        # ===== OPÉRATIONS (ajout/déplacement de points) =====
        self.point_add_op = drawops.PointAddOperation(
            "point_add", self.scene_viewer, self
        )
        self.point_add_op.setUndoLabel("Add Point to Curve")
        
        self.point_move_op = editops.PointMoveOperation(
            "point_move", self.scene_viewer, self
        )
        self.point_move_op.setUndoLabel("Move Curve Points")
        
        self.point_drawmode_move_op = drawops.DrawModeMoveOperation(
            "drawmode_point_move", self.scene_viewer, self
        )
        self.point_drawmode_move_op.setUndoLabel("Move Points (Draw Mode)")
        
        # = Registre des opérations =
        self.available_operations = [
            self.point_add_op,
            self.point_move_op,
            self.point_drawmode_move_op,
        ]
        
        self._active_operation: Optional[object] = None
        
        # ===== État Local =====
        self._current_selection: List[int] = []  # Points sélectionnés
        self._drawn_points: List[hou.Vector3] = []  # Points en cours de dessin
        
    # =====================================================
    # DRAWABLE SETUP (affichage des points)
    # =====================================================
    
    def _setup_drawable_callbacks(self) -> None:
        """
        Configure les callbacks des drawables interactifs.
        Quand l'utilisateur clique sur un point dans le viewport,
        ces callbacks sont déclenchés.
        """
        try:
            # Callback pour clicker sur les points d'ancrage (courbe)
            self._drawable_manager.getBezierControlPointHandle().setCallback(
                self.on_pick_anchor_point
            )
            # Callback pour clicker sur la ligne de la courbe
            self._drawable_manager.getBackboneCurveHandle().setCallback(
                self.on_pick_curve
            )
            # Callback pour clicker sur les points de contrôle Bezier
            self._drawable_manager.getBezierHandlePoints().setCallback(
                self.on_pick_handle_point
            )
        except Exception as e:
            print(f"[SimpleCurveDrawer] Warning: Could not setup drawable callbacks: {e}")
    
    # =====================================================
    # CALLBACKS DRAWABLE (événements souris)
    # =====================================================
    
    def on_pick_anchor_point(self, kwargs: dict, handle_event) -> None:
        """Appelé quand utilisateur clique sur un point d'ancrage."""
        op = self.activeOperation()
        if op and hasattr(op, "onPickAnchorPoint"):
            op.onPickAnchorPoint(kwargs, handle_event)
    
    def on_pick_curve(self, kwargs: dict, handle_event) -> None:
        """Appelé quand utilisateur clique sur la courbe."""
        op = self.activeOperation()
        if op and hasattr(op, "onPickCurve"):
            op.onPickCurve(kwargs, handle_event)
    
    def on_pick_handle_point(self, kwargs: dict, handle_event) -> None:
        """Appelé quand utilisateur clique sur un handle Bezier."""
        op = self.activeOperation()
        if op and hasattr(op, "onPickHandlePoint"):
            op.onPickHandlePoint(kwargs, handle_event)
    
    # =====================================================
    # GESTION DES OPÉRATIONS
    # =====================================================
    
    def setActiveOperation(self, op_name: str) -> None:
        """
        Active une opération par son nom.
        
        Args:
            op_name: Nom de l'opération (ex: "point_add", "point_move")
        """
        for op in self.available_operations:
            op_class_name = op.__class__.__name__
            op_internal_name = getattr(op, "name", None)
            
            if op_internal_name == op_name or op_class_name == op_name:
                self._active_operation = op
                return
        
        print(f"[SimpleCurveDrawer] Operation '{op_name}' not found")
    
    def activeOperation(self) -> Optional[object]:
        """Retourne l'opération actuellement active."""
        return self._active_operation
    
    # =====================================================
    # MÉTHODES PUBLIQUES - API POUR L'UTILISATEUR
    # =====================================================
    
    def getDrawableManager(self) -> drawablemanager.DrawableInteractionManager:
        """Retourne le gestionnaire des drawables."""
        return self._drawable_manager
    
    def getDrawableSelector(self):
        """Retourne le sélecteur de drawable."""
        return self._drawable_manager.getDrawableSelector()
    
    def add_point_at(self, position: hou.Vector3) -> None:
        """
        Ajoute un point à la courbe à la position donnée.
        
        Exemple:
            drawer.add_point_at(hou.Vector3(0, 0, 0))
            drawer.add_point_at(hou.Vector3(1, 0, 0))
            drawer.add_point_at(hou.Vector3(2, 1, 0))
        
        Args:
            position: Position 3D du point hou.Vector3(x, y, z)
        """
        if not self.point_add_op:
            print("[SimpleCurveDrawer] Add operation not initialized")
            return
        
        # Stocker le point
        self._drawn_points.append(position)
        
        # Mettre à jour le paramètre ADDPTS_PARM du node
        # Format: "x,y,z x,y,z ..."
        points_str = self._format_points_for_hda(self._drawn_points)
        self.node.parm(constants.ADDPTS_PARM).set(points_str)
        
        # Dire au HDA: "ajoute des points" (pas "déplace", pas "supprime")
        self.node.parm(constants.OPTYPE_PARM).set(constants.OPTYPE_APPENDPT)
        
        print(f"[SimpleCurveDrawer] Added point at {position}")
    
    def move_point(self, point_index: int, new_position: hou.Vector3) -> None:
        """
        Déplace un point à une nouvelle position.
        
        Exemple:
            drawer.move_point(0, hou.Vector3(1, 1, 0))  # Déplacer point 0
        
        Args:
            point_index: Index du point (0, 1, 2, ...)
            new_position: Nouvelle position hou.Vector3(x, y, z)
        """
        if not self.point_move_op:
            print("[SimpleCurveDrawer] Move operation not initialized")
            return
        
        # Si le point existe dans notre liste locale
        if point_index < len(self._drawn_points):
            self._drawn_points[point_index] = new_position
        
        # Mettre à jour le paramètre du node
        points_str = self._format_points_for_hda(self._drawn_points)
        self.node.parm(constants.ADDPTS_PARM).set(points_str)
        
        # Dire au HDA: "transforme/déplace"
        self.node.parm(constants.OPTYPE_PARM).set(constants.OPTYPE_TRANSFORM)
        
        print(f"[SimpleCurveDrawer] Moved point {point_index} to {new_position}")
    
    def select_point(self, point_index: int) -> None:
        """
        Sélectionne un point.
        
        Args:
            point_index: Index du point
        """
        if point_index not in self._current_selection:
            self._current_selection.append(point_index)
        
        # Mettre à jour le paramètre ACTIVEPOINTS_PARM
        points_str = " ".join(str(p) for p in self._current_selection)
        self.node.parm(constants.ACTIVEPOINTS_PARM).set(points_str)
    
    def deselect_all(self) -> None:
        """Désélectionne tous les points."""
        self._current_selection = []
        self.node.parm(constants.ACTIVEPOINTS_PARM).set("")
    
    def draw_curve(self) -> None:
        """
        Force le redessinage de la courbe.
        Utile après modifications.
        """
        self._drawable_manager.updateNode()
    
    def get_num_points(self) -> int:
        """Retourne le nombre de points dessinés."""
        return len(self._drawn_points)
    
    def get_points(self) -> List[hou.Vector3]:
        """Retourne la liste de tous les points."""
        return self._drawn_points.copy()
    
    def clear_curve(self) -> None:
        """Efface tous les points et ré-initialise."""
        self._drawn_points = []
        self._current_selection = []
        self.node.parm(constants.ADDPTS_PARM).set("")
        self.node.parm(constants.ACTIVEPOINTS_PARM).set("")
        print("[SimpleCurveDrawer] Curve cleared")
    
    # =====================================================
    # UTILITAIRES INTERNES
    # =====================================================
    
    @staticmethod
    def _format_points_for_hda(points: List[hou.Vector3]) -> str:
        """
        Formate une liste de points pour le paramètre ADDPTS_PARM du HDA.
        
        Format pour HDA: "1.0,2.0,3.0 4.0,5.0,6.0 ..."
        
        Args:
            points: Liste de hou.Vector3
        
        Returns:
            String formatée pour le HDA
        """
        formatted = " ".join(
            f"{p[0]},{p[1]},{p[2]}" for p in points
        )
        return formatted
    
    # =====================================================
    # CALLBACKS UTILISATEUR (pour intégration viewer state)
    # =====================================================
    
    def onMouseEvent(self, kwargs: dict) -> bool:
        """
        Événement souris envoyé par le viewer state.
        À implémenter si vous héritez de cette classe ou l'intégrez.
        """
        ui_event = kwargs.get("ui_event")
        if not ui_event:
            return False
        
        reason = ui_event.reason()
        
        # Exemple: left-click pour ajouter un point
        if reason == hou.uiEventReason.Picked:
            if ui_event.mouseX() > 0:  # Fake check pour éviter les erreurs
                print("[SimpleCurveDrawer] User picked in viewport")
                # Ici vous pouvez décider ce qui se passe
        
        return False  # Retourner False = laisser le système gérer aussi
    
    def onEnter(self, kwargs: dict) -> None:
        """Appelé quand le state devient actif."""
        print("[SimpleCurveDrawer] Entered state")
        self._drawable_manager.onEnter(kwargs)
    
    def onExit(self, kwargs: dict) -> None:
        """Appelé quand le state se termine."""
        print("[SimpleCurveDrawer] Exited state")
        self._drawable_manager.onExit(kwargs)
    
    def onDraw(self, kwargs: dict) -> None:
        """Appelé à chaque frame pour redessiner."""
        self._drawable_manager.onDraw(kwargs)


# =====================================================
# EXEMPLE D'UTILISATION
# =====================================================

if __name__ == "__main__":
    # Cet exemple montre comment utiliser SimpleCurveDrawer
    
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║   SimpleCurveDrawer - Drawer Minimaliste de Courbes    ║
    ╚══════════════════════════════════════════════════════════╝
    
    USAGE SIMPLE:
    
    # 1. Créer une instance
    scene_viewer = hou.ui.getPaneTabOfType(hou.paneTabType.SceneViewer)
    node = hou.node("/obj/my_curve_op")
    drawer = SimpleCurveDrawer(scene_viewer.baseCamera().sceneViewer(), node)
    
    # 2. Ajouter des points manuellement
    drawer.add_point_at(hou.Vector3(0, 0, 0))
    drawer.add_point_at(hou.Vector3(1, 0, 0))
    drawer.add_point_at(hou.Vector3(1, 1, 0))
    drawer.add_point_at(hou.Vector3(0, 1, 0))
    
    # 3. Déplacer un point
    drawer.move_point(0, hou.Vector3(0.5, 0.5, 0))
    
    # 4. Obtenir les points
    points = drawer.get_points()
    print(f"Total points: {drawer.get_num_points()}")
    
    # 5. Sélectionner des points
    drawer.select_point(0)
    drawer.select_point(1)
    
    # 6. Redessiner
    drawer.draw_curve()
    """)
