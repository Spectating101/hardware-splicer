"""Bound local hotspot refinement and retain counterevidence to peak convergence."""
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_local_refinement_still_fails_peak_stress_screen():
    d=json.loads((ROOT/'projects/cyberdeck_structural_validation_20261021/P2_LID_LOCAL_REFINEMENT_4_3.json').read_text())
    assert d['part']=='lid'
    assert d['local_refinement']['hotspot_mesh_mm']==1.5
    assert d['local_peak_stress_stable_in_tested_window'] is False
    assert d['fabrication_authorized'] is False
    assert max(x['reaction_z_balance_error_n'] for x in d['mesh_results'])<1e-8


def test_hotspot_mesh_parameters_reject_invalid_target():
    from importlib.util import find_spec
    if find_spec('gmsh') is None or find_spec('skfem') is None:
        pytest.skip('optional scientific environment')
    import sys
    sys.path.insert(0,str(ROOT/'scripts'))
    from screen_cyberdeck_open_source_fem import mesh_existing_gmsh
    with pytest.raises(ValueError):
        mesh_existing_gmsh(ROOT/'tests'/'not-a-file.step',4,hotspot_xy_mm=(0,0),hotspot_mesh_mm=8)
