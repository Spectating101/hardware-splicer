"""General circuit netlist IR and compilation."""

from .._exports import resolve_export as _resolve_export

_MODULES = {
    "CircuitNetlist": "ir",
    "ComponentInstance": "ir",
    "Net": "ir",
    "PinRef": "ir",
    "build_graph_to_netlist": "lower",
    "netlist_to_build_graph": "lower",
    "netlist_from_build_graph": "compile",
    "run_erc": "erc",
    "parse_kicad_netlist": "import_kicad",
    "compile_netlist_to_artifacts": "compile",
}
__all__ = list(_MODULES)


def __getattr__(name):
    return _resolve_export(globals(), _MODULES, name)


def __dir__():
    return sorted(set(globals()).union(__all__, _MODULES.values()))
