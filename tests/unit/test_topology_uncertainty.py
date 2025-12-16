import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "src")
for path in (ROOT, SRC):
    if path not in sys.path:
        sys.path.insert(0, path)

import src.intelligence.circuit_graph_solver as cg


def test_uncertainty_band_low():
    solver = cg.CircuitGraphSolver()
    band = solver._uncertainty_band({"avg_edge_confidence": 0.8, "isolated_components": 0}, 0.8)
    assert band == "low-uncertainty"


def test_uncertainty_band_high():
    solver = cg.CircuitGraphSolver()
    band = solver._uncertainty_band({"avg_edge_confidence": 0.1, "isolated_components": 2}, 0.1)
    assert band == "high-uncertainty"
