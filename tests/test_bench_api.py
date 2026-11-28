"""The workbench data API reports the recorded run and measured comparisons without upgrading anything."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer import bench_api

REGISTRY = json.loads((Path(bench_api.__file__).parent / "data" / "external_tools.json").read_text())


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(bench_api.create_bench_router())
    return TestClient(app)


def test_spine_lists_fourteen_steps_with_four_gates():
    body = _client().get("/v1/bench/spine").json()
    assert [s["n"] for s in body["steps"]] == list(range(1, 15))
    assert body["gates"] == [2, 4, 5, 11]


def test_spine_reads_the_recorded_run_without_inventing_steps():
    steps = {s["key"]: s for s in bench_api.spine()["steps"]}
    assert steps["erc"]["run"] == {"line": "0 errors · 0 warnings", "outcome": "clean"}
    assert steps["drc"]["run"]["outcome"] == "clean"
    assert steps["krt"]["run"]["outcome"] == "not_run"
    assert steps["decoupling"]["run"]["outcome"] == "unknown"
    assert all(s["run"]["outcome"] in {"clean", "failed", "recorded", "not_run", "unknown"} for s in steps.values())


def test_spine_run_carries_its_not_checked_list_and_claim_boundary():
    run = bench_api.spine()["run"]
    assert run["not_checked"] and "not been fabricated" in run["claim_boundary"]


def test_outside_tools_named_by_steps_exist_in_the_registry():
    names = {t["name"] for t in (REGISTRY["tools"] if isinstance(REGISTRY, dict) else REGISTRY)}
    named = {r for s in bench_api.SPINE for r in s["runs"] if not r.startswith(("HS", "KiCad symbol", "pcbnew"))}
    assert named <= names, named - names


def test_measures_quote_the_held_out_numbers():
    rows = {r["name"]: r["caught"] for r in bench_api.measures()["checkers"]["rows"]}
    assert rows["KiCad ERC"] == 9 and rows["HS review (rules fixed before this set)"] == 4 and rows["All three together"] == 14


def test_renders_are_whitelisted():
    client = _client()
    assert client.get("/v1/bench/renders/top").headers["content-type"] == "image/png"
    assert client.get("/v1/bench/renders/..%2Fverification").status_code == 404


def test_records_follow_the_configured_repo_root(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_REPO_ROOT", str(tmp_path))
    body = bench_api.spine()
    assert body["run"] is None
    assert {s["run"]["outcome"] for s in body["steps"]} == {"unknown"}
    assert bench_api.measures() == {}
