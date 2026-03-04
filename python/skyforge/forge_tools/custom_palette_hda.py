# ------------------------------
# custom_palette_hda.py
# ------------------------------


from PySide6 import QtWidgets, QtCore, QtGui
import hou
import os
import json

CFG_PATH = hou.expandString("$HOUDINI_USER_PREF_DIR/skyforge_menu_hda.json")

DEFAULT_CFG = {
    "menu": [
        "header:SkyForge",
        "shelf:SF_reload_python",
    ]
}

# Configure for your setup
SHELF_NAMES = ("skyforge_sh",)
TOOL_MENU_PREFIX = "skyforge"

_SKYFORGE_EDITOR_REF = None
_EDITOR_OBJECT_NAME = "SkyForgePaletteEditorHDA"


# ---------------------------------------------------------
# Paths / IO
# ---------------------------------------------------------
def _package_root():
    # .../SkyForge/python/skyforge/forge_tools/custom_palette_hda.py
    # => package root = .../SkyForge
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )


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


# ---------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------
def _safe_label(value, fallback):
    text = (value or "").strip()
    return text if text else fallback


def _iter_node_types():
    categories = [
        hou.sopNodeTypeCategory(),
        hou.objNodeTypeCategory(),
        hou.vopNodeTypeCategory(),
        hou.ropNodeTypeCategory(),
        hou.cop2NodeTypeCategory(),
        hou.lopNodeTypeCategory(),
    ]

    for category in categories:
        for node_type in category.nodeTypes().values():
            yield category, node_type


def _split_menu_path(path):
    """
    Turn a toolMenuLocation-like string into hierarchical parts.
    Examples:
      "skyforge" -> ["skyforge"]
      "skyforge/state" -> ["skyforge","state"]
      "" -> ["uncategorized"]
    """
    p = (path or "").strip().replace("\\", "/")
    if not p:
        return ["uncategorized"]
    parts = [x.strip() for x in p.split("/") if x.strip()]
    return parts or ["uncategorized"]


def _display_path_part(part):
    # Minimal: keep exact
    return (part or "").strip() or "Other"


# ---------------------------------------------------------
# HDA listing
# ---------------------------------------------------------
def list_package_hdas():
    pkg_root = _package_root().lower()
    out = []
    seen = set()

    for category, node_type in _iter_node_types():
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

        library_abs = os.path.abspath(library_path)
        if not library_abs.lower().startswith(pkg_root):
            continue

        node_type_name = node_type.name()
        if node_type_name in seen:
            continue
        seen.add(node_type_name)

        out.append({
            "action_id": "hda:" + node_type_name,
            "name": node_type_name,
            "label": _safe_label(node_type.description(), node_type_name),
            "category": category.name(),
            "menu_path": "",
            "library_path": library_abs,
        })

    out.sort(key=lambda item: item["label"].lower())
    return out


# ---------------------------------------------------------
# Shelf tools listing
# ---------------------------------------------------------
def _iter_candidate_shelf_tools():
    seen = set()
    shelves = hou.shelves.shelves()

    for shelf_name in SHELF_NAMES:
        shelf = shelves.get(shelf_name)
        if shelf is None:
            continue

        for tool in shelf.tools():
            if tool.name() in seen:
                continue
            seen.add(tool.name())
            yield tool, "shelf:" + shelf_name

    for tool in hou.shelves.tools().values():
        try:
            locs = tool.toolMenuLocations() or ()
        except Exception:
            locs = ()
        if not any((loc or "").startswith(TOOL_MENU_PREFIX) for loc in locs):
            continue
        if tool.name() in seen:
            continue
        seen.add(tool.name())
        yield tool, "tool_menu:" + ", ".join(locs)


def _preferred_tool_menu_path(tool):
    try:
        locs = tool.toolMenuLocations() or ()
    except Exception:
        locs = ()

    for loc in locs:
        loc = (loc or "").strip()
        if loc.startswith(TOOL_MENU_PREFIX):
            return loc

    for loc in locs:
        loc = (loc or "").strip()
        if loc:
            return loc

    return "uncategorized"


def _extract_hda_type_from_tool_script(tool):
    # Best-effort parser for wrapper tools:
    #   soptoolutils.genericTool(kwargs, "foo::bar::1.0")
    try:
        script = tool.script() or ""
    except Exception:
        return None

    marker = "soptoolutils.genericTool"
    if marker not in script:
        return None

    start = script.find(marker)
    if start < 0:
        return None

    open_paren = script.find("(", start)
    if open_paren < 0:
        return None

    close_paren = script.find(")", open_paren)
    if close_paren < 0:
        close_paren = len(script)

    args_text = script[open_paren + 1:close_paren]

    comma = args_text.find(",")
    if comma < 0:
        return None

    tail = args_text[comma + 1:].strip()
    if not tail:
        return None

    quote = tail[0]
    if quote not in ("'", '"'):
        return None

    end = tail.find(quote, 1)
    if end < 0:
        return None

    node_type_name = tail[1:end].strip()
    return node_type_name or None


def build_palette_catalog():
    # 1) HDAs "du package"
    hda_items = list_package_hdas()
    hda_by_name = {item["name"]: item for item in hda_items}

    # 2) Tools split
    nodeless_tools = []

    def _label_for_node_type(node_type_name):
        # label "humain" si Houdini connait le type
        for _cat, nt in _iter_node_types():
            if nt.name() == node_type_name:
                return _safe_label(nt.description(), node_type_name)
        return node_type_name

    for tool, source in _iter_candidate_shelf_tools():
        menu_path = _preferred_tool_menu_path(tool)
        bound_hda = _extract_hda_type_from_tool_script(tool)

        if bound_hda:
            # === NODE TOOL (wrapper genericTool) => on le met côté HDA ===
            # Cas 1: le HDA est déjà dans hda_items (package)
            if bound_hda in hda_by_name:
                # on prend le menu_path du tool (le plus “vrai” pour l’arbo)
                hda_by_name[bound_hda]["menu_path"] = menu_path or hda_by_name[bound_hda].get("menu_path") or "uncategorized"
                # on peut marquer la source (optionnel)
                hda_by_name[bound_hda]["wrapped_by_tool"] = tool.name()
                continue

            # Cas 2: HDA externe / natif : on crée une entrée "hda:" virtuelle
            virtual = {
                "action_id": "hda:" + bound_hda,
                "name": bound_hda,
                "label": _label_for_node_type(bound_hda),
                "category": "wrapped",         # tag
                "menu_path": menu_path or "uncategorized",
                "library_path": "",            # inconnu / pas dans le package
                "wrapped_by_tool": tool.name(),
            }
            hda_items.append(virtual)
            hda_by_name[bound_hda] = virtual
            continue

        # === NODELESS TOOL => reste dans Tools ===
        nodeless_tools.append({
            "action_id": "shelf:" + tool.name(),
            "name": tool.name(),
            "label": _safe_label(tool.label(), tool.name()),
            "source": source,
            "menu_path": menu_path or "uncategorized",
        })

    # normalize + sort
    for item in hda_items:
        if not item.get("menu_path"):
            item["menu_path"] = "uncategorized"

    hda_items.sort(key=lambda item: (item["menu_path"].lower(), item["label"].lower()))
    nodeless_tools.sort(key=lambda item: (item["menu_path"].lower(), item["label"].lower()))
    return hda_items, nodeless_tools


# ---------------------------------------------------------
# Labels
# ---------------------------------------------------------
def label_for_action_id(action_id):
    if action_id == "separator":
        return "----------"

    if action_id.startswith("header:"):
        text = action_id.split(":", 1)[1].strip()
        return "[ " + (text or "Header") + " ]"

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
        for _category, node_type in _iter_node_types():
            if node_type.name() == node_type_name:
                return _safe_label(node_type.description(), node_type_name)
        return node_type_name

    return action_id


# ---------------------------------------------------------
# Drag/drop list
# ---------------------------------------------------------
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
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)

    def mimeTypes(self):
        return [self.MIME]

    def mimeData(self, items):
        md = QtCore.QMimeData()
        if not items:
            return md

        action_id = items[0].data(QtCore.Qt.ItemDataRole.UserRole) or ""
        md.setData(self.MIME, action_id.encode("utf-8"))
        return md

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasFormat(self.MIME) or event.source() is self:
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event):
        md = event.mimeData()
        if md.hasFormat(self.MIME) or event.source() is self:
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event):
        md = event.mimeData()

        # 1) internal reorder
        if event.source() is self and not md.hasFormat(self.MIME):
            super().dropEvent(event)
            self.changed.emit()
            return

        # 2) external drop from trees
        if md.hasFormat(self.MIME):
            action_id = bytes(md.data(self.MIME)).decode("utf-8").strip()
            if not action_id:
                event.ignore()
                return

            label = label_for_action_id(action_id)

            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            row = self.indexAt(pos).row()
            if row < 0:
                row = self.count()

            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, action_id)
            item.setToolTip(action_id)
            self.insertItem(row, item)

            event.acceptProposedAction()
            self.changed.emit()
            return

        event.ignore()

    def supportedDropActions(self):
        return QtCore.Qt.DropAction.MoveAction | QtCore.Qt.DropAction.CopyAction


class ActionTree(QtWidgets.QTreeWidget):
    MIME = "application/x-skyforge-action-id"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        self.setItemsExpandable(True)
        self.setExpandsOnDoubleClick(True)
        self.setAnimated(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)

    def mimeTypes(self):
        return [self.MIME]

    def mimeData(self, items):
        md = QtCore.QMimeData()
        if not items:
            return md

        action_id = items[0].data(0, QtCore.Qt.ItemDataRole.UserRole) or ""
        if action_id:
            md.setData(self.MIME, action_id.encode("utf-8"))
        return md

    def startDrag(self, supported_actions):
        item = self.currentItem()
        if item is None:
            return
        if not item.data(0, QtCore.Qt.ItemDataRole.UserRole):
            return
        super().startDrag(supported_actions)


# ---------------------------------------------------------
# UI helpers
# ---------------------------------------------------------
def make_search_line(placeholder):
    line = QtWidgets.QLineEdit()
    line.setPlaceholderText(placeholder)
    line.setClearButtonEnabled(True)
    return line


def apply_filter(list_widget, text):
    needle = (text or "").lower().strip()

    if isinstance(list_widget, QtWidgets.QTreeWidget):

        def _show_all_descendants(item, show=True):
            item.setHidden(not show)
            for i in range(item.childCount()):
                _show_all_descendants(item.child(i), show)

        def _filter_tree_item(item):
            action_id = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            is_leaf = bool(action_id)

            label = (item.text(0) or "").lower()
            self_match = (not needle) or (needle in label)

            # Leaf: visible only if match (or empty search)
            if is_leaf:
                item.setHidden(not self_match)
                return self_match

            # Folder: if folder matches, show folder + ALL descendants
            if self_match and needle:
                _show_all_descendants(item, True)
                item.setExpanded(True)
                return True

            # Otherwise, filter children normally
            any_child_visible = False
            for i in range(item.childCount()):
                if _filter_tree_item(item.child(i)):
                    any_child_visible = True

            item.setHidden(not any_child_visible and bool(needle))
            if needle and any_child_visible:
                item.setExpanded(True)
            return any_child_visible or (not needle)

        # run on top-level items
        for i in range(list_widget.topLevelItemCount()):
            _filter_tree_item(list_widget.topLevelItem(i))

        return

    # QListWidget case (unchanged)
    for index in range(list_widget.count()):
        item = list_widget.item(index)
        label = (item.text() or "").lower()
        item.setHidden(bool(needle) and needle not in label)
# ---------------------------------------------------------
# Main dialog
# ---------------------------------------------------------
class PaletteEditor(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("SkyForge Palette")
        self.setObjectName(_EDITOR_OBJECT_NAME)
        self.setWindowFlags(QtCore.Qt.WindowType.Tool)
        self.setMinimumSize(1180, 600)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self.cfg = load_cfg()
        self.hda_items, self.tool_items = build_palette_catalog()

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Menu Builder - drag HDA and Tools into the menu")
        title.setStyleSheet("font-size:16px; font-weight:bold; color:#3498DB;")
        header.addWidget(title)
        header.addStretch(1)
        root.addLayout(header)

        cols = QtWidgets.QHBoxLayout()
        cols.setSpacing(10)

        self.left = self._make_column("Menu", "Search menu...")
        self.mid = self._make_tree_column("HDA", "Search HDA...")
        self.right = self._make_tree_column("Tools", "Search tools...")

        cols.addWidget(self.left["box"])
        cols.addWidget(self.mid["box"])
        cols.addWidget(self.right["box"])
        root.addLayout(cols, 1)

        footer = QtWidgets.QHBoxLayout()

        btn_add_sep = QtWidgets.QPushButton("Add Separator")
        btn_add_header = QtWidgets.QPushButton("Add Header")
        btn_print = QtWidgets.QPushButton("Print JSON path")
        btn_reset = QtWidgets.QPushButton("Reset")
        btn_save = QtWidgets.QPushButton("Save")

        btn_add_sep.clicked.connect(self._add_separator)
        btn_add_header.clicked.connect(self._add_header)
        btn_print.clicked.connect(self._print_path)
        btn_reset.clicked.connect(self._reset)
        btn_save.clicked.connect(self._save)

        footer.addWidget(btn_add_sep)
        footer.addWidget(btn_add_header)
        footer.addStretch(1)
        footer.addWidget(btn_print)
        footer.addWidget(btn_reset)
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
            QTreeWidget { background:#1f1f1f; border:1px solid #444; }
            QTreeWidget::item { padding: 4px 6px; }
            QTreeWidget::item:selected { background:#505050; }
            QPushButton { padding:6px 10px; }
            QLineEdit { background:#1f1f1f; border:1px solid #444; padding:6px; }
        """)

        self._load_lists(self.cfg.get("menu", []))

        self.left["search"].textChanged.connect(lambda text: apply_filter(self.left["list"], text))
        self.mid["search"].textChanged.connect(lambda text: apply_filter(self.mid["list"], text))
        self.right["search"].textChanged.connect(lambda text: apply_filter(self.right["list"], text))

        self.left["list"].itemDoubleClicked.connect(self._remove_left_item)

    def _make_column(self, title, search_placeholder):
        box = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        search = make_search_line(search_placeholder)
        lst = ActionList()

        layout.addWidget(search)
        layout.addWidget(lst, 1)

        return {"box": box, "search": search, "list": lst}

    def _make_tree_column(self, title, search_placeholder):
        box = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        search = make_search_line(search_placeholder)
        tree = ActionTree()

        layout.addWidget(search)
        layout.addWidget(tree, 1)

        return {"box": box, "search": search, "list": tree}

    def _add_action_item(self, list_widget, label, action_id):
        item = QtWidgets.QListWidgetItem(label)
        item.setToolTip(action_id)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, action_id)
        list_widget.addItem(item)

    def _load_lists(self, menu_ids):
        # Left: flat menu list (unchanged)
        self.left["list"].clear()
        for action_id in menu_ids:
            self._add_action_item(self.left["list"], label_for_action_id(action_id), action_id)

        # Mid/Right: hierarchical tree (FIXED)
        self._load_hier_tree(self.mid["list"], self.hda_items, "menu_path")
        self._load_hier_tree(self.right["list"], self.tool_items, "menu_path")

    def _load_hier_tree(self, tree, items, path_key):
        tree.clear()
        root = tree.invisibleRootItem()

        # Build hierarchy from path parts
        for it in items:
            parts = _split_menu_path(it.get(path_key))
            parent = root

            for seg in parts:
                seg_disp = _display_path_part(seg)

                # find existing folder under parent
                folder = None
                for i in range(parent.childCount()):
                    c = parent.child(i)
                    # folder nodes have empty UserRole
                    if c.text(0) == seg_disp and not c.data(0, QtCore.Qt.ItemDataRole.UserRole):
                        folder = c
                        break

                if folder is None:
                    folder = QtWidgets.QTreeWidgetItem([seg_disp])
                    folder.setFlags(folder.flags() & ~QtCore.Qt.ItemFlag.ItemIsDragEnabled)
                    folder.setData(0, QtCore.Qt.ItemDataRole.UserRole, "")
                    folder.setExpanded(True)
                    parent.addChild(folder)

                parent = folder

            # Leaf (draggable)
            leaf = QtWidgets.QTreeWidgetItem([it["label"]])
            leaf.setData(0, QtCore.Qt.ItemDataRole.UserRole, it["action_id"])
            leaf.setToolTip(0, it["action_id"])
            parent.addChild(leaf)

        # Sort recursively
        def sort_node(node):
            node.sortChildren(0, QtCore.Qt.SortOrder.AscendingOrder)
            for i in range(node.childCount()):
                sort_node(node.child(i))
        sort_node(root)

    def _current_menu_ids(self):
        result = []
        for index in range(self.left["list"].count()):
            action_id = self.left["list"].item(index).data(QtCore.Qt.ItemDataRole.UserRole)
            if action_id:
                result.append(action_id)
        return result

    def _collect_cfg(self):
        return {"menu": self._current_menu_ids()}

    def _add_separator(self):
        self._add_action_item(self.left["list"], label_for_action_id("separator"), "separator")

    def _add_header(self):
        text, ok = QtWidgets.QInputDialog.getText(
            self,
            "Add Header",
            "Header label:"
        )
        if not ok:
            return

        text = (text or "").strip()
        if not text:
            return

        action_id = "header:" + text
        self._add_action_item(self.left["list"], label_for_action_id(action_id), action_id)

    def _remove_left_item(self, item):
        row = self.left["list"].row(item)
        self.left["list"].takeItem(row)

    def _save(self):
        cfg = self._collect_cfg()
        save_cfg(cfg)
        hou.ui.displayMessage(
            "Saved.\n\nJSON:\n" + CFG_PATH,
            severity=hou.severityType.Message,
        )

    def _reset(self):
        self.cfg = json.loads(json.dumps(DEFAULT_CFG))
        self._load_lists(self.cfg.get("menu", []))
        hou.ui.displayMessage("Reset (not saved yet).", severity=hou.severityType.Message)

    def _print_path(self):
        path = hou.expandString(CFG_PATH)
        print("[SkyForge Palette HDA] JSON path:", path)
        hou.ui.displayMessage(
            "JSON path printed in console:\n" + path,
            severity=hou.severityType.Message,
        )


# ---------------------------------------------------------
# Launcher
# ---------------------------------------------------------
def _find_existing_editor():
    app = QtWidgets.QApplication.instance()
    if app is None:
        return None

    for widget in app.topLevelWidgets():
        try:
            if widget.objectName() == _EDITOR_OBJECT_NAME and widget.isVisible():
                return widget
        except RuntimeError:
            pass
    return None


def show_palette_editor_hda():
    global _SKYFORGE_EDITOR_REF

    existing = _find_existing_editor()
    if existing is not None:
        _SKYFORGE_EDITOR_REF = existing
        existing.raise_()
        existing.activateWindow()
        return

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
