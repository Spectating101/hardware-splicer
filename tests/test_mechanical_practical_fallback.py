"""Make unsupported structural topology useful without inventing FEM authority."""
from hardware_splicer.mechanical_workflow_integration import structural_capability_for_design


def test_enclosure_unsupported_fem_still_returns_build_checks():
    result=structural_capability_for_design({'enclosure':{'inner_w_mm':60,'inner_d_mm':40,'inner_h_mm':20}})
    assert result['status']=='unsupported_mechanical_topology'
    assert not result['mechanical_build_ready']
    assert not result['fabrication_authorized']
    assert not result['release_authorized']
    checks=' '.join(result['practical_next_checks']).lower()
    assert 'port' in checks and 'assembly' in checks and 'clearance' in checks


def test_actuated_assembly_includes_travel_and_collision_checks():
    result=structural_capability_for_design({'pan_tilt':{'pan_servo':'sg90'},'assembly':{'name':'rig'}})
    checks=' '.join(result['practical_next_checks']).lower()
    assert 'travel' in checks and 'collision' in checks
    assert result['supported_for_contact'] is False
