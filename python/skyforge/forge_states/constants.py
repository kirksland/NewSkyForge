"""
Shared constants for modular viewer states.
Single source of truth for visual style and runtime keys.
"""

# ---------------------------------------------------------------------------
# Draw style
# ---------------------------------------------------------------------------
LINE_WIDTH = 3.0
MOVE_GUIDE_LINE_WIDTH = 2.0
MOVE_GUIDE_LENGTH = 0.3

# Shared viewer-state colors (RGBA)
COLOR_PREVIEW_YELLOW = (1.0, 1.0, 0.45, 1.0)
COLOR_COMMITTED_ORANGE = (1.0, 0.55, 0.0, 1.0)

# ---------------------------------------------------------------------------
# Common node parms / keys
# ---------------------------------------------------------------------------
PARM_GRSTR = "grstr"
PARM_BASEGROUP = "basegroup"
GROUP_PARM_NAMES = (PARM_GRSTR, PARM_BASEGROUP)

POINT_RADIUS_USERDATA_SUFFIX = "point_radius"

# ---------------------------------------------------------------------------
# Auto-axis defaults
# ---------------------------------------------------------------------------
DEFAULT_STASH_NODE_NAME = "stash1"
DEFAULT_INPUT_NODE_NAME = "INPUT"

POINT_RADIUS_DEFAULT = 5.0
POINT_RADIUS_STEP = 1.0
POINT_RADIUS_MIN = 1.0
POINT_RADIUS_MAX = 24.0
POINT_HOVER_EXTRA = 2.0

AUTO_AXIS_MODE_ORDER = ("LOCAL", "WORLD", "EDGE")
AUTO_AXIS_SELECT_ORDER = ("POINT", "EDGE", "FACE")
AUTO_AXIS_TOOL_ORDER = ("MOVE", "CUT")
TOOL_MODE_DRAW = "DRAW"

# ---------------------------------------------------------------------------
# Loop modes
# ---------------------------------------------------------------------------
LOOP_MODE_ROLL = "roll"
LOOP_MODE_QUAD = "quad"

# ---------------------------------------------------------------------------
# Path output modes (for loop / astar commits)
# ---------------------------------------------------------------------------
OUTPUT_MODE_EDGE = "edge"
OUTPUT_MODE_POINT = "point"
OUTPUT_MODE_PRIM = "prim"
OUTPUT_MODE_ORDER = (OUTPUT_MODE_EDGE, OUTPUT_MODE_POINT, OUTPUT_MODE_PRIM)

# ---------------------------------------------------------------------------
# Preview channels
# ---------------------------------------------------------------------------
# Generic hover channels
CH_HOVER_EDGE = "hover_edge"
CH_POINT_REST = "point_rest"
CH_HOVER_POINT = "hover_point"
CH_HOVER_FACE = "hover_face"

# Move channels
CH_MOVE_GUIDE = "move_guide"

# A* channels
CH_ASTAR_PREVIEW = "astar_preview"
CH_ASTAR_COMMITTED = "astar_committed"

# Loop channels
CH_LOOP_PREVIEW = "loop_preview"
CH_LOOP_COMMITTED = "loop_committed"

# Curve draw channels
CH_CURVE_POINTS = "curve_points"
CH_CURVE_LINE = "curve_line"
