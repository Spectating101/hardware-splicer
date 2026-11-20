"""Every API call the built UI makes must route on the one served app.

The UI's calls are read from apps/splice-ui/src (template and string literals that
contain an API path), so a new fetch without a backend route fails here instead of
as a 404 in the browser.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Match, Mount

from hardware_splicer.project_store import ProjectStore

ROOT = Path(__file__).resolve().parents[1]
UI_SRC = ROOT / "apps" / "splice-ui" / "src"
LITERAL = re.compile(r"`([^`]*)`|\"([^\"\n]*)\"|'([^'\n]*)'")
API_PATH = re.compile(r"(/v1(?:/|\$\{|\?|$)[^\s]*|/health(?=$|\?))")
METHOD = re.compile(r"method:\s*[\"'`](GET|POST|PUT|PATCH|DELETE)[\"'`]")
SPA_ROUTES = {"splice_ui_root", "splice_ui_spa"}
# URL builders: the literal is a base the caller extends, so check the extensions.
# Each entry names the caller and the template it uses, which must still exist.
BASE_URLS = {
    "/v1/scenes/sample-id/sample-id": (
        "components/fielddeckStage.js", ("`${url}/parts`", "`${url}/model`"), ("/parts", "/model"),
    ),
}


def _normalise(raw: str) -> str:
    path = raw.split("?", 1)[0]
    # A placeholder that fills a whole segment is an id; one glued to a segment
    # (``/v1/projects${suffix}``) is an optional query string or suffix.
    path = re.sub(r"(?<=/)\$\{[^}]*\}", "sample-id", path)
    path = re.sub(r"\$\{[^}]*\}", "", path)
    return path.rstrip("/") or "/"


def ui_api_calls() -> list[tuple[str, str, str]]:
    """Return (path, method, where) for each API path literal in the UI source."""

    calls = []
    for source in sorted(UI_SRC.rglob("*")):
        if source.suffix not in {".js", ".jsx"} or ".test." in source.name:
            continue
        text = source.read_text(encoding="utf-8")
        for match in LITERAL.finditer(text):
            literal = next(group for group in match.groups() if group is not None)
            found = API_PATH.search(literal)
            if not found:
                continue
            prefix = literal[: found.start()]
            if prefix and not re.fullmatch(r"\$\{[A-Za-z_.]+\}", prefix):
                continue  # prose that merely mentions a path
            # The call's options follow within the same statement.
            tail = text[match.end(): match.end() + 240].split(";", 1)[0]
            method = METHOD.search(tail)
            line = text.count("\n", 0, match.start()) + 1
            path = _normalise(found.group(1))
            where = f"{source.relative_to(ROOT)}:{line}"
            if path in BASE_URLS:
                caller, templates, suffixes = BASE_URLS[path]
                caller_text = (UI_SRC / caller).read_text(encoding="utf-8")
                assert all(t in caller_text for t in templates), f"{caller} no longer extends {path}"
                calls.extend((path + suffix, "", f"{where} via {caller}") for suffix in suffixes)
                continue
            calls.append((path, method.group(1) if method else "", where))
    return calls


def api_routes(app):
    return [
        route for route in app.router.routes
        if not isinstance(route, Mount) and getattr(route, "name", "") not in SPA_ROUTES
    ]


def route_for(app, path: str, method: str):
    """FULL match for the method when given, else any path match. None when unrouted."""

    scope = {"type": "http", "path": path, "method": method or "GET", "root_path": ""}
    partial = None
    for route in api_routes(app):
        result, _ = route.matches(scope)
        if result is Match.FULL:
            return route
        if result is Match.PARTIAL and partial is None:
            partial = route
    return None if method else partial


@pytest.fixture
def served_app(tmp_path, monkeypatch):
    pytest.importorskip("pypdf", reason="product API requires pypdf")
    from hardware_splicer.product_api import create_product_app

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>served ui</html>", encoding="utf-8")
    monkeypatch.setenv("HARDWARE_SPLICER_SERVE_UI", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("HARDWARE_SPLICER_JOB_DB", raising=False)
    monkeypatch.setenv("HARDWARE_SPLICER_JOB_WORKERS", "0")
    return create_product_app(ProjectStore(tmp_path / "projects"), ui_dist=dist)


def test_ui_source_scan_finds_the_calls_it_should():
    paths = {path for path, _, _ in ui_api_calls()}
    # Anchors from each family: legacy engine, product, digital and scenes.
    for expected in ("/health", "/v1/examples/splice-intakes", "/v1/jobs", "/v1/vision/capabilities",
                     "/v1/projects", "/v1/digital/cases", "/v1/scenes", "/v1/scenes/sample-id/records",
                     "/v1/scenes/sample-id/sample-id/parts", "/v1/scenes/sample-id/sample-id/model"):
        assert expected in paths, expected
    assert len(paths) > 60


def test_every_ui_api_call_routes_on_the_served_app(served_app):
    missing = [
        f"{method or 'ANY'} {path}  ({where})"
        for path, method, where in ui_api_calls()
        if route_for(served_app, path, method) is None
    ]
    assert not missing, "UI calls with no route on the served app:\n" + "\n".join(missing)


def test_api_routes_win_over_the_spa_and_v1_misses_stay_json(served_app):
    names = [getattr(route, "name", "") for route in served_app.router.routes]
    assert names[-1] == "splice_ui_spa"
    with TestClient(served_app) as client:
        assert client.get("/projects/anything").text == "<html>served ui</html>"
        health = client.get("/health")
        assert health.headers["content-type"].startswith("application/json")
        assert health.json()["ui"]["served"] is True
        assert client.get("/v1/digital/cases").headers["content-type"].startswith("application/json")
        assert client.get("/v1/scenes").headers["content-type"].startswith("application/json")
        for path in ("/v1/no-such-route", "/v1/projects/x/no-such-child", "/v1"):
            response = client.get(path)
            assert response.status_code == 404, path
            assert response.headers["content-type"].startswith("application/json"), path
            assert "served ui" not in response.text
