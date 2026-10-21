"""Check trusted published FEM backend integration, not physical product release."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import hashlib,json
import pytest

np=pytest.importorskip('numpy')
pytest.importorskip('gmsh')
pytest.importorskip('skfem')
shapely=pytest.importorskip('shapely')
from shapely.geometry import Polygon

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('external_cyberdeck_physics',HERE/'scripts/screen_cyberdeck_open_source_fem.py')
solver=importlib.util.module_from_spec(spec)
spec.loader.exec_module(solver)


def test_geos_exact_overlap_is_independent_of_triangle_sampling():
    board=Polygon([(0,0),(6,0),(6,10),(0,10)])
    left=Polygon([(0,0),(10,0),(10,10)])
    right=Polygon([(0,0),(10,10),(0,10)])
    # Exact half-plane polygon clipping: any mesh diagonal yields identical
    # applied area, whereas centroid sampling varies with the triangulation.
    left_area=left.intersection(board).area
    right_area=right.intersection(board).area
    assert left_area + right_area == pytest.approx(60,abs=1e-9)
    reverse=Polygon([(0,0),(10,0),(0,10)])
    reverse_other=Polygon([(10,0),(10,10),(0,10)])
    assert reverse.intersection(board).area + reverse_other.intersection(board).area == pytest.approx(60,abs=1e-9)


def test_scikit_backend_matches_hs_bounded_solver_on_shared_gmsh_tetrahedra(tmp_path):
    import gmsh
    path=tmp_path/'beam.step'
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal',0)
        gmsh.model.add('original-gmsh-beam-check')
        gmsh.model.occ.addBox(0,0,0,30,8,4)
        gmsh.model.occ.synchronize()
        gmsh.write(str(path))
    finally:
        gmsh.finalize()
    mesh=solver.mesh_existing_gmsh(path,mesh_size_mm=9.0)
    xyz=mesh['nodes_m']*1000
    xmin,xmax=xyz[:,0].min(),xyz[:,0].max()
    supports=np.flatnonzero(np.abs(xyz[:,0]-xmin)<0.025)
    loaded=np.flatnonzero(np.abs(xyz[:,0]-xmax)<0.025)
    assert len(supports)>=4 and len(loaded)>=4
    forces=np.zeros(len(xyz))
    forces[loaded]=-5/len(loaded)
    bc={'fixed_nodes':supports,'loaded_nodes':loaded,'loads_z_newtons':forces,
        'contact_force_z_n':-5.,'loaded_surface_mm2':32,'loaded_facets':1}
    result=solver.run_skfem(mesh,bc,1.5e9,0.35)
    matched=solver.compare_existing_hs(mesh,bc,1.5e9,0.35,result)
    assert matched['status']=='same_tetra_boundary_and_material_comparison'
    assert matched['agrees_within_1_percent']
    assert matched['relative_max_displacement_difference']<1e-6
    assert matched['relative_max_von_mises_difference']<1e-6
    assert result['force_equilibrium_residual_n']<1e-6
    assert result['max_von_mises_mpa']>0
    stiffer=solver.run_skfem(mesh,bc,3e9,0.35)
    assert result['max_displacement_mm']==pytest.approx(2*stiffer['max_displacement_mm'],rel=1e-5)
    assert result['max_von_mises_mpa']==pytest.approx(stiffer['max_von_mises_mpa'],rel=1e-5)


def test_changed_source_geometry_is_rejected_before_fem(tmp_path):
    root=tmp_path/'case';root.mkdir()
    (root/'source_edge_capture_lid.step').write_text('not a STEP file')
    (root/'source_edge_retention_report.json').write_text(json.dumps({
        'source_board_sha256':'sha256:expected',
        'generated_artifacts':[{'filename':'source_edge_capture_lid.step','sha256':'sha256:fake'}],
    }))
    source=tmp_path/'original.json';source.write_text(json.dumps({'source_sha256':'sha256:changed'}))
    with pytest.raises(ValueError,match='provenance mismatch'):
        solver.run_part('lid',root,source,tmp_path/'board.step',sizes=[10.,8.],force=1.,E=1.5e9,nu=.35)


def test_report_must_retain_no_physical_fabrication_authority():
    report=HERE/'projects/cyberdeck_structural_validation_20261021/STRUCTURAL_SCREENING.json'
    if not report.exists():pytest.skip('archived optional real-CAD pilot not included')
    payload=json.loads(report.read_text())
    assert payload['release_authorized'] is False
    assert payload['manufactured_device_tested'] is False
    assert payload['no_original_FEM_solver_implemented'] is True
    assert all(part['status']=='hypothetical_software_FEM_screen_only'
               for part in payload['case_results'])
    assert all(not part['fabrication_authorized'] for part in payload['case_results'])


def test_finer_mesh_overturns_apparent_strength_stability():
    folder=HERE/'projects/cyberdeck_structural_validation_20261021'
    verdict=json.loads((folder/'VALIDATION_VERDICT.json').read_text())
    finer=json.loads((folder/'LID_ULTRAFINE_RECHECK.json').read_text())
    assert verdict['source_kicad_sha256'].startswith('sha256:')
    assert verdict['overall_numerical_mesh_convergence_accepted'] is False
    assert verdict['structural_release_authorized'] is False
    assert verdict['physical_product_functional_confirmed'] is False
    assert verdict['fine_results']['lid']['apparent_3mesh_convergence'] is True
    assert verdict['fine_results']['base']['apparent_3mesh_convergence'] is False
    assert verdict['extended_lid_result']['displacement_change_vs_previous_fine_percent']>60
    assert finer['case_results'][0]['sufficient_mesh_convergence_demonstrated'] is False


def test_archived_measured_candidate_geometry_sources_remain_local_only():
    folder=HERE/'projects/cyberdeck_structural_validation_20261021'
    verdict=json.loads((folder/'VALIDATION_VERDICT.json').read_text())
    source=json.loads((folder/'source_edge_retention_report.json').read_text())
    assert verdict['source_kicad_sha256']==source['source_board_sha256']
    assert verdict['cad']['source_edge_capture_base.step'].startswith('sha256:')
    assert verdict['cad']['source_edge_capture_lid.step'].startswith('sha256:')
    assert not (folder/'source_edge_capture_base.step').exists()
    assert not (folder/'source_edge_capture_lid.step').exists()
