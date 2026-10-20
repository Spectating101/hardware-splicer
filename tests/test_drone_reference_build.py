"""Check concrete sourced drone assembly inventory and evidence gates."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REFERENCE=ROOT/'eval/drone_reference_build/x500_v2.json'


def test_x500_reference_is_a_complete_assembly_inventory_not_a_demo_build():
    case=json.loads(REFERENCE.read_text())
    assert 'Pixhawk 6C' in case['target']
    required={'frame','fc','power','motors','esc','props','pdb','gps','telemetry','battery','rc'}
    bom={row['id']:row for row in case['reference_bom']}
    assert set(bom)==required
    assert bom['motors']['quantity']==4 and bom['esc']['quantity']==4
    assert bom['battery']['verified_order'] is False
    assert 'purchase separately' in bom['battery']['supply']
    assert all(row['verified_order'] is False for row in bom.values())
    assert all('url' in row and 'id' in row for row in case['sources'])


def test_assembly_has_power_connector_and_safety_holds():
    case=json.loads(REFERENCE.read_text())
    gates=' '.join(case['critical_variant_checks']).lower()
    assert 'mr30' in gates and 'xt30' in gates
    assert 'xt60' in gates
    stage_ids=[row['id'] for row in case['assembly_stages']]
    assert stage_ids==['identify','frame','power','control','px4','bench','release']
    assert all(row['required_evidence'] for row in case['assembly_stages'])
    assert case['flight_authorized'] is False
    assert case['physical_build_completed'] is False
