from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hardware_splicer.jarvis_build import _open_compose_llm_first, jarvis_build


def test_jarvis_build_open_without_qwen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_COMPOSE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_LLM_TRUST", "0")
    result = jarvis_build("wifi temperature logger with esp32 and dht22", out_dir=tmp_path, export_gerber=False)
    assert result.get("ok") is True
    assert (tmp_path / "build_compilation" / "TRUST_REPORT.json").is_file()


def test_jarvis_narrative_attached_when_mocked(tmp_path: Path) -> None:
    fake_narrative = {
        "ok": True,
        "headline": "Build looks good for bench bring-up",
        "summary": "KiCad DRC is clean and simulation passed.",
        "next_steps": ["Bench test", "Open KiCad if curious"],
        "confidence": "high",
    }
    with patch(
        "hardware_splicer.jarvis_build.generate_jarvis_narrative",
        return_value=fake_narrative,
    ):
        result = jarvis_build(
            "wifi temperature logger with esp32 and dht22",
            out_dir=tmp_path,
            export_gerber=False,
            allow_qwen=False,
        )
    trust = json.loads((tmp_path / "build_compilation" / "TRUST_REPORT.json").read_text(encoding="utf-8"))
    assert trust.get("jarvis_headline") == fake_narrative["headline"]
    assert result.get("jarvis", {}).get("headline") == fake_narrative["headline"]


def test_llm_first_semantic_review_never_executes_scratch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    proposal = {
        "ok": False,
        "error": "semantic_module_review_required",
        "compose_mode": "semantic_module_proposal",
        "requires_human_review": True,
        "module_ids": ["candidate-a", "candidate-b"],
        "semantic_intent": {"goal_summary": "typed intent"},
        "semantic_candidate_set": {"candidates_by_requirement": {}},
        "semantic_selection": {"selected_module_ids": ["candidate-a", "candidate-b"]},
        "authority_effect": "none",
        "automatic_execution": False,
    }

    monkeypatch.setattr(
        "hardware_splicer.jarvis_build.compose_netlist_from_goal",
        lambda goal, constraints=None, allow_qwen=True: dict(proposal),
    )

    def fail_if_scratch_runs(*args, **kwargs):
        raise AssertionError("semantic review boundary was bypassed by scratch execution")

    monkeypatch.setattr(
        "hardware_splicer.jarvis_build.compile_scratch_build",
        fail_if_scratch_runs,
    )

    result = _open_compose_llm_first(
        "novel hardware goal",
        tmp_path,
        constraints={},
        export_gerber=False,
        allow_qwen=True,
    )

    assert result["ok"] is False
    assert result["compose_mode"] == "semantic_module_proposal"
    assert result["requires_human_review"] is True
    assert result["automatic_execution"] is False
    assert result["authority_effect"] == "none"
    assert result["compile_result"] is None
    assert result["module_ids"] == ["candidate-a", "candidate-b"]
