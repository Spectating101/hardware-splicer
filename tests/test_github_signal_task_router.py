"""Task routing and source-native kdif sandbox gates; no fictional hardware claims."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from hardware_splicer.capability_policy import product_capability_report
from hardware_splicer.github_signal_pipeline import ADAPTERS, SignalEvaluationError, normalize_feed
from hardware_splicer.github_signal_task_router import (
    KDIF_CAPABILITY_FILENAME,
    KDIF_HTML_FILENAME,
    KDIF_DOCKER_IMAGE,
    TASK_SCHEMA,
    _kdif_bwrap_args,
    _kdif_docker_args,
    _verify_board_history,
    kdif_registry_row,
    run_task,
    select_task,
)


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _fixtures(tmp_path, monkeypatch):
    source=tmp_path/"reviewed_kdif"
    (source/"kdif").mkdir(parents=True)
    (source/"LICENSE").write_text("MIT License\n\nFixture\n")
    (source/"kdif/__main__.py").write_text("# reviewer fixture\n")
    _git(source,"init","-q")
    _git(source,"add",".")
    _git(source,"-c","user.name=Test","-c","user.email=t@example.invalid",
         "commit","-qm","approved source")
    tool_sha=_git(source,"rev-parse","HEAD")
    monkeypatch.setitem(ADAPTERS["0x12net/kdif"],"approved_commit_sha",tool_sha)
    board_repo=tmp_path/"board_history"
    board_repo.mkdir()
    board=board_repo/"board.kicad_pcb"
    board.write_text("(kicad_pcb) \n")
    _git(board_repo,"init","-q")
    _git(board_repo,"add",".")
    _git(board_repo,"-c","user.name=Test","-c","user.email=t@example.invalid",
         "commit","-qm","baseline")
    a=_git(board_repo,"rev-parse","HEAD")
    board.write_text("(kicad_pcb (gr_text \"controlled fixture\"))\n")
    _git(board_repo,"add",".")
    _git(board_repo,"-c","user.name=Test","-c","user.email=t@example.invalid",
         "commit","-qm","fixture change")
    b=_git(board_repo,"rev-parse","HEAD")
    feed={
        "schema_version":"hardware_splicer.github_signal_feed.v1",
        "source":"github_repository_search",
        "candidates":[
            {"repository":"tipoLi5890/akcli",
             "commit_sha":ADAPTERS["tipoLi5890/akcli"]["approved_commit_sha"],
             "license_spdx_id":"MIT"},
            {"repository":"0x12net/kdif",
             "commit_sha":tool_sha,"license_spdx_id":"MIT"},
        ],
    }
    checkouts=tmp_path/"checkouts"
    checkouts.mkdir()
    (checkouts/"0x12net__kdif").symlink_to(source, target_is_directory=True)
    return board_repo, board, a, b, feed, checkouts


@pytest.mark.parametrize("objective,expected",[
    ("Inspect this schematic for overlapping labels","review_schematic"),
    ("Audit a schematic for electrical risks","review_schematic"),
    ("Compare the revisions of a PCB","compare_board_revisions"),
    ("Show what changed between two board versions","compare_board_revisions"),
])
def test_explicit_task_matching(objective,expected):
    x=select_task(objective)
    assert x["selected_task"]==expected
    assert x["selection_model"]=="rules_v1_not_an_llm"


@pytest.mark.parametrize("objective",[
    "Build a physical drone autonomously",
    "Review these schematic changes",
    "Diagnose the differences between two revisions",
    "",
])
def test_unsupported_or_ambiguous_objective_fails_closed(objective):
    with pytest.raises(SignalEvaluationError):
        select_task(objective)


def test_reviewed_kdif_source_only_available_at_exact_pin(tmp_path,monkeypatch):
    _,_,_,_,feed,_=_fixtures(tmp_path,monkeypatch)
    listed=normalize_feed(feed)
    assert {x["repository"]:x["discovered_only"] for x in listed} == {
        "tipoLi5890/akcli":False,"0x12net/kdif":False
    }
    feed["candidates"][-1]["commit_sha"]="a"*40
    assert normalize_feed(feed)[-1]["discovered_only"] is True


def test_docker_kdif_launch_is_offline_readonly_pinned_and_bounded(tmp_path,monkeypatch):
    monkeypatch.setattr(
        "hardware_splicer.github_signal_task_router.shutil.which",
        lambda command: "/usr/bin/docker" if command=="docker" else None,
    )
    argv=_kdif_docker_args(tmp_path/"source",tmp_path/"repo","board.kicad_pcb",
                           ("a"*40,"b"*40),tmp_path)
    joined=" ".join(argv)
    assert "--pull=never" in argv and "--network=none" in argv
    assert "--read-only" in argv and "--cap-drop=ALL" in argv
    assert "--security-opt=no-new-privileges" in joined
    assert "--pids-limit=64" in joined and "--memory=1500m" in joined
    assert KDIF_DOCKER_IMAGE in argv and "--user" in argv
    assert "kicad-cli" in joined and "kdif" in joined
    assert joined.count(":/output:rw")==1
    assert "source:/opt/kdif:ro" in joined or ":/opt/kdif:ro" in joined
    assert "repo:/workspace:ro" in joined or ":/workspace:ro" in joined


def test_kdif_bwrap_launch_no_network_or_host_shell(tmp_path,monkeypatch):
    monkeypatch.setattr(
        "hardware_splicer.github_signal_task_router.shutil.which",
        lambda command: "/usr/bin/bwrap" if command=="bwrap" else None,
    )
    args=_kdif_bwrap_args(tmp_path,tmp_path,"board.kicad_pcb",("a"*40,"b"*40),tmp_path)
    assert "--unshare-net" in args
    assert "--ro-bind" in args
    assert "--chdir" in args
    assert "--bind" in args
    assert "sh" not in args and "bash" not in args
    assert "--kicad-cli" in args
    assert "F.SilkS" in args


def test_missing_sandbox_rejects_without_host_fallback(tmp_path,monkeypatch):
    monkeypatch.setattr(
        "hardware_splicer.github_signal_task_router.shutil.which",lambda _:None
    )
    with pytest.raises(SignalEvaluationError,match="refusing|unavailable"):
        _kdif_bwrap_args(tmp_path,tmp_path,"b.kicad_pcb",("a"*40,"b"*40),tmp_path)
    with pytest.raises(SignalEvaluationError,match="refusing|absent"):
        _kdif_docker_args(tmp_path,tmp_path,"b.kicad_pcb",("a"*40,"b"*40),tmp_path)


def test_board_revision_validation_rejects_dirty_repo_and_missing_commit(tmp_path,monkeypatch):
    root,board,a,b,_,_=_fixtures(tmp_path,monkeypatch)
    x=_verify_board_history(root,board,a,b)
    assert x["revisions_have_distinct_bytes"] is True
    assert x["revision_a_file_sha256"] != x["revision_b_file_sha256"]
    with pytest.raises(SignalEvaluationError,match="distinct"):
        _verify_board_history(root,board,a,a)
    with pytest.raises(SignalEvaluationError,match="commit"):
        _verify_board_history(root,board,"f"*40,b)
    (root/"payload.txt").write_text("untracked")
    with pytest.raises(SignalEvaluationError,match="uncommitted"):
        _verify_board_history(root,board,a,b)


def test_kdif_routes_and_verifies_native_evidence_then_registers(tmp_path,monkeypatch):
    board_repo,board,a,b,feed,checkouts=_fixtures(tmp_path,monkeypatch)
    out=tmp_path/"results"

    # Stub only the tool executor for this *unit test*. Live integration tests
    # independently run real kdif + real KiCad against an HS PCB and retain
    # real outputs. The fake HTML here is not presented as native proof.
    def simulated_executor(argv,**kwargs):
        assert "--unshare-net" in argv
        out.mkdir(exist_ok=True)
        (out/KDIF_HTML_FILENAME).write_text(
            "<!DOCTYPE html>\n<html><head><title>KiCad Diff</title></head>"
            + " " * 2200 + "<body>fixture only</body></html>"
        )
        return SimpleNamespace(returncode=0,stdout="",stderr="")

    monkeypatch.setattr(
        "hardware_splicer.github_signal_task_router.shutil.which",
        lambda x:"/usr/bin/bwrap" if x=="bwrap" else None,
    )
    result=run_task(
        objective="Compare two committed PCB revisions",
        feed=feed, output_dir=out, checkout_base=checkouts,
        board_repo=board_repo,board=board,revision_a=a,revision_b=b,
        run_fn=simulated_executor
    )
    assert result["ok"] is True
    assert result["selection"]["selected_repository"]=="0x12net/kdif"
    assert result["tool_selection_authority"]=="rules_v1"
    assert result["physical_authority"] is False
    assert result["verified_physical_device_operation"] is False
    assert result["evidence"]["native_result_kind"]=="interactive_pcb_revision_diff"
    row=kdif_registry_row(out)
    assert row is not None and row["readiness"]=="project_used"
    report=product_capability_report(
        build_dir=out,
        which=lambda _: None,
        kicad_happy_discover=lambda: {"available":False,"capabilities":[]},
    )
    assert any(x["id"]=="signal-kdif-board-revision-diff" for x in report["capabilities"])
    (out/KDIF_HTML_FILENAME).write_text("tampered evidence")
    assert kdif_registry_row(out) is None


def test_fake_external_result_without_html_never_registers(tmp_path,monkeypatch):
    board_repo,board,a,b,feed,checkouts=_fixtures(tmp_path,monkeypatch)
    monkeypatch.setattr(
        "hardware_splicer.github_signal_task_router.shutil.which",
        lambda x:"/usr/bin/bwrap" if x=="bwrap" else None,
    )
    with pytest.raises(SignalEvaluationError,match="HTML missing"):
        run_task(
            objective="Compare revisions",feed=feed,output_dir=tmp_path/"out",
            checkout_base=checkouts,board_repo=board_repo,board=board,
            revision_a=a,revision_b=b,
            run_fn=lambda argv,**kw:SimpleNamespace(returncode=0,stdout="",stderr=""),
        )
    assert kdif_registry_row(tmp_path/"out") is None


def test_native_error_has_no_success_projection(tmp_path,monkeypatch):
    board_repo,board,a,b,feed,checkouts=_fixtures(tmp_path,monkeypatch)
    monkeypatch.setattr(
        "hardware_splicer.github_signal_task_router.shutil.which",
        lambda x:"/usr/bin/bwrap" if x=="bwrap" else None,
    )
    with pytest.raises(SignalEvaluationError,match="isolated native invocation failed"):
        run_task(
            objective="Compare revisions",feed=feed,output_dir=tmp_path/"out",
            checkout_base=checkouts,board_repo=board_repo,board=board,
            revision_a=a,revision_b=b,
            run_fn=lambda argv,**kw:SimpleNamespace(returncode=2,stdout="",stderr="failed"),
        )
    assert kdif_registry_row(tmp_path/"out") is None


def test_unapproved_revision_is_not_run_even_if_known_repo(tmp_path,monkeypatch):
    board_repo,board,a,b,feed,checkouts=_fixtures(tmp_path,monkeypatch)
    feed["candidates"][-1]["commit_sha"]="0"*40
    with pytest.raises(SignalEvaluationError,match="revision unapproved"):
        run_task(
            objective="Compare revisions",feed=feed,output_dir=tmp_path/"out",
            checkout_base=checkouts,board_repo=board_repo,board=board,
            revision_a=a,revision_b=b,
        )


def test_registered_kdif_verdict_cannot_upgrade_unapproved_revision(tmp_path,monkeypatch):
    board_repo,board,a,b,feed,checkouts=_fixtures(tmp_path,monkeypatch)
    out=tmp_path/"out"
    monkeypatch.setattr(
        "hardware_splicer.github_signal_task_router.shutil.which",
        lambda x:"/usr/bin/bwrap" if x=="bwrap" else None,
    )
    def tool(argv,**kw):
        out.mkdir(exist_ok=True)
        (out/KDIF_HTML_FILENAME).write_text(
            "<!DOCTYPE html><html><head><title>KiCad Diff</title></head>"
            + " " * 2600 + "</html>"
        )
        return SimpleNamespace(returncode=0,stdout="",stderr="")
    run_task(objective="Compare revisions",feed=feed,output_dir=out,
             checkout_base=checkouts,board_repo=board_repo,board=board,
             revision_a=a,revision_b=b,run_fn=tool)
    assert kdif_registry_row(out) is not None
    v=out/KDIF_CAPABILITY_FILENAME
    c=json.loads(v.read_text())
    c["pinned_revision"]="f"*40
    v.write_text(json.dumps(c))
    assert kdif_registry_row(out) is None
