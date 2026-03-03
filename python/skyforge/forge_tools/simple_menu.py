# ------------------------------
# simple_menu.py
# ------------------------------
# Skyforge - SIMPLE MENU
# Reads JSON { "menu": [ ... ] } written by custom_palette.py
# Supports:
#   - shelf:<toolname>   -> exec shelf tool script
#   - tool:<toolname>    -> create node (mapped) in active network, connected to display-flag node
#   - <nodeTypeName>     -> (fallback demo) create in /obj
#
# Houdini 21 => PySide6

from PySide6 import QtWidgets, QtGui
import hou, os, json
import soptoolutils

CFG_PATH = hou.expandString("$HOUDINI_USER_PREF_DIR/skyforge_menu_demo.json")

DEFAULT_CFG = {
    "menu": [
        "shelf:SF_reload_python",
    ]
}

# ---------------------------------------------------------
# Tool -> opType mapping (YOU control this)
# ---------------------------------------------------------
TOOL_TO_OPTYPE = {
    "justi::sop_flying_selector::1.0": "justi::sop_flying_selector::1.0",
    "justi::sop_forge_edge_flow::1.0": "justi::sop_forge_edge_flow::1.0",
    "justi::sop_forge_edge_loop::1.0": "justi::sop_forge_edge_loop::1.0",
    "justi::sop_pyd_loop::1.0": "justi::sop_pyd_loop::1.0",
}

# ----------------------------
# IO
# ----------------------------
def load_cfg():
    if not os.path.exists(CFG_PATH):
        save_cfg(DEFAULT_CFG)
        return json.loads(json.dumps(DEFAULT_CFG))
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if "menu" not in cfg or not isinstance(cfg["menu"], list):
            cfg["menu"] = []
        return cfg
    except Exception as e:
        print("[SkyforgeMenu] Failed to read cfg:", e)
        return json.loads(json.dumps(DEFAULT_CFG))

def save_cfg(cfg):
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print("[SkyforgeMenu] Failed to write cfg:", e)

# ----------------------------
# Helpers: labels
# ----------------------------
def _label_for_action_id(action_id: str) -> str:
    """Pretty label for menu display."""
    if action_id.startswith("shelf:"):
        tool_name = action_id.split(":", 1)[1]
        try:
            t = hou.shelves.tool(tool_name)
            if t:
                return t.label() or t.name()
        except Exception:
            pass
        return tool_name

    if action_id.startswith("tool:"):
        tool_name = action_id.split(":", 1)[1]
        try:
            t = hou.shelves.tool(tool_name)
            if t:
                return t.label() or t.name()
        except Exception:
            pass
        return tool_name

    return action_id

# ----------------------------
# Network helpers
# ----------------------------
def _active_network_pane():
    try:
        return hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    except Exception:
        return None

def _find_display_flag_node(parent: hou.Node):
    for n in parent.children():
        try:
            if n.isDisplayFlagSet():
                return n
        except Exception:
            pass
    return None

def _spawn_node_attached_to_display(op_type: str):
    pane = _active_network_pane()
    if pane is None:
        raise RuntimeError("No active Network Editor pane.")

    net = pane.pwd()
    if net is None:
        raise RuntimeError("No current network (pwd) in Network Editor.")

    src = _find_display_flag_node(net)
    if src is None:
        raise RuntimeError(
            f"No node with Display Flag in: {net.path()}\n"
            "Go inside the SOP network where your displayed node lives."
        )

    # ------------------------------------------------------------
    # Case A: you're already inside a SOP network => src is a SOP node
    # ------------------------------------------------------------
    if src.childTypeCategory() == hou.sopNodeTypeCategory():
        sop_parent = src.parent()
        sop_src = src

    # ------------------------------------------------------------
    # Case B: you're at OBJ level => src is an OBJ node (geo, subnet, etc.)
    # We need the displayed SOP inside that object.
    # ------------------------------------------------------------
    elif src.childTypeCategory() == hou.objNodeTypeCategory():
        try:
            sop_src = src.displayNode()  # displayed SOP inside the object
        except Exception:
            sop_src = None

        if sop_src is None:
            raise RuntimeError(
                f"Object has no display SOP: {src.path()}\n"
                "Dive inside the object and make sure a SOP has the display flag."
            )

        sop_parent = sop_src.parent()

    else:
        raise RuntimeError(
            f"Unsupported context for display node:\n{src.path()}\n"
            f"Category: {src.childTypeCategory().name()}"
        )

    # Create SOP node in correct SOP parent
    try:
        new = sop_parent.createNode(op_type)
    except Exception as e:
        raise RuntimeError(f"Failed to create SOP node type '{op_type}' in {sop_parent.path()}:\n{e}")

    # Connect to displayed SOP
    try:
        new.setInput(0, sop_src)
    except Exception:
        pass

    # Layout + flags
    try:
        new.moveToGoodPosition()
    except Exception:
        sop_parent.layoutChildren()

    try:
        new.setDisplayFlag(True)
        new.setRenderFlag(True)
    except Exception:
        pass

    try:
        pane.setCurrentNode(new)
        pane.homeToSelection()
    except Exception:
        pass

    return new

# ----------------------------
# Dispatcher
# ----------------------------
def dispatch(action_id: str):
    """Execute the action."""
    if action_id.startswith("shelf:"):
        tool_name = action_id.split(":", 1)[1]
        t = hou.shelves.tool(tool_name)
        if not t:
            raise RuntimeError(f"Shelf tool not found: {tool_name}")
        script = t.script()
        exec(script, {"hou": hou})
        return

    if action_id.startswith("tool:"):
        tool_name = action_id.split(":", 1)[1]
        op_type = TOOL_TO_OPTYPE.get(tool_name)
        if not op_type:
            raise RuntimeError(
                f"No TOOL_TO_OPTYPE mapping for:\n{tool_name}\n\n"
                "Add it in simple_menu.py (TOOL_TO_OPTYPE dict)."
            )
        return _spawn_node_attached_to_display(op_type)

    # fallback: assume "HDA node type" (demo)
    node_type = action_id
    parent = hou.node("/obj")
    if not parent:
        raise RuntimeError("Cannot find /obj")

    try:
        n = parent.createNode(node_type)
        n.moveToGoodPosition()
        parent.layoutChildren()
        return n
    except Exception as e:
        raise RuntimeError(f"Failed to create node type '{node_type}': {e}")

# ----------------------------
# UI
# ----------------------------
def show():
    cfg = load_cfg()
    items = cfg.get("menu", [])

    menu = QtWidgets.QMenu()
    header = menu.addAction("Skyforge")
    header.setEnabled(False)
    menu.addSeparator()

    if not items:
        menu.addAction("(menu vide) ouvre la palette et Save").setEnabled(False)
    else:
        for action_id in items:
            label = _label_for_action_id(action_id)
            act = menu.addAction(label)
            act.setToolTip(action_id)
            act.triggered.connect(lambda checked=False, aid=action_id: _safe_dispatch(aid))

    menu.setStyleSheet("""
        QMenu { background:#282828; color:white; border:1px solid #555; padding:6px; font-size:14px; }
        QMenu::item { padding:6px 24px; }
        QMenu::item:selected { background:#505050; }
        QMenu::separator { height:1px; background:#555; margin:6px 10px; }
    """)

    menu.exec(QtGui.QCursor.pos())

def _safe_dispatch(action_id: str):
    try:
        dispatch(action_id)
    except Exception as e:
        print("[SkyforgeMenu] ERROR:", e)
        hou.ui.displayMessage(str(e), severity=hou.severityType.Error)