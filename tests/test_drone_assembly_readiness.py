import json
from pathlib import Path
import pytest
from hardware_splicer.drone_assembly_readiness import assess_inventory

REFERENCE=json.loads((Path(__file__).resolve().parents[1]/'eval/drone_reference_build/x500_v2.json').read_text())


def test_unknown_inventory_stays_unready():
    result=assess_inventory(REFERENCE,{})
    assert result['unfilled_line_items']==len(REFERENCE['reference_bom'])
    assert all(row['review_status']=='hold' for row in result['stages'])
    assert not result['physical_assembly_authorized']


def test_partial_purchase_does_not_grant_assembly_permission():
    result=assess_inventory(REFERENCE,{'frame':{'quantity':1,'identity_verified':True,'compatibility_verified':True}})
    assert result['unfilled_line_items']==len(REFERENCE['reference_bom'])-1
    assert result['physical_assembly_authorized'] is False
    assert result['stages'][1]['eligible_for_document_review'] is False


def test_complete_inventory_still_requires_review():
    inventory={r['id']:{'quantity':r['quantity'],'identity_verified':True,'compatibility_verified':True}
               for r in REFERENCE['reference_bom']}
    result=assess_inventory(REFERENCE,inventory)
    assert result['unfilled_line_items']==0
    assert all(row['eligible_for_document_review'] for row in result['stages'])
    assert all(row['review_status']=='hold' for row in result['stages'])
    assert not result['flight_authorized']


def test_invalid_declarations_fail_closed():
    with pytest.raises(ValueError): assess_inventory(REFERENCE,{'frame':{'quantity':-1}})
    with pytest.raises(ValueError): assess_inventory(REFERENCE,{'frame':{'quantity':1,'compatibility_verified':True}})
    with pytest.raises(ValueError): assess_inventory(REFERENCE,{'secret_part':{'quantity':1}})
