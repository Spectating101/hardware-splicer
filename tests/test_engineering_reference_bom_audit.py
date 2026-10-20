from hardware_splicer.engineering_reference_bom_audit import audit_markdown_reference_bom
from hardware_splicer.engineering_project_source_bundle import analyze_project_bundle


def sample():
    return b'''# Project\n## Estimated Total by Category\n\n| Category | Est. Cost |\n|----------|-----------|\n| Compute | ~$65-84 |\n| Display | ~$40-53 |\n| Networking | ~$30-50 |\n| **Total (excluding enclosure)** | **~$140-230** |\n'''


def test_missing_or_conflicting_total_is_not_silently_accepted():
    r=audit_markdown_reference_bom(sample(), cap_usd=200)
    assert r['category_sum_min_usd']==135
    assert r['category_sum_max_usd']==187
    assert r['published_total']=={'min_usd':140,'max_usd':230}
    assert r['published_total_reconciles_with_category_sum'] is False
    assert not r['unit_prices_vendor_verified']
    assert not r['purchase_approved']


def test_real_dinodeck_source_when_present():
    from pathlib import Path
    import pytest
    repo=Path('/tmp/hs-real-cyberdeck-replay-20261020/reference-options/dinodeck-2026')
    path=repo/'docs/BOM.md'
    if not path.exists():pytest.skip('public reference repo not cloned')
    r=audit_markdown_reference_bom(path.read_bytes(),cap_usd=250)
    assert r['category_count']==6
    assert r['category_sum_min_usd']==193.0
    assert r['category_sum_max_usd']==270.0
    assert r['published_total']=={'min_usd':140,'max_usd':230}
    assert r['published_total_reconciles_with_category_sum'] is False
    assert r['listed_category_upper_bound_below_cap'] is False


def test_bom_accepted_as_secondary_reference_without_authority():
    result=analyze_project_bundle({'RPI_Dev_1.kicad_pcb':b'(kicad_pcb (version 2024))','BOM.md':sample()})
    assert result['project_context']=='missing'
    assert result['alternative_reference_bom_audit']['category_count']==3
    assert not result['manufacturing_approved']
