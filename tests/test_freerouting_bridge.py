"""Existing FreeRouting build-files bridge stays skip-safe and must not download in tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from hardware_splicer.integrations.freerouting_bridge import (
    run_freerouting_pipeline,
    summarize_freerouting_for_quality,
)

REPO = Path(__file__).resolve().parents[1]
SPI_PCB = (
    REPO
    / "hardware"
    / "reference_designs"
    / "spi_flash_adapter_v1"
    / "spi_flash_adapter_v1.kicad_pcb"
)


def test_missing_pcb_skips(tmp_path: Path) -> None:
    report = run_freerouting_pipeline(tmp_path / "missing.kicad_pcb")
    assert report["ok"] is False
    assert report["skipped"] is True
    assert report["reason"] == "missing_pcb"


def test_skips_without_pcbnew_and_does_not_download() -> None:
    with patch(
        "hardware_splicer.integrations.freerouting_bridge._pcbnew_available",
        return_value=False,
    ):
        with patch(
            "hardware_splicer.integrations.freerouting_bridge.urllib.request.urlretrieve",
        ) as retrieve:
            report = run_freerouting_pipeline(SPI_PCB)
    retrieve.assert_not_called()
    assert report["ok"] is False
    assert report["skipped"] is True
    assert "pcbnew" in str(report["reason"])


def test_skips_without_jar_when_pcbnew_present(tmp_path: Path) -> None:
    pcb = tmp_path / "board.kicad_pcb"
    pcb.write_text("(kicad_pcb (version 20241229))\n", encoding="utf-8")
    with patch(
        "hardware_splicer.integrations.freerouting_bridge._pcbnew_available",
        return_value=True,
    ):
        with patch(
            "hardware_splicer.integrations.freerouting_bridge._resolve_freerouting_jar",
            return_value=None,
        ):
            with patch(
                "hardware_splicer.integrations.freerouting_bridge.urllib.request.urlretrieve",
            ) as retrieve:
                report = run_freerouting_pipeline(pcb)
    retrieve.assert_not_called()
    assert report["skipped"] is True
    assert "jar" in str(report["reason"]) or "java" in str(report["reason"])


def test_summarize_skipped_report() -> None:
    summary = summarize_freerouting_for_quality(
        {"ok": False, "skipped": True, "reason": "pcbnew not available"}
    )
    assert summary["freerouting_ready"] is False
    assert summary["freerouting_skipped"] is True
    assert summary["freerouting_reason"] == "pcbnew not available"


def test_summarize_successful_report() -> None:
    summary = summarize_freerouting_for_quality(
        {
            "ok": True,
            "skipped": False,
            "track_count": 4,
            "routed_pcb_path": "/tmp/routed.kicad_pcb",
            "freerouting_version": "2.1.0",
        }
    )
    assert summary["freerouting_ready"] is True
    assert summary["freerouting_ok"] is True
    assert summary["freerouting_track_count"] == 4
