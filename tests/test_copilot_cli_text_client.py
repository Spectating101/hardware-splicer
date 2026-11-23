import json
from subprocess import CompletedProcess
from hardware_splicer.integrations import llm_text_client as client
from hardware_splicer.integrations import copilot_cli_text_client as bridge


def test_explicit_copilot_model_succeeds_only_with_tools_disabled(monkeypatch):
    monkeypatch.setenv('HARDWARE_SPLICER_LLM_PROVIDER','copilot_cli')
    monkeypatch.setattr(bridge.shutil,'which',lambda _: '/fake/copilot')
    commands=[]
    def fake_run(args,**kwargs):
        commands.append(args)
        return CompletedProcess(args,0,'{"summary":"hold"}', '')
    monkeypatch.setattr(bridge.subprocess,'run',fake_run)
    monkeypatch.setattr(client,'cache_enabled',lambda:False)
    monkeypatch.setattr(client,'write_cached_response',lambda *a,**kw:None)
    monkeypatch.setattr(client,'record_text_usage',lambda *a,**kw:None)
    got=client.call_llm_chat('Generate bounded engineering proposal',json_mode=True)
    assert got['ok'] is True and got['provider']=='copilot_cli'
    assert json.loads(got['content'])['summary']=='hold'
    assert '--available-tools' in commands[0]
    assert commands[0][commands[0].index('--available-tools')+1]=='none'
    assert '--no-custom-instructions' in commands[0]


def test_invalid_json_fails_closed(monkeypatch):
    monkeypatch.setattr(bridge.shutil,'which',lambda _:'/fake')
    monkeypatch.setattr(bridge.subprocess,'run',lambda args,**kw: CompletedProcess(args,0,'not json',''))
    got=bridge.call_copilot_cli_chat('test',json_mode=True)
    assert got['error']=='copilot_cli_invalid_json'


def test_binary_allowlist_prevents_arbitrary_commands(monkeypatch):
    monkeypatch.setenv('HARDWARE_SPLICER_COPILOT_CLI_BINARY','evil-sudo')
    assert not bridge.copilot_cli_configured()
    assert bridge.call_copilot_cli_chat('test')['ok'] is False


def test_bad_model_action_inputs_get_specific_validation_error():
    from hardware_splicer.ai_project_orchestrator import InvalidAIProjectResponse, parse_ai_project_response
    import pytest
    bad={'summary':'proposal','requirements':[], 'open_questions':[],
         'architecture_candidates':[], 'actions':[{'action_type':'run_compose',
          'title':'Create board','rationale':'Draft only','inputs':'use some modules'}]}
    with pytest.raises(InvalidAIProjectResponse,match=r'actions\[0\]\.inputs must be an object'):
        parse_ai_project_response(json.dumps(bad),session_id='s',project_id='p',project_revision=1,max_actions=6)
