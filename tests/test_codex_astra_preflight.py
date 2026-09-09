from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer import codex_astra_preflight as preflight


def test_codex_version_floor() -> None:
    assert preflight.parse_codex_version("codex-cli 0.153.0") == (0, 153, 0)
    assert preflight.version_is_supported("codex 0.153.0")
    assert preflight.version_is_supported("codex 0.160.1")
    assert not preflight.version_is_supported("codex 0.152.9")
    assert not preflight.version_is_supported("unknown")


def test_login_status_distinguishes_chatgpt_from_api_key() -> None:
    assert preflight.classify_login_status("", "Logged in using ChatGPT") == "chatgpt"
    assert preflight.classify_login_status("", "Logged in using API key") == "api_key"
    assert preflight.classify_login_status("", "Not logged in") == "not_authenticated"
    assert preflight.classify_login_status("", "something else") == "unknown"


def test_bundled_catalog_detects_astra_without_loose_string_match() -> None:
    catalog = {
        "models": [
            {"slug": "gpt-5.6-sol"},
            {"slug": "gpt-6-astra", "display_name": "GPT-6 Astra"},
        ]
    }
    assert preflight.bundled_catalog_has_model(json.dumps(catalog)) is True
    assert preflight.bundled_catalog_has_model(
        json.dumps({"notes": "the text gpt-6-astra appears here but is not a model row"})
    ) is False
    assert preflight.bundled_catalog_has_model("not-json") is False


@pytest.mark.parametrize(
    ("workspace", "repo", "expected"),
    [
        ("/tmp/hs-astra", "/src/hardware-splicer", True),
        ("/src/hardware-splicer/experiment", "/src/hardware-splicer", False),
        ("/src", "/src/hardware-splicer", False),
        ("/src/hardware-splicer", "/src/hardware-splicer", False),
    ],
)
def test_workspace_must_not_overlap_repo(workspace: str, repo: str, expected: bool) -> None:
    assert preflight.paths_are_disjoint(workspace, repo) is expected


def test_api_key_presence_is_reported_without_values() -> None:
    env = {"OPENAI_API_KEY": "secret-value", "PATH": "/bin"}
    assert preflight.present_api_key_env(env) == ("OPENAI_API_KEY",)
    clean = preflight.build_launch_environment(env)
    assert "OPENAI_API_KEY" not in clean


def test_cleanroom_overrides_are_fail_closed(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "cleanroom"
    repo = tmp_path / "hardware-splicer"
    mcp = tmp_path / "bin" / "hs-backend-mcp"
    workspace.mkdir()
    repo.mkdir()
    mcp.parent.mkdir()
    mcp.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(preflight.shutil, "which", lambda command, path=None: str(mcp))

    overrides = preflight.build_cleanroom_overrides(
        workspace=workspace,
        hs_repo_root=repo,
        mcp_command="hs-backend-mcp",
    )
    joined = "\n".join(overrides)

    assert 'forced_login_method="chatgpt"' in joined
    assert 'model="gpt-6-astra"' in joined
    assert 'approval_policy="never"' in joined
    assert 'web_search="disabled"' in joined
    assert "features.web_search_request=false" in joined
    assert 'default_permissions="hs-astra-cleanroom"' in joined
    assert 'permissions.hs-astra-cleanroom.filesystem.":minimal"="read"' in joined
    assert f'{str(workspace.resolve())}' in joined and '"write"' in joined
    assert f'{str(repo.resolve())}' in joined and '"deny"' in joined
    assert "permissions.hs-astra-cleanroom.network.enabled=false" in joined
    assert "mcp_servers.hardware-splicer-backend.required=true" in joined
    assert (
        'mcp_servers.hardware-splicer-backend.default_tools_approval_mode="approve"'
        in joined
    )
    assert (
        'mcp_servers.hardware-splicer-backend.enabled_tools='
        '["hs_backend_status","hs_backend_list_operations",'
        '"hs_backend_describe_operation","hs_backend_call"]'
        in joined
    )
    assert "mcp_servers.hardware-splicer-backend.tools.hs_backend_call.output_token_limit=8000" in joined


def test_cleanroom_overrides_reject_repo_nested_workspace(tmp_path: Path) -> None:
    repo = tmp_path / "hardware-splicer"
    workspace = repo / "experiment"
    workspace.mkdir(parents=True)
    with pytest.raises(ValueError, match="clean-room"):
        preflight.build_cleanroom_overrides(
            workspace=workspace,
            hs_repo_root=repo,
            mcp_command="hs-backend-mcp",
        )


def test_launch_argv_is_ephemeral_and_does_not_execute(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "cleanroom"
    repo = tmp_path / "hardware-splicer"
    mcp = tmp_path / "bin" / "hs-backend-mcp"
    workspace.mkdir()
    repo.mkdir()
    mcp.parent.mkdir()
    mcp.write_text("#!/bin/sh\n", encoding="utf-8")
    mission = workspace / "MISSION.txt"
    mission.write_text("mission", encoding="utf-8")
    monkeypatch.setattr(preflight.shutil, "which", lambda command, path=None: str(mcp))

    argv = preflight.build_codex_exec_argv(
        workspace=workspace,
        hs_repo_root=repo,
        mcp_command="hs-backend-mcp",
        prompt_file=mission,
        trace_file=workspace / "trace.jsonl",
        last_message_file=workspace / "last.txt",
    )

    assert argv[0] == "codex"
    assert "exec" in argv
    assert "--ignore-user-config" in argv
    assert "--ignore-rules" in argv
    assert "--skip-git-repo-check" in argv
    assert "--ephemeral" in argv
    assert "--json" in argv
    assert argv[argv.index("-m") + 1] == "gpt-6-astra"
    assert argv[-1] == "-"
    assert "OPENAI_API_KEY" not in " ".join(argv)


def test_launch_files_must_be_inside_cleanroom(tmp_path: Path) -> None:
    workspace = tmp_path / "cleanroom"
    repo = tmp_path / "hardware-splicer"
    workspace.mkdir()
    repo.mkdir()
    mission = tmp_path / "MISSION.txt"
    mission.write_text("mission", encoding="utf-8")

    with pytest.raises(ValueError, match="prompt_file"):
        preflight.build_codex_exec_argv(
            workspace=workspace,
            hs_repo_root=repo,
            mcp_command="/bin/false",
            prompt_file=mission,
            trace_file=workspace / "trace.jsonl",
            last_message_file=workspace / "last.txt",
        )


def test_preflight_passes_only_chatgpt_path_with_bundled_astra(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "cleanroom"
    repo = tmp_path / "hardware-splicer"
    workspace.mkdir()
    repo.mkdir()

    def fake_resolve(command, env=None):
        return f"/fake/{command}"

    def fake_run(argv, *, env=None):
        if argv[-1] == "--version":
            return preflight.CommandResult(tuple(argv), 0, "codex-cli 0.153.0\n", "")
        if argv[-2:] == ["login", "status"]:
            return preflight.CommandResult(tuple(argv), 0, "", "Logged in using ChatGPT\n")
        if argv[-3:] == ["debug", "models", "--bundled"]:
            return preflight.CommandResult(
                tuple(argv),
                0,
                json.dumps({"models": [{"slug": "gpt-6-astra"}]}),
                "",
            )
        raise AssertionError(argv)

    monkeypatch.setattr(preflight, "resolve_executable", fake_resolve)
    monkeypatch.setattr(preflight, "_run", fake_run)

    report = preflight.run_zero_inference_preflight(
        workspace=workspace,
        hs_repo_root=repo,
        env={"PATH": "/fake/bin"},
    )
    assert report.pass_ is True
    assert report.auth_mode == "chatgpt"
    assert report.astra_bundled_catalog_ok is True
    assert report.inference_performed is False
    assert report.provider_network_probe_performed is False
    assert report.as_dict()["bundled_catalog_refresh_performed"] is False


def test_preflight_rejects_binary_without_bundled_astra(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "cleanroom"
    repo = tmp_path / "hardware-splicer"
    workspace.mkdir()
    repo.mkdir()
    monkeypatch.setattr(preflight, "resolve_executable", lambda command, env=None: f"/fake/{command}")

    def fake_run(argv, *, env=None):
        if argv[-1] == "--version":
            return preflight.CommandResult(tuple(argv), 0, "codex-cli 0.153.0\n", "")
        if argv[-2:] == ["login", "status"]:
            return preflight.CommandResult(tuple(argv), 0, "", "Logged in using ChatGPT\n")
        return preflight.CommandResult(
            tuple(argv), 0, json.dumps({"models": [{"slug": "gpt-5.6-sol"}]}), ""
        )

    monkeypatch.setattr(preflight, "_run", fake_run)
    report = preflight.run_zero_inference_preflight(
        workspace=workspace,
        hs_repo_root=repo,
        env={"PATH": "/fake/bin"},
    )
    assert report.pass_ is False
    assert report.chatgpt_auth_ok is True
    assert report.astra_bundled_catalog_ok is False


def test_preflight_rejects_api_key_auth_and_api_key_env(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "cleanroom"
    repo = tmp_path / "hardware-splicer"
    workspace.mkdir()
    repo.mkdir()

    monkeypatch.setattr(preflight, "resolve_executable", lambda command, env=None: f"/fake/{command}")

    def fake_run(argv, *, env=None):
        if argv[-1] == "--version":
            return preflight.CommandResult(tuple(argv), 0, "codex-cli 0.153.0\n", "")
        if argv[-2:] == ["login", "status"]:
            return preflight.CommandResult(tuple(argv), 0, "", "Logged in using API key\n")
        return preflight.CommandResult(
            tuple(argv), 0, json.dumps({"models": [{"slug": "gpt-6-astra"}]}), ""
        )

    monkeypatch.setattr(preflight, "_run", fake_run)
    report = preflight.run_zero_inference_preflight(
        workspace=workspace,
        hs_repo_root=repo,
        env={"PATH": "/fake/bin", "OPENAI_API_KEY": "secret"},
    )
    assert report.pass_ is False
    assert report.auth_mode == "api_key"
    assert report.astra_bundled_catalog_ok is True
    assert report.api_key_env_present == ("OPENAI_API_KEY",)
    assert "secret" not in str(report.as_dict())
