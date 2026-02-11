#### coding=utf-8
"""
State:          sidefx_curve
State type:     sidefx_curve
Description:    sidefx_curve
Date Created:   October 02, 2020
"""

from typing import Type, Callable

import hou

import curveutils as cu
from curvestate import constants
from curvestate import referencegeo
from curvestate.undos import SelectionUndo
from curvestate import baseoperation
from curvestate import simpleselectionops
from curvestate import editops
from curvestate import drawops
from curvestate import orientops
from curvestate import roundcornerops
from curvestate import drawablemanager
from curvestate import stateparms

import resourceutils as ru
import viewerstate.utils as su
import viewerhandle.hudapi as hud
import viewerhandle.hudconstants as hudc
import viewerhandle.hudutils as hudu

# The Curve view state is broken into a number of pieces
# 1. curveutils : Helper functions and classes used in the curve state.
# 2. ReferenceCurve class : a bundle of helper functions, methods used
#       to analyze the current geoemetry. This class handles taking the
#       live geometry, transforming it into a form that matches the
#       internal representation, places many helpful groups and attributes
#       on it to help with operations, and sets up the geoemetry for
#       any drawables that reflect the live geometry.
#       A single ReferenceCurve object is created and stored in the State class.
# 3. The operation classes: There are a number of classes that handle each
#       of the operations. These override most state event methods, allowing
#       events to be sent to them when active.
#
#       There are two types of operations, interactive or button. Button
#       operations always occur immediately to A selection of points, and do
#       not need to stay active. Interactive operations stay active while
#       doing the operation, capturing the events (e.g. draw mode, moving points,
#       interacting with bezier handles, changing round corners, or reshaping curves.)
#
#       Operations work by setting the parameters needed and then requesting to
#       commit the operation, which adds a point that stores the parms, updates the cache,
#       updates the preview curve, and updates and group or point lists in the parms
#       based on the transformations that the operation performs.
#       Operations can also "call" other operations, e.g. breaking while drawing
#       "calls" a break operation.
# 4. The drawable manager : Nearly all drawables (aside from one or two used for guides
#       in specific operations) reside in this class. This class handles etting up
#       these drawables, drawing them. Drawables are all wrapped in helper classes.
#       Any interactive gadget drawables allow you to grab the wrapper object,
#       and register mouse event callbacks, these get called when the gadget is
#       interacted with. The geoemetry for the drawables is mostly derived from
#       the live geoemetry and is retrieved from ReferenceCurve.
# 5. The box selector helper : This class is used in the main modes mouse event
#       handlers and helps with creating a box selection, checking points included
#       based on the pressed keys (Shift/Ctrl+Shift), and drawing the box selection.
# 6. The mode classes : These are structured as "mega" operations, sharing all the same
#       methods, but are directly interacted with by the State class.
#       Each of the four modes have one of these objects. There are three derived classes
#       from the main mode base class, one for Edit/Select Mode, Draw mode, and Orient Mode
#       The two draw modes share a mode class, but have separate objects.
#       For any event the state received, it looks up the active mode, and sends these
#       events to the mode. The mode then processes the event, and if there is an active
#       operation, sends the event to the operation.
#       The mode also handles and hotkeys, and processes mouse events to set up the
#       operations, box selections, etc.
# 7. The State class : this is the lowest level of the view state. Events are first seen here
#       and passed off to the active mode.
#       The state holds on to references to the selection, the handles, the operation objects,
#       and mode objects
#       The state also defines constants for every parameter name, state parm, or mode id.
#       It is strongly recommended to use these constants, as if it is mispelled, a python error
#       will always let you know.
#       This state class also managed setting up and updating the HUD based on the active mode,
#       prim type, order, etc.


# Definitions for backward compatibility.
# Users may have overridden parts of the state. To hopefully
# keep them working, define shortcuts for some classes and
# constants to mimic how they used to be defined.
ReferenceCurve = referencegeo.ReferenceCurve

CurveHandleBase = baseoperation.BaseOperation
BaseSelectPointOperation = baseoperation.BaseSelectPointOperation
BaseSubTool = baseoperation.BaseSubTool

ReverseOperation = simpleselectionops.ReverseOperation
PasteOperation = simpleselectionops.PasteOperation
PointDeleteOperation = simpleselectionops.PointDeleteOperation
SegmentDeleteOperation = simpleselectionops.SegmentDeleteOperation
PointJoinBaseOperation = simpleselectionops.PointJoinBaseOperation
PointFuseOperation = simpleselectionops.PointFuseOperation
PointJoinOperation = simpleselectionops.PointJoinOperation
CurveCloseOperation = simpleselectionops.CurveCloseOperation
FuseBranchOperation = simpleselectionops.FuseBranchOperation
CutBranchOperation = simpleselectionops.CutBranchOperation
PointTypeBaseOperation = simpleselectionops.PointTypeBaseOperation
PointExpandOperation = simpleselectionops.PointExpandOperation
PointMakeManualOperation = simpleselectionops.PointMakeManualOperation
PointTypeBunchedOperation = simpleselectionops.PointTypeBunchedOperation
SegmentMakeStraightOperation = simpleselectionops.SegmentMakeStraightOperation
PointCutOperation = simpleselectionops.PointCutOperation
FlattenOperation = simpleselectionops.FlattenOperation
EvenlySpaceOperation = simpleselectionops.EvenlySpaceOperation
SpaceOnCircleOperation = simpleselectionops.SpaceOnCircleOperation
RelaxSelectionOperation = simpleselectionops.RelaxSelectionOperation
StraightenSelectionOperation = simpleselectionops.StraightenSelectionOperation
ConvertSelectionOperation = simpleselectionops.ConvertSelectionOperation

PointInsertOperation = editops.PointInsertOperation
BezierPullOperation = editops.BezierPullOperation
BaseMoveOperation = editops.BaseMoveOperation
CenterPointsMoveOperation = editops.CenterPointsMoveOperation
PointMoveOperation = editops.PointMoveOperation
EditTool = editops.EditTool

RoundCornerBaseOperation = roundcornerops.RoundCornerBaseOperation
RoundCornerSplitOperation = roundcornerops.RoundCornerSplitOperation
RoundCornerFuseOperation = roundcornerops.RoundCornerFuseOperation
RoundCornerChangeRadiusOperation = roundcornerops.RoundCornerChangeRadiusOperation
RoundCornerBakeOperation = roundcornerops.RoundCornerBakeOperation

DrawModeMoveOperation = drawops.DrawModeMoveOperation
PointAddOperation = drawops.PointAddOperation
DrawTool = drawops.DrawTool

OrientChangeFramesOperation = orientops.OrientChangeFramesOperation
OrientTool = orientops.OrientTool

DrawableInteractionManager = drawablemanager.DrawableInteractionManager


def getAutoEnableCPlanePref(cat_name:str) -> bool:
    the_pref = constants.AUTOENABLECPLANE_CATEGORY_TO_PREF.get(cat_name, None)
    if not the_pref:
        return False

    return int(hou.getPreference(the_pref)) == 1

def getPickingModeMenu(category_name:str) -> list[tuple[str,str]]:
    return constants.PICKING_MODE_MENU

def getDefaultPickingMode(category_name:str) -> str:
    return constants.PICKING_MODE_AXIS_ALIGN

class CurveState(object):

    """
    Encapsulates the high level logic for the viewer state, including
    keeping track of the operations, the modes, and delegating events
    to the appropriate mode.
    """

    # constant short cuts for backward compatibility.
    HK_ACCEPT_SYMBOL =      constants.HK_ACCEPT_SYMBOL
    HK_COPY_SYMBOL =        constants.HK_COPY_SYMBOL
    HK_PASTE_SYMBOL =       constants.HK_PASTE_SYMBOL

    MENU_FINISH_CODE =      constants.MENU_FINISH_CODE

    MENU_SELECTALL_CODE =   constants.MENU_SELECTALL_CODE
    MENU_DESELECTALL_CODE = constants.MENU_DESELECTALL_CODE
    MENU_SELUP_CODE =       constants.MENU_SELUP_CODE
    MENU_SELDOWN_CODE =     constants.MENU_SELDOWN_CODE
    HK_SELUPADD_CODE =      constants.HK_SELUPADD_CODE
    HK_SELUPREM_CODE =      constants.HK_SELUPREM_CODE
    HK_SELDOWNADD_CODE =    constants.HK_SELDOWNADD_CODE
    HK_SELDOWNREM_CODE =    constants.HK_SELDOWNREM_CODE
    MENU_SELCONNECTED_CODE = constants.MENU_SELCONNECTED_CODE
    MENU_SELCONVERT_CODE =  constants.MENU_SELCONVERT_CODE

    MENU_EDITMODE_CODE =    constants.MENU_EDITMODE_CODE
    MENU_DRAWMODE_CODE =    constants.MENU_DRAWMODE_CODE
    MENU_AUTODRAWMODE_CODE = constants.MENU_AUTODRAWMODE_CODE
    MENU_ORIENTMODE_CODE =  constants.MENU_ORIENTMODE_CODE

    MENU_DELETE_CODE =      constants.MENU_DELETE_CODE
    MENU_CUT_CODE =         constants.MENU_CUT_CODE
    MENU_FUSE_CODE =        constants.MENU_FUSE_CODE
    MENU_JOIN_CODE =        constants.MENU_JOIN_CODE

    MENU_BRANCH_CUT_CODE =  constants.MENU_BRANCH_CUT_CODE
    MENU_BRANCH_FUSE_CODE = constants.MENU_BRANCH_FUSE_CODE

    MENU_CONTRACT_CODE =    constants.MENU_CONTRACT_CODE
    MENU_EXPAND_CODE =      constants.MENU_EXPAND_CODE

    MENU_CORNER_CODE =      constants.MENU_CORNER_CODE
    MENU_SMOOTH_CODE =      constants.MENU_SMOOTH_CODE
    MENU_BALANCED_CODE =    constants.MENU_BALANCED_CODE

    MENU_SEGSTRAIGHTEN_CODE = constants.MENU_SEGSTRAIGHTEN_CODE
    MENU_SEGDELETE_CODE =   constants.MENU_SEGDELETE_CODE
    MENU_CLOSECURVE_CODE =  constants.MENU_CLOSECURVE_CODE
    MENU_REVERSECURVE_CODE = constants.MENU_REVERSECURVE_CODE

    MENU_CENTERPIVOT_CODE = constants.MENU_CENTERPIVOT_CODE
    MENU_FLATTEN_CODE =     constants.MENU_FLATTEN_CODE
    MENU_SPACECIRCLE_CODE = constants.MENU_SPACECIRCLE_CODE
    MENU_EVENLYSPACE_CODE = constants.MENU_EVENLYSPACE_CODE
    MENU_RELAX_CODE =       constants.MENU_RELAX_CODE
    MENU_STRAIGHTEN_CODE =  constants.MENU_STRAIGHTEN_CODE
    MENU_CONSTRAIN_STRAIGHTEN_CODE = constants.MENU_CONSTRAIN_STRAIGHTEN_CODE
    MENU_DRAWSNAP_CODE =    constants.MENU_DRAWSNAP_CODE

    BEZIER_ONLY_MENU_ITEMS = constants.BEZIER_ONLY_MENU_ITEMS
    EDIT_ONLY_MENU_ITEMS =  constants.EDIT_ONLY_MENU_ITEMS
    DRAW_ONLY_MENU_ITEMS =  constants.DRAW_ONLY_MENU_ITEMS
    ORIENT_ONLY_MENU_ITEMS = constants.ORIENT_ONLY_MENU_ITEMS

    # Note tied to a menu action
    HK_TOGGLEXFORM_CODE =   constants.HK_TOGGLEXFORM_CODE
    HK_TOGGLELABELS_CODE =  constants.HK_TOGGLELABELS_CODE
    HK_DRAWARC_CODE =       constants.HK_DRAWARC_CODE

    CONTEXT_MENU_NAME =     constants.CONTEXT_MENU_NAME
    PICKING_MODE_MENU =     constants.PICKING_MODE_MENU

    # Define constants for all handles, parms, modes, state parms.
    TRANSFORM_HANDLE =      constants.TRANSFORM_HANDLE
    MULTIPLE_TANGENT_HANDLES = constants.MULTIPLE_TANGENT_HANDLES
    ORIENT_HANDLE =         constants.ORIENT_HANDLE
    HUD_TRANSLATE_HANDLE =  constants.HUD_TRANSLATE_HANDLE

    MSG =                   constants.MSG

    GROUP_PARM =            constants.GROUP_PARM
    OUTPUTTYPE_PARM =       constants.OUTPUTTYPE_PARM
    ORDER_PARM =            constants.ORDER_PARM
    CONVERTCURVES_PARM =    constants.CONVERTCURVES_PARM
    SHOWBEZIEROP_PARM =     constants.SHOWBEZIEROP_PARM

    OPTYPE_PARM =           constants.OPTYPE_PARM
    PARMPOINTS_PARM =       constants.PARMPOINTS_PARM
    STASHGEO_PARM =         constants.STASHGEO_PARM
    SAVEDSTASHGEO_PARM =    constants.SAVEDSTASHGEO_PARM
    STASHID_PARM =          constants.STASHID_PARM
    NINPUTPRIMSCACHED_PARM = constants.NINPUTPRIMSCACHED_PARM
    ADDPTS_PARM =           constants.ADDPTS_PARM
    ACTIVEPRIM_PARM =       constants.ACTIVEPRIM_PARM
    ACTIVEPOINTS_PARM =     constants.ACTIVEPOINTS_PARM
    TRANSLATE_PARM =        constants.TRANSLATE_PARM
    ROTATE_PARM =           constants.ROTATE_PARM
    SCALE_PARM =            constants.SCALE_PARM
    FUSEBTN_PARM =          constants.FUSEBTN_PARM
    CUTBTN_PARM =           constants.CUTBTN_PARM
    DELETEBTN_PARM =        constants.DELETEBTN_PARM
    CONTRACTBTN_PARM =      constants.CONTRACTBTN_PARM
    EXPANDBTN_PARM =        constants.EXPANDBTN_PARM
    BALANCEBTN_PARM =       constants.BALANCEBTN_PARM
    CORNERBTN_PARM =        constants.CORNERBTN_PARM
    SMOOTHBTN_PARM =        constants.SMOOTHBTN_PARM
    AUTOBTN_PARM =          constants.AUTOBTN_PARM
    MANUALBTN_PARM =        constants.MANUALBTN_PARM
    CLOSEBTN_PARM =         constants.CLOSEBTN_PARM
    JOINBTN_PARM =          constants.JOINBTN_PARM
    DELETESEGBTN_PARM =     constants.DELETESEGBTN_PARM
    STRAIGHTSEGBTN_PARM =   constants.STRAIGHTSEGBTN_PARM
    REVERSEBTN_PARM =       constants.REVERSEBTN_PARM
    CUTBRANCHBTN_PARM =     constants.CUTBRANCHBTN_PARM
    FUSEBRANCHBTN_PARM =    constants.FUSEBRANCHBTN_PARM

    SNAPCLOSE_PARM =        constants.SNAPCLOSE_PARM

    MAINTAINPOINT_PARM =    constants.MAINTAINPOINT_PARM
    APPROXENDTANGENTS_PARM = constants.APPROXENDTANGENTS_PARM
    INTERPMETHOD_PARM =     constants.INTERPMETHOD_PARM
    INTERPMETHOD_SMOOTHCURVATURE = constants.INTERPMETHOD_SMOOTHCURVATURE
    SOFTTRANSFORM_PARM =    constants.SOFTTRANSFORM_PARM
    SOFTTRANSFORMRAD_PARM = constants.SOFTTRANSFORMRAD_PARM

    PIVOTROTATE_PARM =      constants.PIVOTROTATE_PARM
    PIVOTTRANSLATE_PARM =   constants.PIVOTTRANSLATE_PARM
    PIVOTFIXED_PARM =       constants.PIVOTFIXED_PARM

    ROUNDCORNERRADIUS_PARM = constants.ROUNDCORNERRADIUS_PARM

    SHOWROUNDEDCORNERWIDGET_PARM =  constants.SHOWROUNDEDCORNERWIDGET_PARM
    SHOWROUNDEDCORNERLABEL_PARM =   constants.SHOWROUNDEDCORNERLABEL_PARM
    BAKEROUNDCORNERBTN_PARM =       constants.BAKEROUNDCORNERBTN_PARM
    CREATEROUNDCORNERBTN_PARM =     constants.CREATEROUNDCORNERBTN_PARM
    REMOVEROUNDCORNERBTN_PARM =     constants.REMOVEROUNDCORNERBTN_PARM
    VIEWROUNDCORNERS_PARM =         constants.VIEWROUNDCORNERS_PARM

    MODE_PARM =             constants.MODE_PARM
    RESET_BTN_PARM =        constants.RESET_BTN_PARM

    HANDLEPTS_PARM =        constants.HANDLEPTS_PARM
    HANDLEP0POS_PARM =      constants.HANDLEP0POS_PARM
    HANDLEP1POS_PARM =      constants.HANDLEP1POS_PARM
    HANDLEP2POS_PARM =      constants.HANDLEP2POS_PARM

    CORNERPTS_PARM =        constants.CORNERPTS_PARM
    SMOOTHPTS_PARM =        constants.SMOOTHPTS_PARM
    ROUNDCORNERPTS_PARM =   constants.ROUNDCORNERPTS_PARM
    AUTOPTS_PARM =          constants.AUTOPTS_PARM

    OUTPUTCORNERGROUP_PARM = constants.OUTPUTCORNERGROUP_PARM
    OUTPUTSMOOTHGROUP_PARM = constants.OUTPUTSMOOTHGROUP_PARM
    OUTPUTAUTOGROUP_PARM =  constants.OUTPUTAUTOGROUP_PARM
    CORNERPTSGROUP_PARM =   constants.CORNERPTSGROUP_PARM
    SMOOTHPTSGROUP_PARM =   constants.SMOOTHPTSGROUP_PARM
    AUTOPTSGROUP_PARM =     constants.AUTOPTSGROUP_PARM

    PLANEORIG_PARM =        constants.PLANEORIG_PARM
    PLANENML_PARM =         constants.PLANENML_PARM
    CONSTRAINSTRAIGHTEN_PARM = constants.CONSTRAINSTRAIGHTEN_PARM

    OUTPUTORIENT_PARM =     constants.OUTPUTORIENT_PARM
    OUTPUTXAXIS_PARM =      constants.OUTPUTXAXIS_PARM
    OUTPUTYAXIS_PARM =      constants.OUTPUTYAXIS_PARM
    OUTPUTZAXIS_PARM =      constants.OUTPUTZAXIS_PARM
    ORIENTATTRIB_PARM =     constants.ORIENTATTRIB_PARM
    XAXISATTRIB_PARM =      constants.XAXISATTRIB_PARM
    YAXISATTRIB_PARM =      constants.YAXISATTRIB_PARM
    ZAXISATTRIB_PARM =      constants.ZAXISATTRIB_PARM
    NUMTARGETPOINTS_PARM =  constants.NUMTARGETPOINTS_PARM
    TARGETPTNUM_PARM =      constants.TARGETPTNUM_PARM
    UPVECTOR_PARM =         constants.UPVECTOR_PARM
    TANGENTVECTOR_PARM =    constants.TANGENTVECTOR_PARM
    ENABLETARGETPT_PARM =   constants.ENABLETARGETPT_PARM
    ALIGNTANGENT_PARM =     constants.ALIGNTANGENT_PARM
    TANGENTTYPE_PARM =      constants.TANGENTTYPE_PARM

    #OPTYPES
    OPTYPE_TRANSFORM =      constants.OPTYPE_TRANSFORM
    OPTYPE_APPENDPT =       constants.OPTYPE_APPENDPT
    OPTYPE_PREPENDPT =      constants.OPTYPE_PREPENDPT
    OPTYPE_DELETE =         constants.OPTYPE_DELETE
    OPTYPE_INSERT =         constants.OPTYPE_INSERT
    OPTYPE_FUSE =           constants.OPTYPE_FUSE
    OPTYPE_CUT =            constants.OPTYPE_CUT
    OPTYPE_EXPAND =         constants.OPTYPE_EXPAND
    OPTYPE_CONTRACT =       constants.OPTYPE_CONTRACT
    OPTYPE_BALANCE =        constants.OPTYPE_BALANCE
    OPTYPE_PULL =           constants.OPTYPE_PULL
    OPTYPE_CLOSE =          constants.OPTYPE_CLOSE
    OPTYPE_JOIN =           constants.OPTYPE_JOIN
    OPTYPE_CORNER =         constants.OPTYPE_CORNER
    OPTYPE_SMOOTH =         constants.OPTYPE_SMOOTH
    OPTYPE_AUTO =           constants.OPTYPE_AUTO
    OPTYPE_MANUAL =         constants.OPTYPE_MANUAL
    OPTYPE_DELETESEG =      constants.OPTYPE_DELETESEG
    OPTYPE_CONTRACTSEG =    constants.OPTYPE_CONTRACTSEG
    OPTYPE_REVERSE =        constants.OPTYPE_REVERSE
    OPTYPE_PASTE =          constants.OPTYPE_PASTE
    OPTYPE_BAKEROUNDCORNERS =   constants.OPTYPE_BAKEROUNDCORNERS
    OPTYPE_BEZIERHANDLEMOVE =   constants.OPTYPE_BEZIERHANDLEMOVE

    OPTYPE_ROUNDCORNERSSPLIT =  constants.OPTYPE_ROUNDCORNERSSPLIT
    OPTYPE_ROUNDCORNERSRADIUS = constants.OPTYPE_ROUNDCORNERSRADIUS
    OPTYPE_ROUNDCORNERSFUSE =   constants.OPTYPE_ROUNDCORNERSFUSE

    OPTYPE_EVENLYSPACE =    constants.OPTYPE_EVENLYSPACE
    OPTYPE_STRAIGHTENSEL =  constants.OPTYPE_STRAIGHTENSEL
    OPTYPE_SPACEONCIRLCE =  constants.OPTYPE_SPACEONCIRCLE
    OPTYPE_FLATTEN =        constants.OPTYPE_FLATTEN
    OPTYPE_RELAXSEL =       constants.OPTYPE_RELAXSEL

    OPTYPE_FUSEBRANCH =     constants.OPTYPE_FUSEBRANCH
    OPTYPE_CUTBRANCH =      constants.OPTYPE_CUTBRANCH

    OPTYPE_CONVERT =        constants.OPTYPE_CONVERT
    OPTYPE_NOP =            constants.OPTYPE_NOP

    OUTPUTTYPE_BEZIER =     constants.OUTPUTTYPE_BEZIER
    OUTPUTTYPE_POLYGON =    constants.OUTPUTTYPE_POLYGON
    OUTPUTTYPE_NURBS =      constants.OUTPUTTYPE_NURBS

    # Config for how operations work
    # Some of this is included for backwards compatibility
    # First value is the default, second is the value to apply
    # The difference is that if the attribute did not exist in the
    # past, then the default will be given, to all previous operations
    CONFIG_LIST =           constants.CONFIG_LIST
    CONFIG_DEFAULTS =       constants.CONFIG_DEFAULTS
    CONFIG_VALUES =         constants.CONFIG_VALUES

    OPERATION_PARMS =           constants.OPERATION_PARMS
    VECTOR_OPERATION_PARMS =    constants.VECTOR_OPERATION_PARMS
    TRANSFORM_PARM_MAPPING =    constants.TRANSFORM_PARM_MAPPING
    PIVOT_PARM_MAPPING =        constants.PIVOT_PARM_MAPPING
    XFORM_HANDLE_BASE_MAPPING = constants.XFORM_HANDLE_BASE_MAPPING
    XFORM_HANDLE_MAPPING =      constants.XFORM_HANDLE_MAPPING

    PICKINGMODE_STATEPARM =         constants.PICKINGMODE_STATEPARM
    ENABLEORIENTGUIDE_STATEPARM =   constants.ENABLEORIENTGUIDE_STATEPARM
    ORIENTGUIDEDENSITY_STATEPARM =  constants.ORIENTGUIDEDENSITY_STATEPARM
    ORIENTGUIDESCALE_STATEPARM =    constants.ORIENTGUIDESCALE_STATEPARM
    SHOWPREVIEWCURVE_STATEPARM =    constants.SHOWPREVIEWCURVE_STATEPARM
    ALLOWSEGMENTSELECT_STATEPARM =  constants.ALLOWSEGMENTSELECT_STATEPARM
    ORIENTANGLESTEP_STATEPARM =     constants.ORIENTANGLESTEP_STATEPARM
    SHOWALLTANGENTS_STATEPARM =     constants.SHOWALLTANGENTS_STATEPARM
    HOVERLABELS_STATEPARM =         constants.HOVERLABELS_STATEPARM
    RELATIVEANGLESNAP_STATEPARM =   constants.RELATIVEANGLESNAP_STATEPARM
    POINTSIZE_STATEPARM =           constants.POINTSIZE_STATEPARM

    Mode =                  constants.Mode

    # Set up the HUD
    MODE_NAMES =            constants.MODE_NAMES
    PRIMTYPE_NAMES =        constants.PRIMTYPE_NAMES

    def __init__(self, state_name, scene_viewer, category=None):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self.node = None
        self.base_node = None

        if category is None:
            category = hou.sopNodeTypeCategory()

        HK_CTXT = su.hotkeyContextForState(state_name, category)

        def hkSymbol(code):
            return HK_CTXT + "." + code

        # Only needed temporarily for the HUD
        hk_finish = constants.HK_ACCEPT_SYMBOL
        hk_edit_mode = hkSymbol(constants.MENU_EDITMODE_CODE)
        hk_draw_mode = hkSymbol(constants.MENU_DRAWMODE_CODE)
        hk_auto_draw_mode = hkSymbol(constants.MENU_AUTODRAWMODE_CODE)
        hk_orient_mode = hkSymbol(constants.MENU_ORIENTMODE_CODE)
        hk_corner = hkSymbol(constants.MENU_CORNER_CODE)
        hk_smooth = hkSymbol(constants.MENU_SMOOTH_CODE)
        hk_balanced = hkSymbol(constants.MENU_BALANCED_CODE)

        # Needed for the HUD and for onKeyEvent/onKeyTransitEvent
        self.hk_toggle_xform = hkSymbol(constants.HK_TOGGLEXFORM_CODE)
        self.hk_toggle_labels = hkSymbol(constants.HK_TOGGLELABELS_CODE)
        self.hk_draw_arc = hkSymbol(constants.HK_DRAWARC_CODE)

        self.hk_stepupadd = hkSymbol(constants.HK_SELUPADD_CODE)
        self.hk_stepuprem = hkSymbol(constants.HK_SELUPREM_CODE)
        self.hk_stepdownadd = hkSymbol(constants.HK_SELDOWNADD_CODE)
        self.hk_stepdownrem = hkSymbol(constants.HK_SELDOWNREM_CODE)

        HUD_TEMPLATE = {
            "title": "Curve", "desc": "tool",
            "icon": "SOP_curve",
            "rows": [
                {
                    "id": "mode", "label": "Mode",
                    "key": "{}/{}/{}/{}".format(su.hudHotkeyRef(hk_edit_mode),
                                                su.hudHotkeyRef(hk_draw_mode),
                                                su.hudHotkeyRef(hk_auto_draw_mode),
                                                su.hudHotkeyRef(hk_orient_mode))
                },
                {"id": "mode_g", "type": "choicegraph", "count": 4},
                {"id": "primtype", "label": "Curve Type"},
                {
                    # This group lets us switch between different "pages" of
                    # hints for the different modes
                    "type": "group", "id": "mode_page",
                    "rows": [
                        {
                            "type": "group", "id": "edit",
                            "rows": [
                                {"label": "Drag entire curve", "key": "Shift + LMB"},
                                {"label": "Drag connected points", "key": "Shift + MMB"},
                                {"label": "Insert a point (on curve)", "key": "Ctrl + LMB"},
                                {"label": "Change soft transform radius", "key": "Scroll"},
                            ]
                        },
                        {
                            "type": "group", "id": "draw",
                            "rows": [
                                {"label": "Insert a point (on curve)", "key": "Ctrl + LMB"},
                                {"label": "Finish curve", "key": "{}/{}".format(su.hudHotkeyRef(hk_finish),"MMB")},
                                {"label" : "Drag point (with no curve active)", "key": "MMB"},
                                {"label": "Align with previous point (hold)", "key": "Shift"},
                                { "type" : "group", "id": "bezierdraw",
                                  "rows" : [
                                    {"label": "Draw arc segment (hold)", "key": su.hudHotkeyRef(self.hk_draw_arc)},
                                    {"label": "Draw straight line segment (hold)", "key": "Shift + Ctrl"}
                                ]}
                            ]
                        },
                        {
                            "type": "group", "id": "auto",
                            "rows": [
                                {"label": "Insert a point (on curve)", "key": "Ctrl + LMB"},
                                {"label": "Finish curve", "key": "{}/{}".format(su.hudHotkeyRef(hk_finish),"MMB")},
                                {"label" : "Drag point (with no curve active)", "key": "MMB"},
                                {"label": "Click where curve should go"},
                                {"label": "Use more points in curvy areas"},
                                {"label": "Finish curve", "key": su.hudHotkeyRef(hk_finish)},
                            ]
                        },
                        {
                            "type": "group", "id": "orient",
                            "rows": [
                                {"label": "Create New Target Orient Point", "key": "Shift + LMB"},
                                {"label": "Remove Target Orient Point", "key": "Ctrl + LMB"},
                                {"label": "Toggle Target Orient Point", "key": "MMB"},
                                {"label": "Show Full Rotation Handle", "key": "LMB"},
                                {"label": "Snap Ring Handles to Fixed Angles", "key": "Shift"},
                                {
                                    "type": "group", "id": "orientfree",
                                    "rows": [
                                        {"label": "Realign Target Point to Tangent", "key": "Ctrl + Shift + LMB"},
                                    ]
                                }
                            ]
                        },
                    ]
                },
                {
                    "type" : "group", "id": "round_corners",
                    "rows": [
                        {"label" : "Change radius widgets relatively", "key": "Ctrl + LMB"},
                        {"label" : "Change round corner radius", "key": "Shift + Scroll"},
                    ]
                },
                {
                    # This group lets us hide this section for geometry types that
                    # don't have tangents
                    "type": "group", "id": "tangents",
                    "rows": [
                        {"type": "divider", "label": "Tangents"},
                        {"label": "Make corner / smooth / balanced", "key": "{}/{}/{}".format(
                            su.hudHotkeyRef(hk_corner),
                            su.hudHotkeyRef(hk_smooth),
                            su.hudHotkeyRef(hk_balanced)
                        )},
                        {"label": "Re-pull tangents (on point)", "key": "Ctrl + LMB"},
                        {"label": "Break tangent on drag", "key": "Ctrl"},
                        {"label": "Lock tangent direction (hold)", "key": "Shift + Ctrl"},
                        {"label": "Snap to 45 degree angles (hold)", "key": "Shift"},
                    ]
                },
                {"type": "divider", "label": "Common"},
                {"label": "Show Radial Menu", "key": su.hudHotkeyRef("h.pane.gview.custom_radial_menu")},
                {"label": "Toggle Transform Handle", "key": su.hudHotkeyRef(self.hk_toggle_xform)},
                {"label": "Toggle Hover Labels", "key": su.hudHotkeyRef(self.hk_toggle_labels)},
                {"label": "Additional State Parameters", "key": su.hudHotkeyRef("h.pane.gview.operation_parameters")},
            ]
        }

        self.scene_viewer.hudInfo(template=HUD_TEMPLATE)

        if not self._checkValidSceneViewer():
            return

        # Add all of the operations here
        self.available_operations = []

        self.point_move_op = PointMoveOperation("point_move", self.scene_viewer, self)
        self.point_move_op.setUndoLabel("Move Curve Points")
        self.available_operations.append(self.point_move_op)

        # Used for moving points in draw mode
        self.point_drawmode_move_op = DrawModeMoveOperation(
            "drawmode_point_move_op", self.scene_viewer, self)
        self.point_drawmode_move_op.setUndoLabel("Move Curve Points")
        self.available_operations.append(self.point_drawmode_move_op)

        # Used for requesting point moves non-interactively
        self.point_passive_move_op = BaseMoveOperation(
            "passive_point_move_op", self.scene_viewer, self)
        self.point_passive_move_op.setUndoLabel("Move Curve Points")
        self.available_operations.append(self.point_passive_move_op)

        self.point_add_op = PointAddOperation(
                "point_add", self.scene_viewer, self)
        self.point_add_op.setUndoLabel("Add Point to Curve")
        self.available_operations.append(self.point_add_op)

        self.point_delete_op = PointDeleteOperation(
                "point_delete", self.scene_viewer, self)
        self.point_delete_op.setUndoLabel("Delete Points")
        self.point_delete_op.setButton(constants.DELETEBTN_PARM)
        self.available_operations.append(self.point_delete_op)

        self.point_insert_op = PointInsertOperation(
                "point_insert", self.scene_viewer, self)
        self.point_insert_op.setUndoLabel("Insert Point")
        self.available_operations.append(self.point_insert_op)

        self.point_fuse_op = PointFuseOperation(
                "point_join", self.scene_viewer, self)
        self.point_fuse_op.setUndoLabel("Join Points")
        self.point_fuse_op.setButton(constants.FUSEBTN_PARM)
        self.available_operations.append(self.point_fuse_op)

        self.segment_join_op = PointJoinOperation(
                "segment_join", self.scene_viewer, self)
        self.segment_join_op.setUndoLabel("Join Endpoints with Segment")
        self.segment_join_op.setButton(constants.JOINBTN_PARM)
        self.available_operations.append(self.segment_join_op)

        self.curve_close_op = CurveCloseOperation(
                "curve_close", self.scene_viewer, self)
        self.curve_close_op.setUndoLabel("Close Curves")
        self.curve_close_op.setButton(constants.CLOSEBTN_PARM)
        self.available_operations.append(self.curve_close_op)

        self.point_cut_op = PointCutOperation(
                "point_cut", self.scene_viewer, self)
        self.point_cut_op.setUndoLabel("Split Curve at Points")
        self.point_cut_op.setButton(constants.CUTBTN_PARM)
        self.available_operations.append(self.point_cut_op)

        self.point_expand_op = PointExpandOperation(
                "point_expand", self.scene_viewer, self,
                op_idx=constants.OPTYPE_EXPAND,
                to_type=PointTypeBaseOperation.TO_TYPE_BALANCED)
        self.point_expand_op.setUndoLabel("Expand Point Tangents")
        self.point_expand_op.setButton(constants.EXPANDBTN_PARM)
        self.available_operations.append(self.point_expand_op)

        self.point_contract_op = PointTypeBunchedOperation(
                "point_retract", self.scene_viewer, self,
                op_idx=constants.OPTYPE_CONTRACT,
                to_type=PointTypeBaseOperation.TO_TYPE_BROKEN,
                do_expand=False)
        self.point_contract_op.setUndoLabel("Retract Selected Anchors")
        self.point_contract_op.setButton(constants.CONTRACTBTN_PARM)
        self.available_operations.append(self.point_contract_op)

        self.segment_makestraight_op = SegmentMakeStraightOperation(
                "segment_make_straight", self.scene_viewer, self)
        self.segment_makestraight_op.setUndoLabel("Make Selected Segments Straight")
        self.segment_makestraight_op.setButton(constants.STRAIGHTSEGBTN_PARM)
        self.available_operations.append(self.segment_makestraight_op)

        self.point_makecorner_op = PointTypeBunchedOperation(
                "point_make_corner", self.scene_viewer, self,
                op_idx=constants.OPTYPE_CORNER,
                to_type=PointTypeBaseOperation.TO_TYPE_BROKEN,
                do_expand=False)
        self.point_makecorner_op.setUndoLabel("Make Selected Points Corner")
        self.point_makecorner_op.setButton(constants.CORNERBTN_PARM)
        self.available_operations.append(self.point_makecorner_op)

        self.point_makesmooth_op = PointTypeBunchedOperation(
                "point_make_smooth", self.scene_viewer, self,
                op_idx=constants.OPTYPE_SMOOTH,
                to_type=PointTypeBaseOperation.TO_TYPE_SMOOTH)
        self.point_makesmooth_op.setUndoLabel("Make Selected Points Smooth")
        self.point_makesmooth_op.setButton(constants.SMOOTHBTN_PARM)
        self.available_operations.append(self.point_makesmooth_op)

        self.point_makebalanced_op = PointTypeBunchedOperation(
                "point_make_balanced", self.scene_viewer, self,
                op_idx=constants.OPTYPE_BALANCE,
                to_type=PointTypeBaseOperation.TO_TYPE_BALANCED)
        self.point_makebalanced_op.setUndoLabel("Make Selected Points Balanced")
        self.point_makebalanced_op.setButton(constants.BALANCEBTN_PARM)
        self.available_operations.append(self.point_makebalanced_op)

        self.point_makeauto_op = PointTypeBaseOperation(
                "point_make_auto", self.scene_viewer, self,
                op_idx=constants.OPTYPE_AUTO,
                to_type=PointTypeBaseOperation.TO_TYPE_AUTO,
                avoid_round_corners=True,
                pre_update_groups=True)
        self.point_makeauto_op.setUndoLabel("Make Selected Points Auto")
        self.point_makeauto_op.setButton(constants.AUTOBTN_PARM)
        self.available_operations.append(self.point_makeauto_op)

        self.point_makemanual_op = PointMakeManualOperation(
                "point_make_manual", self.scene_viewer, self,
                op_idx=constants.OPTYPE_MANUAL,
                to_type=PointTypeBaseOperation.TO_TYPE_BALANCED,
                pre_update_groups=True)
        self.point_makemanual_op.setUndoLabel("Make Selected Points Manual")
        self.point_makemanual_op.setButton(constants.MANUALBTN_PARM)
        self.available_operations.append(self.point_makemanual_op)

        self.bezier_pull_op = BezierPullOperation(
                "bezier_pull", self.scene_viewer, self)
        self.bezier_pull_op.setUndoLabel("Reshape Curve")
        self.available_operations.append(self.bezier_pull_op)

        self.segment_delete_op = SegmentDeleteOperation(
                "segment_delete", self.scene_viewer, self)
        self.segment_delete_op.setUndoLabel("Delete Curve Segment")
        self.segment_delete_op.setButton(constants.DELETESEGBTN_PARM)
        self.available_operations.append(self.segment_delete_op)

        self.curve_reverse_op = ReverseOperation(
                "curve_reverse", self.scene_viewer, self,
                op_idx=constants.OPTYPE_REVERSE)
        self.curve_reverse_op.setUndoLabel("Reverse Curve")
        self.curve_reverse_op.setButton(constants.REVERSEBTN_PARM)
        self.available_operations.append(self.curve_reverse_op)

        self.curve_paste_op = PasteOperation(
                "curve_paste", self.scene_viewer, self,
                op_idx=constants.OPTYPE_PASTE)
        self.curve_paste_op.setUndoLabel("Paste Curve")
        self.available_operations.append(self.curve_paste_op)

        self.point_bakeroundcorner_op = RoundCornerBakeOperation(
                "point_bakeroundcorners", self.scene_viewer, self)
        self.point_bakeroundcorner_op.setUndoLabel("Bake Selected Round Corners")
        self.point_bakeroundcorner_op.setButton(constants.BAKEROUNDCORNERBTN_PARM)
        self.available_operations.append(self.point_bakeroundcorner_op)

        self.point_roundcornersradius_op = RoundCornerChangeRadiusOperation(
                "point_roundcornersradius", self.scene_viewer, self)
        self.point_roundcornersradius_op.setUndoLabel("Round Corners Change Radius")
        self.available_operations.append(self.point_roundcornersradius_op)

        self.point_roundcornerssplit_op = RoundCornerSplitOperation(
                "point_roundcornerssplit", self.scene_viewer, self)
        self.point_roundcornerssplit_op.setUndoLabel("Create Rounded Corners")
        self.point_roundcornerssplit_op.setButton(constants.CREATEROUNDCORNERBTN_PARM)
        self.available_operations.append(self.point_roundcornerssplit_op)

        self.point_roundcornersfuse_op = RoundCornerFuseOperation(
                "point_roundcornersfuse", self.scene_viewer, self)
        self.point_roundcornersfuse_op.setUndoLabel("Remove Rounded Corners")
        self.point_roundcornersfuse_op.setButton(constants.REMOVEROUNDCORNERBTN_PARM)
        self.available_operations.append(self.point_roundcornersfuse_op)

        self.flatten_op = FlattenOperation(
                "flatten_op", self.scene_viewer, self)
        self.flatten_op.setUndoLabel("Flatten Selection")
        self.available_operations.append(self.flatten_op)

        self.evenly_space_op = EvenlySpaceOperation(
                "evenly_space_op", self.scene_viewer, self)
        self.evenly_space_op.setUndoLabel("Evenly Space Selection")
        self.available_operations.append(self.evenly_space_op)

        self.space_circle_op = SpaceOnCircleOperation(
                "space_circle_op", self.scene_viewer, self)
        self.space_circle_op.setUndoLabel("Space Points around Circle")
        self.available_operations.append(self.space_circle_op)

        self.relax_op = RelaxSelectionOperation(
                "relax_op", self.scene_viewer, self)
        self.relax_op.setUndoLabel("Relax Selected Points")
        self.available_operations.append(self.relax_op)

        self.straighten_sel_op = StraightenSelectionOperation(
                "straighten_sel_op", self.scene_viewer, self)
        self.straighten_sel_op.setUndoLabel("Straighten Selection")
        self.available_operations.append(self.straighten_sel_op)

        self.orient_change_frames_op = OrientChangeFramesOperation(
                "orient_change_frames", self.scene_viewer, self)
        self.orient_change_frames_op.setUndoLabel("Change Target Point Orient")
        self.available_operations.append(self.orient_change_frames_op)

        self.nop_op = CurveHandleBase(
                "nop", self.scene_viewer, self, op_idx=constants.OPTYPE_NOP)
        self.available_operations.append(self.nop_op)

        self.center_points_pivot_op = CenterPointsMoveOperation(
                "center_points_pivot", self.scene_viewer, self)
        self.center_points_pivot_op.setUndoLabel("Center Points on Pivot")
        self.available_operations.append(self.center_points_pivot_op)

        self.convert_prims_op = ConvertSelectionOperation(
                "convert_prims", self.scene_viewer, self)
        self.convert_prims_op.setUndoLabel("Convert Selected Primitives")
        self.available_operations.append(self.convert_prims_op)

        self.convert_poly_op = ConvertSelectionOperation(
                "convert_to_poly", self.scene_viewer, self,
                to_prim_type=constants.OUTPUTTYPE_POLYGON)
        self.convert_poly_op.setUndoLabel("Convert Selected Primitives to Polygons")
        self.available_operations.append(self.convert_poly_op)

        self.convert_bezier_op = ConvertSelectionOperation(
                "convert_to_bezier", self.scene_viewer, self,
                to_prim_type=constants.OUTPUTTYPE_BEZIER)
        self.convert_bezier_op.setUndoLabel("Convert Selected Primitives to Bezier")
        self.available_operations.append(self.convert_bezier_op)

        self.convert_nurbs_op = ConvertSelectionOperation(
                "convert_to_nurbs", self.scene_viewer, self,
                to_prim_type=constants.OUTPUTTYPE_NURBS)
        self.convert_nurbs_op.setUndoLabel("Convert Selected Primitives to NURBS")
        self.available_operations.append(self.convert_nurbs_op)

        self.fuse_branch_op = FuseBranchOperation(
                "fuse_branch", self.scene_viewer, self)
        self.fuse_branch_op.setUndoLabel("Fuse Points into Branch")
        self.fuse_branch_op.setButton(constants.FUSEBRANCHBTN_PARM)
        self.available_operations.append(self.fuse_branch_op)

        self.cut_branch_op = CutBranchOperation(
                "cut_branch", self.scene_viewer, self)
        self.cut_branch_op.setUndoLabel("Cut Branch")
        self.cut_branch_op.setButton(constants.CUTBRANCHBTN_PARM)
        self.available_operations.append(self.cut_branch_op)

        # Available Modes
        self.edit_tool = EditTool("edit_tool", self.scene_viewer, self)
        self.draw_tool = DrawTool("draw_tool", self.scene_viewer, self)
        self.auto_draw_tool = DrawTool("auto_draw_tool", self.scene_viewer, self)
        self.orient_tool = OrientTool("orient_tool", self.scene_viewer, self)

        self.sub_tools = [None,None,None,None]
        self.sub_tools[constants.Mode.EDIT] = self.edit_tool
        self.sub_tools[constants.Mode.DRAW] = self.draw_tool
        self.sub_tools[constants.Mode.AUTODRAW] = self.auto_draw_tool
        self.sub_tools[constants.Mode.ORIENT] = self.orient_tool
        self.active_sub_tool = 0

        # Stash geometry
        self._stash_geo = None
        self._input_geo_id = None

        self._current_selection = hou.Selection(hou.geometryType.Points)
        self._cached_selection_ptnums = None

        self.reference_curves = ReferenceCurve(self)
        self.orient_handle = hou.Handle(self.scene_viewer, constants.ORIENT_HANDLE)
        self.xform_handle = hou.Handle(self.scene_viewer, constants.TRANSFORM_HANDLE)
        self.hud_translate_handle = hou.Handle(self.scene_viewer, constants.HUD_TRANSLATE_HANDLE)

        self._draw_picker = cu.curve3DPicker(initial_mode=getDefaultPickingMode(category.name()))
        self._edit_picker = cu.curve3DPicker(initial_mode=getDefaultPickingMode(category.name()))

        self.color_options = ru.ColorOptions(self.scene_viewer)
        self._drawable_manager = DrawableInteractionManager("drawable_manager", self.scene_viewer, self)
        self._drawable_manager.getBezierControlPointHandle().setCallback(
            self.onPickAnchorPoint)
        self._drawable_manager.getBackboneCurveHandle().setCallback(
            self.onPickCurve)
        self._drawable_manager.getRoundedCornerHandle().setCallback(
            self.onPickRoundedCornerHandle)
        self._drawable_manager.getBezierHandlePoints().setCallback(
            self.onPickHandlePoint)
        self._drawable_manager.getBezierHigherOrderPointHandle().setCallback(
            self.onPickHandlePoint)
        self._drawable_manager.getBezierHandleLines().setCallback(
            self.onPickHandleLines)
        self._drawable_manager.getOrientCirclesLinesHandle().setCallback(
            self.onPickOrientCircleLines)
        self._drawable_manager.getOrientCirclesFacesHandle().setCallback(
            self.onPickOrientCircleFaces)

        self._auto_enable_cplane = False
        self._prev_radial_menu = "main"

    def onPickAnchorPoint(self, kwargs, handle_event):
        self.activeOperation().onPickAnchorPoint(kwargs, handle_event)

    def onPickCurve(self, kwargs, handle_event):
        self.activeOperation().onPickCurve(kwargs, handle_event)

    def onPickRoundedCornerHandle(self, kwargs, handle_event):
        self.activeOperation().onPickRoundedCornerHandle(kwargs, handle_event)

    def onPickHandlePoint(self, kwargs, handle_event):
        self.activeOperation().onPickHandlePoint(kwargs, handle_event)

    def onPickHandleLines(self, kwargs, handle_event):
        self.activeOperation().onPickHandleLines(kwargs, handle_event)

    def onPickOrientCircleLines(self,  kwargs, handle_event):
        self.activeOperation().onPickOrientCircleLinesHandle(kwargs, handle_event)

    def onPickOrientCircleFaces(self, kwargs, handle_event):
        self.activeOperation().onPickOrientCircleFacesHandle(kwargs, handle_event)

    def getStateParmPickingMode(self, kwargs: cu.KwargsDict) -> str:
        """
        Get the picking mode, i.e. one of Axis Aligned, View Plane, or Camera Depth.

        :kwargs: The kwargs dictionary.
        """

        val = 0
        state_parms = kwargs.get("state_parms")
        if state_parms is not None:
            val = state_parms[constants.PICKINGMODE_STATEPARM]["value"]

        node = kwargs["node"]
        cat_name = node.type().category().name()
        picking_mode_menu = getPickingModeMenu(cat_name)

        return picking_mode_menu[val][0]


    def updatePickers(self, kwargs: cu.KwargsDict):
        """
        Update the picking mode (set in the right click menu).

        :kwargs: The kwargs dictionary.
        """

        pick_mode = self.getStateParmPickingMode(kwargs)
        if pick_mode == constants.PICKING_MODE_VIEW_PLANE:
            self._draw_picker.setPickMode(cu.curve3DPicker.MODE_VIEWPLANE)
            self._edit_picker.setPickMode(cu.curve3DPicker.MODE_VIEWPLANE)
        elif pick_mode == constants.PICKING_MODE_CAMERA_DEPTH:
            self._draw_picker.setPickMode(cu.curve3DPicker.MODE_CAMERA_ALIGNED)
            self._edit_picker.setPickMode(cu.curve3DPicker.MODE_VIEWPLANE)
        elif pick_mode == constants.PICKING_MODE_IMAGE_PLANE:
            self._draw_picker.setPickMode(cu.curve3DPicker.MODE_IMAGEPLANE)
            self._draw_picker.setPickMode(cu.curve3DPicker.MODE_IMAGEPLANE)
        else:
            self._draw_picker.setPickMode(cu.curve3DPicker.MODE_AXIS_ALIGNED)
            self._edit_picker.setPickMode(cu.curve3DPicker.MODE_AXIS_ALIGNED)

    def setImagePlane(self, layer_xform:hou.Matrix4):
        self._draw_picker.setImagePlane(layer_xform)
        self._edit_picker.setImagePlane(layer_xform)

    def setImagePlaneFromNode(self, node):
        if not isinstance(node, hou.CopNode):
            return

        input_node = node.input(0)
        if input_node is None:
            return

        image_layer = input_node.layer()
        if image_layer is None:
            return

        layer_xform = image_layer.imageToWorldTransform()
        self.setImagePlane(layer_xform)


    def getDrawPicker(self):
        """ Return the position picker for the draw mode. """

        return self._draw_picker


    def getEditPicker(self):
        """ Return the position picker for the edit mode. """

        return self._edit_picker


    def drawSnappingEnabled(self, kwargs: cu.KwargsDict) -> bool:
        """
        Get whether snapping while drawing is enabled.
        This is the 'Auto-Snap to Curve Points' option in the
        context menu while in the draw modes.

        :kwargs: The kwargs dictionary.
        """

        return kwargs.get("enable_draw_snapping", True)


    def _getBaseNode(self) -> hou.SopNode | None:
        """ Get the internal curve node to reference. """

        if self.base_node is not None:
            return self.base_node

        if not self.node:
            return None

        self.base_node = cu.findCurveNode(self.node)
        return self.base_node

    def needsCurveDrawable(self) -> bool:
        """
        Whether we need an extra drawable to show the curve.

        This is needed when we are working with an HDA for which
        the base node does not equal the current node.
        """

        #return self._getBaseNode() != self.node
        return False


    def getNodeGeometry(self, output_index:int=0) -> hou.Geometry | None:
        """ Get the node geometry of the reference curve node. """

        base_node = self._getBaseNode()
        return base_node.geometry(output_index) if base_node else None


    def getNodeReferenceCurveGeometry(self) -> hou.Geometry | None:
        """ The geometry we use for reference curves. """

        return self.getNodeGeometry(constants.REF_CURVE_OUTPUT)


    def getNodeCacheGeometry(self) -> hou.Geometry | None:
        """ The geometry we put into the cache. """

        return self.getNodeGeometry(constants.CACHE_GEO_OUTPUT)


    def getNodeInputGeometry(self) -> hou.Geometry | None:
        """ Get the input geometry on the reference curve node. """

        base_node = self._getBaseNode()
        return base_node.inputGeometry(0) if base_node else None


    def getRefCurves(self) -> ReferenceCurve:
        """
        Get the reference curves object.

        This is used to help with some geometry analysis of the curves.
        """

        return self.reference_curves


    def updateRefCurveGeo(self) -> bool:
        """
        Force the reference curves to update the geometry.
        Return True if successfully updated.
        """

        return self.getRefCurves().checkNodeGeoChange(force_update=True)


    def getDrawableManager(self) -> DrawableInteractionManager:
        """ Get the drawable manager. """

        return self._drawable_manager

    def getDrawableSelector(self) -> drawablemanager.DrawableInteractionManager.DrawableSelector:
        """ Return the drawable selector. """

        return self.getDrawableManager().getDrawableSelector()

    def activePickModifier(self) -> hou.pickModifier:
        """ Return the active pick modifier that the drawable selector is using. """

        return self.getDrawableSelector().activePickModifier()


    def getXFormHandle(self) -> hou.Handle:
        """ Get the xform handle instance. """

        return self.xform_handle


    def getHUDTranslateHandle(self) -> hou.Handle:
        """ Get the HUD Translate handle instance. """

        return self.hud_translate_handle


    def getOrientHandle(self) -> hou.Handle:
        """ Get the orient handle instance. """

        return self.orient_handle


    def getOperationFromButton(self, button:str) -> BaseSelectPointOperation|None:
        """
        Get the operation object corresponding to this button name.

        :button: The name of the button.
        """

        for op in self.available_operations:
            if op.getButton() == button:
                return op

        return None

    def _checkValidSceneViewer(self) -> bool:
        # If we are not in the correct context also return false.
        if isinstance(self.scene_viewer, hou.CompositorViewer):
            return False

        return True

    def _checkValidNode(self, kwargs: cu.KwargsDict) -> bool:
        """
        Check whether the node is valid, if not
        try to update it.

        :kwargs: The kwargs dictionary.
        """

        if not self._checkValidSceneViewer():
            return False

        if ("node" not in kwargs or not self.node):
            self.node = kwargs.get("node", None)
            self._drawable_manager.updateNode()
            for m in self.sub_tools:
                m.updateNode()

            for h in self.available_operations:
                h.updateNode()

        return (self.node is not None)


    # --- Functions to handle selections ---

    def numSelected(self) -> int:
        """ The number of points selected. """

        return self._current_selection.numSelected()


    def getSelectionGeo(self) -> hou.Geometry:
        """ The geometry that selections happen on. """

        return self.getRefCurves().getGeometry()


    def getSelectionPoints(self) -> list[hou.Point]:
        """ The points in the selection. """

        geo = self.getSelectionGeo()
        if not geo:
            return []

        return self._current_selection.points(geo)


    def clearCachedPtnums(self):
        """
        Clear cached point numbers. This is an optimization because
        it is slow to call getSelectionPoints each time.
        """

        self._cached_selection_ptnums = None


    def getSelectionPtNums(self) -> list[int]:
        """ Get a list of point numbers in the selection. """

        # FIXME: If the reset operations button is pressed, this case does not
        # get triggered and the cached selection ptnums get out of sync -> causes bugs.
        if (
            self._cached_selection_ptnums is None
            or len(self._cached_selection_ptnums) != self.numSelected()
        ):
            self._cached_selection_ptnums = [p.number() for p in self.getSelectionPoints()]

        return self._cached_selection_ptnums


    def getSelectionString(self) -> str:
        """ Get the string representation of the selection. """

        geo = self.getSelectionGeo()
        if not geo:
            return ""

        s = self._current_selection.selectionString(geo)
        if s == "" and self.numSelected() > 0:
            s = "*"

        return s


    def addPointsSelection(self, ptnums:list[int], modifier:hou.pickModifier|None=None):
        """
        Add points to the selection.

        :ptnums: The list of point numbers to modify with.
        :modifier: How to merge the ptnums with the existing selection.
        """

        self._addPointsSelection_core(ptnums, modifier=modifier)


    def _addPointsSelection_core(self, ptnums:list[int], modifier:hou.pickModifier|None=None):
        """
        Add points to the selection.

        :ptnums: The list of point numbers to modify with.
        :modifier: How to merge the ptnums with the existing selection.
        """

        if modifier is None:
            modifier = hou.pickModifier.Add

        # Handling changing the selection.
        geo = self.getSelectionGeo()
        if not geo:
            return

        # NOTE: this needs to change to allow mixed primitive types

        new_pts = [geo.point(p) for p in ptnums]
        new_pts = [p for p in new_pts if p is not None]

        # TODO: consider removing this or at least having a flag to turn it off.
        # the reason is that it is a big performance hit.
        ref_curves = self.getRefCurves()
        if ref_curves.needsBezierCase(geo):
            # There might be a better way to achieve this using node verbs
            # such as group boolean, we can just group the incoming
            # points and then check against the anchorpts. That might be much
            # faster and wouldn't even need to do anything different for beziers.
            ref_geo = ref_curves.getGeometry()
            if ref_geo:
                group = ref_geo.findPointGroup(referencegeo.ANCHORPTS_GROUP)
                if group:
                    new_pts = [p for p in new_pts if group.contains(p)]

            # Do a pass on the points to select all rounded corner points
            add_round_corners = []
            for p in new_pts:
                if not ref_curves.isRoundCornerAnchor(p.number()):
                    continue

                prims = p.prims()
                if len(prims) == 0:
                    continue

                prim = prims[0]
                if not referencegeo.isPrimBezier(prim):
                    continue

                order = referencegeo.getPrimOrder(prim)
                adj_pt = None
                # NOTE: We have made the assumption that round corner points
                # are NOT branched, so getRelativeSegmentPoints on p should be ok.
                if ref_curves.isPointRoundCorner(p.number()):
                    adj_pts = cu.getRelativeSegmentPoints(p, [order-1])
                    adj_pt = adj_pts[0]
                else:
                    adj_pts = cu.getRelativeSegmentPoints(p, [-order+1])
                    adj_pt = adj_pts[0]

                if adj_pt is not None:
                    add_round_corners.append(adj_pt)

            new_pts += add_round_corners


        if len(new_pts) == 0 and modifier == hou.pickModifier.Replace:
            self.resetSelection()
            return

        pre_selection = self._current_selection.freeze()
        self._current_selection.combine(geo, hou.Selection(new_pts), modifier)
        post_selection = self._current_selection.freeze()
        undo = SelectionUndo(self, pre_selection, post_selection)
        hou.undos.add(undo, "Selection Changed")

        self.clearLocatedSelection()
        self.clearCachedPtnums()
        self.getRefCurves().updateAnchorGeometries()
        self._broadcastSelectionUpdate()


    def resetSelection(self):
        """ Reset the selection. """

        pre_selection = self._current_selection.freeze()
        self._current_selection.clear()
        post_selection = self._current_selection.freeze()
        undo = SelectionUndo(self, pre_selection, post_selection)
        hou.undos.add(undo, "Selection Reset")

        self.clearLocatedSelection()
        self.clearCachedPtnums()
        self.getRefCurves().updateAnchorGeometries()
        self._broadcastSelectionUpdate()

    def handleSelectionUndoOrRedo(self, new_sel:hou.Selection):
        """
        Handle changing the selection through undo or redo.

        :new_sel: The selection to change to.
        """

        self._current_selection = new_sel
        self.clearLocatedSelection()
        self.clearCachedPtnums()
        self.getRefCurves().updateAnchorGeometries()
        self._broadcastSelectionUpdate()


    def verifySelection(self):
        """
        Re-add the whole selection. This allows it to re-run any tests
        such as when adding selection points for beziers it will only add
        anchor points. This is important when swapping between primitive types.
        """

        self.addPointsSelection(self.getSelectionPtNums(),
                                 modifier=hou.pickModifier.Replace)
        self.getRefCurves().updateAnchorGeometries()


    def stepSelection(self, backward:bool=False, pick_modifier:hou.pickModifier|None=None):
        """
        Move the selection along the curves.

        :backward: Whether to step backward instead of forward.
        :pick_modifier: How to merge the new stepped selection with the current
            selection.
        """

        def getPointSingleStep(p, ref_curves, backward):
            if len(p.vertices()) == 0:
                return None

            vtx = p.vertices()[0]
            idx = vtx.number()
            prim = vtx.prim()
            is_bezier = referencegeo.isPrimBezier(prim)
            step_size = referencegeo.getPrimOrder(prim)-1 if is_bezier else 1
            nvtx = prim.numVertices()
            closed = cu.checkPrimClosed(prim)
            round_corner = False
            if is_bezier:
                round_corner = ref_curves.isRoundCornerAnchor(p.number())
                if round_corner and not ref_curves.isPointRoundCorner(p.number()):
                    return None

            if backward:
                next_idx = idx - step_size
            elif round_corner:
                next_idx = idx + step_size * 2
            else:
                next_idx = idx + step_size

            if closed:
                next_idx = (next_idx + nvtx) % nvtx
            elif next_idx < 0:
                next_idx = nvtx - 1
            elif next_idx >= nvtx:
                next_idx = 0

            return prim.vertices()[next_idx].point()

        if pick_modifier is None:
            pick_modifier = hou.pickModifier.Replace

        sel_pts = self.getSelectionPoints()
        new_sel_ptnums = []
        ref_curves = self.getRefCurves()
        for p in sel_pts:
            new_p = getPointSingleStep(p, ref_curves, backward)
            if new_p is not None:
                new_sel_ptnums.append(new_p.number())

        if pick_modifier == hou.pickModifier.Remove:
            # Keep the intersection of sel_pts and new_sel_ptnums
            old_ptnums = { p.number() for p in sel_pts }
            new_sel_ptnums = [ptnum for ptnum in new_sel_ptnums if ptnum in old_ptnums]
            pick_modifier = hou.pickModifier.Replace

        self.addPointsSelection(new_sel_ptnums, modifier=pick_modifier)


    def selectConnected(self, sel_str:str|None=None):
        """
        Select all points connected to already selected points.
        :sel_str: Optional string to use as the source before expanding.
            This is useful if we want to take some point, expand to all
            connected, then update the selection without first selecting
            one point and then expanding.
        """

        if sel_str is None:
            sel_str = self.getSelectionString()

        if not sel_str:
            return

        input_geo = self.getRefCurves().getGeometry()
        new_sel_ptnums = cu.findConnectedPoints(sel_str, input_geo)
        if new_sel_ptnums is None:
            return

        self.addPointsSelection(new_sel_ptnums,
                                 modifier=hou.pickModifier.Replace)

    def _broadcastSelectionUpdate(self):
        """ Tells the active operaction that the selection changed. """

        self.activeOperation().updateSelection()


    def clearLocatedSelection(self):
        """ Clear located selection indices. """

        self._drawable_manager.setLocateIndices({})


    def updateDrawableSelection(self, drawable_selection: constants.DrawableSelectionDict,
                                 modifier:hou.pickModifier|None=None):
        """
        Update with a new drawable selection. This will update the current
        selection based on the provided drawable_selection.

        :drawable_selection: The new drawable selection.
        :modifier: How to merge the new selection with the current selection.
        """

        if modifier is None:
            modifier = hou.pickModifier.Replace

        ptnums = []
        for k,v in drawable_selection.items():
            if "point" not in v:
                continue

            ptnums += self._drawable_manager.getPointNumbers(k, v["point"])

        self.addPointsSelection(ptnums, modifier=modifier)


    def onSelection(self, kwargs:cu.KwargsDict) -> bool:
        """
        State callback. Triggered after a selection occurs from
        either the geometry selector 's' key, or the drawable selector.

        :kwargs: The kwargs dictionary.
        """

        # Called after selecting
        if not self._checkValidNode(kwargs):
            return False

        # TODO: Remove this case.
        if "drawable_selection" in kwargs:
            selection = kwargs.get("drawable_selection", None)
            self.updateDrawableSelection(selection)
        else:
            # Must return True to accept the selection
            sel = kwargs["selection"]
            ptnums = []
            for s in sel.selections():
                ptnums += [p.number() for p in s.points(self.getSelectionGeo())]

            self.addPointsSelection(
                    ptnums, modifier=hou.pickModifier.Replace)
            return True

        return False


    # TODO: Remove this
    def onLocatedSelection(self, kwargs:cu.KwargsDict):
        """
        State callback. Called when a drawable is located
        in the drawable selector.

        :kwargs: The kwargs dictionary.
        """

        self._drawable_manager.setLocateIndices(kwargs["drawable_selection"])


    def activeOperation(self) -> BaseSubTool:
        """ Get the active mode handle. """

        return self.sub_tools[self.active_sub_tool]


    def _updateActiveMode(self, just_entered:bool=False):
        """
        Update the active mode.

        :just_entered: Whether this was called from onEnter.
            In this case, no tool is yet active so we can skip
            deactivating the active tool.
        """

        new_tool_id = self.node.parm(constants.MODE_PARM).evalAsInt()
        if new_tool_id == self.active_sub_tool and not just_entered:
            return

        if self.activeOperation() and not just_entered:
            self.activeOperation().onDeactivate()

        self.active_sub_tool = new_tool_id

        if self.activeOperation():
            self.activeOperation().onActivate()


    def show(self, val:bool):
        """
        Show the various parts of the tool.

        :val: Whether to show or hide.
        """

        # Hide the non active operations.
        for h in self.available_operations:
            if not self.activeOperation().isOperationActive(h):
                h.show(False)

        # Show the one active operation.
        self.activeOperation().show(val)
        self._drawable_manager.show(val)
        self._showActiveHUD(val)

    def _getStashInputCurves(self) -> bool:
        parm = self.node.parm(constants.UPDATEFROMINPUT_PARM)
        return parm and parm.evalAsInt() == 0

    def _getActiveStashParm(self) -> str:
        """
        Find the stash parm to stash geometry to.
        If there is no input geometry, we store to the saved stash,
        so that curves do not need to be rebuilt when reloading the scene.
        """

        input_geo = self.getNodeInputGeometry()
        use_cleared_stash = input_geo and not self._getStashInputCurves()
        return constants.STASHGEO_PARM if use_cleared_stash\
                                   else constants.SAVEDSTASHGEO_PARM


    def _getInactiveStashParm(self, active_parm:str|None=None) -> str:
        """ Get the opposite stash to _getActiveStashParm. """

        if active_parm is None:
            active_parm = self._getActiveStashParm()

        return constants.SAVEDSTASHGEO_PARM if active_parm == constants.STASHGEO_PARM\
                                        else constants.STASHGEO_PARM


    def _getInputGeoIdString(self) -> str:
        """ Get the id string telling us if the input geometry has changed. """

        input_geo = self.getNodeInputGeometry()
        input_id_str = (" ".join([str(id) for id in input_geo.vexAttribDataId()]))\
                       if input_geo\
                       else ""
        input_group_str = self.node.parm(constants.GROUP_PARM).evalAsString()
        # Encode both the vexattribdataid and the group string, so that
        # we can tell not to use the cache if either changes.
        return "{};{}".format(input_id_str, input_group_str)


    def _getInputGeoNPrims(self) -> int:
        """ Get the number of prims in the input geometry. """

        input_geo = self.getNodeInputGeometry()
        if not input_geo:
            return 0

        n_prims = -1
        input_group_str = self.node.parm(constants.GROUP_PARM).evalAsString()
        if input_group_str == "":
            n_prims = len(input_geo.iterPrims())
        else:
            # Compute the group here
            try:
                n_prims = len(input_geo.globPrims(input_group_str))
            except hou.OperationFailed:
                n_prims = 0

        return n_prims


    def updateStashGeo(self, geo:hou.Geometry):
        """ Update the active stash to geo, and clear the inactive stash. """

        # Update the stash geometry index
        # The internal geometry node that gets cached differentiates between
        # the preview and output for each operation
        # some operations need to cache the currently previewed -> idx = 1
        # some operations need to cache the output geo -> idx = 0

        if not geo:
            return

        self._stash_geo = geo if geo is not None else hou.Geometry()
        active_stash = self._getActiveStashParm()
        self.node.parm(active_stash).set(self._stash_geo)
        self.node.parm(self._getInactiveStashParm(active_stash)).set(hou.Geometry())
        self.node.parm(constants.STASHID_PARM).set(self._getInputGeoIdString())
        self.node.parm(constants.NINPUTPRIMSCACHED_PARM).set(self._getInputGeoNPrims())


    def clearStash(self):
        """ Clear the stashes. """

        self.node.parm(constants.STASHGEO_PARM).revertToDefaults()
        self.node.parm(constants.SAVEDSTASHGEO_PARM).revertToDefaults()
        self.node.parm(constants.STASHID_PARM).revertToDefaults()
        self.node.parm(constants.NINPUTPRIMSCACHED_PARM).revertToDefaults()


    def _updateNodeParmCB(self, event_type: hou.nodeEventType,
                          node: hou.SopNode, **kwargs : cu.KwargsDict):
        """
        Called when a node parameter is changed.

        :event_type: The event type.
        :node: The node the event happened on.
        :kwargs: The kwargs dictionary telling us what happened.
        """

        parm_tuple = kwargs.get("parm_tuple")
        if not parm_tuple:
            return

        self.activeOperation()\
            .reactNodeParmsUpdate(event_type, node, **kwargs)
        self._drawable_manager\
            .reactNodeParmsUpdate(event_type, node, **kwargs)

        parm_name = parm_tuple.name()
        if parm_name == constants.MODE_PARM:
            self._updateActiveMode()
        elif parm_name == constants.PARMPOINTS_PARM:
            geo = self.node.parm(constants.PARMPOINTS_PARM).eval()
            if geo is None:
                self.resetSelection()
        elif parm_name == constants.GROUP_PARM:
            self.clearStash()
        elif parm_name == constants.RESET_BTN_PARM:
            # If reset button is pressed, leave and re-enter
            # the current operation to reset any state.
            self.activeOperation().onDeactivate()
            self.activeOperation().onActivate()

        # Check to update the HUD
        update_hud_parms = (
            constants.MODE_PARM,
            constants.OUTPUTTYPE_PARM,
            constants.ORDER_PARM,
            constants.ALIGNTANGENT_PARM,
        )
        if parm_name in update_hud_parms:
            self._showActiveHUD(True)

    def checkAutoEnableCPlane(self, kwargs):
        """
        Check whether to automatically enable the construction plane
        when entering the state.
        """

        node = kwargs["node"]
        cat_name = node.type().category().name()
        if getAutoEnableCPlanePref(cat_name) and not self.scene_viewer.constructionPlane().isVisible():
            self._auto_enable_cplane = True
            self.scene_viewer.constructionPlane().setIsVisible(True)

    def checkAutoDisableCPlane(self):
        """
        Re-disable the construction plane if it was automatically enabled
        when entering the state.
        """

        if self._auto_enable_cplane:
            self.scene_viewer.constructionPlane().setIsVisible(False)

    def updateFromPrefs(self, kwargs):
        """ Update settings from preferences. """

        self.checkAutoEnableCPlane(kwargs)

    def onPrefChanged(self, pref_name:str):
        """ Called when one of our preferences changes. """

        self._drawable_manager.onPrefChanged(pref_name)

    def _onSceneViewerEvent(self, **kwargs):
        """ Called on scene viewer events. Used for pref changes. """

        event_type = kwargs["event_type"]
        if event_type == hou.sceneViewerEvent.PrefChanged:
            pref_reg = kwargs["pref_registry_name"]
            if pref_reg == constants.PREF_REGISTRY_NAME:
                self.onPrefChanged(kwargs["pref_name"])

    def _onHipFileEvent(self, event_type:hou.hipFileEventType):
        if event_type == hou.hipFileEventType.BeforeSave:
            self._revertRadialMenu()
        elif event_type == hou.hipFileEventType.AfterSave:
            self._setRadialMenu()

    def onUndoOrRedo(self):
        """ Called at the end of the undo or redo to update state properly. """

        self.clearCachedPtnums()
        self._broadcastSelectionUpdate()
        self.activeOperation().updatePreviewCurve()

        self.activeOperation().onUndoOrRedo()
        self._drawable_manager.onUndoOrRedo()


    def setPrompt(self, msg:str=None):
        """
        Set the prompt at the bottom of the viewport.

        :msg: The message to set for the prompt.
        """

        self.scene_viewer.clearPromptMessage()

        if msg is not None:
            self.scene_viewer.setPromptMessage(msg)


    def onEnter(self, kwargs:cu.KwargsDict):
        """
        Called when state is entered.

        :kwargs: The kwargs dictionary.
        """

        if not self._checkValidSceneViewer():
            return

        self.node = kwargs["node"]
        self.base_node = None

        if self.node.type().category().name() == "Cop":
            self.setImagePlaneFromNode(self.node)

        stateparms.loadStateParms(kwargs)

        self.updateFromPrefs(kwargs)

        # NOTE: Disable MMB on HUD handles.
        kwargs["state_flags"]["indirect_handle_drag"] = False

        self.node.addEventCallback([hou.nodeEventType.ParmTupleChanged],
                                   self._updateNodeParmCB)

        # NOTE: Need ref curve geo to be updated before entering tools.
        self.updateRefCurveGeo()

        self._drawable_manager.onEnter(kwargs)

        for m in self.sub_tools:
            m.onEnter(kwargs)

        for h in self.available_operations:
            h.onEnter(kwargs)

        self._updateActiveMode(just_entered=True)
        self.updateMenuToggles(kwargs)

        self.show(True)
        self.setPrompt()

        self._setRadialMenu()

        self.scene_viewer.addEventCallback(self._onSceneViewerEvent)
        hou.hipFile.addEventCallback(self._onHipFileEvent)

    def onHandleToState(self, kwargs:cu.KwargsDict):
        """
        Called when a handle is active and is interacted with.

        :kwargs: The kwargs dictionary.
        """

        if not self._checkValidNode(kwargs):
            return

        self.activeOperation().onHandleToState(kwargs)
        self._drawable_manager.onHandleToState(kwargs)


    def onBeginHandleToState(self, kwargs:cu.KwargsDict):
        """
        Called when a handle starts being interacted with.

        :kwargs: The kwargs dictionary.
        """

        if not self._checkValidNode(kwargs):
            return

        self.activeOperation().onBeginHandleToState(kwargs)
        self._drawable_manager.onBeginHandleToState(kwargs)


    def onEndHandleToState(self, kwargs:cu.KwargsDict):
        """
        Called when a handle stops being interacted with.

        :kwargs: The kwargs dictionary.
        """

        if not self._checkValidNode(kwargs):
            return

        self.activeOperation().onEndHandleToState(kwargs)
        self._drawable_manager.onEndHandleToState(kwargs)


    def onStateToHandle(self, kwargs:cu.KwargsDict):
        """
        Called when a handle is active and a node parm is changed.

        :kwargs: The kwargs dictionary.
        """

        if not self._checkValidNode(kwargs):
            return

        self.activeOperation().onStateToHandle(kwargs)
        self._drawable_manager.onStateToHandle(kwargs)

    def _setRadialMenu(self):
        # NOTE: Hidden functions in the UI library for states
        # that want to override the main radial menu.
        self._prev_radial_menu = hou.ui._getActiveRadialMenu()
        hou.ui._setActiveRadialMenu("curvesop")


    def _revertRadialMenu(self):
        """ Revert the radial menu to the one before entering the state. """

        # Default to main if None was set or it was curvesop when entered.
        if self._prev_radial_menu is None or self._prev_radial_menu == "curvesop":
            self._prev_radial_menu = "main"

        hou.ui._setActiveRadialMenu(self._prev_radial_menu)

    def onExit(self, kwargs:cu.KwargsDict):
        """
        Called when the state exits.

        :kwargs: The kwargs dictionary.
        """

        if not self._checkValidSceneViewer():
            return

        # See if the node is still valid or has been deleted.
        has_valid_node = self._checkValidNode(kwargs)

        # If not deleted, might need to do some deactivation first.
        if has_valid_node:
            self.activeOperation().onDeactivate()

        # Reset radial menu and hide HUD
        self._revertRadialMenu()
        hud.hudCommand(self.scene_viewer, freeze=0, defer=0)

        # Remove event callbacks
        self.scene_viewer.removeEventCallback(self._onSceneViewerEvent)
        hou.hipFile.removeEventCallback(self._onHipFileEvent)

        # If we enabled the construction plane by default, then hide it again.
        self.checkAutoDisableCPlane()

        # Stuff past this point can error with no valid node.
        if not has_valid_node:
            return

        # Remove node callbacks.
        self.node.removeEventCallback([hou.nodeEventType.ParmTupleChanged],
                                      self._updateNodeParmCB)

        # Then call on exit on the operations and sub tools and drawable manager.
        for h in self.available_operations:
            h.onExit(kwargs)

        for m in self.sub_tools:
            m.onExit(kwargs)

        self._drawable_manager.onExit(kwargs)

        # Save state parms to user data.
        stateparms.saveStateParms(kwargs)


    def onInterrupt(self, kwargs:cu.KwargsDict):
        """
        Called when state loses focus.

        :kwargs: The kwargs dictionary.
        """

        if not self._checkValidNode(kwargs):
            return

        hud.hudCommand(self.scene_viewer, freeze=1)

        for h in self.available_operations:
            h.onInterrupt(kwargs)

        for m in self.sub_tools:
            m.onInterrupt(kwargs)

        self._drawable_manager.onInterrupt(kwargs)


    def onResume(self, kwargs:cu.KwargsDict):
        """
        Called when state regains focus.

        :kwargs: The kwargs dictionary.
        """

        if not self._checkValidNode(kwargs):
            return

        hud.hudCommand(self.scene_viewer, freeze=0)

        self.updateRefCurveGeo()

        self._drawable_manager.onResume(kwargs)

        for h in self.available_operations:
            h.onResume(kwargs)

        for m in self.sub_tools:
            m.onResume(kwargs)

        self._updateActiveMode()
        self.scene_viewer.clearPromptMessage()
        self.updateMenuToggles(kwargs)


    def onDraw(self, kwargs: cu.KwargsDict):
        """
        Called when state is redrawn.

        :kwargs: The kwargs dictionary.
        """

        if not self._checkValidNode(kwargs):
            return

        self._drawable_manager.onDraw(kwargs)
        self.activeOperation().onDraw(kwargs)


    def _showActiveHUD(self, val:bool):
        """
        Update the HUD to reflect the current mode and vis.

        :val: Whether to show the hud.
        """

        self.scene_viewer.hudInfo(show=val)
        primtype = self.node.parm(constants.OUTPUTTYPE_PARM).evalAsString()
        order = self.node.parm(constants.ORDER_PARM).evalAsInt()
        show_bezier = (primtype == "bezier") and order >= 4
        show_bezier = show_bezier or self.getRefCurves().needsBezierCase()
        mode = self.node.parm(constants.MODE_PARM).evalAsInt()
        align_curve_tangent = self.node.parm(constants.ALIGNTANGENT_PARM).evalAsInt()
        self.scene_viewer.hudInfo(values={
            "mode": constants.MODE_NAMES[mode],
            "mode_g": mode,
            "mode_page": mode,
            "primtype": constants.PRIMTYPE_NAMES[primtype],
            "edit__visible": mode == constants.Mode.EDIT,
            "draw__visible": mode == constants.Mode.DRAW,
            "auto__visible": mode == constants.Mode.AUTODRAW,
            "orient__visible": mode == constants.Mode.ORIENT,
            "round_corners__visible": (mode == constants.Mode.EDIT
                                       and show_bezier),
            "tangents__visible": (mode == constants.Mode.EDIT
                                  and show_bezier),
            "bezierdraw__visible" : (mode == constants.Mode.DRAW
                                     and show_bezier),
            "orientfree__visible" : (mode == constants.Mode.ORIENT
                                    and align_curve_tangent == 0),
        })


    def onMouseEvent(self, kwargs:cu.KwargsDict) -> bool:
        """
        Called on a mouse event. Return true to consume.

        :kwargs: The kwargs dictionary.
        """

        ui_event = kwargs["ui_event"]
        reason = ui_event.reason()

        if not self._checkValidNode(kwargs):

            if reason in [hou.uiEventReason.Start, hou.uiEventReason.Picked] and ui_event.device().isLeftButton():
                raise hou.Error(f"{self.state_name} state is only supported in the 3D Scene Viewer!")

            return False

        # NOTE: the active tool is responsible for sending the mouse
        # event to the drawable manager when desired.
        result = self.activeOperation().onMouseEvent(kwargs)
        self.activeOperation().updateCursorLabel(kwargs)

        # NOTE: returning true will not send it to the drawable selector
        # if we want it to send the event to the drawable selector,
        # return false...
        return result


    def onMouseWheelEvent(self, kwargs:cu.KwargsDict) -> bool:
        """
        Called on mouse wheel. Return True to consume.

        :kwargs: The kwargs dictionary.
        """

        if not self._checkValidNode(kwargs):
            return False

        return self.activeOperation().onMouseWheelEvent(kwargs)


    def onKeyEvent(self, kwargs: cu.KwargsDict) -> bool:
        """
        Called on key events. Return True to consume.

        :kwargs: The kwargs dictionary.
        """

        if not self._checkValidNode(kwargs):
            return False

        ui_event = kwargs["ui_event"]
        device = ui_event.device()

        if device.isKeyDown():
            key = su.hotkeySymbolOrKeyString(kwargs)
            if not key:
                return False

            if hou.hotkeys.isKeyMatch(key, self.hk_toggle_xform):
                self.activeOperation().onHotkey(constants.HK_TOGGLEXFORM_CODE, kwargs)
            elif hou.hotkeys.isKeyMatch(key, self.hk_toggle_labels):
                hover_labels_parm = kwargs["state_parms"][constants.HOVERLABELS_STATEPARM]
                hover_labels_parm["value"] = not hover_labels_parm["value"]
                self.activeOperation().updateCursorLabelVisibility(kwargs)
                self.scene_viewer.curViewport().draw()
            elif hou.hotkeys.isKeyMatch(key, constants.HK_ACCEPT_SYMBOL):
                self.activeOperation().onHotkey(constants.MENU_FINISH_CODE, kwargs)
            elif hou.hotkeys.isKeyMatch(key, self.hk_stepupadd):
                self.activeOperation().onHotkey(constants.HK_SELUPADD_CODE, kwargs)
            elif hou.hotkeys.isKeyMatch(key, self.hk_stepuprem):
                self.activeOperation().onHotkey(constants.HK_SELUPREM_CODE, kwargs)
            elif hou.hotkeys.isKeyMatch(key, self.hk_stepdownadd):
                self.activeOperation().onHotkey(constants.HK_SELDOWNADD_CODE, kwargs)
            elif hou.hotkeys.isKeyMatch(key, self.hk_stepdownrem):
                self.activeOperation().onHotkey(constants.HK_SELDOWNREM_CODE, kwargs)
            elif hou.hotkeys.isKeyMatch(key, constants.HK_COPY_SYMBOL):
                self.activeOperation().onHotkey(constants.HK_COPY_SYMBOL, kwargs)
            elif hou.hotkeys.isKeyMatch(key, constants.HK_PASTE_SYMBOL):
                self.activeOperation().onHotkey(constants.HK_PASTE_SYMBOL, kwargs)
            else:
                # Return False if unmatched.
                return False

            # Otherwise, consume and return true.
            return True

        # In the future, we may want to pass this through the active
        # operation. But it is not yet needed, so lets hold off.
        return False


    def onKeyTransitEvent(self, kwargs:cu.KwargsDict) -> bool:
        """
        Called when a key is pressed down or lifted up
        Pass through to the active operation to let it handle it.
        Return True to consume.

        :kwargs: The kwargs dictionary.
        """
        return self._checkValidNode(kwargs)\
               and self.activeOperation().onKeyTransitEvent(kwargs)


    def onVolatileClientEvent(self, kwargs:cu.KwargsDict) -> bool:
        """
        Called when a volatile key is lifted.
        Pass through to the active operation to let it handle it.

        :kwargs: The kwargs dictionary.
        """

        return self.activeOperation().onVolatileClientEvent(kwargs)


    def onCommand(self, kwargs:cu.KwargsDict):
        """
        Called on state commands.

        :kwargs: The kwargs dictionary.
        """

        name = kwargs["command"]
        args = kwargs["command_args"]

        if name == "switchHandleTool":
            self.activeOperation().handleSwitchHandleToolCmd(args)

    def onMenuPreOpen( self, kwargs:cu.KwargsDict ):
        """
        Show/hide context menu items based on the mode.

        :kwargs: The kwargs dictionary.
        """

        if not self._checkValidNode(kwargs):
            return

        menu_id = kwargs["menu"]
        node = kwargs["node"]
        menu_states = kwargs["menu_states"]
        menu_item_states = kwargs["menu_item_states"]

        if menu_id == constants.PICKINGMODE_STATEPARM:
            menu_states["value"] = self.getStateParmPickingMode(kwargs)

        if menu_id not in constants.CURVE_STATE_MENUS:
            return

        mode = self.node.parm(constants.MODE_PARM).evalAsInt()
        is_edit = (mode == constants.Mode.EDIT)
        is_draw = (mode in [constants.Mode.DRAW, constants.Mode.AUTODRAW])
        is_orient = (mode == constants.Mode.ORIENT)

        def _try_set_vis(item, val):
            if item in menu_item_states:
                menu_item_states[item]["visible"] = val

        def _try_set_vis_list(items, val):
            for item in items:
                _try_set_vis(item, val)

        _try_set_vis_list(constants.BEZIER_ONLY_MENU_ITEMS, self.getRefCurves().needsBezierCase())
        _try_set_vis_list(constants.EDIT_ONLY_MENU_ITEMS, is_edit)
        _try_set_vis_list(constants.DRAW_ONLY_MENU_ITEMS, is_draw)
        _try_set_vis_list(constants.ORIENT_ONLY_MENU_ITEMS, is_orient)

    def cycleMode(self, reverse:bool):
        """ Cycle the mode forward or backward. """

        mode_int = self.node.parm(constants.MODE_PARM).evalAsInt()
        num_modes = constants.Mode.ORIENT+1
        new_mode_int = (mode_int-1+num_modes)%num_modes if reverse else (mode_int+1)%num_modes
        self.node.parm(constants.MODE_PARM).set(new_mode_int)

    def onMenuAction(self, kwargs:cu.KwargsDict):
        """
        Called on menu action.

        :kwargs: The kwargs dictionary.
        """

        if not self._checkValidNode(kwargs):
            raise hou.Error(f"{self.state_name} state is only supported in the 3D Scene Viewer!")

        item = kwargs["menu_item"]

        if item == constants.PICKINGMODE_STATEPARM:
            node = kwargs["node"]
            cat_name = node.type().category().name()
            picking_mode_menu = getPickingModeMenu(cat_name)
            for i in range(len(picking_mode_menu)):
                if picking_mode_menu[i][0] == kwargs[constants.PICKINGMODE_STATEPARM]:
                    kwargs["state_parms"][constants.PICKINGMODE_STATEPARM]["value"] = i
                    break

        # Handle any actions that need to be at the root state level
        if item == constants.MENU_EDITMODE_CODE:
            self.node.parm(constants.MODE_PARM).set(constants.Mode.EDIT)
        elif item == constants.MENU_DRAWMODE_CODE:
            self.node.parm(constants.MODE_PARM).set(constants.Mode.DRAW)
        elif item == constants.MENU_AUTODRAWMODE_CODE:
            self.node.parm(constants.MODE_PARM).set(constants.Mode.AUTODRAW)
        elif item == constants.MENU_ORIENTMODE_CODE:
            self.node.parm(constants.MODE_PARM).set(constants.Mode.ORIENT)
        elif item == constants.MENU_CONSTRAIN_STRAIGHTEN_CODE:
            self.updateMenuToggles(kwargs)
        elif item == constants.MENU_CYCLEMODE_CODE:
            self.cycleMode(reverse=False)
        elif item == constants.MENU_CYCLEMODEREV_CODE:
            self.cycleMode(reverse=True)
        else:
            return self.activeOperation().onHotkey(item, kwargs)
        return True


    def updateMenuToggles(self, kwargs:cu.KwargsDict):
        """
        Update the node parameters and state context from the
        context menu toggles.

        :kwargs: The kwargs dictionary.
        """

        if not self.node:
            return

        constrain = kwargs["constrain_straighten_toggle"]
        parm = self.node.parm(constants.CONSTRAINSTRAIGHTEN_PARM)
        if parm.evalAsInt() != constrain:
            parm.set(constrain)


    def onParmChangeEvent(self, kwargs:cu.KwargsDict):
        """
        Called on state parm changes.

        :kwargs: The kwargs dictionary.
        """

        if not self._checkValidNode(kwargs):
            return

        parm_name = kwargs["parm_name"]

        if parm_name == constants.OPENPREFSBTN_STATEPARM:
            hou.ui.openPreferences("states", "")

        self.activeOperation().onParmChangeEvent(kwargs)
        self._drawable_manager.onParmChangeEvent(kwargs)


UpdateMenuFn = Callable[[hou.ViewerStateMenu],None]

def bindCurveStateMenuAndHotkeys(template:hou.ViewerStateTemplate,
                                 state_typename:str,
                                 state_category:hou.NodeTypeCategory,
                                 menu:hou.ViewerStateMenu|None=None,
                                 prepend_menu_func:UpdateMenuFn|None=None,
                                 hotkey_definitions:hou.PluginHotkeyDefinitions|None=None):
    """
    Bind the hotkeys and menu items to the Curve State menu.

    :template: The hou.ViewerStateTemplate to bind to.
    :state_typename: The state typename.
    :state_category: The state category.
    :menu: Optionally provide a menu to bind all items to.
    :prepend_menu_func: A function that will be called with the menu
        before any items are added to it.
    :hotkey_definitions: Optionally provide a hou.PluginHotkeyDefinitions
        object to add all definitions to.
    """

    if hotkey_definitions is None:
        hotkey_definitions = hou.PluginHotkeyDefinitions()

    # Hotkeys not bound to menu actions
    # These are picked up in onKeyEvent() OR onKeyTransitEvent().
    su.defineHotkey(hotkey_definitions,
              state_typename, constants.HK_TOGGLEXFORM_CODE, "K",
              "Toggle Transform Handle", state_cat=state_category)
    su.defineHotkey(hotkey_definitions,
              state_typename, constants.HK_TOGGLELABELS_CODE, "L",
              "Toggle Hover Labels", state_cat=state_category)
    su.defineHotkey(hotkey_definitions,
              state_typename, constants.HK_DRAWARC_CODE, "A",
              "Draw Arc Segment", state_cat=state_category)

    if menu is None:
        menu = hou.ViewerStateMenu(constants.CONTEXT_MENU_NAME, "Curve Menu")

    if prepend_menu_func is not None:
        prepend_menu_func(menu)

    # Add hotkey tied to a menu action.
    # These are handled in onMenuAction()
    def addHotkeyActionItem(code, desc, key, submenu=None, hk=None):
        if hk is None:
            hk = su.defineHotkey(hotkey_definitions, state_typename, code, key,
                                 desc, state_cat=state_category)

        if submenu is None:
            submenu = menu

        submenu.addActionItem(code, desc, hotkey=hk)

    def addHotkeySymbolActionItem(code, desc, submenu=None, hk=None):
        addHotkeyActionItem(code, desc, "", submenu=submenu, hk=hk)

    # Handle ENTER specially to use the accept symbol.
    addHotkeySymbolActionItem(constants.MENU_FINISH_CODE, "Finish Adding Points", hk=constants.HK_ACCEPT_SYMBOL)
    addHotkeyActionItem(constants.MENU_FINISHANDCLOSE_CODE, "Close Curve", "Shift+Enter")

    addHotkeyActionItem(constants.MENU_SELECTALL_CODE, "Select All", "Shift+A")
    addHotkeySymbolActionItem(constants.MENU_DESELECTALL_CODE, "De-Select All")

    addHotkeyActionItem(constants.MENU_SELUP_CODE, "Move Selection Up", "UpArrow")
    addHotkeyActionItem(constants.MENU_SELDOWN_CODE, "Move Selection Down","DownArrow")

    # NOTE: We need to manually add extra hotkeys for handling the modifier keys.
    su.defineHotkey(hotkey_definitions,
            state_typename, constants.HK_SELUPADD_CODE, "Shift+UpArrow",
            "Add Selection Up", state_cat=state_category)
    su.defineHotkey(hotkey_definitions,
            state_typename, constants.HK_SELUPREM_CODE, "Ctrl+UpArrow",
            "Remove Selection Up", state_cat=state_category)
    su.defineHotkey(hotkey_definitions,
            state_typename, constants.HK_SELDOWNADD_CODE, "Shift+DownArrow",
            "Add Selection Down", state_cat=state_category)
    su.defineHotkey(hotkey_definitions,
            state_typename, constants.HK_SELDOWNREM_CODE, "Ctrl+DownArrow",
            "Remove Selection Down", state_cat=state_category)

    addHotkeySymbolActionItem(constants.MENU_SELCONNECTED_CODE, "Select Connected")

    menu.addSeparator()

    submenu = hou.ViewerStateMenu(constants.MODE_SUBMENU_NAME, "Change Mode")
    addHotkeyActionItem(constants.MENU_CYCLEMODE_CODE, "Cycle Mode", "", submenu)
    addHotkeyActionItem(constants.MENU_CYCLEMODEREV_CODE, "Cycle Mode Backward", "", submenu)
    submenu.addSeparator()
    addHotkeyActionItem(constants.MENU_EDITMODE_CODE, "Enter Edit Mode", "F", submenu)
    addHotkeyActionItem(constants.MENU_DRAWMODE_CODE, "Enter Draw Mode", "G", submenu)
    addHotkeyActionItem(constants.MENU_AUTODRAWMODE_CODE, "Enter Auto-Bezier Draw Mode", "H", submenu)
    addHotkeyActionItem(constants.MENU_ORIENTMODE_CODE, "Enter Orient Mode", "O", submenu)
    menu.addMenu(submenu)

    #menu.addSeparator()

    submenu = hou.ViewerStateMenu(constants.EDIT_POINTS_SUBMENU_NAME, "Edit Points")
    addHotkeyActionItem(constants.MENU_DELETE_CODE, "Delete Selected Points", "DEL", submenu)
    addHotkeySymbolActionItem(constants.MENU_CONTRACT_CODE, "Retract Points", submenu)
    addHotkeySymbolActionItem(constants.MENU_EXPAND_CODE, "Expand Points", submenu)
    addHotkeySymbolActionItem(constants.MENU_FUSE_CODE, "Join Points", submenu)
    addHotkeySymbolActionItem(constants.MENU_CUT_CODE, "Cut Points", submenu)
    addHotkeySymbolActionItem(constants.MENU_BRANCH_FUSE_CODE, "Fuse Branch", submenu)
    addHotkeySymbolActionItem(constants.MENU_BRANCH_CUT_CODE, "Split Branch", submenu)
    menu.addMenu(submenu)

    submenu = hou.ViewerStateMenu(constants.EDIT_SEG_SUBMENU_NAME, "Edit Segments")
    addHotkeySymbolActionItem(constants.MENU_SEGDELETE_CODE, "Delete Segment", submenu)
    addHotkeySymbolActionItem(constants.MENU_JOIN_CODE, "Join Points with Segment", submenu)
    addHotkeySymbolActionItem(constants.MENU_SEGSTRAIGHTEN_CODE, "Make Segment Straight", submenu)
    addHotkeySymbolActionItem(constants.MENU_CLOSECURVE_CODE, "Close Selected Curves", submenu)
    addHotkeySymbolActionItem(constants.MENU_REVERSECURVE_CODE, "Reverse Selected Curves", submenu)
    menu.addMenu(submenu)
    #menu.addSeparator()

    submenu = hou.ViewerStateMenu(constants.CHANGE_TYPE_SUBMENU_NAME, "Change Point Type")
    addHotkeyActionItem(constants.MENU_CORNER_CODE, "Make Corners", "1", submenu)
    addHotkeyActionItem(constants.MENU_SMOOTH_CODE, "Make Smooth", "2", submenu)
    addHotkeyActionItem(constants.MENU_BALANCED_CODE, "Make Balanced", "3", submenu)
    menu.addMenu(submenu)

    #menu.addSeparator()

    submenu = hou.ViewerStateMenu(constants.CONVERT_SUBMENU, "Convert Selected Curves")
    addHotkeySymbolActionItem(constants.MENU_CONVERTPOLY_CODE, "To Polygon", submenu)
    addHotkeySymbolActionItem(constants.MENU_CONVERTBEZIER_CODE, "To Bezier", submenu)
    addHotkeySymbolActionItem(constants.MENU_CONVERTNURBS_CODE, "To NURBS", submenu)
    addHotkeySymbolActionItem(constants.MENU_SELCONVERT_CODE, "To Current Type and Order", submenu)
    menu.addMenu(submenu)

    submenu = hou.ViewerStateMenu(constants.MISC_OP_SUBMENU_NAME, "Utility")
    addHotkeySymbolActionItem(constants.MENU_CENTERPIVOT_CODE, "Center Selection on Pivot", submenu)
    addHotkeySymbolActionItem(constants.MENU_FLATTEN_CODE, "Flatten Selection to C-Plane", submenu)
    addHotkeySymbolActionItem(constants.MENU_SPACECIRCLE_CODE, "Space Prim Points Around Circle", submenu)
    addHotkeySymbolActionItem(constants.MENU_EVENLYSPACE_CODE, "Evenly Space Selected Points", submenu)
    addHotkeySymbolActionItem(constants.MENU_RELAX_CODE, "Relax Selected Points", submenu)
    addHotkeySymbolActionItem(constants.MENU_STRAIGHTEN_CODE, "Straighten Selected Points", submenu)
    submenu.addToggleItem(constants.MENU_CONSTRAIN_STRAIGHTEN_CODE,
                       "Constrain Straighten to View Plane", 0)
    menu.addMenu(submenu)


    menu.addToggleItem(constants.MENU_DRAWSNAP_CODE, "Auto-Snap to Curve Points", 1)


    picking_mode_menu = getPickingModeMenu(template.categoryName())
    default_pick_mode = getDefaultPickingMode(template.categoryName())

    menu.addRadioStrip(constants.PICKINGMODE_STATEPARM, "Pick Mode", default_pick_mode)

    for item in picking_mode_menu:
        menu.addRadioStripItem(constants.PICKINGMODE_STATEPARM, item[0], item[1])

    template.bindMenu(menu)
    template.bindHotkeyDefinitions(hotkey_definitions)


def bindCurveStateStateParms(template:hou.ViewerStateTemplate):
    """
    Bind the state parameters to the viewerstate template.

    :template: The hou.ViewerStateTemplate to bind to.
    """

    template.bindParameter(hou.parmTemplateType.Toggle,
                           name=constants.ENABLEORIENTGUIDE_STATEPARM,
                           label="Enable Orient Guide",
                           default_value=True, toolbox=False)
    template.bindParameter(hou.parmTemplateType.Float,
                           name=constants.ORIENTGUIDEDENSITY_STATEPARM,
                           label="Orient Guide Density Scale",
                           default_value=0.75, max_limit=2.0, toolbox=False)
    template.bindParameter(hou.parmTemplateType.Float,
                           name=constants.ORIENTGUIDESCALE_STATEPARM,
                           label="Orient Guide Gnomon Scale",
                           default_value=0.75, max_limit=2.0, toolbox=False)
    template.bindParameter(hou.parmTemplateType.Float,
                           name=constants.ORIENTANGLESTEP_STATEPARM,
                           label="Orient Ring Step Size",
                           default_value=15.0, max_limit=90.0, toolbox=False)
    template.bindParameter(hou.parmTemplateType.Toggle,
                           name=constants.SHOWPREVIEWCURVE_STATEPARM,
                           label="Show Preview and Ghosted Curve Guides",
                           default_value=True, toolbox=False)
    template.bindParameter(hou.parmTemplateType.Toggle,
                           name=constants.ALLOWSEGMENTSELECT_STATEPARM,
                           label="Allow Selecting and Dragging Curve Segments",
                           default_value=True, toolbox=False)
    template.bindParameter(hou.parmTemplateType.Toggle,
                           name=constants.SHOWALLTANGENTS_STATEPARM,
                           label="Show Tangent Handles on All Selected Points",
                           default_value=True, toolbox=False)
    template.bindParameter(hou.parmTemplateType.Toggle,
                           name=constants.HOVERLABELS_STATEPARM,
                           label="Show Hover Labels",
                           default_value=True, toolbox=False)
    template.bindParameter(hou.parmTemplateType.Toggle,
                           name=constants.RELATIVEANGLESNAP_STATEPARM,
                           label="Use Relative Angle with Previous Segment to Align in Draw Mode",
                           default_value=False, toolbox=False)

    template.bindParameter(hou.parmTemplateType.Button,
                           name=constants.OPENPREFSBTN_STATEPARM,
                           label="Open State Preferences",
                           toolbox=False)

    template.bindParameter(hou.parmTemplateType.Separator, toolbox=False)

    picking_mode_menu = getPickingModeMenu(template.categoryName())
    default_pick_mode = getDefaultPickingMode(template.categoryName())
    template.bindParameter(hou.parmTemplateType.Menu,
                           name=constants.PICKINGMODE_STATEPARM,
                           label="Picking Mode",
                           default_value=default_pick_mode,
                           menu_items=picking_mode_menu, toolbox=False)


def bindCurveStateGadgetsHandles(template:hou.ViewerStateTemplate):
    """
    Bind the state gadgets and handles to the viewerstate template.

    :template: The hou.ViewerStateTemplate to bind to.
    """

    template.bindHandle("xform", constants.TRANSFORM_HANDLE,
                        settings="snap_to_selection(1)")

    template.bindHandle("xform", constants.ORIENT_HANDLE,
                        handle_parms=["px","py","pz","rx","ry","rz"])

    hud_handle_settings = hudu.formatSettings({
        hudc.PARM_MIN:"-10.0,-10.0,-10.0",
        hudc.PARM_MAX:"10.0,10.0,10.0",
        hudc.PARM_DEFAULT:"0.0,0.0,0.0",
        hudc.PARM_LABEL:["Position (X)", "Position (Y)", "Position (Z)"],
    })
    template.bindHandle("sidefx_hud_slider", constants.HUD_TRANSLATE_HANDLE,
                        settings=hud_handle_settings, cache_previous_parms=True,
                        handle_parms=["value1","value2","value3"])

    template.bindGadget(hou.drawableGeometryType.Line,
                        DrawableInteractionManager.CURVE_GADGET,
                        label="Curve")
    template.bindGadget(hou.drawableGeometryType.Line,
                        DrawableInteractionManager.BEZIER_LINES_GADGET,
                        label="Handle Lines")
    template.bindGadget(hou.drawableGeometryType.Line,
                        DrawableInteractionManager.BEZIER_BROKEN_LINES_GADGET,
                        label="Handle Broken Lines")
    template.bindGadget(hou.drawableGeometryType.Point,
                        DrawableInteractionManager.BEZIER_PTS_GADGET,
                        label="Handle Points")
    template.bindGadget(hou.drawableGeometryType.Point,
                        DrawableInteractionManager.HIDDEN_ANCHOR_GADGET,
                        label="Hidden Anchor Points")
    template.bindGadget(hou.drawableGeometryType.Point,
                        DrawableInteractionManager.ROUNDED_CORNER_GADGET,
                        label="Rounded Corners")
    template.bindGadget(hou.drawableGeometryType.Point,
                        DrawableInteractionManager.BEZIER_HIGHER_ORDER_GADGET,
                        label="Bezier Higher Order Points")
    template.bindGadget(hou.drawableGeometryType.Line,
                        DrawableInteractionManager.ORIENT_CIRCLES_LINES_GADGET,
                        label="Up Vector Circles")
    template.bindGadget(hou.drawableGeometryType.Face,
                        DrawableInteractionManager.ORIENT_CIRCLES_FACES_GADGET,
                        label="Up Vector Circles Faces")



def bindCurveStateTemplate(template:hou.ViewerStateTemplate,
                           state_typename:str,
                           state_category:hou.NodeTypeCategory,
                           drawable_selector_name:str|None=None,
                           auto_start_drawable_selector:bool=True,
                           menu:hou.ViewerStateMenu|None=None,
                           prepend_menu_func:UpdateMenuFn|None=None,
                           hotkey_definitions:hou.PluginHotkeyDefinitions|None=None):
    """
    Bind the menu, hotkeys, state parms, gadgets, handles, and selectors
    to the viewerstate template.

    :template: The hou.ViewerStateTemplate to bind to.
    :state_typename: The state typename.
    :state_category: The state category.
    :drawable_selector_name: The name to give the drawable selector.
    :auto_start_drawable_selector: Whether the drawable selector should
        be started when the state is entered.
    :menu: Optionally provide a menu to bind all items to.
    :prepend_menu_func: A function that will be called with the menu
        before any items are added to it.
    :hotkey_definitions: Optionally provide a hou.PluginHotkeyDefinitions
        object to add all definitions to.
    """

    bindCurveStateMenuAndHotkeys(template, state_typename, state_category,
        menu=menu, prepend_menu_func=prepend_menu_func,
        hotkey_definitions=hotkey_definitions)
    bindCurveStateStateParms(template)
    bindCurveStateGadgetsHandles(template)


def createCurveStateTemplate(state_typename: str,
                             state_label: str,
                             icon_name: str,
                             state_category: hou.NodeTypeCategory,
                             state_class_type: Type) -> hou.ViewerStateTemplate:
    """
    Create the default Curve state template.

    :state_typename: The state typename.
    :state_label: The label for the state.
    :icon_name: The icon to use.
    :state_category: The state category.
    :state_class_type: The class of the state. I.e. CurveState
    """

    template = hou.ViewerStateTemplate(state_typename,
                                       state_label,
                                       state_category)
    template.bindFactory(state_class_type)
    template.bindIcon(icon_name)
    bindCurveStateTemplate(template, state_typename, state_category)
    return template


def createViewerStateTemplate():
    """
    Mandatory entry point to create and return the viewer state
    template to register.
    """

    state_typename = "sidefx_curve"
    state_label = "Curve"
    state_cat = hou.sopNodeTypeCategory()
    state_icon = "SOP_curve"
    state_class_name = CurveState

    template = createCurveStateTemplate(
        state_typename, state_label, state_icon,
        state_cat, state_class_name)
    return template
