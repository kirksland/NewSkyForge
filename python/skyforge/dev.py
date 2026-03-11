# SkyForge/python/skyforge/dev.py
import sys
import importlib


def reload_package(prefix: str) -> None:
    """
    Reload all loaded modules for a given package prefix.
    Example: prefix="skyforge" will reload skyforge.* and skyforge itself.

    Reload order: deepest modules first, then parent packages last.
    """
    modules = [
        name for name in sys.modules
        if name == prefix or name.startswith(prefix + ".")
    ]

    # children first (skyforge.a.b before skyforge.a before skyforge)
    modules.sort(key=lambda m: m.count("."), reverse=True)

    for name in modules:
        mod = sys.modules.get(name)
        if mod is None:
            continue
        try:
            importlib.reload(mod)
            print(f"[reload] {name}")
        except Exception as e:
            print(f"[reload:FAILED] {name} -> {e}")


def reload_skyforge() -> None:
    """
    Reload the new SkyForge python package (skyforge).
    Reload the SkyForge python package (skyforge).
    """
    reload_package("skyforge")
