from PySide6 import QtCore, QtGui, QtWidgets
from hutil.qt import python as hpython
from hutil.qt import editors as _editors
import hou
import inspect
import os
import textwrap


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

        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(8)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)
        main.addWidget(splitter, 1)

        # --- Column 1: Code editor ---
        col1_widget = QtWidgets.QWidget()
        col1 = QtWidgets.QVBoxLayout(col1_widget)
        self.editor = hpython.PythonEditor()
        self.editor.setPlainText("# write python here")
        self.editor.setGutterVisible(True)
        col1.addWidget(self.editor, 1)

        save_bar = QtWidgets.QHBoxLayout()
        self.save_path_edit = QtWidgets.QLineEdit("")
        self.save_path_edit.setPlaceholderText("Save path...")
        save_bar.addWidget(self.save_path_edit, 2)
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.clicked.connect(self._save_file)
        self.reset_btn = QtWidgets.QPushButton("Reset Session")
        self.reset_btn.clicked.connect(self._reset_session)
        save_bar.addStretch(1)
        save_bar.addWidget(self.save_btn)
        save_bar.addWidget(self.reset_btn)
        col1.addLayout(save_bar)

        # --- Column 2: Debug + Commit tabs ---
        col2_widget = QtWidgets.QWidget()
        col2 = QtWidgets.QVBoxLayout(col2_widget)
        tabs = QtWidgets.QTabWidget()
        dbg = QtWidgets.QWidget()
        dbg_layout = QtWidgets.QVBoxLayout(dbg)
        self.debug_text = QtWidgets.QTextEdit()
        self.debug_text.setReadOnly(True)
        self.debug_text.setPlaceholderText("Debug output...")
        dbg_bar = QtWidgets.QHBoxLayout()
        self.clear_debug_btn = QtWidgets.QPushButton("Clear Debug")
        self.clear_debug_btn.clicked.connect(self._clear_debug)
        dbg_bar.addStretch(1)
        dbg_bar.addWidget(self.clear_debug_btn)
        dbg_layout.addLayout(dbg_bar)
        dbg_layout.addWidget(self.debug_text)
        commit = QtWidgets.QWidget()
        commit_layout = QtWidgets.QVBoxLayout(commit)
        self.commit_text = QtWidgets.QTextEdit()
        self.commit_text.setReadOnly(True)
        self.commit_text.setPlaceholderText("Commit log...")
        commit_layout.addWidget(self.commit_text)
        tabs.addTab(dbg, "Debug")
        tabs.addTab(commit, "Commit")
        col2.addWidget(tabs, 1)

        list_tabs = QtWidgets.QTabWidget()

        states_box = QtWidgets.QWidget()
        states_layout = QtWidgets.QVBoxLayout(states_box)
        self.state_list = QtWidgets.QListWidget()
        self.state_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        states_layout.addWidget(self.state_list, 1)
        states_bar = QtWidgets.QHBoxLayout()
        self.refresh_states_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_states_btn.clicked.connect(self._refresh_state_list)
        self.open_state_btn = QtWidgets.QPushButton("Open In Editor")
        self.open_state_btn.clicked.connect(self._open_selected_state)
        states_bar.addStretch(1)
        states_bar.addWidget(self.refresh_states_btn)
        states_bar.addWidget(self.open_state_btn)
        states_layout.addLayout(states_bar)
        list_tabs.addTab(states_box, "ViewerStates")

        features_box = QtWidgets.QWidget()
        features_layout = QtWidgets.QVBoxLayout(features_box)
        self.feature_list = QtWidgets.QListWidget()
        self.feature_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        features_layout.addWidget(self.feature_list, 1)
        features_bar = QtWidgets.QHBoxLayout()
        self.refresh_features_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_features_btn.clicked.connect(self._refresh_feature_list)
        self.open_feature_btn = QtWidgets.QPushButton("Open In Editor")
        self.open_feature_btn.clicked.connect(self._open_selected_feature)
        self.create_feature_btn = QtWidgets.QPushButton("Create")
        self.create_feature_btn.clicked.connect(self._create_feature_template)
        features_bar.addStretch(1)
        features_bar.addWidget(self.refresh_features_btn)
        features_bar.addWidget(self.open_feature_btn)
        features_bar.addWidget(self.create_feature_btn)
        features_layout.addLayout(features_bar)
        list_tabs.addTab(features_box, "Features")

        col2.addWidget(list_tabs, 1)

        # --- Column 3: Feature chooser + parameter blocks ---
        col3_widget = QtWidgets.QWidget()
        col3 = QtWidgets.QVBoxLayout(col3_widget)

        state_form = QtWidgets.QHBoxLayout()
        self.state_name_edit = QtWidgets.QLineEdit("my_state")
        state_form.addWidget(QtWidgets.QLabel("State Name"))
        state_form.addWidget(self.state_name_edit, 1)
        col3.addLayout(state_form)

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

        gen_bar = QtWidgets.QHBoxLayout()
        self.gen_btn = QtWidgets.QPushButton("Generate")
        self.gen_btn.clicked.connect(self._generate_code)
        self.preview_btn = QtWidgets.QPushButton("Preview Context")
        self.preview_btn.clicked.connect(self._preview_context)
        self.append_check = QtWidgets.QCheckBox("Append")
        gen_bar.addStretch(1)
        gen_bar.addWidget(self.append_check)
        gen_bar.addWidget(self.preview_btn)
        gen_bar.addWidget(self.gen_btn)
        col3.addLayout(gen_bar)

        splitter.addWidget(col1_widget)
        splitter.addWidget(col2_widget)
        splitter.addWidget(col3_widget)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 3)
        splitter.setSizes([700, 300, 450])

        self._refresh_state_list()
        self._refresh_feature_list()

    def _save_file(self):
        default_path = self.save_path_edit.text().strip() or "python_scratch.py"
        path = hou.ui.selectFile(
            title="Save Python",
            file_type=hou.fileType.Any,
            default_value=default_path,
            chooser_mode=hou.fileChooserMode.Write,
        )
        if not path:
            return
        path = hou.expandString(path)
        self.save_path_edit.setText(path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.editor.toPlainText())

    def _refresh_state_list(self):
        self.state_list.clear()
        try:
            base_path = hou.expandString("$HPD/viewerState")
        except Exception:
            base_path = ""
        files = []
        if os.path.isdir(base_path):
            try:
                for name in os.listdir(base_path):
                    if not name.lower().endswith(".py"):
                        continue
                    files.append(os.path.join(base_path, name))
            except Exception:
                pass
        for path in sorted(set(files), key=lambda s: s.lower()):
            item = QtWidgets.QListWidgetItem(os.path.basename(path))
            item.setData(QtCore.Qt.UserRole, path)
            self.state_list.addItem(item)

    def _open_selected_state(self):
        item = self.state_list.currentItem()
        if item is None:
            return
        path = item.data(QtCore.Qt.UserRole)
        if not path or not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            return
        self.editor.setPlainText(text)
        self.save_path_edit.setText(path)

    def _refresh_feature_list(self):
        self.feature_list.clear()
        try:
            base_path = hou.expandString("$HPD/python/skyforge/forge_states/features")
        except Exception:
            base_path = ""
        files = []
        if os.path.isdir(base_path):
            try:
                for name in os.listdir(base_path):
                    if not name.lower().endswith(".py"):
                        continue
                    files.append(os.path.join(base_path, name))
            except Exception:
                pass
        for path in sorted(set(files), key=lambda s: s.lower()):
            item = QtWidgets.QListWidgetItem(os.path.basename(path))
            item.setData(QtCore.Qt.UserRole, path)
            self.feature_list.addItem(item)

    def _open_selected_feature(self):
        item = self.feature_list.currentItem()
        if item is None:
            return
        path = item.data(QtCore.Qt.UserRole)
        if not path or not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            return
        self.editor.setPlainText(text)
        self.save_path_edit.setText(path)

    def _create_feature_template(self):
        base_dir = ""
        try:
            base_dir = hou.expandString("$HPD/python/skyforge/forge_states/features")
        except Exception:
            base_dir = ""
        if not base_dir or not os.path.isdir(base_dir):
            QtWidgets.QMessageBox.warning(self, "Create Feature", "Feature folder not found.")
            return

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Create Feature Template")
        layout = QtWidgets.QVBoxLayout(dialog)

        form = QtWidgets.QFormLayout()
        class_edit = QtWidgets.QLineEdit("NewFeature")
        file_edit = QtWidgets.QLineEdit("new_feature.py")
        provides_edit = QtWidgets.QLineEdit("")
        requires_edit = QtWidgets.QLineEdit("")
        hover_check = QtWidgets.QCheckBox("Require hover service")
        preview_check = QtWidgets.QCheckBox("Require preview service")
        form.addRow("Class Name", class_edit)
        form.addRow("File Name", file_edit)
        form.addRow("Provides (csv)", provides_edit)
        form.addRow("Requires (csv)", requires_edit)
        form.addRow("", hover_check)
        form.addRow("", preview_check)
        layout.addLayout(form)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        def _sync_filename():
            name = class_edit.text().strip()
            if not name:
                return
            snake = self._snake_case(name)
            file_edit.setText(snake + ".py")

        class_edit.textChanged.connect(_sync_filename)

        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        class_name = class_edit.text().strip()
        file_name = file_edit.text().strip()
        if not class_name:
            QtWidgets.QMessageBox.warning(self, "Create Feature", "Class name is required.")
            return
        if not file_name:
            file_name = self._snake_case(class_name) + ".py"
        if not file_name.lower().endswith(".py"):
            file_name += ".py"

        path = os.path.join(base_dir, file_name)
        if os.path.exists(path):
            QtWidgets.QMessageBox.warning(self, "Create Feature", "File already exists:\n%s" % path)
            return

        provides = self._parse_csv(provides_edit.text())
        requires = self._parse_csv(requires_edit.text())
        if hover_check.isChecked() and "hover" not in requires:
            requires.append("hover")
        if preview_check.isChecked() and "preview" not in requires:
            requires.append("preview")

        text = self._feature_template_text(
            class_name=class_name,
            provides=provides,
            requires=requires,
            include_hover=hover_check.isChecked(),
            include_preview=preview_check.isChecked(),
        )

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            QtWidgets.QMessageBox.warning(self, "Create Feature", "Failed to write file.")
            return

        self._update_features_init(file_name, class_name)
        self._refresh_feature_list()
        self.editor.setPlainText(text)
        self.save_path_edit.setText(path)

    def _snake_case(self, name):
        out = []
        for i, ch in enumerate(name):
            if ch.isupper() and i > 0 and (not name[i - 1].isupper()):
                out.append("_")
            out.append(ch.lower())
        return "".join(out).strip("_")

    def _parse_csv(self, text):
        out = []
        for part in (text or "").replace(";", ",").split(","):
            item = part.strip()
            if item:
                out.append(item)
        return out

    def _feature_template_text(self, class_name, provides, requires, include_hover=False, include_preview=False):
        provides_txt = ", ".join(["'%s'" % p for p in provides])
        requires_txt = ", ".join(["'%s'" % r for r in requires])
        if provides:
            provides_line = "provides = ({0})".format(provides_txt if len(provides) > 1 else provides_txt + ",")
        else:
            provides_line = "provides = ()"
        if requires:
            requires_line = "requires = ({0})".format(requires_txt if len(requires) > 1 else requires_txt + ",")
        else:
            requires_line = "requires = ()"

        bind_lines = []
        if include_hover:
            bind_lines.append("self.hover = ctx.get_service('hover')")
        if include_preview:
            bind_lines.append("self.preview = ctx.get_service('preview')")
        if not bind_lines:
            bind_lines = ["pass"]
        bind_lines = ["        " + line for line in bind_lines]

        lines = [
            "from skyforge.forge_states.feature_base import ViewerFeature",
            "",
            "",
            "class {0}(ViewerFeature):".format(class_name),
            "    name = \"{0}\"".format(self._snake_case(class_name)),
            "    {0}".format(provides_line),
            "    {0}".format(requires_line),
            "",
            "    def __init__(self):",
            "        super().__init__()",
            "        self.hover = None",
            "        self.preview = None",
            "",
            "    # Optional: expose knobs for the Builder",
            "    @staticmethod",
            "    def builder_schema():",
            "        return {",
            "            \"setup\": [",
            "                # { \"label\": \"Mode\", \"method\": \"set_mode\", \"type\": \"enum\", \"options\": [\"a\", \"b\"], \"default\": \"a\" },",
            "            ]",
            "        }",
            "",
            "    def on_enter(self, ctx, kwargs):",
            "        self._bind_dependencies(ctx)",
            "",
            "    def on_exit(self, ctx, kwargs):",
            "        pass",
            "",
            "    def on_mouse_event(self, ctx, kwargs):",
            "        return False",
            "",
            "    def on_key_event(self, ctx, kwargs):",
            "        return False",
            "",
            "    def on_draw(self, ctx, kwargs):",
            "        pass",
            "",
            "    # Optional HUD",
            "    def hud_template(self):",
            "        return []",
            "",
            "    def hud_values(self, ctx=None):",
            "        return {}",
            "",
            "    def _bind_dependencies(self, ctx):",
        ]
        lines.extend(bind_lines)
        return "\n".join(lines).strip() + "\n"

    def _update_features_init(self, file_name, class_name):
        init_path = hou.expandString("$HPD/python/skyforge/forge_states/features/__init__.py")
        if not os.path.isfile(init_path):
            return
        try:
            with open(init_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return
        import_line = "from .{0} import {1}".format(os.path.splitext(file_name)[0], class_name)
        if import_line not in content:
            if "__all__" in content:
                parts = content.split("__all__", 1)
                content = parts[0].rstrip() + "\n" + import_line + "\n\n__all__" + parts[1]
            else:
                content = content.rstrip() + "\n" + import_line + "\n"
        if "__all__" in content and ("\"%s\"" % class_name) not in content and ("'%s'" % class_name) not in content:
            try:
                before, after = content.split("__all__ = [", 1)
                head, tail = after.split("]", 1)
                entries = [e.strip() for e in head.split(",") if e.strip()]
                entries.append('"%s"' % class_name)
                head = ",\n    ".join(entries)
                content = before + "__all__ = [\n    " + head + "\n]" + tail
            except Exception:
                pass
        try:
            with open(init_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            return

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

    def _generate_code(self):
        state_name = (self.state_name_edit.text() or "my_state").strip()
        state_name = state_name if state_name else "my_state"
        blocks = self._collect_blocks()
        blocks = self._ensure_providers(blocks)
        self._warn_missing_providers(blocks)
        code = build_state_code(state_name, blocks)
        self._debug_log("Generated state: {0}".format(state_name))
        self._debug_log("Features: {0}".format(", ".join([b.get("class") for b in blocks if b.get("class")])))
        if self.append_check.isChecked():
            cur = self.editor.toPlainText()
            self.editor.setPlainText((cur + "\n\n" + code).strip())
        else:
            self.editor.setPlainText(code)

    def _collect_blocks(self):
        blocks = []
        for i in range(self.block_layout.count()):
            item = self.block_layout.itemAt(i)
            w = item.widget()
            if isinstance(w, FeatureParamBlock):
                blocks.append(w.to_config())
        return blocks

    def _preview_context(self):
        blocks = self._collect_blocks()
        blocks = self._ensure_providers(blocks)
        features = [b.get("class") for b in blocks if b.get("class")]
        provides = set()
        requires = set()
        for name in features:
            cls = self._feature_classes.get(name)
            if cls is None:
                continue
            provides.update(self._normalize_tokens(getattr(cls, "provides", None)))
            requires.update(self._normalize_tokens(getattr(cls, "requires", None)))

        base_services = {
            "host",
            "preview",
            "selection_payload",
        }
        auto_services = sorted(set(provides) | base_services)

        preview_lines = []
        preview_lines.append("=== Context Preview (Static) ===")
        preview_lines.append("features: " + ", ".join(features) if features else "features: (none)")
        preview_lines.append("services provided: " + (", ".join(sorted(provides)) if provides else "(none)"))
        preview_lines.append("services required: " + (", ".join(sorted(requires)) if requires else "(none)"))
        preview_lines.append("services in ctx (expected): " + ", ".join(auto_services))
        preview_lines.append("")
        preview_lines.append("payload shapes:")
        preview_lines.append("- hover: {gadget, c1, c2, visible, point, edge, prim}")
        preview_lines.append("- selection_payload: {mode, group} (when selection happens)")
        preview_lines.append("- preview: PreviewService (channels live here)")
        preview_lines.append("- host: viewer state instance")

        self._debug_log("\n".join(preview_lines))

    def _add_block_by_name(self, name):
        cls = self._feature_classes.get(name)
        if cls is None:
            return None
        block = FeatureParamBlock(name, cls)
        self.block_layout.insertWidget(self.block_layout.count() - 1, block)
        return block

    def _ensure_providers(self, blocks):
        provider_map = {
            "preview": "PreviewFeature",
            "hover": "HoverGadgetFeature",
        }
        classes = []
        existing = set()
        for b in blocks or []:
            name = b.get("class")
            if not name:
                continue
            existing.add(name)
            cls = self._feature_classes.get(name)
            if cls is not None:
                classes.append(cls)

        provides = set()
        requires = set()
        for cls in classes:
            try:
                provides.update(self._normalize_tokens(getattr(cls, "provides", None)))
                requires.update(self._normalize_tokens(getattr(cls, "requires", None)))
            except Exception:
                continue

        added = []
        for token in sorted(requires):
            if token in provides:
                continue
            provider_name = provider_map.get(token)
            if not provider_name:
                continue
            if provider_name in existing:
                continue
            if self._add_block_by_name(provider_name) is not None:
                added.append(provider_name)
                existing.add(provider_name)

        if added:
            self._debug_log("Auto-added providers: {0}".format(", ".join(added)))
            QtWidgets.QMessageBox.information(
                self,
                "Providers Added",
                "Added missing providers:\n- " + "\n- ".join(added),
            )
            return self._collect_blocks()
        return blocks

    def _warn_missing_providers(self, blocks):
        classes = []
        for b in blocks or []:
            name = b.get("class")
            if not name:
                continue
            cls = self._feature_classes.get(name)
            if cls is not None:
                classes.append(cls)

        provides = set()
        requires = set()
        for cls in classes:
            try:
                p = getattr(cls, "provides", None)
                r = getattr(cls, "requires", None)
            except Exception:
                continue
            provides.update(self._normalize_tokens(p))
            requires.update(self._normalize_tokens(r))

        implicit = {
            "host",
            "preview",  # BaseState.ensure_preview
            "tool_mode",
            "select_mode",
            "edit_geo",
            "mesh",
            "geometry",
            "node",
        }
        missing = sorted(t for t in requires if t not in provides and t not in implicit)
        if not missing:
            return
        self._debug_log("Missing providers: {0}".format(", ".join(missing)))
        QtWidgets.QMessageBox.warning(
            self,
            "Missing Providers",
            "These required tokens have no provider in this state:\n- " + "\n- ".join(missing),
        )

    def _normalize_tokens(self, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        try:
            return [str(v) for v in value if v is not None]
        except Exception:
            return []

    def _debug_log(self, msg):
        try:
            self.debug_text.append(str(msg))
        except Exception:
            pass

    def _clear_debug(self):
        try:
            self.debug_text.clear()
        except Exception:
            pass

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
        self._label = label
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
        hud_label = QtWidgets.QLabel("HUD")
        hud_label.setStyleSheet("QLabel { color: #a8a8a8; }")
        self._hud_toggle = QtWidgets.QCheckBox()
        self._hud_toggle.setChecked(True)
        header.addWidget(hud_label)
        header.addWidget(self._hud_toggle)
        remove_btn = QtWidgets.QToolButton()
        remove_btn.setText("X")
        remove_btn.setToolTip("Remove block")
        remove_btn.setAutoRaise(True)
        remove_btn.clicked.connect(self._remove_self)
        header.addWidget(remove_btn)
        toggle = QtWidgets.QToolButton()
        toggle.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        header.addWidget(toggle)
        root.addLayout(header)

        body = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)

        params = self._signature_params(cls)
        self._init_widgets = {}
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
                self._init_widgets[name] = widget
        body_layout.addWidget(init_group)

        schema = self._builder_schema(cls)
        self._setup_widgets = []
        if schema and schema.get("setup"):
            setup_group = QtWidgets.QGroupBox("Setup actions")
            setup_layout = QtWidgets.QFormLayout(setup_group)
            setup_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
            for spec in schema.get("setup", []):
                row = self._build_setup_row(spec)
                if row is not None:
                    setup_layout.addRow(spec.get("label") or spec.get("method") or "Action", row)
                    self._setup_widgets.append((spec, row))
            body_layout.addWidget(setup_group)

        section = CollapsibleSection("Details", body, toggle_button=toggle)
        root.addWidget(section)
        self._remove_btn = remove_btn

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

    def to_config(self):
        init_values = {}
        for name, widget in self._init_widgets.items():
            init_values[name] = self._read_widget(widget)

        setup_values = []
        for spec, widget in self._setup_widgets:
            setup_values.append({
                "method": spec.get("method"),
                "type": spec.get("type"),
                "value": self._read_widget(widget),
            })

        return {
            "class": self._label,
            "init": init_values,
            "setup": setup_values,
            "hud": bool(self._hud_toggle.isChecked()),
        }

    def _read_widget(self, widget):
        if isinstance(widget, QtWidgets.QCheckBox):
            return bool(widget.isChecked())
        if isinstance(widget, QtWidgets.QSpinBox):
            return int(widget.value())
        if isinstance(widget, QtWidgets.QDoubleSpinBox):
            return float(widget.value())
        if isinstance(widget, QtWidgets.QComboBox):
            return widget.currentText()
        if isinstance(widget, QtWidgets.QListWidget):
            return [i.text() for i in widget.selectedItems()]
        if isinstance(widget, QtWidgets.QLineEdit):
            return widget.text()
        return None

    def _remove_self(self):
        parent = self.parent()
        self.setParent(None)
        self.deleteLater()
        if parent is not None:
            parent.update()


def show_viewerstate_builder():
    # Singleton
    if not hasattr(hou.session, "_py_scratchpad"):
        hou.session._py_scratchpad = ScratchpadWindow()
    hou.session._py_scratchpad.show()
    hou.session._py_scratchpad.raise_()
    hou.session._py_scratchpad.activateWindow()


def build_state_code(state_name, blocks):
    lines = []
    lines.append("import hou")
    lines.append("")
    lines.append("from skyforge.forge_states.base_state import BaseState")
    lines.append("from skyforge.forge_states.tool_context import ToolContext")
    lines.append("from skyforge.forge_states.feature_hub import FeatureHub")
    lines.append("from skyforge.forge_states import features as F")
    lines.append("")
    lines.append("")
    lines.append("class State(BaseState):")
    lines.append("    def __init__(self, **kwargs):")
    lines.append("        self.__dict__.update(kwargs)")
    lines.append("        self.scene_viewer = kwargs['scene_viewer']")
    lines.append("        self.state_name = kwargs.get('state_name', '%s')" % state_name)
    lines.append("        super().__init__(scene_viewer=self.scene_viewer, state_name=self.state_name)")
    lines.append("")
    lines.append("        self.ctx = ToolContext(self.scene_viewer, state_name=self.state_name)")
    if blocks:
        for i, b in enumerate(blocks):
            cls_name = b.get("class")
            init_args = b.get("init") or {}
            args_txt = ", ".join(["%s=%r" % (k, v) for k, v in init_args.items()])
            if args_txt:
                lines.append("        self.f{0} = F.{1}({2})".format(i, cls_name, args_txt))
            else:
                lines.append("        self.f{0} = F.{1}()".format(i, cls_name))
            if b.get("hud") is False:
                lines.append("        self.f{0}.hud_enabled = False".format(i))
        feat_list = ", ".join(["self.f{0}".format(i) for i in range(len(blocks))])
        lines.append("        self.hub = FeatureHub([{0}])".format(feat_list))
    else:
        lines.append("        self.hub = FeatureHub([])")
    lines.append("")
    lines.append("    def onEnter(self, kwargs):")
    lines.append("        self.bind_context(self.ctx, kwargs, ensure_geo=True, ensure_mesh=True)")
    if blocks:
        needs_edit_geo = any(b.get("class") in ("HoverMoveFeature", "HoverDrawFeature") for b in blocks)
        if needs_edit_geo:
            lines.append("        self.ctx.ensure_edit_geo()")
        hover_idx = None
        for i, b in enumerate(blocks):
            if b.get("class") == "HoverGadgetFeature":
                hover_idx = i
                break
    if blocks:
        for i, b in enumerate(blocks):
            for setup in b.get("setup") or []:
                method = setup.get("method")
                value = setup.get("value")
                if not method:
                    continue
                lines.append("        self.f{0}.{1}({2})".format(i, method, repr(value)))
        if hover_idx is not None and needs_edit_geo:
            lines.append("        self.f{0}.set_use_edit_geo(True)".format(hover_idx))
    lines.append("        base_template = getattr(self, 'HUD_TEMPLATE', None)")
    lines.append("        if base_template is None:")
    lines.append("            try:")
    lines.append("                has_hud = any(callable(getattr(f, 'hud_template', None)) for f in self.hub.features)")
    lines.append("            except Exception:")
    lines.append("                has_hud = False")
    lines.append("            if has_hud:")
    lines.append("                base_template = {")
    lines.append("                    'title': self.state_name,")
    lines.append("                    'desc': '',")
    lines.append("                    'icon': '$SK_ICONS/devtools.svg',")
    lines.append("                    'rows': [],")
    lines.append("                }")
    lines.append("        self.enter_with_hud(self.hub, self.ctx, kwargs, base_template=base_template, update=True)")
    lines.append("")
    lines.append("    def onExit(self, kwargs):")
    lines.append("        self.hub.exit(self.ctx, kwargs)")
    lines.append("")
    lines.append("    def onMouseEvent(self, kwargs):")
    lines.append("        ui = kwargs.get('ui_event')")
    lines.append("        if ui is None:")
    lines.append("            return False")
    lines.append("        self.ctx.ensure_geo()")
    lines.append("        self.ctx.ensure_mesh(geo=self.ctx.geometry)")
    lines.append("        consumed, payload = self.hub.mouse_collect(self.ctx, kwargs)")
    lines.append("        if payload:")
    lines.append("            self.ctx.set_service('selection_payload', payload)")
    lines.append("            return payload")
    lines.append("        return consumed")
    lines.append("")
    lines.append("    def onDraw(self, kwargs):")
    lines.append("        self.hub.draw(self.ctx, kwargs)")
    lines.append("        self.hub.update_hud(self.scene_viewer, self.ctx)")
    lines.append("")
    lines.append("    def onKeyEvent(self, kwargs):")
    lines.append("        return bool(self.hub.key(self.ctx, kwargs, stop_on_consume=False))")
    lines.append("")
    lines.append("    def onKeyTransitEvent(self, kwargs):")
    lines.append("        try:")
    lines.append("            for f in self.hub._iter_features():")
    lines.append("                method = getattr(f, 'on_key_transit_event', None)")
    lines.append("                if callable(method) and method(self.ctx, kwargs):")
    lines.append("                    return True")
    lines.append("        except Exception:")
    lines.append("            pass")
    lines.append("        return False")
    lines.append("")
    lines.append("    def onMenuAction(self, kwargs):")
    lines.append("        handled = bool(self.hub.menu(self.ctx, kwargs, stop_on_consume=False))")
    lines.append("        if handled:")
    lines.append("            self.hub.update_hud(self.scene_viewer, self.ctx)")
    lines.append("        return handled")
    lines.append("")
    lines.append("    def onMenuPreOpen(self, kwargs):")
    lines.append("        return bool(self.hub.menu_pre_open(self.ctx, kwargs, stop_on_consume=False))")
    lines.append("")
    lines.append("")
    lines.append("def createViewerStateTemplate():")
    lines.append("    state_typename = '%s'" % state_name)
    lines.append("    state_label = '%s'" % state_name)
    lines.append("    state_cat = hou.sopNodeTypeCategory()")
    lines.append("")
    lines.append("    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)")
    lines.append("    template.bindFactory(State)")
    if blocks:
        feat_classes = ["F.{0}".format(b.get("class")) for b in blocks if b.get("class")]
        if feat_classes:
            lines.append("    feature_classes = [{0}]".format(", ".join(feat_classes)))
            lines.append("    for cls in feature_classes:")
            lines.append("        if hasattr(cls, 'bind_template'):")
            lines.append("            cls.bind_template(template)")
            lines.append("")
            lines.append("    hotkey_defs = hou.PluginHotkeyDefinitions()")
            lines.append("    hotkeys_by_cls = {}")
            lines.append("    for cls in feature_classes:")
            lines.append("        if hasattr(cls, 'build_hotkeys'):")
            lines.append("            hk = cls.build_hotkeys(hotkey_defs, state_typename)")
            lines.append("            if hk:")
            lines.append("                hotkeys_by_cls[cls] = hk")
            lines.append("")
            lines.append("    menu = None")
            lines.append("    for cls in feature_classes:")
            lines.append("        hk = hotkeys_by_cls.get(cls)")
            lines.append("        if menu is None and hasattr(cls, 'build_menu'):")
            lines.append("            menu = cls.build_menu(state_typename, state_label, hotkeys=hk)")
            lines.append("    if menu is not None:")
            lines.append("        for cls in feature_classes:")
            lines.append("            hk = hotkeys_by_cls.get(cls)")
            lines.append("            if hasattr(cls, 'extend_menu'):")
            lines.append("                cls.extend_menu(menu, hotkeys=hk, add_separator=True)")
            lines.append("")
            lines.append("    if menu is not None:")
            lines.append("        template.bindMenu(menu)")
            lines.append("    if hotkeys_by_cls:")
            lines.append("        template.bindHotkeyDefinitions(hotkey_defs)")
    lines.append("    template.bindIcon('$SK_ICONS/devtools.svg')")
    lines.append("    return template")
    lines.append("")
    return textwrap.dedent("\n".join(lines)).strip() + "\n"
