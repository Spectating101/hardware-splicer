from __future__ import annotations

import json
import sys
from pathlib import Path

from hardware_splicer.integrations.kicad_happy_adapter import run_kicad_happy


def _write_fake_analyzer(root: Path, body: str) -> Path:
    script_dir = root / "skills" / "kicad" / "scripts"
    script_dir.mkdir(parents=True)
    script = script_dir / "analyze_schematic.py"
    script.write_text(body, encoding="utf-8")
    return script


def test_missing_checkout_returns_structured_skip(tmp_path: Path) -> None:
    source = tmp_path / "board.kicad_sch"
    source.write_text("(kicad_sch)", encoding="utf-8")
    result = run_kicad_happy(
        analyzer_root=tmp_path / "missing",
        profile="schematic",
        input_path=source,
        output_dir=tmp_path / "out",
    )
    assert result["skipped"] is True
    assert result["authority_ceiling"] == "observed"
    assert "not found" in result["skip_reason"]


def test_ingests_tier_one_evidence_and_scrubs_secrets(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "kicad-happy"
    source = tmp_path / "board.kicad_sch"
    source.write_text("(kicad_sch)", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    _write_fake_analyzer(
        root,
        """
import argparse, json, os
p = argparse.ArgumentParser()
p.add_argument('source')
p.add_argument('--output', required=True)
a = p.parse_args()
assert not os.environ.get('OPENAI_API_KEY')
payload = {
  'analyzer_type': 'schematic',
  'schema_version': '1.4.0',
  'findings': [{'rule_id': 'TEST-1', 'severity': 'warning', 'confidence': 'deterministic'}],
  'assessments': [{'kind': 'measurement', 'value': 3.3}],
  'trust_summary': {'provenance_coverage_pct': 100},
  'inputs': {'run_id': 'fake-run'},
  'compat': {'minimum_consumer_version': '1.0.0'}
}
open(a.output, 'w', encoding='utf-8').write(json.dumps(payload))
""",
    )
    result = run_kicad_happy(
        analyzer_root=root,
        profile="schematic",
        input_path=source,
        output_dir=tmp_path / "out",
        adapter_version="fake-commit",
        python_executable=sys.executable,
    )
    assert result["casefile"] is None
    assert result["exit_code"] == 0
    assert result["findings"][0]["rule_id"] == "TEST-1"
    assert result["trust_summary"]["provenance_coverage_pct"] == 100
    assert result["authority_ceiling"] == "observed"
    assert result["input_hashes"]
    assert result["output_hashes"]


def test_input_mutation_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "kicad-happy"
    source = tmp_path / "board.kicad_sch"
    source.write_text("original", encoding="utf-8")
    _write_fake_analyzer(
        root,
        """
import argparse, json
p = argparse.ArgumentParser()
p.add_argument('source')
p.add_argument('--output', required=True)
a = p.parse_args()
open(a.source, 'w', encoding='utf-8').write('mutated')
open(a.output, 'w', encoding='utf-8').write(json.dumps({'schema_version': '1.4.0'}))
""",
    )
    result = run_kicad_happy(
        analyzer_root=root,
        profile="schematic",
        input_path=source,
        output_dir=tmp_path / "out",
        python_executable=sys.executable,
    )
    assert result["casefile"]["kind"] == "input_mutation"
    assert result["authority_ceiling"] == "observed"


def test_unsupported_schema_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "kicad-happy"
    source = tmp_path / "board.kicad_sch"
    source.write_text("original", encoding="utf-8")
    _write_fake_analyzer(
        root,
        """
import argparse, json
p = argparse.ArgumentParser()
p.add_argument('source')
p.add_argument('--output', required=True)
a = p.parse_args()
open(a.output, 'w', encoding='utf-8').write(json.dumps({'schema_version': '2.0.0'}))
""",
    )
    result = run_kicad_happy(
        analyzer_root=root,
        profile="schematic",
        input_path=source,
        output_dir=tmp_path / "out",
        python_executable=sys.executable,
    )
    assert result["casefile"]["kind"] == "unsupported_schema"


def test_timeout_returns_casefile(tmp_path: Path) -> None:
    root = tmp_path / "kicad-happy"
    source = tmp_path / "board.kicad_sch"
    source.write_text("original", encoding="utf-8")
    _write_fake_analyzer(
        root,
        """
import time
time.sleep(10)
""",
    )
    result = run_kicad_happy(
        analyzer_root=root,
        profile="schematic",
        input_path=source,
        output_dir=tmp_path / "out",
        python_executable=sys.executable,
        timeout_s=0.1,
    )
    assert result["timed_out"] is True
    assert result["casefile"]["kind"] == "adapter_timeout"
