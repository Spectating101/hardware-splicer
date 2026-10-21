"""Evidence acquisition and no-privilege-escalation tests."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

from hardware_splicer.engineering_web_research import (
    research_engineering_gap,EngineeringResearchError,_valid_public_host,
)
from hardware_splicer.ai_project_orchestrator import build_ai_project_context
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.ai_project_tool_executor import execute_ai_project_action_preview

_HTML=b'''<html><head><title>Holybro Test Datasheet</title></head>
<body><main><h2>Frame specifications</h2><p>X500 has four motors model 2216 KV920 and BLHeli-S 20A ESC controllers.</p><p>Technical publisher claim. No physical compatibility trial.</p></main></body></html>'''
_SERP=b'''<html><body><div class="snippet" data-type="web"><a href="https://holybro.com/products/x500-v2-kits">Holybro X500 V2 Kit</a><p>Supplier product specification</p></div>
<div class="snippet" data-type="web"><a href="https://evil.example.net/steal?secret=1">Bad page</a></div></body></html>'''
_REQUEST={'id':'drone-gap','question':'What specific motor and ESC does Holybro X500 V2 publish?',
          'allowed_hosts':['holybro.com']}


def test_unapproved_domain_and_url_injection_rejected():
    for requested in [
        {**_REQUEST,'source_urls':['https://evil.example.net/internal']},
        {**_REQUEST,'source_urls':['https://holybro.com@evil.example.net/exfil']},
        {**_REQUEST,'allowed_hosts':['127.0.0.1']},
        {**_REQUEST,'allowed_hosts':['evil.holybro.com']},
        {**_REQUEST,'question':'https://internal.local/secret'},
        {**_REQUEST,'evil_url':'https://evil.example.net'},
    ]:
        with pytest.raises(EngineeringResearchError):
            research_engineering_gap(requested)
    for url in ('http://holybro.com/test','https://127.0.0.1/test',
                'https://holybro.com@evil.example.net/path',
                'https://evil.holybro.com/path'):
        with pytest.raises(EngineeringResearchError):
            _valid_public_host(url,frozenset({'holybro.com'}))


def test_fetched_primary_html_is_digest_bound(monkeypatch):
    monkeypatch.setattr('hardware_splicer.engineering_web_research._valid_public_host',
                        lambda url,hosts: 'test-approved')
    def fetched(url,size,timeout):
        if 'search.brave.com' in url:return _SERP,'text/html'
        assert url=='https://holybro.com/products/x500-v2-kits'
        return _HTML,'text/html'
    result=research_engineering_gap(_REQUEST,fetch=fetched)
    assert result['status']=='source_context_retrieved'
    assert result['retrieved_page_count']==1
    assert result['snippet_only_count']==0
    source=result['sources'][0]
    assert source['evidence_kind']=='fetched_primary_webpage'
    assert source['original_sha256'].startswith('sha256:')
    assert 'KV920' in source['excerpt']
    assert 'evil.example.net' not in str(result)
    assert not result['engineering_design_approved']
    assert result['physical_authority_unchanged']


def test_search_snippets_never_become_publisher_document_hashes(monkeypatch):
    monkeypatch.setattr('hardware_splicer.engineering_web_research._valid_public_host',
                        lambda url,hosts:'approved')
    def fetched(url,size,timeout):
        if 'search.brave.com' in url:return _SERP,'text/html'
        raise OSError('manufacturer portal denied')
    result=research_engineering_gap(_REQUEST,fetch=fetched)
    assert result['status']=='search_snippets_only'
    assert result['retrieved_page_count']==0
    assert result['sources'][0]['original_sha256'] is None
    assert result['sources'][0]['source_scope']=='search_engine_snippet_only_source_page_unreadable'


def _action():
    return {'action_id':'research-a','action_type':'research_engineering_context',
            'project_revision':1,'status':'accepted',
            'inputs':{'research_request_id':'drone-gap','url':'https://evil.example.net'},
            'decision':{'decision':'accepted','reviewer':'software-researcher',
                        'decided_at':'2026-10-21T01:00:00+08:00','executed':False}}


def test_agent_action_only_executes_persisted_gap_not_model_url(tmp_path,monkeypatch):
    store=ProjectStore(tmp_path)
    store.save('research-test',{'engineeringResearchRequests':[_REQUEST]})
    observed=[]
    def evaluator(selected):
        observed.append(selected)
        return {'request_id':'drone-gap','request_sha256':'sha256:example',
                'status':'source_context_retrieved','source_count':1,
                'sources':[{'source_id':'web-example','url':'https://holybro.com/products/x500-v2-kits',
                            'excerpt':'2216 KV920 and BLHeli-S 20A',
                            'original_sha256':'sha256:actual-page'}]}
    monkeypatch.setattr('hardware_splicer.ai_project_tool_executor.research_engineering_gap',evaluator)
    result=execute_ai_project_action_preview(store,'research-test',
        {'session_id':'session-research','project_revision':1},_action())
    assert result['status']=='succeeded'
    assert observed==[_REQUEST]
    assert 'evil.example.net' not in str(observed)
    assert result['summary']['source_count']==1
    assert result['physical_authority_unchanged']
    assert not result['release_authorized']


def test_researched_source_available_to_second_ai_session_as_unverified_evidence():
    snapshot={'engineeringResearchRequests':[_REQUEST],
       'engineeringWebResearchRuns':[{
          'request_id':'drone-gap','research_status':'source_context_retrieved',
          'sources':[{'url':'https://holybro.com/products/x500-v2-kits','source_id':'web-abc',
                      'original_sha256':'sha256:aabb',
                      'title':'Holybro X500 V2 Kit',
                      'excerpt':'Holybro 2216 KV920 Motor with ESC 20A',
                      'source_scope':'unverified_external_data'}]}]}
    context=build_ai_project_context('r',2,snapshot,mission='Select X500 motor')
    assert context['external_research_evidence'][0]['sources'][0]['excerpt'].startswith('Holybro 2216')
    assert context['project_summary']['engineeringResearchRequests'][0]['id']=='drone-gap'
    assert context['external_research_evidence'][0]['sources'][0]['source_scope']=='untrusted_external_publication_not_physical_verification'
    assert context['context_policy']['release_authorized'] is False


def test_original_web_publisher_source_alias_allowed_only_for_claims():
    import json
    from hardware_splicer.ai_project_orchestrator import run_ai_project_orchestrator
    snapshot={'engineeringWebResearchRuns':[{
        'request_id':'manufacturer-proof','research_status':'source_context_retrieved',
        'sources':[
            {'source_id':'web-legalpublisher','url':'https://holybro.com/products/x500-v2-kits',
             'original_sha256':'sha256:valid-source-raw-bytes','excerpt':'Holybro 2216 KV920 20A ESC'},
            {'source_id':'web-onlysnippet','url':'https://holybro.com/products/partial',
             'original_sha256':None,'excerpt':'Some web search excerpt'},
        ]}]}
    def mock(prompt,**kwargs):
        return {'ok':True,'provider':'test','model':'test',
                'content':json.dumps({'summary':'Holybro publishes 2216 KV920',
                'requirements':[{'id':'manufacturer','statement':'Published 2216 KV920',
                                 'source_ids':['W1','web-onlysnippet'],'assumptions':[]}],
                'open_questions':[], 'architecture_candidates':[],
                'actions':[]})}
    s=run_ai_project_orchestrator('test',1,snapshot,mission='What motor model is published?',llm_callable=mock)
    assert s['requirements'][0]['source_ids']==['web-legalpublisher']
    assert s['unrecognized_source_references']==['web-onlysnippet']
    assert s['context']['external_evidence_aliases'][0]['alias']=='W1'
    assert s['context']['context_policy']['release_authorized'] is False


def test_native_api_research_action_resumes_model_with_real_source_context(tmp_path,monkeypatch):
    """End-to-end API persistence and second-session source alias visibility."""
    from fastapi.testclient import TestClient
    from hardware_splicer.product_api import create_product_app
    from hardware_splicer.ai_project_orchestrator import run_ai_project_orchestrator
    store=ProjectStore(tmp_path)
    project='browser-context-replay'
    initial={'projectId':project,'engineeringResearchRequests':[_REQUEST]}
    store.save(project,initial)
    def llm(prompt,**kw):
        return {'ok':True,'provider':'test-only','model':'stubbed',
                'content':json.dumps({
                 'summary':'Search for the missing source',
                 'requirements':[],'architecture_candidates':[],'open_questions':[],
                 'actions':[{'action_type':'research_engineering_context',
                  'title':'Look up manufacturer specification','rationale':'No source has yet been retrieved',
                  'inputs':{'research_request_id':'drone-gap'},'source_ids':[]}]})}
    session=run_ai_project_orchestrator(project,1,initial,mission='Check manufacturer claims',llm_callable=llm)
    snapshot={**initial,'engineeringAiSessions':[session]}
    store.save(project,snapshot,expected_revision=1)
    def fake_research(request):
        assert request==_REQUEST
        return {'request_id':'drone-gap','request_sha256':'sha256:request',
           'status':'source_context_retrieved','source_count':1,
           'sources':[{'source_id':'web-abc123','url':'https://holybro.com/products/x500-v2-kits',
                       'title':'X500 official listing','excerpt':'Holybro 2216 KV920 Motor, BLHeli S ESC 20A',
                       'original_sha256':'sha256:publisher-document',
                       'source_scope':'published claims only'}]}
    monkeypatch.setattr('hardware_splicer.ai_project_tool_executor.research_engineering_gap',fake_research)
    app=TestClient(create_product_app(store))
    action=session['actions'][0]
    route=f'/v1/projects/{project}/ai-sessions/{session["session_id"]}/actions/{action["action_id"]}'
    decision=app.post(route+'/decision',json={'decision':'accepted','reviewer':'bounded-software-operator',
                        'note':'Read public documents only','expected_revision':2})
    assert decision.status_code==200,decision.text
    preview=app.post(route+'/execute-preview',json={'expected_revision':decision.json()['revision']})
    assert preview.status_code==200,preview.text
    assert preview.json()['tool_result']['status']=='succeeded'
    latest=store.load_latest_with_recovery(project)
    assert len(latest['snapshot']['engineeringWebResearchRuns'])==1
    context=build_ai_project_context(project,latest['revision'],latest['snapshot'],mission='Check manufacturer claims')
    assert context['external_research_evidence'][0]['sources'][0]['excerpt'].find('KV920')>=0
    assert context['external_evidence_aliases'][0]['alias']=='W1'
    assert not context['context_policy']['release_authorized']
    again=app.post(route+'/execute-preview',json={'expected_revision':latest['revision']})
    assert again.status_code==200 and again.json()['idempotent'] is True
    assert len(store.load_latest_with_recovery(project)['snapshot']['engineeringWebResearchRuns'])==1


def test_project_pinned_known_publisher_url_retrieval_without_search_engine(monkeypatch):
    monkeypatch.setattr('hardware_splicer.engineering_web_research._valid_public_host',
                        lambda url,hosts:'holybro.com')
    def only_official(url,size,timeout):
        assert url=='https://holybro.com/products/x500-v2-kits'
        return _HTML,'text/html'
    query={**_REQUEST,'source_urls':['https://holybro.com/products/x500-v2-kits']}
    result=research_engineering_gap(query,fetch=only_official)
    assert result['status']=='source_context_retrieved'
    assert result['retrieved_page_count']==1
    assert result['discovery_mode']=='project_provided_known_source'
    assert result['sources'][0]['evidence_kind']=='fetched_primary_webpage'


def test_repeat_source_research_reuses_previous_project_evidence(tmp_path,monkeypatch):
    from datetime import datetime,timezone
    from hardware_splicer.engineering_web_research import research_request_sha256
    store=ProjectStore(tmp_path)
    snap={
      'engineeringResearchRequests':[_REQUEST],
      'engineeringWebResearchRuns':[{
        'request_id':'drone-gap','request_sha256':research_request_sha256(_REQUEST),
        'searched_at_utc':datetime.now(timezone.utc).isoformat(),
        'research_status':'source_context_retrieved',
        'sources':[{'url':'https://holybro.com/products/x500-v2-kits',
           'source_id':'web-old','original_sha256':'sha256:old-page',
           'excerpt':'KV920 ESC 20A'}]}],
    }
    store.save('research-cache',snap)
    def no_network(_):
        raise AssertionError('same project should not requery public network')
    monkeypatch.setattr('hardware_splicer.ai_project_tool_executor.research_engineering_gap',no_network)
    result=execute_ai_project_action_preview(store,'research-cache',
       {'session_id':'cached-research','project_revision':1},_action())
    assert result['status']=='succeeded'
    assert result['summary']['research_status']=='source_context_reused'
    assert result['summary']['source_count']==1
    assert not result['release_authorized']


def test_changed_research_question_invalidates_source_cache(tmp_path,monkeypatch):
    from datetime import datetime,timezone
    from hardware_splicer.engineering_web_research import research_request_sha256
    old_request={**_REQUEST,'question':'What was the original X500 V2 motor?' }
    new_request={**_REQUEST,'question':'What are the revised X500 V2 ESC requirements?'}
    store=ProjectStore(tmp_path)
    store.save('changed-question',{
       'engineeringResearchRequests':[new_request],
       'engineeringWebResearchRuns':[{
          'request_id':'drone-gap','request_sha256':research_request_sha256(old_request),
          'searched_at_utc':datetime.now(timezone.utc).isoformat(),
          'research_status':'source_context_retrieved',
          'sources':[{'source_id':'web-old','url':'https://holybro.com/products/x500-v2-kits',
                      'original_sha256':'sha256:old','excerpt':'old'}],
       }],
    })
    observed=[]
    def freshly_fetched(q):
        observed.append(q)
        return {'request_id':'drone-gap','request_sha256':research_request_sha256(q),
                'searched_at_utc':datetime.now(timezone.utc).isoformat(),
                'status':'source_context_retrieved','source_count':1,
                'sources':[{'url':'https://holybro.com/products/x500-v2-kits',
                   'source_id':'web-new','original_sha256':'sha256:new','excerpt':'new'}]}
    monkeypatch.setattr('hardware_splicer.ai_project_tool_executor.research_engineering_gap',freshly_fetched)
    result=execute_ai_project_action_preview(store,'changed-question',
       {'session_id':'new-research','project_revision':1},_action())
    assert observed==[new_request]
    assert result['summary']['research_status']=='source_context_retrieved'
    assert result['summary']['sources'][0]['source_id']=='web-new'
