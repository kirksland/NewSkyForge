import os
import sys
import importlib
import hou


class PackageManager:
    def __init__(self, package_name, package_root):
        """
        Initialize the package manager.

        :param package_name: Package name as declared in Houdini (e.g. "MyPackage")
        :param package_root: Root path of the package (e.g. "$HOUDINI_USER_PREF_DIR/packages/MyPackage")
        """

        self.package_name = package_name
        # Resolve Houdini environment variables in the path
        self.package_root = hou.expandString(package_root)
        # Directory containing Python scripts
        self.python_dir = os.path.join(self.package_root, "python")

    def scanPythonFolder(self):
        """
        Scan the package 'python' folder and return a list of .py files.
        """
        modules = []
        if os.path.isdir(self.python_dir):
            for filename in os.listdir(self.python_dir):
                if filename.endswith(".py"):
                    modules.append(filename)
        else:
            print(f"Directory does not exist: {self.python_dir}")
        return modules

    def reloadPython(self):
        """
        Reload a specific Python module if it is already loaded.
        """
        module_name = "sForge"
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
            print(f"Python module '{module_name}' reloaded")
        else:
            print(f"Python module '{module_name}' is not loaded")

    def reload_package(self):
        """
        Reload the Houdini package.
        """
        try:
            hou.ui.reloadPackage(self.package_name)
            print(f"Package '{self.package_name}' successfully reloaded")
        except Exception as e:
            print(f"Failed to reload package '{self.package_name}': {e}")

    def addNode(self, nodeType, nodeLabel):
        """
        Create a node after the currently selected node and connect it.
        """
        # Get currently selected nodes
        selected_nodes = hou.selectedNodes()

        if selected_nodes:
            # Take the first selected node
            selected_node = selected_nodes[0]

            # Get the parent network
            parent = selected_node.parent()

            # Create a new node (example: a null node)
            new_node = parent.createNode('null', 'my_new_nodeTest')

            # Position the new node below the selected one
            new_node.setPosition(selected_node.position() + hou.Vector2(0, -1))

            # Connect the new node to the selected node output
            new_node.setInput(0, selected_node)

            # Select the new node
            new_node.setSelected(True)

            print(f"Created node '{new_node.name()}' after '{selected_node.name()}'")
        else:
            print("No node selected")
