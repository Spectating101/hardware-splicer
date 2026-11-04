"""Safety and evidence tests for GitHub discovery -> HS capability acquisition."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from hardware_splicer.github_signal_pipeline import (
    SCHEMA,
    ADAPTERS,
    SignalEvaluationError,
    _bwrap_args,
    evaluate_signals,
    normalize_feed,
    registry_row,
)
from hardware_splicer.capability_policy import product_capability_report


def _feed(repo="tipoLi5890/akcli", sha="a" * 40, license="MIT"):
    return {
        "schema_version": "hardware_splicer.github_signal_feed.v1",
        "source": "github_repository_search",
        "candidates": [{
            "repository": repo, "commit_sha": sha,
            "license_spdx_id": license,
        }],
    }


def _checkout(tmp_path, monkeypatch):
    repo = tmp_path / "akcli"
    (repo / "src" / "akcli").mkdir(parents=True)
    (repo / "src" / "akcli" / "__main__.py").write_text("# fixture\n")
    (repo / "LICENSE").write_text("MIT License\n\nTest\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test",
                    "-c", "user.email=test@example.com", "commit", "-qm", "fixture"], check=True)
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    monkeypatch.setitem(ADAPTERS["tipoLi5890/akcli"], "approved_commit_sha", sha)
    return repo, sha


def test_normalized_external_signal_never_counts_unknown_as_executable():
    item = normalize_feed(_feed(repo="0x12net/kdif"))[0]
    assert item["discovered_only"] is True
    assert item["adapter_id"] is None


@pytest.mark.parametrize("sha", ["main", "a" * 39, "A" * 40, "../HEAD", "g" * 40])
def test_nonimmutable_revision_is_rejected(sha):
    with pytest.raises(SignalEvaluationError):
        normalize_feed(_feed(sha=sha))


@pytest.mark.parametrize("repo", ["../akcli", "https://github.com/x", "owner/repo/extra"])
def test_malformed_repository_cannot_be_acquired(repo):
    with pytest.raises(SignalEvaluationError):
        normalize_feed(_feed(repo=repo))


def test_missing_or_fake_provenance_fails_closed():
    feed = _feed()
    feed["source"] = "unknown remote API"
    with pytest.raises(SignalEvaluationError):
        normalize_feed(feed)


def test_duplicate_repo_names_rejected():
    feed = _feed()
    feed["candidates"].append({**feed["candidates"][0]})
    with pytest.raises(SignalEvaluationError):
        normalize_feed(feed)


def test_known_repository_at_unapproved_upstream_revision_is_not_executable(tmp_path):
    feed = _feed(sha="b" * 40)
    evaluated = evaluate_signals(
        feed, checkout=tmp_path / "no_checkout",
        schematic=tmp_path / "not_a_real_design.kicad_sch",
        output_dir=tmp_path / "output",
    )
    assert evaluated["ok"] is False
    assert evaluated["candidates"][0]["state"] == "discovered_only"
    assert evaluated["candidates"][0]["adapter_id"] is None


def test_unknown_candidate_discovered_not_run(tmp_path, monkeypatch):
    r = evaluate_signals(
        _feed(repo="0x12net/kdif"),
        checkout=tmp_path / "absent",
        schematic=tmp_path / "absent.kicad_sch",
        output_dir=tmp_path / "out",
    )
    assert r["ok"] is False
    assert r["candidates"][0]["state"] == "discovered_only"
    assert r["capability"] is None
    assert registry_row(tmp_path / "out") is None


def test_existing_checkout_wrong_pin_rejected_before_tool_call(tmp_path, monkeypatch):
    repo, sha = _checkout(tmp_path, monkeypatch)
    schematic = tmp_path / "fixture.kicad_sch"
    schematic.write_text("(kicad_sch)")
    result = evaluate_signals(
        _feed(sha="a" * 40), checkout=repo,
        schematic=schematic, output_dir=tmp_path / "out",
    )
    assert result["ok"] is False
    assert result["candidates"][0]["state"] == "discovered_only"
    assert registry_row(tmp_path / "out") is None


def test_pin_is_not_enough_if_checkout_source_has_been_modified(tmp_path, monkeypatch):
    repo, sha = _checkout(tmp_path, monkeypatch)
    (repo / "src" / "akcli" / "__main__.py").write_text("print('malicious')\n")
    schematic = tmp_path / "fixture.kicad_sch"
    schematic.write_text("(kicad_sch)")
    with pytest.raises(SignalEvaluationError, match="checkout dirty"):
        evaluate_signals(_feed(sha=sha), checkout=repo,
                         schematic=schematic, output_dir=tmp_path / "out")


def test_untracked_injection_rejected(tmp_path, monkeypatch):
    repo, sha = _checkout(tmp_path, monkeypatch)
    (repo / "src" / "akcli" / "injected.py").write_text("# injection")
    schematic = tmp_path / "fixture.kicad_sch"
    schematic.write_text("(kicad_sch)")
    with pytest.raises(SignalEvaluationError, match="checkout dirty"):
        evaluate_signals(_feed(sha=sha), checkout=repo,
                         schematic=schematic, output_dir=tmp_path / "out")


def test_license_claim_not_sufficient_without_local_approved_license(tmp_path, monkeypatch):
    repo, sha = _checkout(tmp_path, monkeypatch)
    (repo / "LICENSE").write_text("Proprietary all rights reserved\n")
    subprocess.run(["git", "-C", str(repo), "add", "LICENSE"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test",
                    "-c", "user.email=test@example.com", "commit", "-qm",
                    "replace license with proprietary text"], check=True)
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    monkeypatch.setitem(ADAPTERS["tipoLi5890/akcli"], "approved_commit_sha", sha)
    schematic = tmp_path / "fixture.kicad_sch"
    schematic.write_text("(kicad_sch)")
    with pytest.raises(SignalEvaluationError, match="license not independently"):
        evaluate_signals(_feed(sha=sha), checkout=repo,
                         schematic=schematic, output_dir=tmp_path / "out")


def test_metadata_license_spoof_rejected(tmp_path, monkeypatch):
    repo, sha = _checkout(tmp_path, monkeypatch)
    schematic = tmp_path / "fixture.kicad_sch"
    schematic.write_text("(kicad_sch)")
    with pytest.raises(SignalEvaluationError, match="metadata inconsistent"):
        evaluate_signals(_feed(sha=sha, license="GPL-3.0"), checkout=repo,
                         schematic=schematic, output_dir=tmp_path / "out")


def test_bwrap_fixed_tool_arguments_are_networkless_and_readonly(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "hardware_splicer.github_signal_pipeline.shutil.which",
        lambda x: "/usr/bin/bwrap" if x == "bwrap" else None,
    )
    argv = _bwrap_args(tmp_path, tmp_path / "test.kicad_sch")
    assert "--unshare-net" in argv
    assert "--clearenv" in argv
    assert "--ro-bind" in argv
    assert "--bind" not in argv
    assert "--tmpfs" in argv
    assert "check" in argv
    assert "--fail-on" in argv
    assert "never" in argv
    assert all(x not in argv for x in ("-c", "--apply", "curl", "sh", "bash"))
    assert not any("/home/" in str(x) and "/.ssh/" in str(x) for x in argv)


def test_bwrap_missing_rejects_unsafe_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "hardware_splicer.github_signal_pipeline.shutil.which",
        lambda _: None,
    )
    with pytest.raises(SignalEvaluationError, match="refusing unsandboxed"):
        _bwrap_args(tmp_path, tmp_path / "fixture.kicad_sch")


def test_native_execution_is_real_evidence_and_registry_requires_hash(tmp_path, monkeypatch):
    repo, sha = _checkout(tmp_path, monkeypatch)
    schematic = tmp_path / "fixture.kicad_sch"
    schematic.write_text("(kicad_sch (version 20231120))")
    monkeypatch.setattr(
        "hardware_splicer.github_signal_pipeline.shutil.which",
        lambda _: "/usr/bin/bwrap",
    )
    commands = []

    def fake_run(argv, **kwargs):
        commands.append((argv, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "schema_version": "2.0", "metadata": {"component_count": 5},
                "findings": [
                    {"severity": "note", "code": "BOM_DNP", "message": "Check DNP"},
                    {"severity": "warning", "code": "LAYOUT", "message": "Review label"},
                ],
            }),
            stderr="",
        )

    r = evaluate_signals(
        _feed(sha=sha),
        checkout=repo, schematic=schematic,
        output_dir=tmp_path / "out", run_fn=fake_run,
    )
    assert r["ok"] and r["physical_authority"] is False
    assert r["capability"]["findings"] == {"note": 1, "warning": 1}
    assert r["capability"]["fabrication_authorized"] is False
    assert len(commands) == 1
    assert commands[0][1]["timeout"] == 75
    assert "--unshare-net" in commands[0][0]
    row = registry_row(tmp_path / "out")
    assert row is not None
    assert row["readiness"] == "project_used"
    report = product_capability_report(
        build_dir=tmp_path / "out", which=lambda _: None,
        kicad_happy_discover=lambda: {"available": False, "capabilities": []},
    )
    inserted = [x for x in report["capabilities"] if x["id"] == row["id"]]
    assert len(inserted) == 1
    assert inserted[0]["evidence"]["machine_tested"] is True
    artifact = tmp_path / "out" / "akcli_schematic_findings.json"
    artifact.write_text('{"findings":[]}')
    assert registry_row(tmp_path / "out") is None


def test_failed_native_tool_does_not_register_success(tmp_path, monkeypatch):
    repo, sha = _checkout(tmp_path, monkeypatch)
    schematic = tmp_path / "fixture.kicad_sch"
    schematic.write_text("(kicad_sch)")
    monkeypatch.setattr(
        "hardware_splicer.github_signal_pipeline.shutil.which",
        lambda _: "/usr/bin/bwrap",
    )

    def failed(*_a, **_kw):
        return SimpleNamespace(returncode=2, stdout="{}", stderr="failed")

    with pytest.raises(SignalEvaluationError, match="native tool failed"):
        evaluate_signals(
            _feed(sha=sha), checkout=repo, schematic=schematic,
            output_dir=tmp_path / "out", run_fn=failed,
        )
    assert registry_row(tmp_path / "out") is None


def test_malicious_output_not_imported_into_registry(tmp_path, monkeypatch):
    repo, sha = _checkout(tmp_path, monkeypatch)
    schematic = tmp_path / "fixture.kicad_sch"
    schematic.write_text("(kicad_sch)")
    monkeypatch.setattr(
        "hardware_splicer.github_signal_pipeline.shutil.which",
        lambda _: "/usr/bin/bwrap",
    )

    def malicious(*_a, **_kw):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"findings": [{"severity": "executed_motors", "code": "ok"}]}),
            stderr="",
        )

    with pytest.raises(SignalEvaluationError, match="findings schema"):
        evaluate_signals(
            _feed(sha=sha), checkout=repo, schematic=schematic,
            output_dir=tmp_path / "out", run_fn=malicious,
        )
    assert registry_row(tmp_path / "out") is None
