from PySide2 import QtWidgets, QtGui, QtCore
import sForge
import os
import hou

class HoudiniContextMenu(QtWidgets.QMenu):
    """
    Custom vertical context menu for Houdini with Skyforge integration.
    Provides quick access to shelf tools, HDAs, console operations, and viewport settings.
    """

    def __init__(self, parent=None):
        super(HoudiniContextMenu, self).__init__(parent)
        self.manager = sForge.packageManager()
        self.toolkit = sForge.toolKit()
        self.viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        self.setMinimumWidth(200)

        # Header label "Skyforge"
        header_label = QtWidgets.QLabel("Skyforge")
        header_label.setAlignment(QtCore.Qt.AlignCenter)
        header_label.setStyleSheet(
            "color: #3498DB; font-size: 21px; font-weight: bold; padding: 3px; min-width: 100px;"
        )
        header_widget_action = QtWidgets.QWidgetAction(self)
        header_widget_action.setDefaultWidget(header_label)
        self.addAction(header_widget_action)
        self.addSeparator()

        # Add menu actions
        self.addAction("Subdivide", self.invoke_shelf_tool)
        self.addSeparator()
        self.addAction("Reload Python", self.reloadPackage)
        self.addAction("Clear Console", self.clearConsole)
        self.addAction("Toggle Background", self.backgroundColor)

        # Add HDAs dynamically
        my_hda = self.get_hda()
        for h in my_hda:
            self.addAction(h, lambda h=h: self.CreateNode(h))

        # Menu style
        self.setStyleSheet("""
            QMenu {
                background-color: #282828;
                color: white;
                border: 1px solid #555;
                padding: 5px;
                font-size: 15px;
                min-width: 100px;
            }
            QMenu::item {
                padding: 8px 25px;
                margin: 2px 0px;
                min-width: 100px;
            }
            QMenu::item:selected {
                background-color: #505050;
            }
            QMenu::separator {
                height: 1px;
                background: #555;
                margin: 5px 10px;
            }
        """)

    def CreateNode(self, node_name):
        """ Spawn an HDA node using the toolkit """
        self.toolkit.spawnNode(node_name)

    def get_hda(self):
        """
        Scan the HDAs folder and return a list of nodeTypeNames for all HDAs found.
        """
        hda_files = self.manager.scanFolder()
        hda_defs = []
        for hda in hda_files:
            path = os.path.expandvars("$HPD/hda")
            extension = ".hdanc"
            file_path = os.path.join(path, hda + extension)

            try:
                definitions = hou.hda.definitionsInFile(file_path)
                if definitions:
                    hda_defs.append(definitions[0].nodeTypeName())
            except Exception as e:
                print(f"[DEBUG] Failed to load HDA {file_path}: {e}")

        return hda_defs

    def show_menu(self):
        """ Show the context menu at the current mouse position """
        cursor_pos = QtGui.QCursor.pos()
        self.move(cursor_pos)
        self.exec_()

    def invoke_shelf_tool(self):
        """ Execute an existing shelf tool by name """
        try:
            tool_script = hou.shelves.tool("QuickSubdivide").script()
            exec(tool_script)
        except Exception as e:
            print(f"[DEBUG] Failed to run QuickSubdivide: {e}")

    def SKT_relax(self):
        """ Execute SKT_relax shelf tool """
        try:
            tool_script = hou.shelves.tool("SKT_relax").script()
            exec(tool_script)
        except Exception as e:
            print(f"[DEBUG] Failed to run SKT_relax: {e}")

    def reloadPackage(self):
        """ Reload the Skyforge Python package """
        try:
            self.manager.reloadPython()
            hou.ui.reloadPackage("$HOUDINI_USER_PREF_DIR/packages/SkyForgePackage.json")
        except Exception as e:
            print(f"[DEBUG] Failed to reload Skyforge package: {e}")

    def scanShelfTool(self):
        """ Scan shelf tools in a specific folder (not currently used) """
        toolbar_path = hou.expandString("$HPD/tools")
        shelf_filename = "default.shelf"
        return self.manager.scanShelfTool(toolbar_path, shelf_filename)

    def clearConsole(self):
        """ Clear the Houdini Python console """
        print("\n" * 500)
        print("[DEBUG] Console cleared")

    def backgroundColor(self):
        """ Cycle viewport background color: Dark -> Grey -> Light """
        if not self.viewer:
            print("[DEBUG] No scene viewer found.")
            return

        settings = self.viewer.curViewport().settings()
        scheme = settings.colorScheme()

        # Mapping from current scheme to the next
        color_schemes = {
            hou.viewportColorScheme.Dark: lambda: settings.setColorScheme(hou.viewportColorScheme.Grey),
            hou.viewportColorScheme.Grey: lambda: settings.setColorScheme(hou.viewportColorScheme.Light),
            hou.viewportColorScheme.Light: lambda: settings.setColorScheme(hou.viewportColorScheme.Dark),
        }

        if scheme in color_schemes:
            color_schemes[scheme]()
        else:
            print(f"[DEBUG] Unknown color scheme: {scheme}")


# Function to call the custom menu
def show_custom_menu():
    menu = HoudiniContextMenu()
    menu.show_menu()


# Execute menu
show_custom_menu()
