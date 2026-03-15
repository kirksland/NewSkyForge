from PySide6 import QtCore, QtGui, QtWidgets
from hutil.qt import python as hpython
from hutil.qt import editors as _editors
import hou
import inspect


# --- Fix PySide6 indentation (override) ---
def _indentation_fixed(self, cursor=None):
    cursor = cursor or self.textCursor()
    start, end = cursor.selectionStart(), cursor.selectionEnd()
    doc = self.document()
    cursor.movePosition(QtGui.QTextCursor.StartOfBlock)
    while doc.characterAt(cursor.position()) == " ":
        cursor.movePosition(QtGui.QTextCursor.Right)
    width = cursor.positionInBlock()
    cursor.setPosition(start)
    cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
    return width


if not hasattr(_editors.CodeEditor, "_indentation_fixed"):
    _editors.CodeEditor._indentation_fixed = _editors.CodeEditor._indentation
    _editors.CodeEditor._indentation = _indentation_fixed


class ScratchpadWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        parent = parent or hou.qt.mainWindow()
        super().__init__(parent)
        self.setWindowTitle("ViewerState Builder")
        self.resize(1200, 750)

        main = QtWidgets.QHBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(8)

        # --- Column 1: Code editor ---
        col1 = QtWidgets.QVBoxLayout()
        self.editor = hpython.PythonEditor()
        self.editor.setPlainText("# write python here")
        self.editor.setGutterVisible(True)
        col1.addWidget(self.editor, 1)

        save_bar = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.clicked.connect(self._save_file)
        self.reset_btn = QtWidgets.QPushButton("Reset Session")
        self.reset_btn.clicked.connect(self._reset_session)
        save_bar.addStretch(1)
        save_bar.addWidget(self.save_btn)
        save_bar.addWidget(self.reset_btn)
        col1.addLayout(save_bar)

        # --- Column 2: Debug + Commit blocks ---
        col2 = QtWidgets.QVBoxLayout()
        dbg = QtWidgets.QGroupBox("Debug")
        dbg_layout = QtWidgets.QVBoxLayout(dbg)
        dbg_layout.addWidget(QtWidgets.QTextEdit("Fake debug output..."))

        commit = QtWidgets.QGroupBox("Commit")
        commit_layout = QtWidgets.QVBoxLayout(commit)
        commit_layout.addWidget(QtWidgets.QTextEdit("Fake commit log..."))

        col2.addWidget(dbg, 1)
        col2.addWidget(commit, 1)

        # --- Column 3: Feature chooser + parameter blocks ---
        col3 = QtWidgets.QVBoxLayout()

        top_form = QtWidgets.QHBoxLayout()
        self.feature_combo = QtWidgets.QComboBox()
        self._feature_classes = self._load_feature_classes()
        self.feature_combo.addItems(sorted(self._feature_classes.keys()))
        add_btn = QtWidgets.QPushButton("Add")
        add_btn.clicked.connect(self._add_block)

        top_form.addWidget(QtWidgets.QLabel("Feature"))
        top_form.addWidget(self.feature_combo, 1)
        top_form.addWidget(add_btn)
        col3.addLayout(top_form)

        self.block_area = QtWidgets.QScrollArea()
        self.block_area.setWidgetResizable(True)
        self.block_container = QtWidgets.QWidget()
        self.block_layout = QtWidgets.QVBoxLayout(self.block_container)
        self.block_layout.addStretch(1)
        self.block_area.setWidget(self.block_container)

        col3.addWidget(self.block_area, 1)

        main.addLayout(col1, 5)
        main.addLayout(col2, 2)
        main.addLayout(col3, 3)

    def _save_file(self):
        path = hou.ui.selectFile(
            title="Save Python",
            file_type=hou.fileType.Any,
            default_value="python_scratch.py",
            chooser_mode=hou.fileChooserMode.Write,
        )
        if not path:
            return
        path = hou.expandString(path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.editor.toPlainText())

    def _reset_session(self):
        try:
            if hasattr(hou.session, "_py_scratchpad"):
                try:
                    hou.session._py_scratchpad.close()
                except Exception:
                    pass
                try:
                    delattr(hou.session, "_py_scratchpad")
                except Exception:
                    pass
        finally:
            self.close()

    def _add_block(self):
        label = self.feature_combo.currentText()
        cls = self._feature_classes.get(label)
        if cls is None:
            return
        block = FeatureParamBlock(label, cls)
        self.block_layout.insertWidget(self.block_layout.count() - 1, block)

    def _load_feature_classes(self):
        out = {}
        try:
            from skyforge.forge_states import features as feature_mod
            names = getattr(feature_mod, "__all__", [])
            for name in names:
                cls = getattr(feature_mod, name, None)
                if cls is not None:
                    out[str(name)] = cls
        except Exception:
            pass
        return out


class CollapsibleSection(QtWidgets.QWidget):
    def __init__(self, title, content, parent=None, toggle_button=None):
        super().__init__(parent)
        self._content = content
        self._toggle = toggle_button
        if self._toggle is None:
            self._toggle = QtWidgets.QToolButton()
            self._toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
            self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(True)
        self._toggle.setArrowType(QtCore.Qt.DownArrow)
        self._toggle.clicked.connect(self._on_toggled)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._content)

        self._content.setVisible(True)

    def _on_toggled(self, checked):
        self._content.setVisible(checked)
        self._toggle.setArrowType(QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow)


class FeatureParamBlock(QtWidgets.QFrame):
    def __init__(self, label, cls):
        super().__init__()
        self._cls = cls
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame { background: #1f1f1f; border: 1px solid #3a3a3a; border-radius: 6px; }"
            "QLabel { color: #d0d0d0; border: none; }"
            "QToolButton { border: none; color: #cfcfcf; }"
            "QGroupBox { border: 1px solid #2f2f2f; margin-top: 8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px 0 4px; }"
            "QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QListWidget { background: #232323; border: 1px solid #333; border-radius: 3px; }"
            "QFormLayout QLabel { background: transparent; border: none; padding: 0; margin: 0; }"
        )

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel(label)
        title.setStyleSheet("QLabel { font-weight: bold; font-size: 12px; }")
        header.addWidget(title, 1)
        toggle = QtWidgets.QToolButton()
        toggle.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        header.addWidget(toggle)
        root.addLayout(header)

        body = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)

        params = self._signature_params(cls)
        init_group = QtWidgets.QGroupBox("__init__ params")
        init_layout = QtWidgets.QFormLayout(init_group)
        init_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        if not params:
            init_layout.addRow(QtWidgets.QLabel("No exposed __init__ params"))
        else:
            for name, default in params:
                widget = self._widget_for_default(default)
                self._set_default(widget, default)
                init_layout.addRow(name, widget)
        body_layout.addWidget(init_group)

        schema = self._builder_schema(cls)
        if schema and schema.get("setup"):
            setup_group = QtWidgets.QGroupBox("Setup actions")
            setup_layout = QtWidgets.QFormLayout(setup_group)
            setup_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
            for spec in schema.get("setup", []):
                row = self._build_setup_row(spec)
                if row is not None:
                    setup_layout.addRow(spec.get("label") or spec.get("method") or "Action", row)
            body_layout.addWidget(setup_group)

        section = CollapsibleSection("Details", body, toggle_button=toggle)
        root.addWidget(section)

    def _signature_params(self, cls):
        try:
            sig = inspect.signature(cls.__init__)
        except Exception:
            return []
        out = []
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            default = None if param.default is inspect._empty else param.default
            out.append((name, default))
        return out

    def _builder_schema(self, cls):
        try:
            fn = getattr(cls, "builder_schema", None)
            if callable(fn):
                return fn()
        except Exception:
            return None
        return None

    def _widget_for_default(self, default):
        if isinstance(default, bool):
            return QtWidgets.QCheckBox()
        if isinstance(default, int) and not isinstance(default, bool):
            w = QtWidgets.QSpinBox()
            w.setRange(-10**9, 10**9)
            return w
        if isinstance(default, float):
            w = QtWidgets.QDoubleSpinBox()
            w.setRange(-1e12, 1e12)
            w.setDecimals(6)
            return w
        return QtWidgets.QLineEdit()

    def _set_default(self, widget, default):
        if default is None:
            return
        if isinstance(widget, QtWidgets.QCheckBox):
            widget.setChecked(bool(default))
        elif isinstance(widget, QtWidgets.QSpinBox):
            widget.setValue(int(default))
        elif isinstance(widget, QtWidgets.QDoubleSpinBox):
            widget.setValue(float(default))
        elif isinstance(widget, QtWidgets.QLineEdit):
            widget.setText(str(default))

    def _build_setup_row(self, spec):
        stype = (spec.get("type") or "").lower().strip()
        default = spec.get("default")
        options = spec.get("options") or []

        if stype == "enum":
            combo = QtWidgets.QComboBox()
            combo.addItems([str(o) for o in options])
            if default is not None:
                idx = combo.findText(str(default))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            return combo

        if stype == "multi_enum":
            w = QtWidgets.QListWidget()
            w.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
            for opt in options:
                item = QtWidgets.QListWidgetItem(str(opt))
                w.addItem(item)
                if default is not None and str(opt) in [str(d) for d in default]:
                    item.setSelected(True)
            w.setMaximumHeight(80)
            return w

        if stype == "bool":
            cb = QtWidgets.QCheckBox()
            cb.setChecked(bool(default))
            return cb

        if stype == "int":
            sp = QtWidgets.QSpinBox()
            sp.setRange(-10**9, 10**9)
            if default is not None:
                sp.setValue(int(default))
            return sp

        if stype == "float":
            sp = QtWidgets.QDoubleSpinBox()
            sp.setRange(-1e12, 1e12)
            sp.setDecimals(6)
            if default is not None:
                sp.setValue(float(default))
            return sp

        line = QtWidgets.QLineEdit()
        if default is not None:
            line.setText(str(default))
        return line


def show_viewerstate_builder():
    # Singleton
    if not hasattr(hou.session, "_py_scratchpad"):
        hou.session._py_scratchpad = ScratchpadWindow()
    hou.session._py_scratchpad.show()
    hou.session._py_scratchpad.raise_()
    hou.session._py_scratchpad.activateWindow()
