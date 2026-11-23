"""Python PCB engine for geometry, DRC and KiCad."""

from .._exports import resolve_export as _resolve_export

_MODULES = {
    "build_graph_to_geometry": "build_to_geometry",
    "compile_graph_to_artifacts": "geometry_compile",
}
__all__ = list(_MODULES)


def __getattr__(name):
    return _resolve_export(globals(), _MODULES, name)


def __dir__():
    return sorted(set(globals()).union(__all__, _MODULES.values()))
