# ------------------------------
# simple_menu_hda.py
# ------------------------------
# SkyForge - SIMPLE MENU (HDA + Shelf)
#
# Reads JSON { "menu": [ ... ] } written by custom_palette_hda.py
#
# Supports:
#   - shelf:<tool_name>      -> execute shelf tool script
#   - hda:<node_type_name>   -> create HDA node
#   - separator              -> menu separator
#   - header:<text>          -> disabled menu label
#
# For SOP HDAs:
#   - forces a Scene Viewer context for soptoolutils.genericTool()
#   - injects a selected node explicitly (current node first, display node fallback)
#
# Houdini 21 / PySide6

from PySide6 import QtWidgets, QtGui, QtCore
import hou
import os
import json
import soptoolutils

CFG_PATH = hou.expandString("$HOUDINI_USER_PREF_DIR/skyforge_menu_hda.json")


# ---------------------------------------------------------
# IO
# ---------------------------------------------------------
def load_cfg():
    if not os.path.exists(CFG_PATH):
        return {"menu": []}

    try:
        with open(CFG_PATH, "r", encoding="utf-8") as handle:
            cfg = json.load(handle)
        if "menu" not in cfg or not isinstance(cfg["menu"], list):
            cfg["menu"] = []
        return cfg
    except Exception as exc:
        print("[SkyForge Simple Menu HDA] Failed to read config:", exc)
        return {"menu": []}


# ---------------------------------------------------------
# Node type helpers
# ---------------------------------------------------------
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


def _find_node_type(node_type_name):
    for category, node_type in _iter_node_types():
        if node_type.name() == node_type_name:
            return category, node_type
    return None, None


# ---------------------------------------------------------
# Labels
# ---------------------------------------------------------
def _label_for_action_id(action_id):
    if action_id == "separator":
        return ""

    if action_id.startswith("header:"):
        text = action_id.split(":", 1)[1].strip()
        return text or "Header"

    if action_id.startswith("shelf:"):
        tool_name = action_id.split(":", 1)[1]
        try:
            tool = hou.shelves.tool(tool_name)
            if tool is not None:
                return tool.label() or tool.name()
        except Exception:
            pass
        return tool_name

    if action_id.startswith("hda:"):
        node_type_name = action_id.split(":", 1)[1]
        _category, node_type = _find_node_type(node_type_name)
        if node_type is not None:
            return node_type.description() or node_type.name()
        return node_type_name

    return action_id


# ---------------------------------------------------------
# Pane helpers
# ---------------------------------------------------------
def _active_network_editor():
    try:
        return hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    except Exception:
        return None


def _active_scene_viewer():
    try:
        return hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    except Exception:
        return None


# ---------------------------------------------------------
# SOP selection helpers
# ---------------------------------------------------------
def _find_current_or_display_sop(container):
    try:
        for child in container.children():
            try:
                if child.isCurrent():
                    return child
            except Exception:
                pass
    except Exception:
        pass

    try:
        return container.displayNode()
    except Exception:
        return None


def _build_forced_sop_selection():
    net = _active_network_editor()
    if net is None:
        raise RuntimeError("No active Network Editor pane.")

    container = net.pwd()
    if container is None:
        raise RuntimeError("No current network in Network Editor.")

    if container.childTypeCategory() != hou.sopNodeTypeCategory():
        raise RuntimeError(
            "Current Network Editor is not inside a SOP network.\n"
            "Dive inside a SOP context, then try again."
        )

    selectednode = _find_current_or_display_sop(container)

    # Format expected by soptoolutils.genericTool(selection=...)
    # => (container, selections, selectednode)
    return container, [], selectednode


def _build_scene_tool_kwargs(tool_name):
    viewer = _active_scene_viewer()
    if viewer is None:
        raise RuntimeError("No active Scene Viewer pane.")

    return {
        "pane": viewer,
        "toolname": tool_name,
        "scriptargs": {},
    }


# ---------------------------------------------------------
# HDA creation
# ---------------------------------------------------------
def _create_sop_hda(node_type_name):
    category, node_type = _find_node_type(node_type_name)
    if node_type is None:
        raise RuntimeError("Node type not found: " + node_type_name)

    if category != hou.sopNodeTypeCategory():
        raise RuntimeError("Requested SOP creation for non-SOP type: " + node_type_name)

    kwargs = _build_scene_tool_kwargs(node_type_name)
    selection = _build_forced_sop_selection()

    new_node = soptoolutils.genericTool(
        kwargs,
        node_type_name,
        selection=selection,
    )

    # Safety pass: if the node was created but left unconnected, force
    # input 0 to the same source node used to build the synthetic selection.
    try:
        _container, _selections, selectednode = selection
        if (
            isinstance(new_node, hou.SopNode)
            and selectednode is not None
            and len(new_node.inputs()) > 0
            and new_node.inputs()[0] is None
        ):
            new_node.setFirstInput(selectednode)
            if selectednode.isDisplayFlagSet():
                new_node.setDisplayFlag(True)
            if selectednode.isRenderFlagSet():
                new_node.setRenderFlag(True)
    except Exception:
        pass

    return new_node


def _create_non_sop_hda(node_type_name):
    pane = _active_network_editor()
    if pane is None:
        raise RuntimeError("No active Network Editor pane.")

    parent = pane.pwd()
    if parent is None:
        raise RuntimeError("No current network in Network Editor.")

    try:
        new_node = parent.createNode(node_type_name)
    except Exception as exc:
        raise RuntimeError(
            "Failed to create node type '{0}' in {1}:\n{2}".format(
                node_type_name, parent.path(), exc
            )
        )

    try:
        new_node.moveToGoodPosition()
    except Exception:
        try:
            parent.layoutChildren()
        except Exception:
            pass

    try:
        new_node.setSelected(True, clear_all_selected=True)
    except Exception:
        pass

    try:
        pane.setCurrentNode(new_node)
        pane.homeToSelection()
    except Exception:
        pass

    return new_node


def _create_hda(node_type_name):
    category, node_type = _find_node_type(node_type_name)
    if node_type is None:
        raise RuntimeError("Node type not found: " + node_type_name)

    if category == hou.sopNodeTypeCategory():
        return _create_sop_hda(node_type_name)

    return _create_non_sop_hda(node_type_name)


# ---------------------------------------------------------
# Shelf execution
# ---------------------------------------------------------
def _exec_shelf_tool(tool_name):
    tool = hou.shelves.tool(tool_name)
    if tool is None:
        raise RuntimeError("Shelf tool not found: " + tool_name)

    script = tool.script()
    if not script:
        raise RuntimeError("Shelf tool has no script: " + tool_name)

    # Best effort:
    # if we have a Scene Viewer, provide it in kwargs so tools using
    # toolutils.activePane(kwargs) behave more like a real viewer launch.
    try:
        kwargs = _build_scene_tool_kwargs(tool_name)
    except Exception:
        kwargs = {
            "toolname": tool_name,
            "scriptargs": {},
        }

    namespace = {
        "hou": hou,
        "kwargs": kwargs,
    }

    exec(script, namespace, namespace)


# ---------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------
def dispatch(action_id):
    if action_id == "separator":
        return

    if action_id.startswith("header:"):
        return

    if action_id.startswith("shelf:"):
        tool_name = action_id.split(":", 1)[1]
        _exec_shelf_tool(tool_name)
        return

    if action_id.startswith("hda:"):
        node_type_name = action_id.split(":", 1)[1]
        return _create_hda(node_type_name)

    raise RuntimeError("Unsupported action id: " + action_id)


def _safe_dispatch(action_id):
    try:
        dispatch(action_id)
    except Exception as exc:
        print("[SkyForge Simple Menu HDA] ERROR:", exc)
        hou.ui.displayMessage(str(exc), severity=hou.severityType.Error)


def _make_header_widget(text):
    container = QtWidgets.QWidget()
    container.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
    container.setStyleSheet("background: transparent;")

    layout = QtWidgets.QHBoxLayout(container)
    layout.setContentsMargins(12, 6, 12, 4)
    layout.setSpacing(8)

    label = QtWidgets.QLabel(text.upper())
    label.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft)
    label.setStyleSheet("""
        QLabel {
            color: #bda97a;
            background: transparent;
            font-size: 10px;
            font-weight: 600;
            padding: 0;
        }
    """)

    line = QtWidgets.QFrame()
    line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
    line.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
    line.setStyleSheet("color: #4a4a4a; background: transparent;")

    layout.addWidget(label, 0)
    layout.addWidget(line, 1)
    return container


# ---------------------------------------------------------
# UI
# ---------------------------------------------------------
def show():
    cfg = load_cfg()
    items = cfg.get("menu", [])

    menu = QtWidgets.QMenu()
    header = menu.addAction("SkyForge")
    header.setEnabled(False)
    menu.addSeparator()

    if not items:
        menu.addAction("(empty menu, open palette and save)").setEnabled(False)
    else:
        for action_id in items:
            if action_id == "separator":
                menu.addSeparator()
                continue

            if action_id.startswith("header:"):
                title = _label_for_action_id(action_id)
                act = QtWidgets.QWidgetAction(menu)
                act.setDefaultWidget(_make_header_widget(title))
                act.setEnabled(False)
                menu.addAction(act)
                continue

            label = _label_for_action_id(action_id)
            act = menu.addAction(label)
            act.setToolTip(action_id)
            act.triggered.connect(
                lambda checked=False, aid=action_id: _safe_dispatch(aid)
            )

    menu.setStyleSheet("""
        QMenu { background:#282828; color:white; border:1px solid #555; padding:6px; font-size:14px; }
        QMenu::item { padding:6px 24px; }
        QMenu::item:selected { background:#505050; }
        QMenu::item:disabled { color:#8a8a8a; background:transparent; }
        QMenu::separator { height:1px; background:#555; margin:6px 10px; }
    """)

    menu.exec(QtGui.QCursor.pos())
