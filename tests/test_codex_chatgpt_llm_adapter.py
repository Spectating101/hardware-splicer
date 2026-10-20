"""Codex CLI safety/credential boundary; no live service in unit tests."""
from __future__ import annotations
import json
from pathlib import Path
from types import SimpleNamespace

from hardware_splicer.codex_chatgpt_llm_adapter import CodexCliAdapter


def test_cli_uses_chatgpt_auth_without_environment_api_credentials(monkeypatch,tmp_path):
    cli=tmp_path/"codex.js"
    cli.write_text("/* fake executable path */")
    for secret in ("OPENAI_API_KEY","OPENAI_BASE_URL","ANTHROPIC_API_KEY","QWEN_API_KEY"):
        monkeypatch.setenv(secret,"DELIBERATELY_FAKE_SECRET")
    seen={}
    def fake_run(argv,**kwargs):
        seen.update({"argv":argv,**kwargs})
        output=Path(argv[argv.index("-o")+1])
        output.write_text(json.dumps({
            "action":"finish","reason":"source not observed",
            "result":{"measured_donors":0}
        }))
        return SimpleNamespace(returncode=0,stdout="",stderr="")
    monkeypatch.setattr("hardware_splicer.codex_chatgpt_llm_adapter.subprocess.run",fake_run)
    result=CodexCliAdapter(cli_js=cli)("Only inspect context")
    assert result["ok"] and result["provider"]=="codex_chatgpt"
    assert result["separate_api_key_used"] is False
    assert "--ignore-user-config" in seen["argv"]
    assert "--ignore-rules" in seen["argv"]
    assert "--ephemeral" in seen["argv"]
    assert seen["argv"][seen["argv"].index("--sandbox")+1]=="read-only"
    assert seen["argv"][seen["argv"].index("-m")+1]=="gpt-6.1-sol"
    assert seen["input"]==""
    for key in ("OPENAI_API_KEY","OPENAI_BASE_URL","ANTHROPIC_API_KEY","QWEN_API_KEY"):
        assert key not in seen["env"]


def test_invalid_response_fails_without_fake_completion(monkeypatch,tmp_path):
    cli=tmp_path/"codex.js"
    cli.write_text("/* fake */")
    def fake_run(argv,**kw):
        Path(argv[argv.index("-o")+1]).write_text("not JSON")
        return SimpleNamespace(returncode=0,stdout="",stderr="")
    monkeypatch.setattr("hardware_splicer.codex_chatgpt_llm_adapter.subprocess.run",fake_run)
    result=CodexCliAdapter(cli_js=cli)("any")
    assert not result["ok"]
    assert result["error"]=="codex_invalid_json"


def test_cli_rejects_arbitrary_files(tmp_path):
    import pytest
    file=tmp_path/"random_script.py"
    file.write_text("x")
    with pytest.raises(ValueError):
        CodexCliAdapter(cli_js=file)


def test_default_sdk_selects_local_codex_without_other_provider_fallback(monkeypatch,tmp_path):
    import sys,types
    from hardware_splicer import sdk
    fake=tmp_path/"codex.js"
    fake.write_text("/* fake installer path */")
    monkeypatch.setenv("HARDWARE_SPLICER_CODEX_CHATGPT_JS",str(fake))
    fake_module=types.SimpleNamespace(
        run_engineering_reasoning_agent=lambda scenario,**kw: {
            "is_codex":isinstance(kw.get("llm_callable"),CodexCliAdapter),
            "is_live":kw["llm_callable"].is_live_model,
            "steps":kw["max_steps"],
        })
    monkeypatch.setitem(sys.modules,"hardware_splicer.engineering_reasoning_agent",fake_module)
    result=sdk.run_reasoning_engineering_agent(
        scenario={"intake":{"goal":"A new machine"}},max_steps=2
    )
    assert result=={"is_codex":True,"is_live":True,"steps":2}
    import pytest
    with pytest.raises(ValueError):
        sdk.run_reasoning_engineering_agent(
            scenario={"intake":{"goal":"A new machine"}},provider="untrusted_api"
        )
