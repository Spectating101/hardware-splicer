"""Owner-approved Interactive HTML BOM adapter: admission, routing, output gate.

Approval (2026-11-20) covers one exact commit and grants presentation only:
the viewer never carries build, fabrication or electrical authority.
"""
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from hardware_splicer import github_signal_proposals as proposals
from hardware_splicer import github_signal_task_router as router
from hardware_splicer.github_signal_pipeline import (
    ADAPTERS, SignalEvaluationError, acquire_pinned_repo, normalize_feed,
)
from hardware_splicer.runtime import ROOT, scratch_path
from test_github_signal_proposals import _page

IBOM, KIKIT = proposals.IBOM, proposals.KIKIT
PINNED = "5c192e794cd66fde04bab11810601b711bf8581b"
REAL_BOARD = ROOT / "hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb"


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=Test", "-c", "user.email=t@example.invalid",
         "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _feed(sha, license_id="MIT"):
    return {"schema_version": "hardware_splicer.github_signal_feed.v1",
            "source": "github_repository_search",
            "candidates": [{"repository": IBOM, "commit_sha": sha,
                            "license_spdx_id": license_id}]}


@pytest.fixture
def source(tmp_path, monkeypatch):
    """A reviewed-shape iBOM checkout whose fixture commit stands in for the pin."""
    repo = tmp_path / "checkouts" / IBOM.replace("/", "__")
    (repo / "InteractiveHtmlBom").mkdir(parents=True)
    (repo / "InteractiveHtmlBom/generate_interactive_bom.py").write_text("# fixture\n")
    (repo / "LICENSE").write_text("MIT License\n\nFixture\n")
    (repo / ".gitignore").write_text("__pycache__/\n")
    _git(repo, "init", "-q")
    sha = _commit(repo, "approved source")
    monkeypatch.setitem(ADAPTERS[IBOM], "approved_commit_sha", sha)
    return repo, sha


@pytest.fixture
def board(tmp_path):
    path = tmp_path / "board" / "board.kicad_pcb"
    path.parent.mkdir()
    path.write_text('(kicad_pcb (footprint "R" (property "Reference" "R1")) '
                    '(footprint "C" (property "Reference" "C1")))')
    return path


def test_approval_record_pins_exact_commit_and_grants_no_authority():
    spec = ADAPTERS[IBOM]
    assert spec["approved_commit_sha"] == PINNED
    assert spec["approval"]["approved_commit_sha"] == PINNED
    assert spec["approval"]["approved_on"] == "2026-11-20"
    assert spec["capability_id"] == "signal-ibom-assembly-viewer"
    assert spec["input_suffix"] == ".kicad_pcb"
    assert spec["module_file"] == "InteractiveHtmlBom/generate_interactive_bom.py"
    assert spec["authority"] == "presentation_only"
    assert "no authority" in spec["approval"]["grants"]
    assert IBOM not in proposals.PROPOSED_ADAPTERS
    assert proposals.IBOM_TRIAL_EVIDENCE["reference_count"] == 40
    assert proposals.IBOM_TRIAL_EVIDENCE["approval_effect"] == "none"


def test_feed_admits_only_the_approved_commit():
    admitted = normalize_feed(_feed(PINNED))[0]
    assert admitted["discovered_only"] is False
    assert admitted["adapter_id"] == "signal-ibom-assembly-viewer"
    other = normalize_feed(_feed("a" * 40))[0]
    assert other["discovered_only"] is True and other["adapter_id"] is None


def test_acquisition_admits_clean_pinned_checkout(source):
    repo, sha = source
    candidate = normalize_feed(_feed(sha))[0]
    assert acquire_pinned_repo(candidate, repo, fetch=False) == repo


def test_acquisition_refuses_another_commit(source):
    repo, sha = source
    candidate = {**normalize_feed(_feed(sha))[0], "commit_sha": "b" * 40}
    with pytest.raises(SignalEvaluationError, match="not approved"):
        acquire_pinned_repo(candidate, repo, fetch=False)


def test_acquisition_refuses_dirty_checkout(source):
    repo, sha = source
    (repo / "InteractiveHtmlBom/injected.py").write_text("import os\n")
    with pytest.raises(SignalEvaluationError, match="dirty"):
        acquire_pinned_repo(normalize_feed(_feed(sha))[0], repo, fetch=False)


def test_acquisition_refuses_non_mit_licence(source, monkeypatch):
    repo, _ = source
    (repo / "LICENSE").write_text("GNU GENERAL PUBLIC LICENSE\n")
    sha = _commit(repo, "relicensed")
    monkeypatch.setitem(ADAPTERS[IBOM], "approved_commit_sha", sha)
    with pytest.raises(SignalEvaluationError, match="MIT license not independently verified"):
        acquire_pinned_repo(normalize_feed(_feed(sha))[0], repo, fetch=False)


def test_acquisition_refuses_feed_licence_mismatch(source):
    repo, sha = source
    with pytest.raises(SignalEvaluationError, match="license metadata"):
        acquire_pinned_repo(normalize_feed(_feed(sha, "GPL-3.0"))[0], repo, fetch=False)


@pytest.fixture
def fake_host(monkeypatch):
    monkeypatch.setattr(router.shutil, "which", lambda _: "/usr/bin/bwrap")
    monkeypatch.setattr(router, "_host_capabilities", lambda bwrap: {
        "bwrap": bwrap, "/usr/bin/python3": True, "pcbnew": True, "wx": True, "KiCad 9": True,
    })


def _fake_ibom(refs, calls):
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        out = Path(argv[argv.index("/output") - 1])
        (out / "ibom.html").write_text(_page({
            "footprints": [{"ref": r} for r in refs], "bom": {"both": []},
        }))
        return SimpleNamespace(returncode=0, stderr="", stdout="")
    return run


@pytest.mark.parametrize("objective", [
    "interactive assembly BOM / placement viewer for a KiCad board",
    "Interactive HTML BOM", "placement viewer",
])
def test_router_runs_approved_ibom_with_trial_argv(source, board, fake_host, tmp_path, objective):
    repo, sha = source
    calls = []
    out = tmp_path / "out"
    result = router.run_task(objective=objective, feed=_feed(sha), output_dir=out,
                             checkout_base=repo.parent, board=board,
                             run_fn=_fake_ibom(["R1", "C1"], calls))
    assert result["ok"] is True and result["selection"]["selected_repository"] == IBOM
    evidence = result["evidence"]
    assert evidence["id"] == "signal-ibom-assembly-viewer"
    assert evidence["board_reference_count"] == 2
    assert evidence["authority"] == "presentation_only" and evidence["build_ready"] is False
    assert result["physical_authority"] is False
    argv, kwargs = calls[0]
    expected = [x.format(checkout=repo.resolve(), board=board.resolve(),
                         out=(out / router.IBOM_OUTPUT_DIRNAME).resolve())
                for x in proposals.IBOM_ARGV]
    expected[0] = "/usr/bin/bwrap"
    assert argv == expected and "--unshare-all" in argv and argv.count("--bind") == 1
    assert kwargs["env"] == {"PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    cap = json.loads((out / router.IBOM_CAPABILITY_FILENAME).read_text())
    assert cap["accepted"] is True and cap["fab_approved"] is False
    assert cap["electrical_correctness_verified"] is False and cap["build_ready"] is False
    assert cap["artifact_sha256"] == proposals.sha256_file(out / cap["artifact"])
    assert "no build, fabrication or electrical authority" in cap["authority_statement"]


def test_missing_reference_is_rejected_not_passed(source, board, fake_host, tmp_path):
    repo, sha = source
    out = tmp_path / "out"
    result = router.run_task(objective="Interactive HTML BOM", feed=_feed(sha),
                             output_dir=out, checkout_base=repo.parent, board=board,
                             run_fn=_fake_ibom(["R1"], []))
    assert result["ok"] is False and result["status"] == "rejected_incomplete"
    assert result["evidence"] is None and result["output_check"]["missing_refs"] == ["C1"]
    cap = json.loads((out / router.IBOM_CAPABILITY_FILENAME).read_text())
    assert cap["accepted"] is False and cap["status"] == "rejected_incomplete"
    on_disk = json.loads((out / router.VERDICT_FILENAME).read_text())
    assert on_disk["ok"] is False and on_disk["build_ready"] is False


@pytest.mark.parametrize("failure,match", [
    ("ignored", "dirty"),
    ("docker", "only in bwrap"),
    ("capabilities", "host capabilities unavailable"),
    ("output_exists", "new directory outside the checkout"),
])
def test_refusals_precede_execution(source, board, fake_host, tmp_path, monkeypatch,
                                    failure, match):
    repo, sha = source
    out = tmp_path / "out"
    backend = "bwrap"
    if failure == "ignored":
        (repo / "InteractiveHtmlBom/__pycache__").mkdir()
        (repo / "InteractiveHtmlBom/__pycache__/stale.pyc").write_bytes(b"x")
    elif failure == "docker":
        backend = "docker"
    elif failure == "capabilities":
        monkeypatch.setattr(router, "_host_capabilities", lambda bwrap: {"pcbnew": False})
    else:
        (out / router.IBOM_OUTPUT_DIRNAME).mkdir(parents=True)
    calls = []
    with pytest.raises(SignalEvaluationError, match=match):
        router.run_task(objective="Interactive HTML BOM", feed=_feed(sha), output_dir=out,
                        checkout_base=repo.parent, board=board,
                        run_fn=_fake_ibom(["R1", "C1"], calls), sandbox_backend=backend)
    assert calls == []


def test_router_keeps_kikit_blocked(tmp_path):
    feed = {"schema_version": "hardware_splicer.github_signal_feed.v1",
            "source": "github_repository_search",
            "candidates": [{"repository": KIKIT,
                            "commit_sha": proposals.PROPOSED_ADAPTERS[KIKIT]["proposed_commit"],
                            "license_spdx_id": "MIT"}]}
    result = router.run_task(objective="panelisation", feed=feed,
                             output_dir=tmp_path / "out", checkout_base=tmp_path / "absent")
    assert result["status"] == "tool_blocked" and result["executed"] is False
    assert KIKIT not in ADAPTERS


def test_real_sandboxed_ibom_run_on_spi_flash_adapter(tmp_path):
    """Real pinned upstream in bwrap; skipped when the host cannot run it.

    The pinned checkout is fetched once, by the pipeline's own acquisition (the
    only network use, for this one approved public repository), into the
    scratch cache. Nothing is installed.
    """
    bwrap = shutil.which("bwrap")
    if not bwrap:
        pytest.skip("bubblewrap unavailable")
    capabilities = proposals._host_capabilities(bwrap)
    if not all(capabilities.get(name) for name in proposals.IBOM_HOST_CAPABILITIES):
        pytest.skip("host /usr/bin/python3 lacks KiCad 9 pcbnew or wx")
    probe = subprocess.run([bwrap, "--unshare-all", "--ro-bind", "/usr", "/usr",
                            "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
                            "--symlink", "usr/bin", "/bin", "/usr/bin/true"],
                           capture_output=True, timeout=15, check=False)
    if probe.returncode != 0:
        pytest.skip("bubblewrap cannot create namespaces on this host")
    candidate = normalize_feed(_feed(PINNED))[0]
    checkout = scratch_path("signal-checkouts") / IBOM.replace("/", "__")
    if not checkout.exists():
        try:
            acquire_pinned_repo(candidate, checkout, fetch=True)
        except (subprocess.SubprocessError, OSError) as exc:
            shutil.rmtree(checkout, ignore_errors=True)
            pytest.skip("pinned iBOM checkout unavailable: " + type(exc).__name__)
    out = tmp_path / "out"
    result = router.run_task(objective="Interactive HTML BOM", feed=_feed(PINNED),
                             output_dir=out, checkout_base=checkout.parent, board=REAL_BOARD)
    assert result["ok"] is True, result
    assert result["evidence"]["board_reference_count"] == 40
    assert result["evidence"]["build_ready"] is False
    cap = json.loads((out / router.IBOM_CAPABILITY_FILENAME).read_text())
    assert cap["output_check"]["ok"] is True and cap["output_check"]["missing_refs"] == []
    assert cap["output_check"]["output_reference_count"] == 40
    assert cap["pinned_revision"] == PINNED and cap["authority"] == "presentation_only"
    assert (out / cap["artifact"]).stat().st_size > 50_000
