"""Guard quadrature-based hotspot reporting against release overclaims."""
import ast
from pathlib import Path


def test_quadratic_runner_records_physical_peak_and_screw_distance():
    source = (Path(__file__).resolve().parents[1] / 'scripts/diagnose_cyberdeck_p2.py').read_text()
    ast.parse(source)
    assert "'peak_quadrature_location_mm':peak_location_mm" in source
    assert "'peak_distance_to_nearest_screw_xy_mm':min(screw_distances_mm)" in source
    assert "'fabrication_authorized':False" in source
