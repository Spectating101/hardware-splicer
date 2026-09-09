"""Exercise the real runner with synthetic corpus inputs and mock HTTP, never a paid API.

Only corpus construction and provider I/O are replaced. The runner's request building,
trace audit, case persistence, aggregate persistence, selection, and exit logic execute.
The frozen experiment corpus and product backend are not evaluated by these tests.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import httpx
import pytest


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    cases = [
        SimpleNamespace(
            case_id=f"fixture-{i}", equivalence_group="fixture-equiv", perturbation_kind="fixture",
            project_revision="fixture-r1", metadata={"outer_only": "hidden-evaluator-marker"},
            snapshot={"mission": "Inspect the supplied evidence; leave unknowns unresolved.",
                      "engineeringSources": [{"source_id": "src-a"}]},
        )
        for i in range(3)
    ]
    # Isolate this harness test from hardware, heavy cleanroom imports, and scored cases.
    corpus = ModuleType("hardware_splicer.cleanroom_unseen_spi_flash_experiment")
    corpus.SCHEMA_VERSION = "test-only-corpus"  # type: ignore[attr-defined]
    corpus.build_unseen_spi_flash_cases = lambda: cases  # type: ignore[attr-defined]
    corpus.validate_unseen_spi_flash_corpus = lambda: {"pass": True}  # type: ignore[attr-defined]
    replay = ModuleType("hardware_splicer.cleanroom_replay")
    replay.ReplayCase = SimpleNamespace  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, corpus.__name__, corpus)
    monkeypatch.setitem(sys.modules, replay.__name__, replay)
    monkeypatch.setattr(sys, "path", list(sys.path))
    path = Path(__file__).resolve().parents[1] / "scripts/run_external_mcp_agent_proof.py"
    spec = importlib.util.spec_from_file_location("hs_external_proof_runner_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_git_head", lambda: "test-only-head")
    return module


def _response(request: httpx.Request) -> dict:
    payload = json.loads(request.content)
    assert payload["store"] is False
    assert "hidden-evaluator-marker" not in payload["input"]
    assert "fixture-equiv" not in payload["input"]
    match = re.search(r"experiment_project_id: (\S+)", payload["input"])
    assert match is not None
    project_id = match.group(1)
    calls = [
        ("hs_backend_status", {}),
        ("hs_backend_list_operations", {}),
        ("hs_backend_describe_operation", {"operation_id": "save_project"}),
        ("hs_backend_call", {"operation_id": "save_project", "path_params": {"project_id": project_id},
                             "json_body": {"source_ids": ["src-a"], "power_on_authorized": False}}),
    ]
    return {
        "id": "synthetic-response", "model": "test-model", "status": "completed",
        "output": [{"type": "mcp_call", "name": name, "server_label": "hardware_splicer",
                    "status": "completed", "arguments": json.dumps(arguments), "output": "{}"}
                   for name, arguments in calls],
    }


def _invoke(runner: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, mode: str, selected: bool = False):
    real_client = httpx.Client
    request_count = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        payload = _response(request)
        # Keep one accepted case before the failure so aggregate masking is exercised.
        if request_count == 2:
            if mode == "interrupt":
                raise KeyboardInterrupt()
            if mode == "transport_error":
                raise httpx.ReadTimeout("synthetic timeout", request=request)
            if mode == "http_error":
                return httpx.Response(429, json={"error": "synthetic rate limit"})
            if mode == "redirect":
                return httpx.Response(302, json=payload)
            if mode == "array":
                return httpx.Response(200, json=[payload])
            if mode == "text":
                return httpx.Response(200, text="not JSON")
            if mode == "incomplete":
                payload["status"] = "incomplete"
                payload["incomplete_details"] = {"reason": "max_output_tokens"}
            if mode == "status_only":
                payload["output"] = payload["output"][:1]
            if mode == "bad_arguments":
                payload["output"][-1]["arguments"] = "{bad-json"
            if mode == "calling":
                payload["output"][-1]["status"] = "calling"
            if mode == "authority_attempt":
                args = json.loads(payload["output"][-1]["arguments"])
                args["json_body"]["power_on_authorized"] = True
                payload["output"][-1]["arguments"] = json.dumps(args)
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(runner.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs))
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key-never-sent")
    for key in ("HS_MCP_SERVER_URL", "HS_MCP_TUNNEL_ID", "HS_EXTERNAL_AGENT_MODEL"):
        monkeypatch.delenv(key, raising=False)
    args = ["runner", "--server-url", "https://example.invalid/mcp", "--model", "test-model", "--out-dir", str(tmp_path)]
    if selected:
        args += ["--case-id", "fixture-0", "--case-id", "fixture-1"]
    monkeypatch.setattr(sys, "argv", args)
    exit_code = runner.main()
    root = next(tmp_path.iterdir())
    aggregate = json.loads((root / "EXTERNAL_REPLAY.json").read_text())
    audit = json.loads((root / "EXTERNAL_TRUTH_AUDIT.json").read_text())
    return exit_code, aggregate, audit, root


@pytest.mark.parametrize("selected", [False, True])
@pytest.mark.parametrize("mode,expected_exit", [
    ("status_only", 9), ("incomplete", 7), ("bad_arguments", 9), ("calling", 6),
    ("authority_attempt", 9), ("transport_error", 7), ("http_error", 7),
    ("redirect", 7), ("array", 7), ("text", 7),
])
def test_runner_rejects_bad_case_without_masking_it(runner, monkeypatch, tmp_path, selected, mode, expected_exit):
    exit_code, aggregate, audit, root = _invoke(runner, monkeypatch, tmp_path, mode=mode, selected=selected)
    assert exit_code == expected_exit
    assert aggregate["selected_cases_proof_pass"] is False
    assert audit["hard_truth_contract_pass"] is False
    assert audit["hard_truth_failure_count"] == 1
    assert audit["hard_truth_failures"][0]["case_id"] == "fixture-1"
    assert len(aggregate["case_summaries"]) == (2 if selected else 3)
    if expected_exit == 7:
        assert aggregate["selected_cases_completed"] is False
        assert aggregate["full_frozen_corpus_completed"] is False
    else:
        assert aggregate["selected_cases_completed"] is True
    bad_dir = root / "cases" / "02-fixture-1"
    assert (bad_dir / "CASE_SUMMARY.json").exists()
    if mode == "transport_error":
        assert (bad_dir / "TRANSPORT_ERROR.txt").exists()
    else:
        assert (bad_dir / "OPENAI_RESPONSE.json").exists()
    if mode == "incomplete":
        bad = json.loads((bad_dir / "CASE_SUMMARY.json").read_text())
        assert bad["status"] == "openai_response_not_completed"
        assert bad["response_status"] == "incomplete"
        assert bad["response_incomplete_details"] == {"reason": "max_output_tokens"}
    if mode == "bad_arguments":
        raw = json.loads((bad_dir / "OPENAI_RESPONSE.json").read_text())
        assert raw["output"][-1]["arguments"] == "{bad-json"
    assert aggregate["physical_authority_granted"] is False
    assert aggregate["live_unseen_competence"] == "UNADJUDICATED"
    assert aggregate["physical_correctness"] == "UNPROVEN"


@pytest.mark.parametrize("selected", [False, True])
def test_runner_accepts_complete_selected_scope_without_upgrading_claims(runner, monkeypatch, tmp_path, selected):
    exit_code, aggregate, audit, root = _invoke(runner, monkeypatch, tmp_path, mode="safe", selected=selected)
    assert exit_code == 0
    assert aggregate["selected_cases_completed"] is True
    assert aggregate["selected_cases_proof_pass"] is True
    assert aggregate["full_frozen_corpus_completed"] is (not selected)
    assert audit["hard_truth_contract_pass"] is True
    assert aggregate["physical_authority_granted"] is False
    assert aggregate["live_unseen_competence"] == "UNADJUDICATED"
    assert aggregate["physical_correctness"] == "UNPROVEN"
    for path in root.rglob("*.json"):
        assert "synthetic-test-key-never-sent" not in path.read_text()


def test_interrupted_run_keeps_partial_evidence_and_missing_inventory(runner, monkeypatch, tmp_path):
    with pytest.raises(KeyboardInterrupt):
        _invoke(runner, monkeypatch, tmp_path, mode="interrupt")
    root = next(tmp_path.iterdir())
    audit = json.loads((root / "EXTERNAL_TRUTH_AUDIT.json").read_text())
    aggregate = json.loads((root / "EXTERNAL_REPLAY.json").read_text())
    assert audit["missing_case_ids"] == ["fixture-1", "fixture-2"]
    assert audit["hard_truth_contract_pass"] is False
    assert aggregate["selected_cases_proof_pass"] is False
    assert aggregate["completed_case_count"] == 1
    assert aggregate["selected_case_count"] == 3
