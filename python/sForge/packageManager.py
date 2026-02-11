"""
Description:    Various utilities used to manage a Houdini package.
Author:         kirksland
Date Created:   Feb 21, 2024
"""

import os
import sys
import importlib
import hou


class PackageManager:
    def __init__(self, package_name='SkyForgePackage', package_root='$HPD'):
        """
        Initialize the package manager.

        :param package_name: Name of the package as declared in Houdini
                             (e.g. "MyPackage")
        :param package_root: Root path of the package
                             (e.g. "$HOUDINI_USER_PREF_DIR/packages/MyPackage")
        """
        self.package_name = package_name
        # Resolve Houdini environment variables in the path
        self.package_root = hou.expandString(package_root)
        # Directory containing Python scripts
        self.python_dir = os.path.join(self.package_root, "python")
        # Directory containing HDA files
        self.hda_dir = os.path.join(self.package_root, "hda")

    def scanFolder(self, folderPath='$HPD/hda', extension='hdanc'):
        """
        Scan a folder and return a list of file names without extension.

        :param folderPath: Path to the folder to scan
        :param extension: File extension to search for (without dot)
        :return: List of file names without extension
        """
        folder_path = os.path.expandvars(folderPath)
        modules = []

        if os.path.isdir(folder_path):
            for filename in os.listdir(folder_path):
                if filename.endswith('.' + extension):
                    name_without_extension = os.path.splitext(filename)[0]
                    modules.append(name_without_extension)

            if not modules:
                print(f"No files with extension '{extension}' found")
        else:
            print(f"Directory does not exist: {folder_path}")

        return modules

    def reloadPython(self):
        """
        Reload all Python modules belonging to the sForge package.

        Modules are reloaded in dependency order (children first,
        parent module last).
        """
        modules_to_reload = [
            'sForge.packageManager',
            'sForge.toolKit',
            'sForge.customUI',
            'sForge'  # Parent module last
        ]

        for module_name in modules_to_reload:
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
                print(f"Module '{module_name}' reloaded")
            else:
                print(f"Module '{module_name}' not found in sys.modules")

    def scanShelfTool(self, toolbar_path, shelf_filename):
        """
        Scan a Houdini shelf file and extract basic tool information.

        :param toolbar_path: Path to the toolbar directory
        :param shelf_filename: Shelf XML file name
        :return: Dictionary containing shelf metadata and tools, or None
        """
        import xml.etree.ElementTree as ET

        shelf_path = os.path.join(toolbar_path, shelf_filename)

        if not os.path.exists(shelf_path):
            print(f"Shelf file does not exist: {shelf_path}")
            return None

        try:
            tree = ET.parse(shelf_path)
            root = tree.getroot()

            shelf_info = {
                'name': root.get('name', 'Unknown'),
                'label': root.get('label', 'Unknown'),
                'tools': []
            }

            for tool in root.findall('.//tool'):
                tool_info = {
                    'name': tool.get('name', 'Unknown'),
                    'label': tool.get('label', 'Unknown'),
                    'icon': tool.get('icon', 'None')
                }

                script_tag = tool.find('./script')
                if script_tag is not None:
                    tool_info['script'] = script_tag.text

                shelf_info['tools'].append(tool_info)

            print(f"Shelf '{shelf_info['name']}' found with {len(shelf_info['tools'])} tools")
            for tool in shelf_info['tools']:
                print(f"- {tool['name']}: {tool['label']}")

            return shelf_info

        except Exception as e:
            print(f"Failed to parse shelf file: {e}")
            return None
