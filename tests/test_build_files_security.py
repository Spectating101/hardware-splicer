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


def _client_with_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Path]:
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)
    root = tmp_path / "allowed"
    build = root / "job-1"
    (build / "build_compilation").mkdir(parents=True)
    (build / "build_compilation" / "demo.kicad_pcb").write_text("(kicad_pcb)\n", encoding="utf-8")
    (build / "notes.txt").write_text("not a kicad file", encoding="utf-8")
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(root))
    return TestClient(create_app()), build


def test_content_serves_kicad_file_inside_build_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, build = _client_with_root(tmp_path, monkeypatch)
    ok = client.post(
        "/v1/build-files/content",
        json={"build_dir": str(build), "relative": "build_compilation/demo.kicad_pcb"},
    )
    assert ok.status_code == 200
    assert ok.json()["kind"] == "pcb"


@pytest.mark.parametrize("relative", ["../outside.kicad_pcb", "build_compilation/../../outside.kicad_pcb"])
def test_content_rejects_parent_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str) -> None:
    client, build = _client_with_root(tmp_path, monkeypatch)
    (build.parent / "outside.kicad_pcb").write_text("(kicad_pcb)\n", encoding="utf-8")
    denied = client.post("/v1/build-files/content", json={"build_dir": str(build), "relative": relative})
    assert denied.status_code == 422


def test_content_does_not_follow_absolute_relative_outside_build_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, build = _client_with_root(tmp_path, monkeypatch)
    secret = tmp_path / "secret.kicad_pcb"
    secret.write_text("(kicad_pcb (secret))\n", encoding="utf-8")
    denied = client.post("/v1/build-files/content", json={"build_dir": str(build), "relative": str(secret)})
    assert denied.status_code == 422


def test_content_rejects_symlink_escaping_build_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, build = _client_with_root(tmp_path, monkeypatch)
    secret = tmp_path / "secret.kicad_pcb"
    secret.write_text("(kicad_pcb (secret))\n", encoding="utf-8")
    (build / "link.kicad_pcb").symlink_to(secret)
    denied = client.post("/v1/build-files/content", json={"build_dir": str(build), "relative": "link.kicad_pcb"})
    assert denied.status_code == 422


def test_content_rejects_non_kicad_suffix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, build = _client_with_root(tmp_path, monkeypatch)
    denied = client.post("/v1/build-files/content", json={"build_dir": str(build), "relative": "notes.txt"})
    assert denied.status_code == 422


def test_content_and_list_reject_build_dir_outside_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _build = _client_with_root(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.kicad_pcb").write_text("(kicad_pcb)\n", encoding="utf-8")
    assert client.post("/v1/build-files/list", json={"build_dir": str(outside)}).status_code == 422
    assert (
        client.post(
            "/v1/build-files/content", json={"build_dir": str(outside), "relative": "x.kicad_pcb"}
        ).status_code
        == 422
    )
