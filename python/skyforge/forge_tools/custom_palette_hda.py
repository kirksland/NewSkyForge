# ------------------------------
# custom_palette_hda.py  (ACCORDION CATEGORIES, SINGLE COLUMN SCROLL)
# ------------------------------
# SkyForge - PALETTE EDITOR
# Right column is an accordion (click category -> slides open -> items push down).
# IMPORTANT: Each category list has NO internal scrollbar; the whole right column scrolls.
#
# Output JSON action ids:
#   - hda:<node_type_name>
#   - shelf:<tool_name>
#
# Houdini 21 / PySide6

from PySide6 import QtWidgets, QtCore, QtGui
import hou
import os
import json
from collections import defaultdict

CFG_PATH = hou.expandString("$HOUDINI_USER_PREF_DIR/skyforge_menu_hda.json")

DEFAULT_CFG = {"menu": ["shelf:SF_reload_python"]}

# Configure these for your setup
SHELF_NAMES = ("skyforge_sh",)
TOOL_MENU_PREFIX = "skyforge"

# Keep the dialog alive
_SKYFORGE_EDITOR_REF = None


# =========================================================
# Package root
# =========================================================
def _package_root():
    # .../SkyForge/python/skyforge/forge_tools/custom_palette_hda.py
    # => package root = .../SkyForge
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


# =========================================================
# IO
# =========================================================
def load_cfg():
    if not os.path.exists(CFG_PATH):
        save_cfg(DEFAULT_CFG)
        return json.loads(json.dumps(DEFAULT_CFG))
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as handle:
            cfg = json.load(handle)
        if "menu" not in cfg or not isinstance(cfg["menu"], list):
            cfg["menu"] = list(DEFAULT_CFG["menu"])
        return cfg
    except Exception as exc:
        print("[SkyForge Palette HDA] Failed to read config:", exc)
        return json.loads(json.dumps(DEFAULT_CFG))


def save_cfg(cfg):
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as handle:
            json.dump(cfg, handle, indent=2)
    except Exception as exc:
        print("[SkyForge Palette HDA] Failed to write config:", exc)


def _safe_label(value, fallback):
    text = (value or "").strip()
    return text if text else fallback


# =========================================================
# Tool-menu folder parsing
# =========================================================
def _tool_folder_from_locs(locs, prefix="skyforge"):
    """
    Returns a folder path under prefix from toolMenuLocations.
      ["skyforge/modeling/loops"] -> "modeling/loops"
      ["skyforge"]               -> ""   (root)
    If multiple locations, pick the deepest under prefix.
    """
    best = ""
    for loc in (locs or ()):
        loc = (loc or "").strip()
        if not loc.startswith(prefix):
            continue
        rest = loc[len(prefix):].lstrip("/")
        if len(rest) > len(best):
            best = rest
    return best  # "" means root under prefix


# =========================================================
# Sources: Shelf tools + tool menu locations
# =========================================================
def list_shelf_tools():
    seen = set()
    out = []

    shelves = hou.shelves.shelves()

    # A) tools from explicit shelf tabs
    for shelf_name in SHELF_NAMES:
        shelf = shelves.get(shelf_name)
        if shelf is None:
            continue

        for tool in shelf.tools():
            if tool.name() in seen:
                continue
            seen.add(tool.name())

            out.append({
                "action_id": "shelf:" + tool.name(),
                "name": tool.name(),
                "label": _safe_label(tool.label(), tool.name()),
                "source": "shelf",
                "folder": f"Shelf/{shelf_name}",
                "meta": shelf_name,
            })

    # B) tools visible in toolMenuLocations prefix
    for tool in hou.shelves.tools().values():
        locs = tool.toolMenuLocations() or ()
        if not any((loc or "").startswith(TOOL_MENU_PREFIX) for loc in locs):
            continue
        if tool.name() in seen:
            continue
        seen.add(tool.name())

        folder = _tool_folder_from_locs(locs, TOOL_MENU_PREFIX)  # "" = root
        folder_title = "Skyforge" + (f"/{folder}" if folder else "")

        out.append({
            "action_id": "shelf:" + tool.name(),
            "name": tool.name(),
            "label": _safe_label(tool.label(), tool.name()),
            "source": "tool_menu",
            "folder": folder_title,
            "meta": ", ".join(locs),
        })

    out.sort(key=lambda item: item["label"].lower())
    return out


# =========================================================
# HDA scan (from package root)
# =========================================================
def _iter_all_node_types():
    categories = [
        hou.sopNodeTypeCategory(),
        hou.objNodeTypeCategory(),
        hou.vopNodeTypeCategory(),
        hou.ropNodeTypeCategory(),
        hou.cop2NodeTypeCategory(),
        hou.lopNodeTypeCategory(),
        hou.dopNodeTypeCategory(),
        hou.chopNodeTypeCategory(),
        hou.topNodeTypeCategory(),
    ]
    for category in categories:
        for node_type in category.nodeTypes().values():
            yield category, node_type


def list_package_hdas():
    pkg_root = _package_root().lower()
    out = []
    seen = set()

    for category, node_type in _iter_all_node_types():
        try:
            definition = node_type.definition()
        except Exception:
            definition = None
        if definition is None:
            continue

        try:
            library_path = definition.libraryFilePath()
        except Exception:
            library_path = ""
        if not library_path:
            continue

        if not os.path.abspath(library_path).lower().startswith(pkg_root):
            continue

        node_type_name = node_type.name()
        if node_type_name in seen:
            continue
        seen.add(node_type_name)

        label = _safe_label(node_type.description(), node_type_name)

        out.append({
            "action_id": "hda:" + node_type_name,
            "name": node_type_name,
            "label": label,
            "category": category.name(),
            "library_path": library_path,
        })

    out.sort(key=lambda item: item["label"].lower())
    return out


def label_for_action_id(action_id):
    if action_id.startswith("shelf:"):
        tool_name = action_id.split(":", 1)[1]
        try:
            tool = hou.shelves.tool(tool_name)
            if tool is not None:
                return _safe_label(tool.label(), tool.name())
        except Exception:
            pass
        return tool_name

    if action_id.startswith("hda:"):
        node_type_name = action_id.split(":", 1)[1]
        for _category, node_type in _iter_all_node_types():
            if node_type.name() == node_type_name:
                return _safe_label(node_type.description(), node_type_name)
        return node_type_name

    return action_id


# =========================================================
# Left list (menu) drag/drop target
# =========================================================
class ActionList(QtWidgets.QListWidget):
    MIME = "application/x-skyforge-action-id"
    changed = QtCore.Signal()

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
        action_id = items[0].data(QtCore.Qt.ItemDataRole.UserRole) or ""
        md.setData(self.MIME, action_id.encode("utf-8"))
        return md

    def dropMimeData(self, index, data, action):
        if not data.hasFormat(self.MIME):
            return False

        action_id = bytes(data.data(self.MIME)).decode("utf-8")
        if not action_id:
            return False

        item = QtWidgets.QListWidgetItem(label_for_action_id(action_id))
        item.setData(QtCore.Qt.ItemDataRole.UserRole, action_id)
        item.setToolTip(action_id)

        row = index
        if row < 0 or row > self.count():
            row = self.count()

        self.insertItem(row, item)
        self.changed.emit()
        return True

    def supportedDropActions(self):
        return QtCore.Qt.DropAction.MoveAction | QtCore.Qt.DropAction.CopyAction


# =========================================================
# Right accordion: Drag-only lists per category (AUTO HEIGHT)
# =========================================================
class DragList(QtWidgets.QListWidget):
    MIME = ActionList.MIME

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragOnly)
        self.setDefaultDropAction(QtCore.Qt.DropAction.CopyAction)

        # IMPORTANT: no internal scrollbars
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setUniformItemSizes(True)

    def mimeTypes(self):
        return [self.MIME]

    def mimeData(self, items):
        md = QtCore.QMimeData()
        if not items:
            return md
        aid = items[0].data(QtCore.Qt.ItemDataRole.UserRole) or ""
        md.setData(self.MIME, aid.encode("utf-8"))
        return md

    def _visible_row_count(self) -> int:
        c = 0
        for i in range(self.count()):
            it = self.item(i)
            if it is not None and not it.isHidden():
                c += 1
        return c

    def update_height(self):
        rows = self._visible_row_count()
        if rows <= 0:
            h = self.frameWidth() * 2 + 8
            self.setFixedHeight(h)
            return

        row_h = self.sizeHintForRow(0)
        if row_h < 1:
            row_h = 24

        h = (row_h * rows) + (self.frameWidth() * 2) + 2
        self.setFixedHeight(h)


class AccordionSection(QtWidgets.QWidget):
    def __init__(self, title: str, content: QtWidgets.QWidget, parent=None):
        super().__init__(parent)

        self.btn = QtWidgets.QToolButton()
        self.btn.setText(title)
        self.btn.setCheckable(True)
        self.btn.setChecked(False)
        self.btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.btn.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

        self.content = content
        self.content.setMaximumHeight(0)
        self.content.setMinimumHeight(0)
        self.content.setVisible(False)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addWidget(self.btn)
        lay.addWidget(self.content)

        self.anim = QtCore.QPropertyAnimation(self.content, b"maximumHeight", self)
        self.anim.setDuration(160)
        self.anim.setEasingCurve(QtCore.QEasingCurve.Type.InOutCubic)

        self.btn.toggled.connect(self.set_expanded)
        self.anim.finished.connect(self._on_anim_finished)

    def _on_anim_finished(self):
        if not self.btn.isChecked():
            self.content.setVisible(False)

    def set_expanded(self, on: bool):
        self.btn.setArrowType(QtCore.Qt.ArrowType.DownArrow if on else QtCore.Qt.ArrowType.RightArrow)

        # keep height in sync before anim
        if hasattr(self.content, "update_height"):
            try:
                self.content.update_height()
            except Exception:
                pass

        self.anim.stop()
        if on:
            self.content.setVisible(True)
            target = max(20, self.content.height())
            self.anim.setStartValue(self.content.maximumHeight())
            self.anim.setEndValue(target)
            self.anim.start()
        else:
            self.anim.setStartValue(self.content.maximumHeight())
            self.anim.setEndValue(0)
            self.anim.start()


class Accordion(QtWidgets.QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        self._body = QtWidgets.QWidget()
        self._layout = QtWidgets.QVBoxLayout(self._body)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._layout.addStretch(1)

        self.setWidget(self._body)
        self.sections = []

    def clear(self):
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self.sections = []

    def add_section(self, title: str, content: QtWidgets.QWidget):
        sec = AccordionSection(title, content)
        self._layout.insertWidget(self._layout.count() - 1, sec)
        self.sections.append(sec)
        return sec


# =========================================================
# UI helpers
# =========================================================
def make_search_line(placeholder):
    line = QtWidgets.QLineEdit()
    line.setPlaceholderText(placeholder)
    line.setClearButtonEnabled(True)
    return line


def apply_filter_list(list_widget, text):
    needle = (text or "").lower().strip()
    for i in range(list_widget.count()):
        it = list_widget.item(i)
        label = (it.text() or "").lower()
        it.setHidden(bool(needle) and needle not in label)


def apply_filter_accordion(acc: Accordion, text: str):
    """
    Filter items inside each section's DragList.
    Hide entire section if no items visible.
    Expand matching sections when filtering.
    Update list heights so accordion size stays correct.
    """
    needle = (text or "").lower().strip()

    for sec in acc.sections:
        lst = sec.content
        any_visible = False

        for i in range(lst.count()):
            it = lst.item(i)
            label = (it.text() or "").lower()
            visible = (not needle) or (needle in label)
            it.setHidden(not visible)
            any_visible = any_visible or visible

        if hasattr(lst, "update_height"):
            try:
                lst.update_height()
            except Exception:
                pass

        sec.setHidden(bool(needle) and not any_visible)
        if needle and any_visible:
            sec.btn.setChecked(True)


# =========================================================
# Dialog
# =========================================================
class PaletteEditor(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("SkyForge Palette - HDA + Tools (Accordion)")
        self.setWindowFlags(QtCore.Qt.WindowType.Tool)
        self.setMinimumSize(1180, 600)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self.cfg = load_cfg()

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Menu Builder - drag HDA and Tools into the menu")
        title.setStyleSheet("font-size:16px; font-weight:bold; color:#3498DB;")
        header.addWidget(title)
        header.addStretch(1)

        btn_close = QtWidgets.QToolButton()
        btn_close.setText("X")
        btn_close.setFixedSize(28, 28)
        btn_close.clicked.connect(self.close)
        header.addWidget(btn_close)
        root.addLayout(header)

        cols = QtWidgets.QHBoxLayout()
        cols.setSpacing(10)

        self.left = self._make_list_column("Menu", "Search menu...")
        self.mid = self._make_list_column("HDA", "Search HDA...")
        self.right = self._make_accordion_column("Tools (categories)", "Search tools...")

        cols.addWidget(self.left["box"])
        cols.addWidget(self.mid["box"])
        cols.addWidget(self.right["box"])
        root.addLayout(cols, 1)

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)

        btn_reset = QtWidgets.QPushButton("Reset")
        btn_save = QtWidgets.QPushButton("Save")
        btn_print = QtWidgets.QPushButton("Print JSON path")

        btn_reset.clicked.connect(self._reset)
        btn_save.clicked.connect(self._save)
        btn_print.clicked.connect(self._print_path)

        footer.addWidget(btn_print)
        footer.addWidget(btn_reset)
        footer.addWidget(btn_save)
        root.addLayout(footer)

        # Keep your existing design style (unchanged vibe)
        self.setStyleSheet("""
            QDialog { background:#282828; color:white; }
            QLabel { color:white; }
            QGroupBox { border:1px solid #555; margin-top:8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color:#bbb; }
            QListWidget { background:#1f1f1f; border:1px solid #444; }
            QListWidget::item { padding: 6px; }
            QListWidget::item:selected { background:#505050; }
            QScrollArea { background:transparent; }
            QToolButton { padding:6px; border:1px solid #444; background:#1f1f1f; }
            QToolButton:checked { background:#242424; }
            QPushButton { padding:6px 10px; }
            QLineEdit { background:#1f1f1f; border:1px solid #444; padding:6px; }
        """)

        self.hda_items = list_package_hdas()
        self.tool_items = list_shelf_tools()

        self._load_lists(self.cfg.get("menu", []))

        self.left["search"].textChanged.connect(lambda text: apply_filter_list(self.left["list"], text))
        self.mid["search"].textChanged.connect(lambda text: apply_filter_list(self.mid["list"], text))
        self.right["search"].textChanged.connect(lambda text: apply_filter_accordion(self.right["acc"], text))

        self.left["list"].itemDoubleClicked.connect(self._remove_left_item)

    def _make_list_column(self, title, search_placeholder):
        box = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        search = make_search_line(search_placeholder)
        lst = ActionList()

        layout.addWidget(search)
        layout.addWidget(lst, 1)

        return {"box": box, "search": search, "list": lst}

    def _make_accordion_column(self, title, search_placeholder):
        box = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        search = make_search_line(search_placeholder)
        acc = Accordion()

        layout.addWidget(search)
        layout.addWidget(acc, 1)

        return {"box": box, "search": search, "acc": acc}

    def _add_action_item_list(self, list_widget, label, action_id):
        item = QtWidgets.QListWidgetItem(label)
        item.setToolTip(action_id)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, action_id)
        list_widget.addItem(item)

    def _load_lists(self, menu_ids):
        # LEFT
        self.left["list"].clear()
        for action_id in menu_ids:
            self._add_action_item_list(self.left["list"], label_for_action_id(action_id), action_id)

        # MID (HDAs)
        self.mid["list"].clear()
        for item in self.hda_items:
            self._add_action_item_list(self.mid["list"], item["label"], item["action_id"])

        # RIGHT (Accordion)
        acc = self.right["acc"]
        acc.clear()

        groups = defaultdict(list)
        for it in self.tool_items:
            groups[it.get("folder", "Misc")].append(it)

        # Sort folders (Skyforge near top)
        folder_names = sorted(groups.keys(), key=lambda s: (not s.lower().startswith("skyforge"), s.lower()))

        for folder in folder_names:
            lst = DragList()
            lst.setStyleSheet("QListWidget { border:1px solid #333; } QListWidget::item { padding:6px; }")

            for it in sorted(groups[folder], key=lambda x: x["label"].lower()):
                item = QtWidgets.QListWidgetItem(it["label"])
                item.setToolTip(it["action_id"])
                item.setData(QtCore.Qt.ItemDataRole.UserRole, it["action_id"])
                lst.addItem(item)

            # important: auto-height (no internal scroll)
            lst.update_height()

            sec = acc.add_section(folder, lst)

            # Auto expand Skyforge root
            if folder == "Skyforge":
                sec.btn.setChecked(True)

    def _remove_left_item(self, item):
        row = self.left["list"].row(item)
        self.left["list"].takeItem(row)

    def _current_menu_ids(self):
        res = []
        for i in range(self.left["list"].count()):
            action_id = self.left["list"].item(i).data(QtCore.Qt.ItemDataRole.UserRole)
            if action_id:
                res.append(action_id)
        return res

    def _collect_cfg(self):
        return {"menu": self._current_menu_ids()}

    def _save(self):
        cfg = self._collect_cfg()
        save_cfg(cfg)
        print("[SkyForge Palette HDA] saved:", cfg)
        hou.ui.displayMessage("Saved.\n\nJSON:\n" + CFG_PATH, severity=hou.severityType.Message)

    def _reset(self):
        self.cfg = json.loads(json.dumps(DEFAULT_CFG))
        self._load_lists(self.cfg.get("menu", []))
        hou.ui.displayMessage("Reset (not saved yet).", severity=hou.severityType.Message)

    def _print_path(self):
        path = hou.expandString(CFG_PATH)
        print("[SkyForge Palette HDA] JSON path:", path)
        hou.ui.displayMessage("JSON path printed in console:\n" + path, severity=hou.severityType.Message)


def show_palette_editor_hda():
    global _SKYFORGE_EDITOR_REF

    try:
        if _SKYFORGE_EDITOR_REF is not None and _SKYFORGE_EDITOR_REF.isVisible():
            _SKYFORGE_EDITOR_REF.raise_()
            _SKYFORGE_EDITOR_REF.activateWindow()
            return
    except RuntimeError:
        _SKYFORGE_EDITOR_REF = None

    try:
        parent = hou.ui.mainQtWindow()
    except Exception:
        parent = None

    _SKYFORGE_EDITOR_REF = PaletteEditor(parent=parent)
    _SKYFORGE_EDITOR_REF.move(QtGui.QCursor.pos())
    _SKYFORGE_EDITOR_REF.show()
    _SKYFORGE_EDITOR_REF.raise_()
    _SKYFORGE_EDITOR_REF.activateWindow()