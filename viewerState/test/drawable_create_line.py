"""
State:          Justi::Forge Remesher::1.0
State type:     justi::Forge_Remesher::1.0
Description:    Justi::Forge Remesher::1.0
Author:         justi
Date Created:   February 08, 2026 - 15:09:16
"""

# Usage: This sample uses a geometry drawable group to draw highlights
# when hovering over geometry polygons. Make sure to add an input on the
# node, connect a polygon mesh geometry and hit enter in the viewer.

import hou
import viewerstate.utils as su

class State(object):
    MSG = "Move the mouse over the geometry."

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.poly_id = -1
        self.cursor_text = "Text"
        self.geometry = None
        self.mouse_screen = hou.Vector2()

        self.text = hou.TextDrawable(self.scene_viewer, "text")

        # Construct a geometry drawable group
        line = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Line, "line",
            params = {
                "color1": (0.0,0.0,1.0,1.0),            
                "style": hou.drawableGeometryLineStyle.Plain,
                "line_width": 3 }
        )

        face = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Face, "face", 
            params = {
                "style": hou.drawableGeometryFaceStyle.Plain,
                "color1": (0.0,1.0,0.0,1.0) }
        )

        point = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Point, "point",
            params = {
                "num_rings": 2,
                "radius": 8,
                "color1": (1.0,0.0,0.0,1.0),
                "style" : hou.drawableGeometryPointStyle.LinearCircle}
        )

        self.poly_guide = hou.GeometryDrawableGroup("poly_guide")

        self.poly_guide.addDrawable( face )
        self.poly_guide.addDrawable( line )
        self.poly_guide.addDrawable( point )

    def show(self, visible):
        """ Display or hide drawables.
        """
        self.text.show(visible)
        self.poly_guide.show(visible)

    def onEnter(self, kwargs):
        """ Assign the geometry to drawabled
        """
        node = kwargs["node"]
        self.geometry = node.geometry()
        self.show(True)

        self.scene_viewer.setPromptMessage( State.MSG )

    def onResume(self, kwargs):
        self.show(True)
        self.scene_viewer.setPromptMessage( State.MSG )

    def onInterrupt(self,kwargs):
        self.show(False)

    def onMouseEvent(self, kwargs):
        """ Computes the cursor text position and drawable geometry
        """
        ui_event = kwargs["ui_event"]

        mousex = ui_event.device().mouseX()
        mousey = ui_event.device().mouseY()

        (origin, dir) = ui_event.ray()
        self.mouse_screen = self.scene_viewer.curViewport().mapToScreen(origin)      
        self.cursor_text = "<font size=4,>%.2f, %.2f</font>" % ( self.mouse_screen[0],
            self.mouse_screen[1] )

        gi = su.GeometryIntersector(self.geometry)
        gi.intersect(origin, dir, snapping=False)

        # update the geometry used by drawables
        if gi.prim_num != -1 and gi.prim_num != self.poly_id:
            self.poly_id = gi.prim_num

            # Construct a new geometry
            poly_points = self.geometry.prim(self.poly_id).points()                                                                      
            poly_geo = hou.Geometry()
            poly = poly_geo.createPolygon()
            for pt in poly_points:
                point = poly_geo.createPoint()
                point.setPosition(pt.position())
                poly.addVertex(point)        

            # update the drawable                
            self.poly_guide.setGeometry(poly_geo)
            self.show(True)

        elif gi.prim_num == -1:
            self.poly_id = -1
            self.poly_geo = None            
            self.show(False)

    def onDraw( self, kwargs ):
        """ This callback is used for rendering the drawables
        """
        handle = kwargs["draw_handle"]

        self.poly_guide.draw(handle) 

        # cursor text
        params = {
            "text": self.cursor_text,
            "multi_line": True,
            "translate": (self.mouse_screen[0],self.mouse_screen[1], 0.0),
            "highlight_mode": hou.drawableHighlightMode.MatteOverGlow,
            "glow_width": 1,
            "color1": hou.Color(1.0,1.0,1.0),
            "color2": (0.0,0.0,0.0,1.0) }            
        self.text.draw( handle, params )

def createViewerStateTemplate():
    """ Mandatory entry point to create and return the viewer state 
        template to register. """

    state_typename = kwargs["type"].definition().sections()["DefaultState"].contents()
    state_label = "Justi::Forge Remesher::1.0"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon(kwargs["type"].icon())

    return template