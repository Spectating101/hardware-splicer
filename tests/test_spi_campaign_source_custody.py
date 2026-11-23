"""Campaign generation must preserve the reference used by other evidence."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess

import pytest


def test_failed_native_campaign_build_preserves_reference_receipt(tmp_path, monkeypatch):
    builder = Path(__file__).resolve().parents[1] / (
        "hardware/reference_designs/spi_flash_adapter_v1/build_remote_fct_campaign.py"
    )
    spec = importlib.util.spec_from_file_location("spi_campaign_custody", builder)
    campaign = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(campaign)

    source = tmp_path / "reference"
    source.mkdir()
    receipt = source / "verification.json"
    receipt.write_text('{"toolchain": "previously recorded"}\n')
    (source / "build_package.py").write_text("# stand-in source\n")
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    monkeypatch.setattr(campaign, "HERE", source)
    working_directories = []

    def failed_native_build(*args, cwd=source):
        # Real build_package.py calls verify_design.py, which overwrites the
        # receipt with the installed toolchain's version before later exports.
        working_directories.append(cwd)
        (cwd / "verification.json").write_text('{"toolchain": "new native run"}\n')
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(campaign, "run", failed_native_build)
    with pytest.raises(subprocess.CalledProcessError):
        campaign.build_campaign()

    assert {p.name: p.read_bytes() for p in source.iterdir()} == before
    assert working_directories and all(p != source for p in working_directories)
