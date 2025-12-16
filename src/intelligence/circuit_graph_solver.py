"""
Circuit Graph Solver (AlphaFold-Pro Edition)

1. Builds topological graph from vision data.
2. Serializes graph to semantic Netlist description.
3. Enables LLM to perform 'General Circuit Reasoning' on the topology.
"""

from typing import List, Dict, Any, Set, Tuple, Optional
import networkx as nx
from loguru import logger
import itertools
import math
from .gnn_motif_classifier import GNNSignatureClassifier

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
        self.gnn_classifier = GNNSignatureClassifier()
        self.gnn_available = self.gnn_classifier.is_available()
        # Very simple library of known boards/modules (component signatures)
        self.library = {
            "arduino_uno": {"components": ["microcontroller", "resistor", "capacitor", "connector"], "aspect_range": (1.2, 1.6)},
            "esp32_devkit": {"components": ["esp32", "antenna", "connector"], "aspect_range": (1.7, 2.2)},
            "power_stage": {"components": ["transformer", "cap4", "mosfet"], "aspect_range": (0.8, 1.5)},
        }

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
            
            # Score proximity of trace endpoints to component
            for trace in net['traces']:
                conf_start = self._edge_confidence(trace.start, comp_bbox)
                conf_end = self._edge_confidence(trace.end, comp_bbox)
                edge_conf = max(conf_start, conf_end)
                if edge_conf > 0:
                    G.add_edge(comp_node, net['net_id'], confidence=edge_conf)
                    break

    def _is_near(self, point: Tuple[float, float], bbox: List[float], threshold: float = 30.0) -> bool:
        """Distance check between a point and a bbox with adaptive margin."""
        x, y = point
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        bw = abs(x2 - x1)
        bh = abs(y2 - y1)
        # Scale threshold based on component size
        adaptive = threshold + 0.25 * max(bw, bh)
        dist = math.hypot(cx - x, cy - y)
        return dist <= adaptive

    def _edge_confidence(self, point: Tuple[float, float], bbox: List[float], threshold: float = 30.0) -> float:
        """Return a soft confidence 0..1 based on distance to bbox center with adaptive threshold."""
        x, y = point
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        bw = abs(x2 - x1)
        bh = abs(y2 - y1)
        adaptive = threshold + 0.25 * max(bw, bh)
        dist = math.hypot(cx - x, cy - y)
        if dist > adaptive:
            return 0.0
        # Confidence decays linearly with distance
        return max(0.0, 1.0 - dist / adaptive)

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
        Returns motif counts and a heuristic confidence (normalized 0..1).
        """
        found_signatures = []
        for name, sig in self.FUNCTIONAL_FOLDS.items():
            count = sig["fingerprint"](G)
            if count > 0:
                found_signatures.append({"structure": name, "count": count})
        
        # Heuristic confidence: more motifs and more edges imply more confidence
        edge_confidences = []
        for _, _, data in G.edges(data=True):
            if "confidence" in data and data["confidence"] is not None:
                edge_confidences.append(data["confidence"])
        avg_edge_conf = float(sum(edge_confidences) / len(edge_confidences)) if edge_confidences else 0.0
        motif_conf = min(1.0, 0.2 * len(found_signatures))
        
        return {
            "signatures": found_signatures,
            "confidence": round((avg_edge_conf * 0.6 + motif_conf * 0.4), 3)
        }

    def analyze(self, detections: List[Any], net_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full graph analysis: graph, signatures, stats, netlist text.
        Safe to call with empty detections/nets.
        """
        try:
            G = self.build_graph(detections, net_data or {})
        except Exception as e:
            logger.warning(f"Graph build failed: {e}")
            return {
                "graph": None,
                "signatures": [],
                "netlist_text": "Graph build failed.",
                "stats": {},
                "connections": [],
                "isolated_components": [],
                "topology_confidence": 0.0
            }

        signatures = self.solve_function_lite(G)
        gnn_signatures = []
        if self.gnn_available:
            try:
                gnn_signatures = self.gnn_classifier.predict(G)
            except Exception as e:
                logger.warning(f"GNN motif prediction failed: {e}")
        stats = self._graph_stats(G)
        connections = self._extract_connections(G)
        netlist_text = self.generate_text_netlist(G)
        isolated = self._isolated_components(G)
        topo_conf = signatures.get("confidence", 0.0)
        uncertainty_band = self._uncertainty_band(stats, topo_conf)

        return {
            "graph": G,
            "signatures": signatures.get("signatures", []),
            "gnn_signatures": gnn_signatures,
            "netlist_text": netlist_text,
            "stats": stats,
            "connections": connections,
            "isolated_components": isolated,
            "topology_confidence": topo_conf,
            "topology_uncertainty": uncertainty_band,
            "library_matches": self._match_library(detections)
        }

    def _graph_stats(self, G: nx.Graph) -> Dict[str, Any]:
        comps = [n for n, attr in G.nodes(data=True) if attr.get("type") == "component"]
        nets = [n for n, attr in G.nodes(data=True) if attr.get("type") == "net"]
        degrees = [deg for _, deg in G.degree(comps)]
        edge_confidences = [data.get("confidence") for _, _, data in G.edges(data=True) if data.get("confidence") is not None]
        return {
            "components": len(comps),
            "nets": len(nets),
            "edges": G.number_of_edges(),
            "avg_component_degree": float(sum(degrees) / len(degrees)) if degrees else 0.0,
            "isolated_components": len([d for d in degrees if d == 0]),
            "avg_edge_confidence": float(sum(edge_confidences) / len(edge_confidences)) if edge_confidences else 0.0,
        }

    def _extract_connections(self, G: nx.Graph) -> List[Dict[str, Any]]:
        """Return a simple net-to-components mapping."""
        mapping = []
        nets = [n for n, attr in G.nodes(data=True) if attr.get("type") == "net"]
        for net in nets:
            comps = []
            for nbr in G.neighbors(net):
                if G.nodes[nbr].get("type") == "component":
                    edge_data = G.get_edge_data(net, nbr) or {}
                    comps.append({
                        "component": nbr,
                        "confidence": edge_data.get("confidence")
                    })
            mapping.append({
                "net": net,
                "components": comps,
                "degree": len(comps)
            })
        return mapping

    def _isolated_components(self, G: nx.Graph) -> List[str]:
        return [n for n, attr in G.nodes(data=True) if attr.get("type") == "component" and G.degree[n] == 0]

    def _match_library(self, detections: List[Any]) -> List[Dict[str, Any]]:
        """
        Naive library matching based on component presence overlap.
        """
        if not detections:
            return []
        detected_classes = set([getattr(d, "class_name", "").lower() for d in detections])
        aspect = self._footprint_aspect(detections)
        matches = []
        for name, sig in self.library.items():
            expected = set([c.lower() for c in sig.get("components", [])])
            if not expected:
                continue
            overlap = len(detected_classes & expected)
            score = overlap / float(len(expected))
            aspect_score = 0.0
            if aspect and sig.get("aspect_range"):
                lo, hi = sig["aspect_range"]
                if lo <= aspect <= hi:
                    aspect_score = 1.0
                else:
                    # penalize based on distance from range
                    delta = min(abs(aspect - lo), abs(aspect - hi))
                    aspect_score = max(0.0, 1.0 - delta * 0.2)
            combined = round(0.7 * score + 0.3 * aspect_score, 2)
            if score > 0:
                missing = list(expected - detected_classes)
                matches.append({
                    "name": name,
                    "score": combined,
                    "component_score": round(score, 2),
                    "aspect_score": round(aspect_score, 2),
                    "expected": list(expected),
                    "missing": missing
                })
        matches.sort(key=lambda m: m["score"], reverse=True)
        return matches[:3]

    def _uncertainty_band(self, stats: Dict[str, Any], topo_conf: float) -> str:
        """
        Derive a coarse uncertainty band using topology confidence and edge stats.
        """
        avg_edge_conf = stats.get("avg_edge_confidence", 0.0)
        iso = stats.get("isolated_components", 0)
        score = 0.5 * topo_conf + 0.5 * avg_edge_conf - 0.05 * iso
        if score >= 0.7:
            return "low-uncertainty"
        if score >= 0.4:
            return "medium-uncertainty"
        return "high-uncertainty"

    def _footprint_aspect(self, detections: List[Any]) -> Optional[float]:
        """Compute aspect ratio of bounding envelope."""
        if not detections:
            return None
        x1s, y1s, x2s, y2s = [], [], [], []
        for d in detections:
            try:
                x1, y1, x2, y2 = d.bbox
                x1s.append(x1); y1s.append(y1); x2s.append(x2); y2s.append(y2)
            except Exception:
                continue
        if not x1s:
            return None
        w = max(x2s) - min(x1s)
        h = max(y2s) - min(y1s)
        if h <= 0 or w <= 0:
            return None
        return float(w / h)

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
