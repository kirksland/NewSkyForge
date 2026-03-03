# Skyforge DEMO - SIMPLE MENU (lit config JSON)
from PySide6 import QtWidgets, QtGui
import hou, os, json

CFG_PATH = hou.expandString("$HOUDINI_USER_PREF_DIR/skyforge_menu_demo.json")

# Action registry (demo) : id -> (label, callable)
def _act_msg(text):
    print("[MENU DEMO]", text)
    hou.ui.displayMessage(text, severity=hou.severityType.Message)

ACTIONS = {
    "demo.subd": ("QuickSubdivide (fake)", lambda: _act_msg("FAKE: QuickSubdivide")),
    "demo.reload": ("Reload Python (fake)", lambda: _act_msg("FAKE: Reload Python")),
    "demo.bg": ("Toggle Background (fake)", lambda: _act_msg("FAKE: Toggle Background")),
    "demo.clear": ("Clear Console (fake)", lambda: (print("\n"*200), _act_msg("FAKE: Console cleared"))),
    "demo.banana": ("Banana", lambda: _act_msg("🍌 Banana executed.")),
    "demo.laser": ("Laser", lambda: _act_msg("🔫 Pew pew.")),
}

DEFAULT_CFG = {
    "columns": {
        "Left":  ["demo.subd", "demo.reload"],
        "Mid":   ["demo.bg", "demo.clear"],
        "Right": ["demo.banana", "demo.laser"]
    },
    # Le menu simple prend UNE colonne "active" (ex: Left/Mid/Right)
    "menu_active_column": "Left"
}

def load_cfg():
    if not os.path.exists(CFG_PATH):
        save_cfg(DEFAULT_CFG)
        return DEFAULT_CFG
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # fallback si clés manquantes
        if "columns" not in cfg:
            cfg["columns"] = DEFAULT_CFG["columns"]
        if "menu_active_column" not in cfg:
            cfg["menu_active_column"] = DEFAULT_CFG["menu_active_column"]
        return cfg
    except Exception as e:
        print("[MENU DEMO] Failed to read cfg:", e)
        return DEFAULT_CFG

def save_cfg(cfg):
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print("[MENU DEMO] Failed to write cfg:", e)

def show_simple_menu():
    cfg = load_cfg()
    active = cfg.get("menu_active_column", "Left")
    columns = cfg.get("columns", {})
    ids = columns.get(active, [])

    menu = QtWidgets.QMenu()
    header = menu.addAction(f"Skyforge MENU DEMO — {active}")
    header.setEnabled(False)
    menu.addSeparator()

    # Construit selon config
    any_added = False
    for aid in ids:
        spec = ACTIONS.get(aid)
        if not spec:
            # action inconnue -> on l’ignore
            continue
        label, fn = spec
        menu.addAction(label, fn)
        any_added = True

    if not any_added:
        menu.addAction("(menu vide) ouvre la palette et Save").setEnabled(False)

    menu.addSeparator()
    menu.addAction("Open Palette Editor", lambda: _act_msg("Ouvre l’autre shelf tool (Palette) 😉"))

    menu.setStyleSheet("""
        QMenu { background:#282828; color:white; border:1px solid #555; padding:6px; font-size:14px; }
        QMenu::item { padding:6px 24px; }
        QMenu::item:selected { background:#505050; }
        QMenu::separator { height:1px; background:#555; margin:6px 10px; }
    """)

    menu.exec(QtGui.QCursor.pos())

show_simple_menu()