"""
State:          Justi::Forge Remesher::1.0
State type:     justi::Forge_Remesher::1.0
Description:    Justi::Forge Remesher::1.0
Author:         justi
Date Created:   February 08, 2026 - 17:04:04
"""


import hou
import viewerstate.utils as su


class State(object):

    COLOR_S = hou.Color(1,1,0)
    COLOR_H = hou.Color(0,1,1)
    COLOR_FH = hou.Vector4(0,1,1,0.5)
    COLOR_FS = hou.Vector4(1,1,0,0.5)
    H_SIZE = 7
    H_SIZE2 = H_SIZE/2


    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

        self.geo = hou.Geometry();
        self.hda = None
        self.stash = None

        box_color = self.color_options.colorFromName("HandlePivotColor")
        box_color_f = self.color_options.colorFromName("HandlePivotColor", alpha=0.3)

        # Line drawable set
        # The geometry component line
        self.box_lines = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Line, "box_lines")
        self.box_lines.setParams({"color1":box_color})

        # Line drawable for highlighting the located line
        self.box_lines_h = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Line, "box_lines_h")
        self.box_lines_h.setParams({"color1":State.COLOR_H, "line_width":State.H_SIZE2})

        # Line drawable for highlighting the selected line
        self.box_lines_s = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Line, "box_lines_s")
        self.box_lines_s.setParams({"color1":State.COLOR_S})

        # Point drawable set
        self.box_points = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Point, "box_points")
        self.box_points.setParams({"color1":box_color, "radius":State.H_SIZE2, "style":hou.drawableGeometryPointStyle.LinearCircle})
        self.box_points_h = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Point, "box_points_h")
        self.box_points_h.setParams({"color1":State.COLOR_H, "radius":State.H_SIZE, "style":hou.drawableGeometryPointStyle.LinearCircle})
        self.box_points_s = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Point, "box_points_s")
        self.box_points_s.setParams({"color1":State.COLOR_S})

        # Face drawable set
        self.box_faces = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Face, "box_faces")
        self.box_faces.setParams({"color1":box_color_f})
        self.box_faces_h = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Face, "box_faces_h")
        self.box_faces_h.setParams({"color1":State.COLOR_FH})
        self.box_faces_s = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Face, "box_faces_s")
        self.box_faces_s.setParams({"color1":State.COLOR_FS})
        
        # ✨ Drawables pour les lignes sélectionnées
        self.selected_line_highlight = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Line, "selected_line_highlight")
        self.selected_line_highlight.setParams({"color1": hou.Color(1, 1, 0), "line_width": 5})
        
        self.selected_line_points = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Point, "selected_line_points")
        self.selected_line_points.setParams({"color1": hou.Color(1, 0, 0), "radius": 10, "style": hou.drawableGeometryPointStyle.LinearCircle})
        
        # ✨ Drawables pour le hover sur les lignes
        self.hovered_line_highlight = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Line, "hovered_line_highlight")
        self.hovered_line_highlight.setParams({"color1": State.COLOR_H, "line_width": 3})
        
        self.hovered_line_points = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Point, "hovered_line_points")
        self.hovered_line_points.setParams({"color1": State.COLOR_H, "radius": 8, "style": hou.drawableGeometryPointStyle.LinearCircle})

        


    def _createPolylineFromPoints(self, line_indices):
        """
        Crée une polyligne qui relie tous les points sélectionnés.
        Cela permet de surligner la ligne.
        """
        if not self.geo or not line_indices or len(line_indices) < 2:
            return None
        
        new_geo = hou.Geometry()
        
        # Créer les points dans la nouvelle géométrie
        new_points = []
        for point_idx in line_indices:
            pt = self.geo.point(point_idx)
            if pt:
                new_pt = new_geo.createPoint()
                new_pt.setPosition(pt.position())
                new_points.append(new_pt)
        
        # Créer une polyligne (polygon) qui relie tous les points
        if len(new_points) >= 2:
            poly = new_geo.createPolygon(is_closed=False)  # is_closed=False pour une polyligne
            for pt in new_points:
                poly.addVertex(pt)
        
        return new_geo
    

    def _updateSelection(self, selection):
        """ Update the drawables used for drawing the selected
            components.
        """

        self.selection = selection

        # Clear previous selection highlights if any
        self._clearLocatedSelection(clear_selection=not self.selection)

        if not self.selection:
            return

        self.box_points_s.show(False)            
        self.box_lines_s.show(False)            
        self.box_faces_s.show(False)            

        # Iterate over the selected drawables and set the drawables to 
        # draw the selection.
        for k,v in self.selection.items():

            if k == "box_points":
                if "point" in v:
                    indices = v["point"]
                    self.box_points_s.setParams({"indices":indices})
                    self.box_points_s.show(True)

            if k == "box_faces":
                if "face" in v:
                    indices = v["face"]
                    self.box_faces_s.setParams({"indices":indices})
                    self.box_faces_s.show(True)

            if k == "box_lines":                    
                if "line" in v:
                    indices = v["line"]
                    
                    
                    # Réutiliser les drawables existants (créés dans __init__)
                    polyline_geo = self._createPolylineFromPoints(indices)
                    if polyline_geo:
                        self.selected_line_highlight.setGeometry(polyline_geo)
                        self.selected_line_highlight.show(True)
                    
                    points_geo = self._getPointsFromSelectedLines(indices)
                    if points_geo:
                        self.selected_line_points.setGeometry(points_geo)
                        self.selected_line_points.show(True)


    def _getPointsFromSelectedLines(self, line_indices):
        """
        Récupère les points des lignes sélectionnées.
        line_indices contient les indices des POINTS
        """
        if not self.geo:
            return None
        
        new_geo = hou.Geometry()
    
        for point_idx in line_indices:
            pt = self.geo.point(point_idx)
            
            if pt:
                new_pt = new_geo.createPoint()
                new_pt.setPosition(pt.position())
        
        return new_geo
    



    def _clearLocatedSelection(self, clear_selection=False):
        """ Hide the located drawable components
        """
        self.box_points_h.show(False)
        self.box_lines_h.show(False)
        self.box_faces_h.show(False)

        if clear_selection:
            self.box_points_s.show(False)
            self.box_lines_s.show(False)
            self.box_faces_s.show(False)
            self.selected_line_highlight.show(False)
            self.selected_line_points.show(False)



    def _setupConstructionPlaneFromView(self):
        sv = self.scene_viewer
        if not sv:
            return

        viewport = sv.curViewport()
        if not viewport:
            return

        view_xform = viewport.viewTransform()
        rot_matrix = view_xform.extractRotationMatrix3()

        m = hou.Matrix4(rot_matrix)
        m.setAt(3, 0, 0)
        m.setAt(3, 1, 0)
        m.setAt(3, 2, 0)

        cplane = sv.constructionPlane()
        cplane.setIsVisible(True)
        cplane.setTransform(m)

    def _getStashGeo(self):
        """ Récupère la geo déjà dans le stash (si elle existe) et la stocke dans self.geo"""
        self.stash = self.hda.node("stash1")
        self.geo = hou.Geometry()

        if self.stash:
            existing_geo = self.stash.parm("stash").evalAsGeometry()
            if existing_geo:
                self.geo.merge(existing_geo)

    def _updateStash(self, position):
        """ Ajoute un point à la geo déjà dans le stash et réinjecte """
        
        if not self.stash:
            return
        # créer le nouveau point
        self.geo.createPoints(position)
    
        # remettre dans le stash
        self.stash.parm("stash").set(self.geo)  
    
            
    def _onHdaParmChanged(self, **kwargs):
        parm = kwargs["parm_tuple"]
        name = parm.name()
        if name == "stashinput":
            print("BOUTON STASHINPUT PRESSÉ")
            self.geo = hou.Geometry()


    # -------------------                ------------------- #
    # ------------------- Event Handlers ------------------- #                                             """
    # -------------------                ------------------- # 


    def onEnter(self, kwargs):

        self.hda = kwargs["node"]
        

        self._setupConstructionPlaneFromView()
        self._getStashGeo()

        self.hda.addEventCallback(
            (hou.nodeEventType.ParmTupleChanged,),
            self._onHdaParmChanged
        )

    def onMouseEvent(self, kwargs):
        """ Find the position of the point to add by 
            intersecting the construction plane. 
        """
        
        ui_event = kwargs["ui_event"]
        reason = ui_event.reason()
        device = ui_event.device()
        origin, direction = ui_event.ray()

        position = su.cplaneIntersection(self.scene_viewer, origin, direction)
        
        if device.isLeftButtonReleased():

            pos =[ hou.Vector3(*position)]
            self._updateStash(pos)
        
        if reason == hou.uiEventReason.Start:
            self._setupConstructionPlaneFromView()

    def onDraw( self, kwargs ):
        """ This callback is used for rendering the drawables
        """
        handle = kwargs["draw_handle"]
        self.box_lines.draw(handle)    
        self.box_lines_h.draw(handle)    
        self.box_lines_s.draw(handle)    
        self.box_points.draw(handle)    
        self.box_points_h.draw(handle)    
        self.box_points_s.draw(handle)    
        self.box_faces.draw(handle)    
        self.box_faces_h.draw(handle)    
        self.box_faces_s.draw(handle)
        
        # ✨ Dessiner les drawables de sélection
        self.selected_line_highlight.draw(handle)
        self.selected_line_points.draw(handle)
        
        # ✨ Dessiner les drawables de hover
        self.hovered_line_highlight.draw(handle)
        self.hovered_line_points.draw(handle)    

    def onLocatedSelection(self, kwargs):
        """ This handler is called when drawables are located. This is
            where the drawables for highlighting the geometries are setup.
        """
        # Hide all highlighted drawables
        self.box_points_h.show(False)
        self.box_lines_h.show(False)
        self.box_faces_h.show(False)
        self.hovered_line_highlight.show(False)
        self.hovered_line_points.show(False)

        # Iterate over the selection to set the drawables to highlight.
        for k,v in kwargs["drawable_selection"].items():

            if k == "box_points":
                if "point" in v:
                    indices = v["point"]
                    self.box_points_h.setParams({"indices":indices})
                    self.box_points_h.show(True)

            if k == "box_faces":
                if "face" in v:
                    indices = v["face"]
                    self.box_faces_h.setParams({"indices":indices})
                    self.box_faces_h.show(True)

            if k == "box_lines":
                if "line" in v:
                    indices = v["line"]
                    
                    #  Créer une polyligne survolée (cyan)
                    polyline_geo = self._createPolylineFromPoints(indices)
                    if polyline_geo:
                        self.hovered_line_highlight.setGeometry(polyline_geo)
                        self.hovered_line_highlight.show(True)
                    
                    #  Créer les points survolés (cyan)
                    points_geo = self._getPointsFromSelectedLines(indices)
                    if points_geo:
                        self.hovered_line_points.setGeometry(points_geo)
                        self.hovered_line_points.show(True)

    def onSelection(self, kwargs):
        """ Called when a selector has selected something.
        """

        # Handle the selection only if the data is available in the kwargs
        if "drawable_selection" in kwargs:
            # Handle the drawable selection
            self.selection = kwargs["drawable_selection"]
            self._updateSelection(self.selection)

        return False

    def onStartSelection(self, kwargs):
        """ Called when a bound selector has been started
        """
        selector_name = kwargs["name"]


        if selector_name == "my_drawable_selector":
            # A new drawable mask can be assigned before selecting
            # kwargs["drawable_mask"] = ["box_lines"]
            return

        # Process other selector type if any
        return

    def onStopSelection(self, kwargs):
        """ Called when a bound selector has been terminated
        """
        selector_name = kwargs["name"]


        if selector_name == "my_drawable_selector":
            self._clearLocatedSelection()
            return

        # Process other selector type if any
        return

    def onExit(self, kwargs):
        translation = hou.hmath.buildTranslate(hou.Vector3((0,0,0))) 
        translation = hou.hmath.buildRotate(90,90,0)
        sv = self.scene_viewer
        if sv:
            cplane = sv.constructionPlane()

            # Translation = 0, rotation = 0, scale = 1
            cplane.setTransform(translation)
        
        if self.hda:
            self.hda.removeEventCallback(
                (hou.nodeEventType.ParmTupleChanged,),
                self._onHdaParmChanged
            )
            
def createViewerStateTemplate():
    """ Mandatory entry point to create and return the viewer state 
        template to register. """

    state_typename = kwargs["type"].definition().sections()["DefaultState"].contents()
    state_label = "Justi::Forge Remesher::1.0"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon(kwargs["type"].icon())

    hotkey_definitions = hou.PluginHotkeyDefinitions()
    hk1 = su.defineHotkey(hotkey_definitions, state_typename,
                          "drawable selector", "1")
    template.bindHotkeyDefinitions(hotkey_definitions)

    template.bindDrawableSelector("Select a drawable component", 
        name="my_drawable_selector",
        auto_start=True, 
        drawable_mask=["box_points","box_lines","box_faces"],
        hotkey=hk1)    


    return template