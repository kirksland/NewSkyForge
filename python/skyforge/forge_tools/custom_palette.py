# Skyforge DEMO - PALETTE EDITOR v2

from PySide6 import QtWidgets, QtCore, QtGui
import hou, os, json

CFG_PATH = hou.expandString("$HOUDINI_USER_PREF_DIR/skyforge_menu_demo.json")

# ----------------------------
# Demo: "Skyforge-only HDA list"
# Replace this with your real scan (sForge manager.scanFolder etc.)
# For now: fake list, but structured as real IDs.
# ----------------------------
SKYFORGE_HDA_IDS = [
    "skyforge::stash::1.0",
    "skyforge::retopo_brush::1.0",
    "skyforge::edge_loop::1.0",
    "skyforge::relax::1.0",
    "skyforge::quick_subdivide::1.0",
    "skyforge::boolean_magic::0.1",
]

DEFAULT_CFG = {
    "menu": [
        "skyforge::edge_loop::1.0",
        "skyforge::relax::1.0",
    ]
}

# IMPORTANT: ref globale sinon GC
_SKYFORGE_EDITOR_REF = None


# ----------------------------
# IO JSON
# ----------------------------
def load_cfg():
    if not os.path.exists(CFG_PATH):
        save_cfg(DEFAULT_CFG)
        return json.loads(json.dumps(DEFAULT_CFG))
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if "menu" not in cfg or not isinstance(cfg["menu"], list):
            cfg["menu"] = DEFAULT_CFG["menu"]
        return cfg
    except Exception as e:
        print("[PALETTE v2] Failed to read cfg:", e)
        return json.loads(json.dumps(DEFAULT_CFG))

def save_cfg(cfg):
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print("[PALETTE v2] Failed to write cfg:", e)


# ----------------------------
# Drag & drop list widget
# Store action id in UserRole
# ----------------------------
class ActionList(QtWidgets.QListWidget):
    MIME = "application/x-skyforge-action-id"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)

    def mimeTypes(self):
        return [self.MIME]

    def mimeData(self, items):
        md = QtCore.QMimeData()
        if not items:
            return md
        aid = items[0].data(QtCore.Qt.ItemDataRole.UserRole) or ""
        md.setData(self.MIME, aid.encode("utf-8"))
        return md

    def dropMimeData(self, index, data, action):
        # If internal move, QListWidget handles it.
        # If external, we create a new item with same id.
        if not data.hasFormat(self.MIME):
            return False

        aid = bytes(data.data(self.MIME)).decode("utf-8")
        if not aid:
            return False

        # Prevent duplicates in destination list (optional)
        # Uncomment if you want menu to not have duplicates:
        # for i in range(self.count()):
        #     if self.item(i).data(QtCore.Qt.ItemDataRole.UserRole) == aid:
        #         return False

        label = aid  # label = id for now (you can map to nicer names later)
        item = QtWidgets.QListWidgetItem(label)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, aid)

        # Insert at drop position
        row = index
        if row < 0 or row > self.count():
            row = self.count()
        self.insertItem(row, item)
        return True

    def supportedDropActions(self):
        return QtCore.Qt.DropAction.MoveAction | QtCore.Qt.DropAction.CopyAction

    def startDrag(self, supportedActions):
        # Default drag but allow copy between lists if you want later
        super().startDrag(supportedActions)


# ----------------------------
# UI helpers
# ----------------------------
def make_search_line(placeholder):
    le = QtWidgets.QLineEdit()
    le.setPlaceholderText(placeholder)
    le.setClearButtonEnabled(True)
    return le

def apply_filter(list_widget, text):
    t = (text or "").lower().strip()
    for i in range(list_widget.count()):
        it = list_widget.item(i)
        label = (it.text() or "").lower()
        it.setHidden(bool(t) and (t not in label))


class PaletteEditorV2(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Skyforge Palette — Menu Builder (demo v2)")
        self.setWindowFlags(QtCore.Qt.WindowType.Tool)
        self.setMinimumSize(980, 520)

        self.cfg = load_cfg()

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Header
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Menu Builder  ⇐  Drag from Skyforge HDAs")
        title.setStyleSheet("font-size:16px; font-weight:bold; color:#3498DB;")
        header.addWidget(title)
        header.addStretch(1)

        btn_close = QtWidgets.QToolButton()
        btn_close.setText("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.clicked.connect(self.close)
        header.addWidget(btn_close)
        root.addLayout(header)

        # Columns
        cols = QtWidgets.QHBoxLayout()
        cols.setSpacing(10)

        self.left  = self._make_column("Menu Simple", "Search menu items…")
        self.mid   = self._make_column("Skyforge HDAs", "Search HDAs…")
        self.right = self._make_column("Right", "Search…")

        cols.addWidget(self.left["box"])
        cols.addWidget(self.mid["box"])
        cols.addWidget(self.right["box"])
        root.addLayout(cols, 1)

        # Footer
        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)

        btn_reset = QtWidgets.QPushButton("Reset")
        btn_save  = QtWidgets.QPushButton("Save")
        btn_print = QtWidgets.QPushButton("Print JSON path")

        btn_reset.clicked.connect(self._reset)
        btn_save.clicked.connect(self._save)
        btn_print.clicked.connect(self._print_path)

        footer.addWidget(btn_print)
        footer.addWidget(btn_reset)
        footer.addWidget(btn_save)
        root.addLayout(footer)

        # Style
        self.setStyleSheet("""
            QDialog { background:#282828; color:white; }
            QLabel { color:white; }
            QGroupBox { border:1px solid #555; margin-top:8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color:#bbb; }
            QListWidget { background:#1f1f1f; border:1px solid #444; }
            QListWidget::item { padding: 6px; }
            QListWidget::item:selected { background:#505050; }
            QPushButton { padding:6px 10px; }
            QLineEdit { background:#1f1f1f; border:1px solid #444; padding:6px; }
        """)

        # Populate lists
        self._load_lists()

        # Search filters
        self.left["search"].textChanged.connect(lambda t: apply_filter(self.left["list"], t))
        self.mid["search"].textChanged.connect(lambda t: apply_filter(self.mid["list"], t))
        self.right["search"].textChanged.connect(lambda t: apply_filter(self.right["list"], t))

        # Demo interaction: double click removes item (left only)
        self.left["list"].itemDoubleClicked.connect(self._remove_left_item)

    def _make_column(self, title, search_placeholder):
        box = QtWidgets.QGroupBox(title)
        v = QtWidgets.QVBoxLayout(box)
        v.setContentsMargins(8, 12, 8, 8)
        v.setSpacing(6)

        search = make_search_line(search_placeholder)
        lst = ActionList()

        hint = QtWidgets.QLabel("Hint: drag/drop. Left: double-click = remove")
        hint.setStyleSheet("color:#aaa; font-size:12px;")

        v.addWidget(search)
        v.addWidget(lst, 1)
        v.addWidget(hint)

        return {"box": box, "search": search, "list": lst}

    def _load_lists(self):
        # LEFT = cfg menu
        self.left["list"].clear()
        for aid in self.cfg.get("menu", []):
            it = QtWidgets.QListWidgetItem(aid)
            it.setData(QtCore.Qt.ItemDataRole.UserRole, aid)
            self.left["list"].addItem(it)

        # MID = skyforge hdAs (source)
        self.mid["list"].clear()
        for aid in SKYFORGE_HDA_IDS:
            it = QtWidgets.QListWidgetItem(aid)
            it.setData(QtCore.Qt.ItemDataRole.UserRole, aid)
            self.mid["list"].addItem(it)

        # RIGHT = placeholder (empty)
        self.right["list"].clear()
        for aid in ["todo::recent", "todo::favorites", "todo::commands"]:
            it = QtWidgets.QListWidgetItem(aid)
            it.setData(QtCore.Qt.ItemDataRole.UserRole, aid)
            self.right["list"].addItem(it)

    def _remove_left_item(self, item):
        row = self.left["list"].row(item)
        self.left["list"].takeItem(row)

    def _collect_cfg(self):
        menu_ids = []
        for i in range(self.left["list"].count()):
            aid = self.left["list"].item(i).data(QtCore.Qt.ItemDataRole.UserRole)
            if aid:
                menu_ids.append(aid)
        return {"menu": menu_ids}

    def _save(self):
        cfg = self._collect_cfg()
        save_cfg(cfg)

        hou.ui.displayMessage(
            "Saved!\n\nJSON:\n" + CFG_PATH + "\n\nOuvre le shelf tool du menu simple pour voir le menu.",
            severity=hou.severityType.Message
        )
        print("[PALETTE v2] saved:", cfg)

    def _reset(self):
        self.cfg = json.loads(json.dumps(DEFAULT_CFG))
        self._load_lists()
        hou.ui.displayMessage("Reset (not saved yet).", severity=hou.severityType.Message)

    def _print_path(self):
        p = hou.expandString(CFG_PATH)
        print("[PALETTE v2] JSON path:", p)
        hou.ui.displayMessage("JSON path printed in console:\n" + p, severity=hou.severityType.Message)


def show_palette_editor_v2():
    global _SKYFORGE_EDITOR_REF
    try:
        parent = hou.ui.mainQtWindow()
    except Exception:
        parent = None
    _SKYFORGE_EDITOR_REF = PaletteEditorV2(parent=parent)
    _SKYFORGE_EDITOR_REF.move(QtGui.QCursor.pos())
    _SKYFORGE_EDITOR_REF.show()

