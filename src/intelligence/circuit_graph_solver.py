"Circuit Graph Solver (AlphaFold-Pro Edition)"

1. Builds topological graph from vision data.
2. Serializes graph to semantic Netlist description.
3. Enables LLM to perform 'General Circuit Reasoning' on the topology.
"

from typing import List, Dict, Any, Set
import networkx as nx
from loguru import logger
import itertools

class CircuitGraphSolver:
    """
    Solves circuit structure by converting topology into a 
    semantic language for LLM analysis.
    """

    # Keep Lite signatures for fast, cheap detection
    FUNCTIONAL_FOLDS = {
        "Voltage Divider": {
            "fingerprint": lambda g: CircuitGraphSolver._find_voltage_divider(g)
        },
        "Filter Stage": {
            "fingerprint": lambda g: CircuitGraphSolver._find_rc_filter(g)
        },
        "H-Bridge (Motor Driver)": {
            "fingerprint": lambda g: CircuitGraphSolver._find_h_bridge(g)
        }
    }

    def __init__(self):
        logger.info("CircuitGraphSolver initialized (Pro Mode)")

    def build_graph(self, detections: List[Any], net_data: Dict[str, Any]) -> nx.Graph:
        """
        Converts vision/trace data into a semantic circuit graph.
        """
        G = nx.Graph()
        
        # 1. Add Component Nodes
        for i, det in enumerate(detections):
            # Use unique ID but keep class info
            node_id = f"{det.class_name}_{i}"
            G.add_node(node_id, type="component", cls=det.class_name, bbox=det.bbox)
        
        # 2. Add Net Nodes
        if 'nets' in net_data:
            for net in net_data['nets']:
                net_id = net['net_id']
                G.add_node(net_id, type="net")
                self._link_components_to_net(G, net, detections)

        return G

    def _link_components_to_net(self, G: nx.Graph, net: Dict, detections: List[Any]):
        """Geometrically links components to nets."""
        # Get all component nodes
        comp_nodes = [n for n, attr in G.nodes(data=True) if attr.get('type') == 'component']
        
        for comp_node in comp_nodes:
            comp_bbox = G.nodes[comp_node]['bbox']
            
            # Simple heuristic: If trace ends near component
            for trace in net['traces']:
                if self._is_near(trace.start, comp_bbox) or self._is_near(trace.end, comp_bbox):
                    G.add_edge(comp_node, net['net_id'])
                    break

    def _is_near(self, point, bbox, threshold=30): # Increased threshold for robustness
        x, y = point
        x1, y1, x2, y2 = bbox
        return (x1-threshold <= x <= x2+threshold) and (y1-threshold <= y <= y2+threshold)

    def generate_text_netlist(self, G: nx.Graph) -> str:
        """
        Converts the Graph into a human-readable Netlist description.
        This is the 'Prompt Engineering' for the Topology.
        """
        lines = []
        lines.append("CIRCUIT NETLIST DESCRIPTION:")
        
        # Group by Net
        nets = [n for n, attr in G.nodes(data=True) if attr.get('type') == 'net']
        
        for net in nets:
            neighbors = list(G.neighbors(net))
            if len(neighbors) > 1:
                # Filter to just component names
                comps = [n for n in neighbors if G.nodes[n].get('type') == 'component']
                if len(comps) > 1:
                    lines.append(f"- Net '{net}' connects: {', '.join(comps)}")
        
        # Isolated components check
        components = [n for n, attr in G.nodes(data=True) if attr.get('type') == 'component']
        if not nets and components:
             lines.append("(No explicit traces found. Components listed by proximity inference)")
             # Fallback: List components
             lines.append(f"Components present: {', '.join(components)}")

        return "\n".join(lines)

    def solve_function_lite(self, G: nx.Graph) -> Dict[str, Any]:
        """
        Fast, heuristic-based solving (Lite Mode).
        """
        found_signatures = []
        for name, sig in self.FUNCTIONAL_FOLDS.items():
            count = sig["fingerprint"](G)
            if count > 0:
                found_signatures.append({"structure": name, "count": count})
        
        return {
            "signatures": found_signatures
        }

    # --- Topological Fingerprints (Lite) ---
    
    @staticmethod
    def _find_rc_filter(G: nx.Graph) -> int:
        count = 0
        resistors = [n for n, attr in G.nodes(data=True) if attr.get('cls') == "Resistor"]
        capacitors = [n for n, attr in G.nodes(data=True) if attr.get('cls') in ["Capacitor", "Cap1", "Cap2", "Cap3", "Cap4"]]
        for r in resistors:
            for c in capacitors:
                try:
                    if list(nx.common_neighbors(G, r, c)): count += 1
                except: pass
        return count

    @staticmethod
    def _find_voltage_divider(G: nx.Graph) -> int:
        count = 0
        resistors = [n for n, attr in G.nodes(data=True) if attr.get('cls') == "Resistor"]
        for r1, r2 in itertools.combinations(resistors, 2):
            try:
                if list(nx.common_neighbors(G, r1, r2)): count += 1
            except: pass
        return count

    @staticmethod
    def _find_h_bridge(G: nx.Graph) -> int:
        mosfets = [n for n, attr in G.nodes(data=True) if attr.get('cls') == "MOSFET"]
        if len(mosfets) < 4: return 0
        subgraph = G.subgraph(mosfets + [n for m in mosfets for n in G.neighbors(m)])
        if nx.is_connected(subgraph): return 1
        return 0