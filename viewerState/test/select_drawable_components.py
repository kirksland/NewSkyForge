"""
State:          Justi::Forge Remesher::1.0
State type:     justi::Forge_Remesher::1.0
Description:    Justi::Forge Remesher::1.0
Author:         justi
Date Created:   February 08, 2026 - 15:10:21
"""

# Usage: Sample to select drawable components.

import hou
import viewerstate.utils as su

import resourceutils as ru

class State(object):
    COLOR_S = hou.Color(1,1,0)
    COLOR_H = hou.Color(0,1,1)
    COLOR_FH = hou.Vector4(0,1,1,0.5)
    COLOR_FS = hou.Vector4(1,1,0,0.5)
    H_SIZE = 7
    H_SIZE2 = H_SIZE/2

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.selection = None
        self.geo = None  # Stocker la géométrie
        self.color_options = ru.ColorOptions(self.scene_viewer)                
        box_color = self.color_options.colorFromName("HandlePivotColor")
        box_color_f = self.color_options.colorFromName("HandlePivotColor", alpha=0.3)

        # Creates a set of drawables for each type of drawables we want 
        # to support. 
        self.geometry = None
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

    def _createBox(self, size=(1.5,1.5,1.5),t=(0,1,0),divrate=(2,2,2)):
        sop_cat = hou.sopNodeTypeCategory()        
        verb = sop_cat.nodeVerb("box")
        verb.setParms({
            "type" : 1, 
            "divrate":divrate, 
            "size":size,
            "t": t })
        geo = hou.Geometry()        
        verb.execute(geo, [])
        return geo

    def _getPointsFromSelectedLines(self, line_indices):
        """
        Récupère les points des lignes sélectionnées.
        line_indices contient les indices des POINTS, pas des primitives.
        """
        if not self.geo:
            return None
        
        new_geo = hou.Geometry()
        
        # line_indices sont directement les indices des points
        for point_idx in line_indices:
            pt = self.geo.point(point_idx)
            
            if pt:
                new_pt = new_geo.createPoint()
                new_pt.setPosition(pt.position())
        
        return new_geo

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
         

        # Iterate over the selected drawables and set the drawables to 
        # draw the selection.
        for k,v in self.selection.items():

            if k == "box_points":
                if "point" in v:
                    indices = v["point"]
                    self.box_points_s.setParams({"indices":indices})
                    self.box_points_s.show(True)


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

    def _clearLocatedSelection(self, clear_selection=False):
        """ Hide the located drawable components
        """
        self.box_points_h.show(False)
        self.box_lines_h.show(False)


        if clear_selection:
            self.box_points_s.show(False)
            self.box_lines_s.show(False)

            self.selected_line_highlight.show(False)
            self.selected_line_points.show(False)

    def _logLocatedInfo(self, kwargs):
        self.log("-"*30)
        self.log("located",len(kwargs["drawable_selection"]), kwargs["drawable_selection"])

    def onEnter(self, kwargs):
        """ Setup the drawables.
        """

        node = kwargs["node"]
        self.geo = node.geometry()

        # Set the drawable geometries

        self.box_lines.setGeometry(self.geo)
        self.box_points.setGeometry(self.geo)
       
        self.box_lines_h.setGeometry(self.geo)
        self.box_lines_s.setGeometry(self.geo)
        self.box_points_h.setGeometry(self.geo)
        self.box_points_s.setGeometry(self.geo)



        self.box_points.show(True)
        self.box_lines.show(True)


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

        self.hovered_line_highlight.show(False)
        self.hovered_line_points.show(False)

        # Iterate over the selection to set the drawables to highlight.
        for k,v in kwargs["drawable_selection"].items():

            if k == "box_points":
                if "point" in v:
                    indices = v["point"]
                    self.box_points_h.setParams({"indices":indices})
                    self.box_points_h.show(True)



            if k == "box_lines":
                if "line" in v:
                    indices = v["line"]
                    
                    # ✨ Créer une polyligne survolée (cyan)
                    polyline_geo = self._createPolylineFromPoints(indices)
                    if polyline_geo:
                        self.hovered_line_highlight.setGeometry(polyline_geo)
                        self.hovered_line_highlight.show(True)
                    
                    # ✨ Créer les points survolés (cyan)
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

        return True

    def onStartSelection(self, kwargs):
        """ Called when a bound selector has been started
        """
        selector_name = kwargs["name"]
        self.log(selector_name + " has started")

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
        self.log(selector_name + " has stopped")

        if selector_name == "my_drawable_selector":
            self._clearLocatedSelection()
            return

        # Process other selector type if any
        return

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
        drawable_mask=["box_points","box_lines"],
        hotkey=hk1)    

    return template