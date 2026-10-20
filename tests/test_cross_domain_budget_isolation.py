from hardware_splicer.engineering_project_source_bundle import analyze_project_bundle

BOM=b'''# Example\n## Estimated Total by Category\n\n| Category | Est. Cost |\n| --- | --- |\n| Boards | $300-500 |\n| Case | $100-150 |\n| **Total** | $400-650 |\n'''


def test_different_projects_get_their_own_budget_without_hardcoded_250():
    generic=analyze_project_bundle({'refurb-supplier-estimate.md':BOM})
    expensive=analyze_project_bundle({'refurb-supplier-estimate.md':BOM},budget_cap_usd=800)
    cheap=analyze_project_bundle({'refurb-supplier-estimate.md':BOM},budget_cap_usd=250)
    assert generic['alternative_reference_bom_audit']['budget_cap_usd'] is None
    assert expensive['alternative_reference_bom_audit']['listed_category_upper_bound_below_cap'] is True
    assert cheap['alternative_reference_bom_audit']['listed_category_upper_bound_below_cap'] is False
    assert expensive['alternative_reference_bom_audit']['published_total_reconciles_with_category_sum']
    assert generic['status']=='analyzed_non_electrical_sources'


def test_budget_change_invalidates_persisted_analysis_without_changing_source_hash(tmp_path):
    import base64
    from fastapi.testclient import TestClient
    from hardware_splicer.product_api import create_product_app
    from hardware_splicer.project_store import ProjectStore
    store=ProjectStore(tmp_path)
    project='budget-isolation'
    store.save(project,{'projectId':project,'constraints':{'max_cost_usd':250}})
    client=TestClient(create_product_app(store))
    upload=client.post(f'/v1/projects/{project}/sources/ingest',json={
        'filename':'refurb-supplier-estimate.md',
        'content_base64':base64.b64encode(BOM).decode(),
        'expected_revision':1})
    assert upload.status_code==201
    rev=upload.json()['revision']
    first=client.post(f'/v1/projects/{project}/engineering/source-bundle/check',json={'expected_revision':rev})
    assert first.status_code==200 and first.json()['registered']
    first_row=first.json()['source_bundle_run']
    assert first_row['alternative_reference_bom_audit']['listed_category_upper_bound_below_cap'] is False
    loaded=store.load_latest_with_recovery(project)
    snap=loaded['snapshot'];snap['constraints']['max_cost_usd']=800
    store.save(project,snap,expected_revision=loaded['revision'])
    updated=store.load_latest_with_recovery(project)
    second=client.post(f'/v1/projects/{project}/engineering/source-bundle/check',
                       json={'expected_revision':updated['revision']})
    assert second.status_code==200 and second.json()['registered'] is True
    second_row=second.json()['source_bundle_run']
    assert second_row['source_set_sha256']==first_row['source_set_sha256']
    assert second_row['analysis_parameters_sha256'] != first_row['analysis_parameters_sha256']
    assert second_row['alternative_reference_bom_audit']['listed_category_upper_bound_below_cap'] is True
    third=client.post(f'/v1/projects/{project}/engineering/source-bundle/check',
                      json={'expected_revision':second.json()['revision']})
    assert third.status_code==200 and third.json()['registered'] is False
