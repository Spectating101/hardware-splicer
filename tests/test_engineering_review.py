from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.integrations.engineering_review import (
    engineering_review_status,
    run_engineering_review,
)

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


def _fake_adapter(
    root: Path,
    *,
    schema_version: str = "1.4.0",
    mutate_input: bool = False,
    sleep_s: float = 0.0,
) -> Path:
    script_dir = root / "skills" / "kicad" / "scripts"
    script_dir.mkdir(parents=True)
    for analyzer_type in ("schematic", "pcb", "gerber"):
        script = script_dir / f"analyze_{analyzer_type}.py"
        script.write_text(
            f'''from __future__ import annotations
import argparse
import json
import os
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("input")
parser.add_argument("--output", required=True)
args = parser.parse_args()

if os.environ.get("OPENAI_API_KEY"):
    raise RuntimeError("provider secret leaked into analyzer")
time.sleep({sleep_s!r})
input_path = Path(args.input)
if {mutate_input!r} and input_path.is_file():
    input_path.write_text(input_path.read_text(encoding="utf-8") + "\\nmutated", encoding="utf-8")

payload = {{
    "analyzer_type": {analyzer_type!r},
    "schema_version": {schema_version!r},
    "summary": {{"total_findings": 1}},
    "trust_summary": {{"provenance_coverage_pct": 92.0}},
    "inputs": {{"source_files": [str(input_path)]}},
    "compat": {{"minimum_consumer_version": "1.0.0"}},
    "findings": [{{
        "rule_id": "PW-001",
        "severity": "error",
        "summary": "Power rail mismatch",
        "recommendation": "Verify the regulator feedback network.",
        "confidence": "deterministic",
        "evidence_source": "schematic-net-graph",
        "components": ["U1"],
        "nets": ["+3V3"],
    }}],
    "assessments": [],
}}
Path(args.output).write_text(json.dumps(payload), encoding="utf-8")
''',
            encoding="utf-8",
        )
    return root


def _build(root: Path, *, pcb: bool = True, schematic: bool = True) -> Path:
    compilation = root / "build_compilation"
    compilation.mkdir(parents=True)
    if pcb:
        (compilation / "demo.kicad_pcb").write_text(
            "(kicad_pcb (version 20241229))\n",
            encoding="utf-8",
        )
    if schematic:
        (compilation / "demo.kicad_sch").write_text(
            "(kicad_sch (version 20231120))\n",
            encoding="utf-8",
        )
    return root


def _configure(monkeypatch: pytest.MonkeyPatch, build: Path, adapter: Path) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_HAPPY_ROOT", str(adapter))
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-adapter")


def test_engineering_review_normalizes_findings_and_caches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build = _build(tmp_path / "build")
    adapter = _fake_adapter(tmp_path / "kicad-happy")
    _configure(monkeypatch, build, adapter)

    status = engineering_review_status(build)
    assert status["can_run"] is True
    assert set(status["supported_inputs"]) == {"pcb", "schematic"}

    result = run_engineering_review(build, timeout_s=5, force=True)
    assert result["ok"] is True
    assert result["authority"]["maximum"] == "observed"
    assert result["authority"]["may_authorize_release"] is False
    assert result["summary"]["blocker_count"] == 2
    assert result["release_effect"] == "blocked"
    assert result["findings"][0]["components"] == ["U1"]
    assert result["findings"][0]["nets"] == ["+3V3"]
    assert (build / "build_compilation" / "ENGINEERING_REVIEW.json").is_file()

    cached = run_engineering_review(build, timeout_s=5)
    assert cached["cached"] is True
    assert cached["run_id"] == result["run_id"]


def test_engineering_review_fails_closed_when_input_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build = _build(tmp_path / "build", pcb=False)
    adapter = _fake_adapter(tmp_path / "kicad-happy", mutate_input=True)
    _configure(monkeypatch, build, adapter)

    result = run_engineering_review(build, timeout_s=5, force=True)
    assert result["ok"] is False
    assert result["summary"]["status"] == "failed"
    assert result["findings"] == []
    assert any(row["reason"] == "input_mutation_detected" for row in result["failures"])
    assert any(row["kind"] == "casefile" for row in result["artifacts"])


def test_engineering_review_rejects_unsupported_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build = _build(tmp_path / "build", pcb=False)
    adapter = _fake_adapter(tmp_path / "kicad-happy", schema_version="2.0.0")
    _configure(monkeypatch, build, adapter)

    result = run_engineering_review(build, timeout_s=5, force=True)
    assert result["ok"] is False
    assert result["summary"]["status"] == "failed"
    assert result["failures"][0]["reason"] == "invalid_output"
    assert "unsupported schematic schema major 2" in result["failures"][0]["detail"]


def test_engineering_review_timeout_is_structured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build = _build(tmp_path / "build", pcb=False)
    adapter = _fake_adapter(tmp_path / "kicad-happy", sleep_s=2.0)
    _configure(monkeypatch, build, adapter)

    result = run_engineering_review(build, timeout_s=0.1, force=True)
    assert result["ok"] is False
    assert result["failures"][0]["reason"] == "timeout"
    assert result["invocations"][0]["timed_out"] is True


def test_product_api_exposes_review_status_and_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build = _build(tmp_path / "build")
    adapter = _fake_adapter(tmp_path / "kicad-happy")
    _configure(monkeypatch, build, adapter)
    client = TestClient(create_product_app())

    status = client.post(
        "/v1/build-files/engineering-review/status",
        json={"build_dir": str(build)},
    )
    assert status.status_code == 200
    assert status.json()["can_run"] is True

    run = client.post(
        "/v1/build-files/engineering-review/run",
        json={"build_dir": str(build), "timeout_s": 5, "force": True},
    )
    assert run.status_code == 200
    assert run.json()["summary"]["blocker_count"] == 2
