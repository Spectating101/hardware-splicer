"""Ensure agy print-mode arguments do not silently turn switches into prompt."""
from __future__ import annotations
import subprocess
from hardware_splicer.integrations import agy_text_client as client


def test_agy_cli_uses_equals_prompt_and_disables_file_side_effects(monkeypatch):
    seen=[]
    monkeypatch.setattr(client, 'agy_configured', lambda: True)
    def mocked(cmd, **kw):
        seen.append((cmd,kw))
        return subprocess.CompletedProcess(cmd, 0, '{"summary":"test"}', '')
    monkeypatch.setattr(client.subprocess, 'run', mocked)
    result=client.call_agy_chat('Respond in JSON', model='claude-opus-5-5-high',
            json_mode=True,timeout_s=35,system='No tools')
    assert result['ok'] and result['model']=='claude-opus-5-5-high'
    cmd=seen[0][0]
    assert '--mode' in cmd and cmd[cmd.index('--mode')+1]=='plan'
    assert '--sandbox' in cmd and '--disable-slash-commands' in cmd
    assert '--print' not in cmd
    assert cmd[-1].startswith('--print=')
    assert 'Respond in JSON' in cmd[-1]
    assert cmd.index('--model') < cmd.index('--print-timeout')
    assert seen[0][1].get('shell') is not True


def test_agy_prompt_size_has_bounded_failure(monkeypatch):
    monkeypatch.setattr(client,'agy_configured',lambda: True)
    resp=client.call_agy_chat('x'*120_000,model='gemini-4-argon-high')
    assert resp['ok'] is False
    assert resp['error']=='agy_prompt_too_large_for_cli'


def test_agy_never_accepts_nonzero_exit_with_json_stdout(monkeypatch):
    monkeypatch.setattr(client,'agy_configured',lambda:True)
    def quota_result(cmd,**kw):
        return subprocess.CompletedProcess(cmd,3,
          '{"conversation_id":"test","status":"ERROR","response":"",'
          '"error":"Individual quota reached. Resets in 4h."}',
          'AGY_ERROR: RESOURCE_EXHAUSTED (code 429)')
    monkeypatch.setattr(client.subprocess,'run',quota_result)
    result=client.call_agy_chat('Return JSON',model='claude-sonnet-5-5-high',json_mode=True)
    assert result['ok'] is False
    assert result['error']=='agy_quota_exhausted'


def test_agy_enforces_json_and_safe_temporary_cwd(monkeypatch):
    monkeypatch.setattr(client,'agy_configured',lambda:True)
    seen=[]
    def invalid(cmd,**kw):
        seen.append(kw)
        return subprocess.CompletedProcess(cmd,0,'This is not JSON.','')
    monkeypatch.setattr(client.subprocess,'run',invalid)
    result=client.call_agy_chat('Return one JSON object',model='claude-opus-5-5-high',json_mode=True)
    assert result['error']=='agy_invalid_json'
    assert seen[0]['cwd'].startswith('/tmp/hs-agy-model-only-')
    assert not __import__('os').path.exists(seen[0]['cwd'])
