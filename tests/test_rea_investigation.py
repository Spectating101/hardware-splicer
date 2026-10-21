import json
from types import SimpleNamespace
from hardware_splicer.rea_investigation import investigate_artifact

def test_rea_accepts_static_evidence_without_authorization(tmp_path,monkeypatch):
    p=tmp_path/'owned.bin';p.write_bytes(b'controlled demo')
    seen={}
    def runner(argv,**kwargs):
        seen['args']=argv
        return SimpleNamespace(returncode=0,stdout=json.dumps({'artifact':{'kind':'example'},'observations':[]}),stderr='')
    monkeypatch.setattr('hardware_splicer.rea_investigation.subprocess.run',runner)
    r=investigate_artifact(p,rea_executable='/opt/rea')
    assert seen['args']==['/opt/rea','inspect-artifact',str(p),'--format','json']
    assert r['status']=='analysis_available_unverified'
    assert r['artifact_sha256'].startswith('sha256:')
    assert not r['release_authorized']

def test_rea_rejects_unsupported_artifact_without_false_positive(tmp_path,monkeypatch):
    p=tmp_path/'blob.bin';p.write_bytes(b'not a known format')
    monkeypatch.setattr('hardware_splicer.rea_investigation.subprocess.run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=json.dumps({'error':'Analysis failed','code':'target_unavailable','message':'unsupported binary format'}),stderr=''))
    r=investigate_artifact(p)
    assert r['status']=='blocked' and r['provider_code']=='target_unavailable'
    assert not r['firmware_flash_authorized']

def test_rea_unavailable_does_not_promote(tmp_path,monkeypatch):
    p=tmp_path/'f.bin';p.write_bytes(b'hi')
    monkeypatch.setattr('hardware_splicer.rea_investigation.subprocess.run',lambda *a,**k:(_ for _ in ()).throw(FileNotFoundError()))
    assert investigate_artifact(p)['status']=='unavailable'

def test_js_analysis_uses_static_cli_and_keeps_nonrelease(tmp_path,monkeypatch):
    from hardware_splicer.rea_investigation import investigate_javascript_application
    (tmp_path/'index.js').write_text('module.exports={a:1}')
    observed={}
    def run(argv,**kw):
        observed['argv']=argv
        return SimpleNamespace(returncode=0,stdout=json.dumps({'predicate_type':'rea.javascript-application-analysis','evidence_id':'ev_demo','subject':{'digest':{'sha256':'sample'}}}),stderr='')
    monkeypatch.setattr('hardware_splicer.rea_investigation.subprocess.run',run)
    r=investigate_javascript_application(tmp_path)
    assert observed['argv'][1]=='analyze-javascript-application'
    assert r['status']=='static_analysis_available_unverified'
    assert not r['source_executed'] and not r['release_authorized']
