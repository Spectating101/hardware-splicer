import json
from pathlib import Path
from hardware_splicer.real_device_work_package import compile_work_package

ROOT=Path(__file__).resolve().parents[1]/'eval/real_hardware_projects'


def test_real_device_work_packages_preserve_blockers():
    for path in ROOT.glob('*.json'):
        case=json.loads(path.read_text())
        review=json.loads((ROOT/'reports'/path.name).read_text())
        result=compile_work_package(case,review,planner=review['hs_raw_plan'])
        assert result['catalog_routing']['status']=='blocked_no_compatible_catalog_build'
        assert len(result['requirements'])==len(case['deliverables'])
        assert result['work_steps']
        assert result['required_parts']
        assert result['critical_unknowns']
        assert result['engineering_readiness']=='blocked'
        assert all(not item['compatibility_verified'] for item in result['required_parts'])
        assert all(not item['verified_full_document'] for item in result['source_leads'])
        assert all(item['status']=='not_accepted' for item in result['acceptance_gates'])
