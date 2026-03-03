# Skyforge - SIMPLE MENU
# Reads JSON { "menu": [ ... ] } written by custom_palette.py
# Supports:
#   - shelf:<toolname>            -> exec shelf tool script
#   - <nodeTypeName> (HDA type)   -> create node in /obj (demo)
#
# Houdini 21 => PySide6

from PySide6 import QtWidgets, QtGui
import hou, os, json

CFG_PATH = hou.expandString("$HOUDINI_USER_PREF_DIR/skyforge_menu_demo.json")

DEFAULT_CFG = {
    "menu": [
        "shelf:SF_reload_python",
    ]
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

    # For HDAs: show nodeTypeName as-is for now
    return action_id

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
        # NOTE: this runs whatever is in the tool; keep tools as thin launchers
        exec(script, {"hou": hou})
        return

    # Assume "HDA node type" otherwise (demo)
    # You can tighten this later (prefix skyforge::, etc.)
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