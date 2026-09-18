"""Auto-load every *_plugin.py module in this package."""
import importlib
import pkgutil


def load_plugins():
    plugins = []
    for mod in pkgutil.iter_modules(__path__):
        if not mod.name.endswith("_plugin"):
            continue
        module = importlib.import_module(f"{__name__}.{mod.name}")
        inst = getattr(module, "plugin", None)
        if inst is not None:
            plugins.append(inst)
    return sorted(plugins, key=lambda p: p.name)
