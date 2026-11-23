"""Resolve a package re-export without importing unrelated engine subsystems."""

from importlib import import_module


def resolve_export(namespace, modules, name):
    package = namespace["__name__"]
    module = modules.get(name)
    if module is None and name in modules.values():
        return import_module(f".{name}", package)
    if module is None:
        raise AttributeError(f"module {package!r} has no attribute {name!r}")
    value = getattr(import_module(f".{module}", package), name)
    namespace[name] = value
    return value
