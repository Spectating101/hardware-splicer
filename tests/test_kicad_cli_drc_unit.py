from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from hardware_splicer.pcb.kicad_cli_drc import run_kicad_cli_drc, summarize_for_quality


def _pcb(tmp_path: Path) -> Path:
    path = tmp_path / "board.kicad_pcb"
    path.write_text("(kicad_pcb (version 20240108) (generator pcbnew))", encoding="utf-8")
    return path


def test_drc_ignores_explicitly_excluded_violations(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("hardware_splicer.pcb.kicad_cli_drc.shutil.which", lambda _: "/usr/bin/kicad-cli")

    def fake_run(args, **kwargs):
        report_path = Path(args[args.index("--output") + 1])
        report_path.write_text(
            json.dumps(
                {
                    "kicad_version": "9.0.6",
                    "source": "board.kicad_pcb",
                    "violations": [
                        {"severity": "error", "type": "courtyard", "excluded": True},
                        {"severity": "warning", "type": "silk"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="saved", stderr="")

    monkeypatch.setattr("hardware_splicer.pcb.kicad_cli_drc.subprocess.run", fake_run)
    report = run_kicad_cli_drc(_pcb(tmp_path), out_dir=tmp_path / "drc")
    assert report["pass"] is True
    assert report["errors"] == 0
    assert report["warnings"] == 1
    assert report["kicad_version"] == "9.0.6"


def test_nonzero_execution_keeps_report_and_diagnostics(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("hardware_splicer.pcb.kicad_cli_drc.shutil.which", lambda _: "/usr/bin/kicad-cli")

    def fake_run(args, **kwargs):
        report_path = Path(args[args.index("--output") + 1])
        report_path.write_text(
            json.dumps(
                {
                    "kicad_version": "9.0.0",
                    "violations": [{"severity": "error", "type": "clearance", "description": "Too close"}],
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=2, stdout="report written", stderr="plugin load warning")

    monkeypatch.setattr("hardware_splicer.pcb.kicad_cli_drc.subprocess.run", fake_run)
    report = run_kicad_cli_drc(_pcb(tmp_path), out_dir=tmp_path / "drc")
    quality = summarize_for_quality(report)
    assert report["pass"] is False
    assert report["report_errors"] == 1
    assert report["errors"] == 2
    assert report["returncode"] == 2
    assert quality["kicad_drc_violations"][0]["type"] == "clearance"
    assert "plugin load warning" in quality["kicad_drc_stderr"]


def test_missing_report_retains_cli_failure_text(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("hardware_splicer.pcb.kicad_cli_drc.shutil.which", lambda _: "/usr/bin/kicad-cli")
    monkeypatch.setattr(
        "hardware_splicer.pcb.kicad_cli_drc.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="unknown option --format"),
    )
    report = run_kicad_cli_drc(_pcb(tmp_path), out_dir=tmp_path / "drc")
    assert report["pass"] is False
    assert report["reason"] == "kicad-cli drc failed"
    assert report["violations"][0]["type"] == "kicad_cli_error"
    assert "unknown option" in report["stderr"]
