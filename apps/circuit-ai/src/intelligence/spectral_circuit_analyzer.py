"""
Spectral Circuit Analyzer (Mathematical Topology)

Uses Spectral Graph Theory to fingerprint circuits.
1. Constructs the Component-Net Graph.
2. Computes the Laplacian Matrix (L = D - A).
3. Calculates Eigenvalues (The 'Spectrum') to create a rotation-invariant signature.
4. Compares against Reference Spectra to identify circuit function mathematically.
"""

import networkx as nx
import numpy as np
from scipy.linalg import eigh
from typing import List, Dict, Any
from loguru import logger

class SpectralCircuitAnalyzer:
    """
    Identifies circuit topology using the Eigenvalues of the Graph Laplacian.
    This provides a mathematically rigorous 'Fingerprint' of the circuit's connectivity.
    """

    def __init__(self):
        # Reference Spectra (Pre-computed eigenvalues for standard topologies)
        # In a real production system, these would be loaded from a database of millions of circuits.
        # These are illustrative exact eigenvalues for specific small graphs.
        self.REFERENCE_SPECTRA = {
            "Voltage Divider": {
                # 3 Nodes (VCC, GND, Mid), 2 Resistors edges. 
                # Simple path graph P3 usually has specific eigenvalues.
                "spectrum": [0.0, 1.0, 3.0], 
                "tolerance": 0.1
            },
            "H-Bridge (Core)": {
                # 4 Switches in a ring/bridge structure.
                # Cycle graph C4 or similar.
                "spectrum": [0.0, 2.0, 2.0, 4.0],
                "tolerance": 0.2
            },
            "Differential Pair": {
                # Common Emitter/Source pair topology
                "spectrum": [0.0, 0.58, 2.0, 3.41], 
                "tolerance": 0.15
            }
        }
        logger.info("SpectralCircuitAnalyzer initialized")

    def build_graph(self, detections: List[Any], net_data: Dict[str, Any]) -> nx.Graph:
        """
        Builds a simplified connectivity graph for spectral analysis.
        Nodes = Components ONLY (we collapse nets to edges for direct component-component links).
        """
        G = nx.Graph()
        
        # 1. Add Components
        for i, det in enumerate(detections):
            G.add_node(i, label=det.class_name)

        # 2. Build Edges via Nets
        # If Component A and Component B share a Net, add an edge.
        if 'nets' in net_data:
            for net in net_data['nets']:
                # Find components touching this net
                connected_indices = []
                for i, det in enumerate(detections):
                    det_bbox = det.bbox
                    # Check proximity to all trace segments in net
                    is_connected = False
                    for trace in net['traces']:
                        if self._is_near(trace.start, det_bbox) or self._is_near(trace.end, det_bbox):
                            is_connected = True
                            break
                    if is_connected:
                        connected_indices.append(i)
                
                # Clique connect all components on this net (They are electrically common)
                for u in connected_indices:
                    for v in connected_indices:
                        if u < v:
                            if G.has_edge(u, v):
                                G[u][v]['weight'] += 1
                            else:
                                G.add_edge(u, v, weight=1)
        return G

    def _is_near(self, point, bbox, threshold=30):
        x, y = point
        x1, y1, x2, y2 = bbox
        return (x1-threshold <= x <= x2+threshold) and (y1-threshold <= y <= y2+threshold)

    def compute_fingerprint(self, G: nx.Graph) -> List[float]:
        """
        Computes the Laplacian Eigenvalues of the graph.
        Returns a sorted list of floats (The Spectrum).
        """
        if G.number_of_nodes() < 2:
            return [0.0]

        # Get Laplacian Matrix
        L = nx.laplacian_matrix(G).toarray()
        
        # Compute Eigenvalues (Real symmetric matrix)
        eigenvalues = eigh(L, eigvals_only=True)
        
        # Sort and rounded for comparison
        return sorted([float(ev) for ev in eigenvalues])

    def identify_topology(self, G: nx.Graph) -> Dict[str, Any]:
        """
        Compares graph spectrum against known references.
        """
        spectrum = self.compute_fingerprint(G)
        
        best_match = "Unknown"
        lowest_error = float('inf')
        
        # Spectral Matching (Euclidean Distance between spectra)
        # Note: Graphs must be roughly same size for direct comparison, 
        # or we compare 'spectral density' for larger graphs.
        # Here we do direct matching for sub-circuits.
        
        for name, ref in self.REFERENCE_SPECTRA.items():
            ref_spec = ref["spectrum"]
            
            # Simple size check: if node counts differ significantly, eigenvalues won't align.
            # In a pro implementation, we'd search for subgraph isomorphism or padding.
            if abs(len(spectrum) - len(ref_spec)) > 1:
                continue
                
            # Pad smaller spectrum with zeros for comparison
            s1 = np.array(spectrum)
            s2 = np.array(ref_spec)
            
            if len(s1) < len(s2):
                s1 = np.pad(s1, (0, len(s2)-len(s1)))
            elif len(s2) < len(s1):
                s2 = np.pad(s2, (0, len(s1)-len(s2)))
                
            distance = np.linalg.norm(s1 - s2)
            
            if distance < ref["tolerance"] and distance < lowest_error:
                lowest_error = distance
                best_match = name

        return {
            "topology_name": best_match,
            "spectrum": [round(x, 3) for x in spectrum],
            "spectral_error": round(lowest_error, 4) if lowest_error != float('inf') else None,
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges()
        }
