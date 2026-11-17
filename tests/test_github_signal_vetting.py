"""Offline evidence tests: neither metadata nor vetting can approve a tool."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from hardware_splicer import github_signal_pipeline as pipeline
from hardware_splicer import github_signal_vetting as vetting
from scripts import vet_github_signal_candidates as cli

PCM_FIXTURE = Path(__file__).parent / "fixtures" / "kicad_pcm_packages.json"
PIN = "a" * 40
NOW = datetime(2026, 11, 18, tzinfo=timezone.utc)
CANDIDATE = {"repository": "example/board-review", "commit_sha": PIN, "license_spdx_id": "MIT"}


@pytest.fixture(autouse=True)
def no_live_http(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("tests must never use live HTTP")
    monkeypatch.setattr(vetting, "urlopen", forbidden)


def card_data(commit=PIN, score=8):
    return {"score": score, "repo": {"name": "github.com/example/board-review", "commit": commit},
            "checks": [{"name": name, "score": 10} for name in vetting.CHECKS]}


def eco_data(**updates):
    return {"license": "MIT", "archived": False, "fork": False,
            "stargazers_count": 123, "pushed_at": "2026-11-01T00:00:00Z",
            "default_branch": "main", "dependent_repos_count": 7, **updates}


def transport_for(data=None, *, raw=None, error=None, status=200, calls=None):
    def transport(request, *, timeout):
        assert timeout == 7
        if calls is not None:
            calls.append(request.full_url)
        if error:
            raise error
        response = io.BytesIO(raw if raw is not None else json.dumps(data).encode())
        response.status = status
        return response
    return transport


def clients(card=None, eco=None):
    return {
        "scorecard_client": vetting.ScorecardClient(
            transport=transport_for(card if card is not None else card_data()), timeout=7),
        "ecosystems_client": vetting.EcosystemsClient(
            transport=transport_for(eco if eco is not None else eco_data()), timeout=7),
        "scancode_fn": lambda *args: {"status": "unavailable"},
        "now": NOW,
    }


def test_pcm_fixture_keeps_provenance_without_inventing_source_pins():
    data = json.loads(PCM_FIXTURE.read_text())
    feed = vetting.parse_pcm_feed(data)
    plugin, library, unlicensed = feed["candidates"]
    assert feed["schema_version"] == "hardware_splicer.github_signal_feed.v1"
    assert plugin["repository"] == "example/board-review"
    assert plugin["license_spdx_id"] == "MIT"
    assert plugin["pcm"]["versions"] == data["packages"][0]["versions"]
    assert plugin["pcm"]["license"] == "MIT"
    assert library["pcm"]["type"] == "library" and library["repository"] is None
    assert unlicensed["license_spdx_id"] == "UNKNOWN"
    assert unlicensed["repository"] == "example/outline-helper"
    assert all(candidate["commit_sha"] is None for candidate in feed["candidates"])
    # Archive hashes must never become execution pins or relax admission.
    with pytest.raises(pipeline.SignalEvaluationError, match="source pin"):
        pipeline.normalize_feed(feed)


def test_pcm_repository_descriptor_local_and_remote(tmp_path):
    raw = PCM_FIXTURE.read_bytes()
    descriptor = {"name": "Example PCM", "packages": {
        "url": "packages.json", "sha256": hashlib.sha256(raw).hexdigest(),
    }}
    (tmp_path / "packages.json").write_bytes(raw)
    metadata = tmp_path / "repository.json"
    metadata.write_text(json.dumps(descriptor))
    assert len(vetting.load_pcm_feed(metadata, offline=True)["candidates"]) == 3
    calls = []

    def transport(request, *, timeout):
        calls.append(request.full_url)
        return transport_for(descriptor if request.full_url.endswith("repository.json") else None,
                             raw=raw if request.full_url.endswith("packages.json") else None)(
                                 request, timeout=timeout)

    feed = vetting.load_pcm_feed("https://example.org/pcm/repository.json", transport=transport, timeout=7)
    assert len(feed["candidates"]) == 3
    assert calls == ["https://example.org/pcm/repository.json", "https://example.org/pcm/packages.json"]
    descriptor["packages"]["sha256"] = "0" * 64
    metadata.write_text(json.dumps(descriptor))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        vetting.load_pcm_feed(metadata, offline=True)
    with pytest.raises(ValueError, match="offline"):
        vetting.load_pcm_feed("https://example.org/packages.json", offline=True)


def test_scorecard_client_extracts_requested_checks_and_pin():
    calls = []
    result = vetting.ScorecardClient(transport=transport_for(card_data(), calls=calls), timeout=7).get(
        CANDIDATE["repository"], PIN)
    assert calls == ["https://api.securityscorecards.dev/projects/github.com/example/board-review"]
    assert result["status"] == "ok" and result["score"] == 8
    assert result["scored_commit"] == PIN and result["matches_pinned_commit"] is True
    assert set(result["checks"]) == set(vetting.CHECKS)
    assert result["retrieved_at"]


def test_ecosystems_client_lookup_and_metadata():
    calls = []
    result = vetting.EcosystemsClient(transport=transport_for(eco_data(), calls=calls), timeout=7).get(
        "https://github.com/example/board-review")
    assert calls == ["https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/example%2Fboard-review"]
    assert result["status"] == "ok" and result["license_spdx_id"] == "MIT"
    assert result["stargazers_count"] == 123 and result["dependent_repos_count"] == 7
    assert result["pushed_at"] == "2026-11-01T00:00:00Z"
    assert result["default_branch"] == "main" and result["archived"] is False


@pytest.mark.parametrize("pushed", [42, "not-a-date", "2026-11-01T00:00:00"])
def test_malformed_activity_is_source_error_not_a_vetter_exception(pushed):
    result = vetting.vet_candidate(CANDIDATE, **clients(eco=eco_data(pushed_at=pushed)))
    assert result["sources"]["ecosystems"]["status"] == "error"
    assert result["approval_effect"] == "none"


def test_raising_injected_clients_are_source_errors():
    def fail(*args):
        raise TimeoutError("source timed out")

    client = SimpleNamespace(get=fail)
    result = vetting.vet_candidate(CANDIDATE, scorecard_client=client,
                                   ecosystems_client=client, scancode_fn=fail)
    assert all(result["sources"][name]["status"] == "error"
               for name in ("scorecard", "ecosystems", "scancode"))
    assert result["approval_effect"] == "none"


@pytest.mark.parametrize("source", ["scorecard", "ecosystems"])
@pytest.mark.parametrize("failure", ["http", "http_status", "timeout", "url_error", "json", "schema"])
def test_client_failures_are_error_evidence_through_vetter(source, failure):
    options = {
        "http": {"error": HTTPError("https://example.org", 503, "unavailable", {}, None)},
        "http_status": {"status": 429},
        "timeout": {"error": TimeoutError("timed out")},
        "url_error": {"error": URLError("connection refused")},
        "json": {"raw": b"not JSON"},
        "schema": {"raw": b"[]"},
    }[failure]
    client_type = vetting.ScorecardClient if source == "scorecard" else vetting.EcosystemsClient
    kwargs = clients()
    kwargs[source + "_client"] = client_type(transport=transport_for(**options), timeout=7)
    result = vetting.vet_candidate(CANDIDATE, **kwargs)
    assert result["sources"][source]["status"] == "error"
    assert result["sources"][source]["message"]
    assert result["sources"][source]["retrieved_at"]
    assert result["approval_effect"] == "none" and result["requires_human_review"] is True


@pytest.mark.parametrize("pin", [PIN, None])
def test_different_commit_scores_are_retained_but_never_applied(pin):
    card = card_data(commit="b" * 40, score=1)
    for check in card["checks"]:
        check["score"] = 0
    result = vetting.vet_candidate({**CANDIDATE, "commit_sha": pin}, **clients(card=card))
    assert result["sources"]["scorecard"]["status"] == "different_commit"
    assert result["sources"]["scorecard"]["score"] == 1
    assert result["sources"]["scorecard"]["matches_pinned_commit"] is False
    assert result["licence_agreement"]["scorecard_license_present"] is None
    assert not {"dangerous_workflow", "scorecard_below_4", "licence_mismatch"} & set(result["review_flags"])


def test_licence_mismatch_and_risk_flags():
    card = card_data(score=3)
    card["checks"][2]["score"] = 0
    result = vetting.vet_candidate(CANDIDATE, **clients(
        card=card, eco=eco_data(license="GPL-3.0-only", archived=True, fork=True,
                               pushed_at="2025-11-17T00:00:00Z")))
    assert set(result["review_flags"]) == {
        "licence_mismatch", "archived", "fork", "unmaintained_over_365_days",
        "scorecard_below_4", "dangerous_workflow",
    }
    assert result["licence_agreement"]["status"] == "mismatch"
    assert all(source["retrieved_at"] for source in result["sources"].values())


def test_scancode_expression_is_part_of_licence_agreement():
    kwargs = clients()
    kwargs["scancode_fn"] = lambda *args: {"spdx_expressions": ["Apache-2.0"], "status": "ok"}
    result = vetting.vet_candidate(CANDIDATE, **kwargs)
    assert "licence_mismatch" in result["review_flags"]
    assert result["licence_agreement"]["spdx_expressions"]["scancode"] == ["Apache-2.0"]


def test_scorecard_license_check_is_presence_not_an_spdx_claim():
    result = vetting.vet_candidate(CANDIDATE, **clients())
    assert result["review_flags"] == []
    assert result["licence_agreement"]["scorecard_license_present"] is True
    card = card_data()
    card["checks"][1]["score"] = 0
    result = vetting.vet_candidate(CANDIDATE, **clients(card=card))
    assert "licence_mismatch" in result["review_flags"]


def test_scancode_unavailable_and_no_licence(monkeypatch):
    monkeypatch.setattr(vetting.shutil, "which", lambda name: None)
    assert vetting.scan_local_license(None, PIN)["status"] == "unavailable"
    result = vetting.vet_candidate({**CANDIDATE, "license_spdx_id": "UNKNOWN"}, offline=True)
    assert "no_licence" in result["review_flags"]
    assert all(result["sources"][key]["status"] == "unavailable"
               for key in ("scorecard", "ecosystems", "scancode"))


@pytest.mark.parametrize("failure", [None, "timeout", "json", "dirty", "wrong_pin"])
def test_scancode_only_scans_verified_local_checkout_without_network(tmp_path, monkeypatch, failure):
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    monkeypatch.setattr(vetting.shutil, "which", lambda name: "/usr/bin/" + name)
    commands = []

    def run(argv, **kwargs):
        commands.append(argv)
        assert kwargs["timeout"] > 0 and kwargs["cwd"] == "/"
        assert kwargs["env"].get("PYTHONPATH") is None
        if argv[0] == "git":
            value = ("b" * 40 if failure == "wrong_pin" else PIN) if "rev-parse" in argv else (
                " M changed.py" if failure == "dirty" else "")
            return SimpleNamespace(stdout=value)
        assert argv[0] == "/usr/bin/bwrap" and "--unshare-net" in argv
        assert "/usr/bin/scancode" in argv and "--license" in argv
        assert "--ro-bind" in argv and argv[-1] == "/checkout"
        if failure == "timeout":
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        output_dir = Path(argv[argv.index("--bind") + 1])
        output_dir.joinpath("scan.json").write_text("invalid" if failure == "json" else json.dumps({
            "files": [
                {"path": "LICENSE", "type": "file", "detected_license_expression_spdx": "MIT"},
                {"path": "board.py", "type": "file", "license_detections": [
                    {"license_expression_spdx": "Apache-2.0"}]},
                {"path": "notes.txt", "type": "file"},
                {"path": "src", "type": "directory"},
            ],
        }))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(vetting.subprocess, "run", run)
    result = vetting.scan_local_license(checkout, PIN)
    if failure:
        assert result["status"] == "error" and result["message"]
        if failure in {"dirty", "wrong_pin"}:
            assert all(argv[0] == "git" for argv in commands)
    else:
        assert result["status"] == "ok"
        assert result["spdx_expressions"] == ["Apache-2.0", "MIT"]
        assert result["files_lacking_license_info"] == ["notes.txt"]


def test_scancode_never_falls_back_to_host_execution(tmp_path, monkeypatch):
    monkeypatch.setattr(vetting.shutil, "which", lambda name: "/usr/bin/scancode" if name == "scancode" else None)
    assert vetting.scan_local_license(tmp_path, PIN)["status"] == "unavailable"


@pytest.mark.parametrize("candidate", [CANDIDATE, {
    "repository": "tipoLi5890/akcli",
    "commit_sha": pipeline.ADAPTERS["tipoLi5890/akcli"]["approved_commit_sha"],
    "license_spdx_id": "MIT", "approval_effect": "approve",
}])
def test_vetting_does_not_approve_fetch_or_execute(candidate, monkeypatch):
    before = copy.deepcopy(pipeline.ADAPTERS)
    original = copy.deepcopy(candidate)

    def forbidden(*args, **kwargs):
        pytest.fail("vetting must not acquire or execute a candidate")

    monkeypatch.setattr(pipeline, "acquire_pinned_repo", forbidden)
    monkeypatch.setattr(pipeline, "evaluate_signals", forbidden)
    monkeypatch.setattr(pipeline.subprocess, "run", forbidden)
    result = vetting.vet_candidate(candidate, offline=True)
    assert pipeline.ADAPTERS == before and candidate == original
    assert result["approval_effect"] == "none" and result["requires_human_review"] is True


def test_discovery_report_displays_vetting_without_execution(tmp_path):
    evidence = vetting.vet_candidate(CANDIDATE, **clients())
    feed = {"schema_version": "hardware_splicer.github_signal_feed.v1",
            "source": "github_signals_export", "candidates": [{**CANDIDATE, "vetting": evidence}]}

    def forbidden(*args, **kwargs):
        pytest.fail("discovered candidate must never execute")

    result = pipeline.evaluate_signals(feed, checkout=tmp_path / "absent",
                                       schematic=tmp_path / "absent.kicad_sch",
                                       output_dir=tmp_path / "out", run_fn=forbidden)
    assert result["candidates"][0]["vetting"] == evidence
    assert result["candidates"][0]["executed"] is False
    assert result["candidates"][0]["adapter_id"] is None
    assert pipeline.registry_row(tmp_path / "out") is None


def test_task_router_preserves_vetting_in_both_reports(tmp_path, monkeypatch):
    from hardware_splicer import github_signal_task_router as router

    evidence = vetting.vet_candidate(CANDIDATE, **clients())
    approved = {"repository": "tipoLi5890/akcli", "license_spdx_id": "MIT",
                "commit_sha": pipeline.ADAPTERS["tipoLi5890/akcli"]["approved_commit_sha"],
                "vetting": evidence}
    feed = {"schema_version": "hardware_splicer.github_signal_feed.v1",
            "source": "github_signals_export", "candidates": [approved]}
    schematic = tmp_path / "fixture.kicad_sch"
    schematic.write_text("(kicad_sch)")

    def fake_evaluation(filtered, **kwargs):
        assert filtered["candidates"][0]["vetting"] == evidence
        return {"ok": True, "capability": {
            "id": "signal-akcli-schematic-review", "diagnostics_file": "findings.json",
            "diagnostics_sha256": "0" * 64, "finding_count": 0,
            "license": "MIT", "pinned_revision": approved["commit_sha"],
        }}

    monkeypatch.setattr(router, "evaluate_signals", fake_evaluation)
    result = router.run_task(objective="Review schematic", feed=feed,
                             checkout_base=tmp_path / "absent", schematic=schematic,
                             output_dir=tmp_path / "out")
    assert result["considered"][0]["vetting"] == evidence


@pytest.mark.parametrize("source", ["feed", "pcm"])
def test_cli_enriches_offline_without_touching_feed_or_registry(tmp_path, monkeypatch, source):
    monkeypatch.setattr(vetting.shutil, "which", lambda name: None)
    output = tmp_path / "enriched.json"
    if source == "feed":
        input_file = tmp_path / "feed.json"
        input_file.write_text(json.dumps({
            "schema_version": "hardware_splicer.github_signal_feed.v1",
            "source": "github_repository_search", "custom": "preserved",
            "candidates": [CANDIDATE],
        }))
        arguments = ["--feed", str(input_file)]
    else:
        input_file = PCM_FIXTURE
        arguments = ["--kicad-pcm", str(input_file)]
    original = input_file.read_bytes()
    registry_before = copy.deepcopy(pipeline.ADAPTERS)
    monkeypatch.setattr("sys.argv", ["vet", *arguments, "--out", str(output), "--offline"])
    assert cli.main() == 0
    enriched = json.loads(output.read_text())
    assert input_file.read_bytes() == original
    assert pipeline.ADAPTERS == registry_before
    for candidate in enriched["candidates"]:
        assert candidate["vetting"]["approval_effect"] == "none"
        assert candidate["vetting"]["sources"]["scorecard"]["status"] == "unavailable"
        assert candidate["vetting"]["sources"]["ecosystems"]["status"] == "unavailable"
    if source == "feed":
        assert enriched["custom"] == "preserved"
        assert {k: v for k, v in enriched["candidates"][0].items() if k != "vetting"} == CANDIDATE


def test_github_site_sections_are_not_repositories():
    from hardware_splicer.github_signal_vetting import _repository
    assert _repository("https://github.com/sponsors/bennymeg") is None
    assert _repository("https://github.com/orgs/kicad") is None
    assert _repository("https://github.com/yaqwsx/KiKit") == "yaqwsx/KiKit"


def test_scorecard_404_is_not_scored_not_an_error():
    import io
    from urllib.error import HTTPError
    from hardware_splicer.github_signal_vetting import ScorecardClient

    def transport(request, timeout):
        raise HTTPError(request.full_url, 404, "Not Found", {}, io.BytesIO(b""))

    result = ScorecardClient(transport=transport).get("yaqwsx/KiKit", "a" * 40)
    assert result["status"] == "not_scored"
