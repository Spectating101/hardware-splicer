"""Security boundaries for build-files API."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hardware_splicer.api import create_app


def test_build_dir_rejected_outside_output_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)
    allowed_root = tmp_path / "allowed"
    build = allowed_root / "job-1"
    comp = build / "build_compilation"
    comp.mkdir(parents=True)
    (comp / "demo.kicad_pcb").write_text("(kicad_pcb (version 20241229))\n", encoding="utf-8")

    outside = tmp_path / "outside"
    outside.mkdir()
    evil = outside / "secret.txt"
    evil.write_text("nope", encoding="utf-8")

    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(allowed_root))

    client = TestClient(create_app())
    ok = client.post("/v1/build-files/list", json={"build_dir": str(build)}).json()
    assert ok["ok"] is True

    denied = client.post("/v1/build-files/list", json={"build_dir": str(outside)})
    assert denied.status_code == 422
    assert "OUTPUT_ROOT" in denied.json()["detail"]["error"]["message"]


def test_download_rejects_traversal_and_unknown_suffix(tmp_path: Path) -> None:
    comp = tmp_path / "build_compilation"
    comp.mkdir(parents=True)
    (comp / "demo.kicad_pcb").write_text("(kicad_pcb)\n", encoding="utf-8")
    (comp / "evil.exe").write_bytes(b"MZ")

    client = TestClient(create_app())
    traversal = client.post(
        "/v1/build-files/download",
        json={"build_dir": str(tmp_path), "relative": "../outside"},
    )
    assert traversal.status_code == 422

    bad_type = client.post(
        "/v1/build-files/download",
        json={"build_dir": str(tmp_path), "relative": "build_compilation/evil.exe"},
    )
    assert bad_type.status_code == 422
