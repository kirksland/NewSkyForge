"""
State:          DraggerGadget (fixed)
State type:     DraggerGadget
Description:    Point drag along averaged normal, with editable Python geometry
"""
import hou
import resourceutils as ru
import viewerstate.utils as su

class State(object):
    MSG = "Press Y to cycle through the gadgets. Move the mouse over the geometry components."

    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self._src_geo = None
        self._draw_geo = None
        self._node = None
        self.rotate = None
        self.face_gadget = None
        self.line_gadget = None
        self.point_gadget = None
        self.gadget_grouping = None
        self.stash = None

        self.dragger = hou.ViewerStateDragger("dragger")
        self.color_options = ru.ColorOptions(self.scene_viewer)        
        
        # guide geometry
        self.guide_line_geo = hou.Geometry()
        
        self.guide_line_points = []
        self.guide_line_points.append(self.guide_line_geo.createPoint())
        self.guide_line_points.append(self.guide_line_geo.createPoint())
        
        self.poly_guide_line = self.guide_line_geo.createPolygon()
        self.poly_guide_line.addVertex(self.guide_line_points[0])
        self.poly_guide_line.addVertex(self.guide_line_points[1])
        self.poly_guide_line.addVertex(self.guide_line_points[0])
                
        self.guide_line = hou.GeometryDrawable(scene_viewer, hou.drawableGeometryType.Line, 
            "guide_line")
        self.guide_line.setGeometry(self.guide_line_geo)
        self.guide_line.setParams({"color1":self.color_options.colorFromName("PickedHandleColor"),
            "line_width":1.0})
        self.guide_line.show(False)
        
        sops = hou.sopNodeTypeCategory()        
        verb = sops.nodeVerb('tube')
        verb.setParms({
            "type" : 1,
            "rad": (0.002, 0.02),
            "rows": 3,
            "cols": 6,
            'height': 0.08,
            "cap":True
        })
        self.guide_arrow_geo = hou.Geometry()
        verb.execute(self.guide_arrow_geo, [])
        
        self.guide_arrow = hou.GeometryDrawable(scene_viewer, hou.drawableGeometryType.Face, 
            "guide_arrow")
        self.guide_arrow.setGeometry(self.guide_arrow_geo)
        self.guide_arrow.setParams({"color1":self.color_options.colorFromName("PickedHandleColor")})
        self.guide_arrow.setParams({"scale":hou.Vector3(0.5,0.5,0.5)})
        self.guide_arrow.show(False)
        
        # Editable point display drawable (for transformations)
        self.point_display = hou.GeometryDrawable(
            scene_viewer, hou.drawableGeometryType.Point, "point_display"
        )
        self.point_display.setParams({
            "color1": self.color_options.colorFromName("PickedHandleColor"),
            "radius": 8.0,
            "style": hou.drawableGeometryPointStyle.LinearCircle,
        })
        self.point_display.show(False)
                
        self.cursor = su.CursorLabel(scene_viewer, "cursor")        


    def _getStashGeo(self):
        """ Récupère la geo déjà dans le stash (si elle existe) et la stocke dans self.geo"""
        self.stash = self._node.node("stash1")
        self._draw_geo = hou.Geometry()

        if self.stash:
            existing_geo = self.stash.parm("stash").evalAsGeometry()
            if existing_geo:
                self._draw_geo.merge(existing_geo)

    def _push_src_geo_to_stash(self):
        if self.stash is not None:
            self.stash.parm("stash").set(self._src_geo)  # optionnel mais propre
            self.stash.cook(force=True)
            if self._node is not None:
                self._node.cook(force=True)

    def _translate_point(self, point_index, delta):
        pt = self._src_geo.point(point_index)
        if pt is None:
            return False
        pt.setPosition(pt.position() + delta)
        self._src_geo.incrementModificationCounter()
        # Update the display drawable
        if hasattr(self, 'point_display'):
            self.point_display.setGeometry(self._src_geo)
        return True

    def _translate_line_points(self, point1_index, point2_index, delta):
        moved = False
        moved = self._translate_point(point1_index, delta) or moved
        moved = self._translate_point(point2_index, delta) or moved
        return moved

    def _translate_face_points(self, prim_index, delta):
        prim = self._src_geo.prim(prim_index)
        if prim is None:
            return False

        moved = False
        for vert in prim.vertices():
            pt = vert.point()
            if pt is not None:
                pt.setPosition(pt.position() + delta)
                moved = True
        
        if moved:
            self._src_geo.incrementModificationCounter()
            # Update the display drawable
            if hasattr(self, 'point_display'):
                self.point_display.setGeometry(self._src_geo)
        return moved
        
#-------------------------------------------------------------------------------
    #   utility methods
#--------------------------------------------------------------------------------

    def _compute_face_drag_line(self, prim_index):
        poly = self._src_geo.prim(prim_index)
        return poly.boundingBox().center(), poly.normal()

    def _compute_point_drag_line(self, point_index):
        pt = self._src_geo.point(point_index)
        normal = hou.Vector3()
        for poly in pt.prims():
            normal += poly.normal()
        return pt.position(), normal.normalized()

    def _compute_line_drag_line(self, point1_index, point2_index):
        p1 = self._src_geo.point(point1_index)
        p2 = self._src_geo.point(point2_index)
        return p1.position(), (p2.position() - p1.position()).normalized()

    def _update_guide_arrow_transform(self):
        xform = self.rotate
        xform *= hou.hmath.buildTranslate(self.guide_line_points[1].position())
        self.guide_arrow.setTransform(xform)

    def _start_drag_with_guide(self, ui_event, line_orig, line_dir):
        self.dragger.startDragAlongLine(ui_event, line_orig, line_dir)
        self.guide_line_points[0].setPosition(line_orig)
        self.guide_line_points[1].setPosition(line_orig + line_dir * 0.3)

        rot_mat = hou.Vector3(0, 1, 0).matrixToRotateTo(line_dir)
        self.rotate = hou.hmath.buildRotate(rot_mat.extractRotates())
        self._update_guide_arrow_transform()

        self.guide_line.show(True)
        self.guide_arrow.show(True)

    def _apply_drag_delta(self, ui_event, gadget_name, c1, c2):
        try:
            delta = self.dragger.drag(ui_event)["delta_position"]
        except:
            return False

        moved = False
        if gadget_name == "point_gadget":
            moved = self._translate_point(c1, delta)
        elif gadget_name == "line_gadget":
            moved = self._translate_line_points(c1, c2, delta)
        elif gadget_name == "face_gadget":
            moved = self._translate_face_points(c1, delta)

        if not moved:
            return False

        # Refresh all gadgets with the updated geometry
        self.point_gadget.setGeometry(self._src_geo)
        self.line_gadget.setGeometry(self._src_geo)
        self.face_gadget.setGeometry(self._src_geo)

        self._push_src_geo_to_stash()

        self.guide_line_points[0].setPosition(self.guide_line_points[0].position() + delta)
        self.guide_line_points[1].setPosition(self.guide_line_points[1].position() + delta)
        self._update_guide_arrow_transform()
        return True
    
#-------------------------------------------------------------------------------
    # viewer state event handlers
#--------------------------------------------------------------------------------   
       
    def onEnter(self, kwargs):

        node = self._node = kwargs["node"]
        self.hda = node
        self.stash = node.node("stash1")
        geo_copy = hou.Geometry()
        loaded_from_stash = False

        if self.stash is not None:
            existing_geo = self.stash.parm("stash").evalAsGeometry()
            if existing_geo is not None and (len(existing_geo.points()) > 0 or len(existing_geo.prims()) > 0):
                geo_copy.merge(existing_geo)
                loaded_from_stash = True

        if not loaded_from_stash:
            input_node = node.node("INPUT")
            if input_node is not None:
                src_geo = input_node.geometry()
                if src_geo is not None:
                    geo_copy.merge(src_geo)

        self._src_geo = geo_copy
        if not loaded_from_stash:
            self._push_src_geo_to_stash()


        # Assign the geometry to gadgets        
        self.face_gadget = self.state_gadgets["face_gadget"]
        self.face_gadget.setParams({"draw_color":self.color_options.colorFromName("HandleXAxisColor", alpha_name="LocateAlpha")})
        self.face_gadget.setGeometry(self._src_geo)

        self.line_gadget = self.state_gadgets["line_gadget"]
        self.line_gadget.setGeometry(self._src_geo)
        self.line_gadget.setParams({"draw_color":self.color_options.colorFromName("HandleYAxisColor", alpha_name="LocateAlpha")})        
        self.line_gadget.setParams({"line_width":2.0})
        
        self.point_gadget = self.state_gadgets["point_gadget"]
        self.point_gadget.setGeometry(self._src_geo)
        self.point_gadget.setParams({"draw_color":self.color_options.colorFromName("HandleZAxisColor", alpha_name="LocateAlpha")})
        self.point_gadget.setParams({"radius":5.0})
        
        # Configure the editable point display drawable
        self.point_display.setGeometry(self._src_geo)

        # Setup the display group to show individual gadgets
        gadgets = [self.face_gadget, self.line_gadget, self.point_gadget]
        grouping = [("Face",[0]), ("Line",[1]), ("Point",[2]), ("All",[0,1,2])]
        self.gadget_grouping = ru.DisplayGroup(self.scene_viewer, gadgets, grouping)
        self.gadget_grouping.showGroup("Face",True)

        self.scene_viewer.setPromptMessage( State.MSG )

    def onResume(self, kwargs):
        self.gadget_grouping.showCurrent(True)
        self.scene_viewer.setPromptMessage( State.MSG )

    def onInterrupt(self,kwargs):
        self.gadget_grouping.showCurrent(False)

    def onMouseEvent(self, kwargs):

        ui_event = kwargs["ui_event"]
        reason = ui_event.reason()    
        consumed = False
        gadget_name = self.state_context.gadget()

        # update the cursor with the ui kwargs
        self.cursor.setParams(kwargs)
        
        if gadget_name not in ["line_gadget", "face_gadget", "point_gadget"]:
            # if none of the gadgets are active, hide cursor and guides
            self.cursor.show(False)
            self.guide_line.show(False)
            self.guide_arrow.show(False)

            # Safely end dragging if one was started
            self.dragger.endDrag()
            
            try:
                # Terminate pending undo if any
                self.scene_viewer.endStateUndo()                        
            except:
                pass
            
            return True
            
        # update the cursor with the active gadget info
        label = self.state_context.gadgetLabel()
        c1 = self.state_context.component1()
        c2 = self.state_context.component2()
        
        self.cursor.setLabel("{} : {} {}".format(label, c1, c2 if c2 > -1 else ""))
        self.cursor.show(True)
        
        if reason == hou.uiEventReason.Located:        
            # Nothing to do for the locate UI event 
            return False
                    
        if gadget_name == "face_gadget":
        
            consumed = True
            if reason == hou.uiEventReason.Start:
                                
                # setup the dragger to translate the geometry along the 
                # located polygon normal
                self.scene_viewer.beginStateUndo("Drag face normal")
                line_orig, line_dir = self._compute_face_drag_line(c1)
                self._start_drag_with_guide(ui_event, line_orig, line_dir)
                
            elif reason in [hou.uiEventReason.Active, hou.uiEventReason.Changed]:
                if not self._apply_drag_delta(ui_event, gadget_name, c1, c2):
                    return False
                                    
        elif gadget_name == "point_gadget":

            consumed = True
            if reason == hou.uiEventReason.Start:                
                # setup the dragger to translate the geometry along the 
                # located point normal
                self.scene_viewer.beginStateUndo("Drag vertex normal")
                line_orig, line_dir = self._compute_point_drag_line(c1)
                self._start_drag_with_guide(ui_event, line_orig, line_dir)
                
            elif reason in [hou.uiEventReason.Active, hou.uiEventReason.Changed]:
                if not self._apply_drag_delta(ui_event, gadget_name, c1, c2):
                    return False
                
        elif gadget_name == "line_gadget":

            consumed = True
            if reason == hou.uiEventReason.Start:                
                # setup the dragger to translate the geometry along the located edge
                self.scene_viewer.beginStateUndo("Drag edge")
                line_orig, line_dir = self._compute_line_drag_line(c1, c2)
                self._start_drag_with_guide(ui_event, line_orig, line_dir)
                
            elif reason in [hou.uiEventReason.Active, hou.uiEventReason.Changed]:
                if not self._apply_drag_delta(ui_event, gadget_name, c1, c2):
                    return False
        
        # Update the guide geometry data id
        self.guide_line_geo.findPointAttrib("P").incrementDataId()
        self.guide_line_geo.incrementModificationCounter()
        self.guide_arrow_geo.incrementModificationCounter()
    
        if reason == hou.uiEventReason.Changed:
            # Dragging terminated
            
            self.dragger.endDrag()
            self.guide_line.show(False)
            self.guide_arrow.show(False)
            
            try:
                # Careful when closing a pending undo event as we 
                # may haven't been called to open one in the frst place.
                # So it's safer to catch any exception when doing so.
                self.scene_viewer.endStateUndo()                        
            except:
                pass
                            
        return consumed
        
    def onDraw( self, kwargs ):
        if self.state_context.isPicking():
            return
            
        handle = kwargs["draw_handle"]

        self.face_gadget.setParams({"indices":[]})
        self.point_gadget.setParams({"indices":[]})            
        
        gadget_name = self.state_context.gadget()
        c1 = self.state_context.component1()
        
        if gadget_name == "face_gadget":                
            # Draw the located polygon only
            self.face_gadget.setParams({"indices":[c1]})
                    
        elif gadget_name == "point_gadget":
            # Draw the located point only
            self.point_gadget.setParams({"indices":[c1]})            

        elif gadget_name == "line_gadget":        
            pass

        self.line_gadget.draw(handle) 
        self.face_gadget.draw(handle) 
        self.point_gadget.draw(handle)
        
        # Draw the editable point display if a point is being selected
        if gadget_name == "point_gadget":
            self.point_display.setParams({"indices": [c1]})
            self.point_display.show(True)
        else:
            self.point_display.show(False)         
        
        self.point_display.draw(handle)
        self.guide_line.draw(handle) 
        self.guide_arrow.draw(handle) 
        self.cursor.draw(handle)

    def onMenuAction(self, kwargs):
        menu_item = kwargs["menu_item"]    
        if kwargs["menu_item"] == "cycle":
            self.gadget_grouping.showNext(True)            
# ----------------------------------------------------------------------

def createViewerStateTemplate():
    """ Mandatory entry point to create and return the viewer state 
        template to register. """

    state_typename = "DraggerGadget"
    state_label = "DraggerGadget"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon("DESKTOP_application_sierra")
    
    template.bindGadget( hou.drawableGeometryType.Line, "line_gadget", label="Line" )
    template.bindGadget( hou.drawableGeometryType.Face, "face_gadget", label="Face" )
    template.bindGadget( hou.drawableGeometryType.Point, "point_gadget", label="Point" )

    hotkey_definitions = hou.PluginHotkeyDefinitions()
    menu = hou.ViewerStateMenu(state_typename + "_menu", state_label)        
    menu.addActionItem("cycle", "Cycle Gadgets", hotkey=su.defineHotkey(hotkey_definitions, state_typename, "cycle", "y"))
    template.bindMenu(menu)
    template.bindHotkeyDefinitions(hotkey_definitions)
    
    return template
