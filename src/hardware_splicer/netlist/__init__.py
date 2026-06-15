"""General circuit netlist IR — source of truth for the compile engine."""

from .compile import compile_netlist_to_artifacts, netlist_from_build_graph
from .erc import run_erc
from .import_kicad import parse_kicad_netlist
from .ir import CircuitNetlist, ComponentInstance, Net, PinRef
from .lower import build_graph_to_netlist, netlist_to_build_graph

__all__ = [
    "CircuitNetlist",
    "ComponentInstance",
    "Net",
    "PinRef",
    "build_graph_to_netlist",
    "netlist_to_build_graph",
    "netlist_from_build_graph",
    "run_erc",
    "parse_kicad_netlist",
    "compile_netlist_to_artifacts",
]
