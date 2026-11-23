import json
from pathlib import Path
from scripts.run_real_hardware_projects import model_casefile

ROOT=Path(__file__).resolve().parents[1]


def test_rejects_demo_catalog_for_all_real_devices():
    for path in (ROOT/'eval/real_hardware_projects').glob('*.json'):
        case=json.loads(path.read_text())
        report=json.loads((ROOT/'eval/real_hardware_projects/reports'/path.name).read_text())
        assert report['project_id']==case['id']
        assert report['catalog_compatibility_gate']['status']=='unverified_mismatch'
        assert report['physical_build_completed'] is False
        assert report['independent_design_verification_completed'] is False
        assert report['operator_casefile']['physical_validation_claimed'] is False


def test_declared_catalog_allowlist_is_independent_of_model_verdict():
    case=json.loads((ROOT/'eval/real_hardware_projects/drone_px4_quad.json').read_text())
    plan={'recommended_build_id':'bench_power_adapter','archetype':'aerial_robot'}
    data={'catalog_verdict':'relevant','project_type':'quad','functional_subsystems':[],
          'decision_tree':[],'compatible_parts_or_requirements':[],
          'build_or_repair_sequence':[], 'critical_technical_unknowns':[],
          'validation_plan':[], 'deliverable_gaps':[],'completion_state':'blocked',
          'physical_validation_claimed':False}
    result=model_casefile(case,plan,operator=lambda _prompt:data)
    assert result['catalog_compatibility_gate']['status']=='unverified_mismatch'
    case['approved_catalog_build_ids']=['bench_power_adapter']
    approved=model_casefile(case,plan,operator=lambda _prompt:data)
    assert approved['catalog_compatibility_gate']['status']=='candidate_allowed'
