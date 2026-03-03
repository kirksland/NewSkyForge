# Skyforge DEMO - PALETTE EDITOR (customise config du menu simple)
from PySide6 import QtWidgets, QtCore, QtGui
import hou, os, json

CFG_PATH = hou.expandString("$HOUDINI_USER_PREF_DIR/skyforge_menu_demo.json")

ACTIONS = {
    "demo.subd": ("QuickSubdivide (fake)",),
    "demo.reload": ("Reload Python (fake)",),
    "demo.bg": ("Toggle Background (fake)",),
    "demo.clear": ("Clear Console (fake)",),
    "demo.banana": ("Banana",),
    "demo.laser": ("Laser",),
}

DEFAULT_CFG = {
    "columns": {
        "Left":  ["demo.subd", "demo.reload"],
        "Mid":   ["demo.bg", "demo.clear"],
        "Right": ["demo.banana", "demo.laser"]
    },
    "menu_active_column": "Left"
}

# IMPORTANT: ref globale sinon GC
_SKYFORGE_EDITOR_REF = None

def load_cfg():
    if not os.path.exists(CFG_PATH):
        save_cfg(DEFAULT_CFG)
        return DEFAULT_CFG
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if "columns" not in cfg:
            cfg["columns"] = DEFAULT_CFG["columns"]
        if "menu_active_column" not in cfg:
            cfg["menu_active_column"] = DEFAULT_CFG["menu_active_column"]
        return cfg
    except Exception as e:
        print("[PALETTE DEMO] Failed to read cfg:", e)
        return DEFAULT_CFG

def save_cfg(cfg):
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print("[PALETTE DEMO] Failed to write cfg:", e)

class _PaletteEditor(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Skyforge Palette DEMO — Customize Simple Menu")
        self.setWindowFlags(QtCore.Qt.WindowType.Tool)
        self.setMinimumSize(820, 420)

        self.cfg = load_cfg()

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Header
        head = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Palette Editor DEMO (drag & drop entre colonnes)")
        title.setStyleSheet("font-size:16px; font-weight:bold; color:#3498DB;")
        head.addWidget(title)
        head.addStretch(1)

        head.addWidget(QtWidgets.QLabel("Menu simple = colonne active:"))
        self.cmb_active = QtWidgets.QComboBox()
        self.cmb_active.addItems(["Left", "Mid", "Right"])
        self.cmb_active.setCurrentText(self.cfg.get("menu_active_column", "Left"))
        head.addWidget(self.cmb_active)

        btn_close = QtWidgets.QToolButton()
        btn_close.setText("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.clicked.connect(self.close)
        head.addWidget(btn_close)

        root.addLayout(head)

        # Center columns
        center = QtWidgets.QHBoxLayout()
        center.setSpacing(10)

        self.col_left = self._make_column("Left",  "Colonne LEFT")
        self.col_mid  = self._make_column("Mid",   "Colonne MID")
        self.col_right= self._make_column("Right", "Colonne RIGHT")

        center.addWidget(self.col_left["container"])
        center.addWidget(self.col_mid["container"])
        center.addWidget(self.col_right["container"])
        root.addLayout(center, 1)

        # Footer
        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)

        btn_reset = QtWidgets.QPushButton("Reset Default")
        btn_save  = QtWidgets.QPushButton("Save (écrit le JSON)")
        btn_dump  = QtWidgets.QPushButton("Print Config")

        btn_reset.clicked.connect(self._reset)
        btn_save.clicked.connect(self._save)
        btn_dump.clicked.connect(self._dump)

        footer.addWidget(btn_reset)
        footer.addWidget(btn_dump)
        footer.addWidget(btn_save)
        root.addLayout(footer)

        self.setStyleSheet("""
            QDialog { background:#282828; color:white; }
            QLabel { color:white; }
            QGroupBox { border:1px solid #555; margin-top:8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color:#bbb; }
            QListWidget { background:#1f1f1f; border:1px solid #444; }
            QListWidget::item { padding: 6px; }
            QListWidget::item:selected { background:#505050; }
            QPushButton { padding:6px 10px; }
            QComboBox { background:#1f1f1f; border:1px solid #444; padding:4px; }
        """)

        # Load current cfg into lists
        self._apply_cfg_to_lists()

    def _make_column(self, key, title):
        gb = QtWidgets.QGroupBox(title)
        v = QtWidgets.QVBoxLayout(gb)
        v.setContentsMargins(8, 12, 8, 8)

        lst = QtWidgets.QListWidget()
        lst.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        lst.setDragEnabled(True)
        lst.setAcceptDrops(True)
        lst.setDropIndicatorShown(True)
        lst.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        lst.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)

        # Petit hint
        hint = QtWidgets.QLabel("Double-clic = remove (pour la démo)")
        hint.setStyleSheet("color:#aaa; font-size:12px;")

        lst.itemDoubleClicked.connect(lambda it, k=key: self._remove_item(k, it))

        v.addWidget(lst)
        v.addWidget(hint)

        return {"key": key, "container": gb, "list": lst}

    def _apply_cfg_to_lists(self):
        for col in [self.col_left, self.col_mid, self.col_right]:
            col["list"].clear()

        cols = self.cfg.get("columns", {})
        for col in [self.col_left, self.col_mid, self.col_right]:
            key = col["key"]
            for aid in cols.get(key, []):
                if aid in ACTIONS:
                    item = QtWidgets.QListWidgetItem(ACTIONS[aid][0])
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, aid)  # store action id
                    col["list"].addItem(item)

        # Ajouter des actions manquantes (pas dans cfg) dans Mid, juste pour être visible
        all_in_cfg = set(sum(cols.values(), []))
        missing = [aid for aid in ACTIONS.keys() if aid not in all_in_cfg]
        for aid in missing:
            item = QtWidgets.QListWidgetItem(ACTIONS[aid][0] + "  (new)")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, aid)
            self.col_mid["list"].addItem(item)

    def _remove_item(self, col_key, item):
        # Connerie démo: double clic = delete
        row = None
        if col_key == "Left":
            row = self.col_left["list"].row(item)
            self.col_left["list"].takeItem(row)
        elif col_key == "Mid":
            row = self.col_mid["list"].row(item)
            self.col_mid["list"].takeItem(row)
        elif col_key == "Right":
            row = self.col_right["list"].row(item)
            self.col_right["list"].takeItem(row)

    def _lists_to_cfg(self):
        def list_ids(lst):
            ids = []
            for i in range(lst.count()):
                aid = lst.item(i).data(QtCore.Qt.ItemDataRole.UserRole)
                if aid:
                    ids.append(aid)
            return ids

        return {
            "columns": {
                "Left":  list_ids(self.col_left["list"]),
                "Mid":   list_ids(self.col_mid["list"]),
                "Right": list_ids(self.col_right["list"]),
            },
            "menu_active_column": self.cmb_active.currentText()
        }

    def _save(self):
        cfg = self._lists_to_cfg()
        save_cfg(cfg)
        hou.ui.displayMessage(
            f"Saved!\n\n{CFG_PATH}\n\nOuvre le shelf tool du menu simple pour voir le résultat.",
            severity=hou.severityType.Message
        )
        print("[PALETTE DEMO] saved:", cfg)

    def _dump(self):
        cfg = self._lists_to_cfg()
        print("[PALETTE DEMO] current cfg:", json.dumps(cfg, indent=2))
        hou.ui.displayMessage("Config printed to console.", severity=hou.severityType.Message)

    def _reset(self):
        self.cfg = json.loads(json.dumps(DEFAULT_CFG))
        self.cmb_active.setCurrentText(self.cfg["menu_active_column"])
        self._apply_cfg_to_lists()
        hou.ui.displayMessage("Reset to default (pas encore sauvé).", severity=hou.severityType.Message)

def show_palette_editor():
    global _SKYFORGE_EDITOR_REF
    try:
        parent = hou.ui.mainQtWindow()
    except Exception:
        parent = None
    _SKYFORGE_EDITOR_REF = _PaletteEditor(parent=parent)
    _SKYFORGE_EDITOR_REF.move(QtGui.QCursor.pos())
    _SKYFORGE_EDITOR_REF.show()

show_palette_editor()