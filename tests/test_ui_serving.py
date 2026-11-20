from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
import sys

from fastapi.testclient import TestClient
import pytest

from hardware_splicer import api, cli_entry
from hardware_splicer.project_store import ProjectStore


def product_factory():
    pytest.importorskip("pypdf", reason="product API requires pypdf")
    from hardware_splicer.product_api import create_product_app

    return create_product_app


def fake_dist(path: Path) -> Path:
    (path / "assets").mkdir(parents=True)
    (path / "index.html").write_text("<html>Hardware-Splicer test UI</html>", encoding="utf-8")
    (path / "assets/app-aB12_cdE.js").write_text("console.log('test')", encoding="utf-8")
    (path / "assets/plain.js").write_text("// unversioned", encoding="utf-8")
    (path / "robots.txt").write_text("User-agent: *", encoding="utf-8")
    return path


@pytest.fixture
def ui_paths(tmp_path, monkeypatch):
    module = tmp_path / "checkout/src/hardware_splicer/api.py"
    monkeypatch.setattr(api, "__file__", str(module))
    monkeypatch.setenv("HARDWARE_SPLICER_REPO_ROOT", str(tmp_path / "checkout"))
    monkeypatch.delenv("HARDWARE_SPLICER_UI_DIST", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_SERVE_UI", raising=False)
    monkeypatch.setenv("HARDWARE_SPLICER_JOB_DB", str(tmp_path / "jobs.sqlite"))
    monkeypatch.setenv("HARDWARE_SPLICER_PROJECT_ROOT", str(tmp_path / "projects"))
    # Lookup order: explicit (--ui-dist), environment, packaged ui_dist, checkout dist.
    return [
        tmp_path / "cli",
        tmp_path / "env",
        module.parent / "ui_dist",
        tmp_path / "checkout/apps/splice-ui/dist",
    ]


@pytest.mark.parametrize("first_available", range(4))
def test_ui_resolution_order(ui_paths, monkeypatch, first_available):
    for path in ui_paths[first_available:]:
        fake_dist(path)
    monkeypatch.setenv("HARDWARE_SPLICER_UI_DIST", str(ui_paths[1]))
    assert api._resolve_ui_dist(ui_paths[0]) == ui_paths[first_available]


def test_auto_mode_serves_a_build_when_found_and_skips_quietly_otherwise(ui_paths, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_SERVE_UI", "auto")
    with TestClient(api.create_app()) as client:
        assert client.get("/health").json()["ui"]["served"] is False
        assert client.get("/").status_code == 404
    fake_dist(ui_paths[3])
    with TestClient(api.create_app()) as client:
        assert client.get("/health").json()["ui"]["source"] == "checkout"
        assert client.app.state.ui_dist == str(ui_paths[3])
        assert "test UI" in client.get("/").text


def test_ui_requested_but_missing_fails_startup(ui_paths, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_SERVE_UI", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_UI_DIST", str(ui_paths[1]))
    app = api.create_app(ui_dist=ui_paths[0])
    with pytest.raises(RuntimeError, match="UI serving requested") as error:
        with TestClient(app):
            pytest.fail("startup should fail")
    for path in ui_paths:
        assert str(path / "index.html") in str(error.value)
    assert "make ui-package" in str(error.value)


def test_ui_disabled_health(ui_paths):
    with TestClient(api.create_app()) as client:
        assert client.get("/").status_code == 404
        assert client.get("/health").json()["ui"] == {
            "served": False, "source": None, "index_sha256": None,
        }


@pytest.mark.parametrize("product", [False, True])
def test_ui_routes_health_and_cache_headers(ui_paths, monkeypatch, tmp_path, product):
    dist = fake_dist(ui_paths[1])
    (dist / "escape.txt").symlink_to(tmp_path / "secret.txt")
    (tmp_path / "secret.txt").write_text("outside dist", encoding="utf-8")
    monkeypatch.setenv("HARDWARE_SPLICER_SERVE_UI", "1")
    if product:
        app = product_factory()(ProjectStore(tmp_path / "store"), ui_dist=dist)
    else:
        app = api.create_app(ui_dist=dist)
    with TestClient(app) as client:
        # Every client route the SPA router owns reloads to index.html, query string included.
        for path in ("/", "/projects/project-123", "/index.html", "/projects/new",
                     "/projects/project-123?rev=2", "/library", "/library/sorting-workcell",
                     "/advanced", "/advanced/interface-lab", "/scenes/fielddeck", "/no/such/page"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.text == (dist / "index.html").read_text(encoding="utf-8")
            assert response.headers["cache-control"] == "no-cache"
        ui = client.get("/health").json()["ui"]
        assert ui == {
            "served": True,
            "source": "argument",
            "index_sha256": hashlib.sha256((dist / "index.html").read_bytes()).hexdigest(),
        }
        assert client.get("/docs").status_code == 200
        schema = client.get("/openapi.json")
        assert schema.status_code == 200
        assert "/health" in schema.json()["paths"]
        assert client.get("/v1/jobs").json()["ok"] is True
        if product:
            assert client.get("/v1/projects").status_code == 200
            assert "projects" in client.get("/v1/projects").json()
        for path in ("/api", "/api/missing", "/v1", "/v1/missing", "/docs/missing",
                     "/health/missing", "/assets", "/assets/missing.js", "/escape.txt",
                     "/%2e%2e/secret.txt"):
            assert client.get(path).status_code == 404, path
        assert client.get("/robots.txt").text == "User-agent: *"
        asset = client.get("/assets/app-aB12_cdE.js")
        assert asset.status_code == 200
        assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
        cached = client.get("/assets/app-aB12_cdE.js", headers={"If-None-Match": asset.headers["etag"]})
        assert cached.status_code == 304
        assert cached.headers["cache-control"] == asset.headers["cache-control"]
        assert "immutable" not in client.get("/assets/plain.js").headers.get("cache-control", "")


def test_missing_assets_without_assets_directory(ui_paths, monkeypatch):
    dist = ui_paths[1]
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("UI", encoding="utf-8")
    monkeypatch.setenv("HARDWARE_SPLICER_SERVE_UI", "1")
    with TestClient(api.create_app(ui_dist=dist)) as client:
        assert client.get("/assets/missing.js").status_code == 404
        assert client.get("/projects/one").text == "UI"


@pytest.fixture
def serve(monkeypatch):
    calls = []
    monkeypatch.delenv("HARDWARE_SPLICER_HOST", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_PORT", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_UI_DIST", raising=False)
    monkeypatch.setenv("HARDWARE_SPLICER_SERVE_UI", "")
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: calls.append((args, kwargs)))

    def invoke(*args):
        monkeypatch.setattr(sys, "argv", ["hs-serve", *args])
        cli_entry.main_serve()
        return calls

    return invoke


def test_serve_defaults_and_environment(serve, monkeypatch):
    import os

    assert serve()[-1] == (("hardware_splicer.product_api:app",), {
        "host": "127.0.0.1", "port": 8787, "reload": False,
    })
    assert os.environ["HARDWARE_SPLICER_SERVE_UI"] == "auto"
    monkeypatch.setenv("HARDWARE_SPLICER_HOST", "::1")
    monkeypatch.setenv("HARDWARE_SPLICER_PORT", "9000")
    assert serve()[-1][1]["host"] == "::1"
    assert serve()[-1][1]["port"] == 9000
    options = serve("--host", "127.0.0.2", "--port", "9001")[-1][1]
    assert options["host"] == "127.0.0.2"
    assert options["port"] == 9001


def test_serve_ui_dist_option_overrides_environment(serve, ui_paths, monkeypatch):
    import os

    product_factory()
    env_dist = fake_dist(ui_paths[1])
    cli_dist = fake_dist(ui_paths[0])
    monkeypatch.setenv("HARDWARE_SPLICER_UI_DIST", str(env_dist))
    assert serve("--ui", "--ui-dist", str(cli_dist))[-1][0] == ("hardware_splicer.product_api:app",)
    assert os.environ["HARDWARE_SPLICER_SERVE_UI"] == "1"
    assert os.environ["HARDWARE_SPLICER_UI_DIST"] == str(cli_dist)
    with TestClient(product_factory()(ProjectStore(ui_paths[0].parent / "store"))) as client:
        assert client.get("/health").json()["ui"]["source"] == "environment"
        assert client.app.state.ui_dist == str(cli_dist)


def test_serve_ui_flags(serve):
    import os

    serve("--ui")
    assert os.environ["HARDWARE_SPLICER_SERVE_UI"] == "1"
    serve("--no-ui")
    assert os.environ["HARDWARE_SPLICER_SERVE_UI"] == "0"
    with pytest.raises(SystemExit):
        serve("--ui", "--no-ui")


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.0.2.1", "example.invalid"])
@pytest.mark.parametrize("via_env", [False, True])
def test_remote_bind_requires_allow_remote(serve, monkeypatch, capsys, host, via_env):
    args = [] if via_env else ["--host", host]
    if via_env:
        monkeypatch.setenv("HARDWARE_SPLICER_HOST", host)
    with pytest.raises(SystemExit) as error:
        serve(*args)
    assert error.value.code == 2
    message = capsys.readouterr().err
    for text in ("--allow-remote", "no in-app authentication yet", "DEPLOY.md", "nginx"):
        assert text in message
    assert serve(*args, "--allow-remote")[-1][1]["host"] == host
    assert "no in-app authentication yet" in capsys.readouterr().err


def test_package_ui_copies_files_and_hashes_and_removes_stale_files(tmp_path):
    package_ui = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/package_ui.py"))["package_ui"]
    source = fake_dist(tmp_path / "dist")
    destination = tmp_path / "package/ui_dist"
    destination.mkdir(parents=True)
    (destination / "stale.js").write_text("stale", encoding="utf-8")
    package_ui(source, destination)
    assert not (destination / "stale.js").exists()
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["sha256"] == {
        path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source.rglob("*") if path.is_file()
    }
    for name in manifest["sha256"]:
        assert (destination / name).read_bytes() == (source / name).read_bytes()
