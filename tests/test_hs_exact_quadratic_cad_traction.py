"""Source-derived exact 2D facet load assembly with already installed GEOS/FEM."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import numpy as np
import pytest

pytest.importorskip('shapely')
pytest.importorskip('skfem')
from shapely.geometry import Polygon
from skfem import MeshTet,ElementVector,ElementTetP1,ElementTetP2,Basis

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from hs_exact_p2_traction import polygon_moments,exact_planar_traction


def test_analytic_polygon_moments_including_holes():
    rect=Polygon([(0,0),(10,0),(10,5),(0,5)])
    m=polygon_moments(rect)
    assert m[0]==pytest.approx(50)
    assert m[1]==pytest.approx(250)
    assert m[2]==pytest.approx(125)
    assert m[3]==pytest.approx(5000/3)
    assert m[4]==pytest.approx(625)
    assert m[5]==pytest.approx(1250/3)
    ring=Polygon([(0,0),(10,0),(10,10),(0,10)],holes=[[(3,3),(3,7),(7,7),(7,3)]])
    rm=polygon_moments(ring)
    assert rm[0]==pytest.approx(84)
    assert rm[1]==pytest.approx(420)
    assert rm[2]==pytest.approx(420)


@pytest.mark.parametrize('degree', [1,2])
@pytest.mark.parametrize('nx', [3,5])
def test_exact_facet_traction_constant_for_all_meshes_and_p_orders(degree,nx):
    mesh=MeshTet.init_tensor(np.linspace(0,.03,nx),np.linspace(0,.02,4),np.linspace(0,.004,2))
    field=ElementVector(ElementTetP1() if degree==1 else ElementTetP2())
    basis=Basis(mesh,field)
    pcb=Polygon([(0,0),(12,0),(12,20),(0,20)])
    F,meta=exact_planar_traction(basis,pcb,zplane_m=0.,force_z_newtons=-5,degree=degree)
    assert meta['clipped_lip_area_mm2']==pytest.approx(240,rel=1e-10)
    assert F.sum()==pytest.approx(-5,abs=1e-8)
    assert meta['source_polygon_integral_not_quadrature_sample'] is True
    assert np.count_nonzero(abs(F)>1e-15)>5


def test_invalid_polygon_or_incorrect_basis_fails_closed():
    mesh=MeshTet.init_tensor(np.array([0,.01]),np.array([0,.01]),np.array([0,.004]))
    basis=Basis(mesh,ElementVector(ElementTetP2()))
    with pytest.raises(ValueError,match='invalid source'):
        exact_planar_traction(basis,Polygon([(0,0),(10,10),(0,10),(10,0)]),
            zplane_m=0.,force_z_newtons=1,degree=2)
    with pytest.raises(ValueError,match='P1/P2'):
        exact_planar_traction(basis,Polygon([(0,0),(10,0),(10,10),(0,10)]),
            zplane_m=0.,force_z_newtons=1,degree=3)


def test_quadratic_archived_mechanical_evidence_rejects_physical_release():
    payload=__import__('json').loads((ROOT/'projects/cyberdeck_structural_validation_20261021/P2_CORRECT_LOAD_VALIDATION.json').read_text())
    assert payload['schema']=='hardware_splicer.corrected_cyberdeck_quadratic_FEM.v1'
    assert payload['fabrication_authorized'] is False
    assert payload['operational_safety_verified'] is False
    assert payload['load_and_material_measured'] is False
    assert payload['source_original_kicad_sha256'].startswith('sha256:')
    assert payload['corrected_base_load_on_original_pcb_bottom_z_mm']==0
    assert payload['base_corrected_top_face_results']['source_step_sha256'].startswith('sha256:')
    assert payload['source_derived_load_area_constant_with_refinement']
    assert payload['number_of_actual_physical_specimens_tested']==0
