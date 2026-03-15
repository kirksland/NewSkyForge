from PySide6 import QtGui, QtWidgets
from hutil.qt import python as hpython
from hutil.qt import editors as _editors
import hou


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
        self.setWindowTitle("Python Scratchpad")
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
        save_bar.addStretch(1)
        save_bar.addWidget(self.save_btn)
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
        self.feature_combo.addItems([
            "HoverGadgetFeature",
            "AstarTurnFeature",
            "TransversalLoopFeature",
            "HoverMoveFeature",
            "HoverDrawFeature",
        ])
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

    def _add_block(self):
        label = self.feature_combo.currentText()
        block = QtWidgets.QGroupBox(label)
        layout = QtWidgets.QFormLayout(block)
        layout.addRow("Param A", QtWidgets.QLineEdit("42"))
        layout.addRow("Param B", QtWidgets.QLineEdit("foo"))
        layout.addRow("Enabled", QtWidgets.QCheckBox())
        self.block_layout.insertWidget(self.block_layout.count() - 1, block)


def show_viewerstate_builder():
    # Singleton
    if not hasattr(hou.session, "_py_scratchpad"):
        hou.session._py_scratchpad = ScratchpadWindow()
    hou.session._py_scratchpad.show()
    hou.session._py_scratchpad.raise_()
    hou.session._py_scratchpad.activateWindow()
