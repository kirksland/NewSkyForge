# skyforge/constants.py
"""
SkyForge constants and conventions.

Rules:
- Do NOT put tool-specific values here unless they are shared.
- Prefer adding items under the appropriate section.
"""

# ---------------------------------------------------------------------
# HDA / Network Naming Conventions (stable contracts)
# ---------------------------------------------------------------------
PARM_EDGELOOP_SPEC = "edgeloop_spec"
PARM_STASH_RESET = "stashinput"

NODE_CACHE_GEO = "cache_geo"
NODE_STASH = "stash1"
NODE_INPUT = "INPUT"

# ---------------------------------------------------------------------
# Common Mode Strings (shared across tools)
# ---------------------------------------------------------------------
MODE_LOCAL = "LOCAL"
MODE_WORLD = "WORLD"
MODE_EDGE = "EDGE"

TOOL_MOVE = "MOVE"
TOOL_CUT = "CUT"

SEL_POINT = "POINT"
SEL_EDGE = "EDGE"
SEL_FACE = "FACE"
