"""Fail-closed evidence tests for HS-controlled GitHub Actions engineering jobs."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from hardware_splicer.github_signal_remote_dispatch import (
    REPO,
    WORKFLOW,
    TASKS,
    GithubCLI,
    WorkerStateError,
    _inspect_downloads,
    _matching_run,
    collect,
    read_job,
    status,
    submit,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/github_signals/workshop_task_router_20261105"


def _head():
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True, text=True, capture_output=True,
    ).stdout.strip()


class FakeClient:
    def __init__(self, head=None):
        self.head=head or _head()
        self.calls=[]
        self.dispatched=[]
        self.runs=[]
        self.jobs=[]
        self.fail_download=False
        self.override_source=None

    def get(self,path):
        self.calls.append(path)
        if path == f"repos/{REPO}/git/ref/heads/main":
            return {"object":{"sha":self.head}}
        if path.startswith(f"repos/{REPO}/actions/workflows/{WORKFLOW}/runs?"):
            return {"workflow_runs":self.runs}
        if path.startswith(f"repos/{REPO}/actions/runs/") and "/jobs?" in path:
            return {"jobs":self.jobs}
        if path.startswith(f"repos/{REPO}/actions/runs/") and "/artifacts?" in path:
            task=self.dispatched[-1]["task"]
            return {"artifacts":[{"id":55,"name":TASKS[task]["artifact_name"],"expired":False}]}
        raise AssertionError("unexpected GitHub endpoint: "+path)

    def dispatch(self, *, task, request_id):
        self.dispatched.append({"task":task,"request_id":request_id})

    def download(self,*,run_id,artifact,directory):
        if self.fail_download:
            raise WorkerStateError("download failed")
        assert run_id==750019
        task=self.dispatched[-1]["task"]
        assert artifact==TASKS[task]["artifact_name"]
        src=EVIDENCE/("review" if task=="review_schematic" else "diff")
        dst=directory if task=="review_schematic" else directory/"github_signals_kdif"
        dst.mkdir(parents=True,exist_ok=True)
        for f in src.iterdir():
            if f.is_file():
                shutil.copyfile(f,dst/f.name)
        if self.override_source:
            self.override_source(dst)

    def complete(self, job, *, conclusion="success"):
        names=["intake-unit-gates", "native-reviewed-integration", "native-reviewed-kdif-task"]
        selected=TASKS[job["task"]]["job_name"]
        self.jobs=[{"name":name,"conclusion":(
            conclusion if name==selected else
            "success" if name=="intake-unit-gates" else "skipped"
        )} for name in names]
        self.runs=[{
            "id":750019,
            "display_title":f"HS GitHub Signal / {job['task']} / {job['request_id']}",
            "event":"workflow_dispatch",
            "head_sha":job["ref_sha"],"head_branch":"main",
            "status":"completed","conclusion":conclusion,
            "html_url":"https://github.com/Spectating101/hardware-splicer/actions/runs/750019",
        }]


def test_submit_requires_explicit_execute_and_no_duplicate(tmp_path):
    client=FakeClient()
    rid="hs-1234567890abcdef"
    j=submit("Compare PCB revisions",ledger=tmp_path/"ledger",workspace=ROOT,
             client=client,request_id=rid,execute=False)
    assert j["task"]=="compare_board_revisions"
    assert j["status"]=="prepared"
    assert j["physical_authority"] is False
    assert not client.dispatched
    assert not (tmp_path/"ledger").exists()
    sent=submit("Compare PCB revisions",ledger=tmp_path/"ledger",workspace=ROOT,
                client=client,request_id=rid,execute=True)
    assert sent["status"]=="submitted"
    assert len(client.dispatched)==1
    assert read_job(tmp_path/"ledger",rid)["ref_sha"]==_head()
    with pytest.raises(WorkerStateError,match="duplicate"):
        submit("Compare PCB revisions",ledger=tmp_path/"ledger",workspace=ROOT,
               client=client,request_id=rid,execute=True)
    assert len(client.dispatched)==1


def test_unsupported_task_not_dispatched(tmp_path):
    client=FakeClient()
    with pytest.raises(ValueError,match="ambiguous"):
        submit("Make me a robotic production lab",ledger=tmp_path,
               workspace=ROOT,client=client,execute=True)
    assert not client.dispatched


def test_dispatch_failure_is_persisted_ambiguous_not_automatically_retried(tmp_path):
    client=FakeClient()
    def reject(*,task,request_id):
        raise WorkerStateError("synthetic disconnected host")
    client.dispatch=reject
    with pytest.raises(WorkerStateError,match="disconnected"):
        submit("Inspect schematic",ledger=tmp_path,workspace=ROOT,
               client=client,request_id="hs-1111111111111111",execute=True)
    x=read_job(tmp_path,"hs-1111111111111111")
    assert x["status"]=="dispatch_unknown_check_remote_before_retry"


def test_job_identifier_cannot_escape_ledger(tmp_path):
    client=FakeClient()
    for value in ("../secret","hs-abc", "hs-FFFFFFFFFFFFFFFF"):
        with pytest.raises(WorkerStateError):
            submit("Inspect schematic",ledger=tmp_path,workspace=ROOT,
                   client=client,request_id=value,execute=True)
    assert not client.dispatched


def test_status_ref_and_job_topology_must_match(tmp_path):
    client=FakeClient()
    job=submit("Inspect schematic",ledger=tmp_path,workspace=ROOT,
               client=client,request_id="hs-aabbccddeeff0011",execute=True)
    assert status(ledger=tmp_path,request_id=job["request_id"],client=client)["status"]=="awaiting_run_discovery"
    client.complete(job)
    remote=status(ledger=tmp_path,request_id=job["request_id"],client=client)
    assert remote["status"]=="remote_succeeded"
    assert remote["run_id"]==750019
    assert remote["worker_jobs"]["native-reviewed-kdif-task"]=="skipped"
    client.runs[0]["head_sha"]="f"*40
    with pytest.raises(WorkerStateError,match="ref differs"):
        status(ledger=tmp_path,request_id=job["request_id"],client=client)


def test_status_rejects_duplicate_run_id_and_wrong_job_output(tmp_path):
    client=FakeClient()
    job=submit("Compare revisions",ledger=tmp_path,workspace=ROOT,
               client=client,request_id="hs-1234432112344321",execute=True)
    client.complete(job)
    client.runs.append(dict(client.runs[0],id=750020))
    with pytest.raises(WorkerStateError,match="multiple"):
        status(ledger=tmp_path,request_id=job["request_id"],client=client)
    client.runs.pop()
    client.jobs[1]["conclusion"]="success"
    state=status(ledger=tmp_path,request_id=job["request_id"],client=client)
    assert state["status"]=="remote_failed_or_unexpected_worker_topology"


@pytest.mark.parametrize("objective,tool",[
    ("Inspect schematic for label problems","akcli"),
    ("Compare the two board revisions","kdif"),
])
def test_remote_collect_verifies_real_previous_native_evidence(tmp_path,objective,tool):
    client=FakeClient()
    job=submit(objective,ledger=tmp_path,workspace=ROOT,
               client=client,request_id="hs-3333333333333333",execute=True)
    client.complete(job)
    out=collect(ledger=tmp_path,request_id=job["request_id"],client=client)
    assert out["status"]=="collected"
    assert out["evidence"]["tool"]==tool
    assert out["evidence"]["artifact_sha256"]
    assert Path(out["artifact_dir"]).exists()
    again=collect(ledger=tmp_path,request_id=job["request_id"],client=client)
    assert again["evidence"]==out["evidence"]


def test_tampered_kdif_html_rejected_before_marking_collected(tmp_path):
    client=FakeClient()
    job=submit("Compare board revisions",ledger=tmp_path,workspace=ROOT,
               client=client,request_id="hs-4444444444444444",execute=True)
    client.complete(job)
    def tamper(directory):
        (directory/"HS_SIGNAL_KDIF_REVISIONS.html").write_text("forged")
    client.override_source=tamper
    with pytest.raises(WorkerStateError,match="not approved"):
        collect(ledger=tmp_path,request_id=job["request_id"],client=client)
    assert read_job(tmp_path,job["request_id"])["status"]=="remote_succeeded"


def test_tampered_akcli_findings_rejected(tmp_path):
    client=FakeClient()
    job=submit("Review schematic",ledger=tmp_path,workspace=ROOT,
               client=client,request_id="hs-5555555555555555",execute=True)
    client.complete(job)
    client.override_source=lambda directory:(directory/"akcli_schematic_findings.json").write_text("{}")
    with pytest.raises(WorkerStateError,match="not approved"):
        collect(ledger=tmp_path,request_id=job["request_id"],client=client)


def test_failed_remote_run_cannot_collect(tmp_path):
    client=FakeClient()
    job=submit("Inspect schematic",ledger=tmp_path,workspace=ROOT,
               client=client,request_id="hs-6666666666666666",execute=True)
    client.complete(job,conclusion="failure")
    with pytest.raises(WorkerStateError,match="not completed"):
        collect(ledger=tmp_path,request_id=job["request_id"],client=client)
    assert not (tmp_path/job["request_id"]/"artifact").exists()


def test_github_cli_never_uses_shell_and_dispatch_body_is_fixed():
    calls=[]
    def runner(argv,**kwargs):
        calls.append((argv,kwargs))
        return SimpleNamespace(returncode=0,stdout="",stderr="")
    api=GithubCLI(run_fn=runner)
    api.dispatch(task="compare_board_revisions",request_id="hs-aaaaaaaaaaaaaaaa")
    argv,kw=calls[0]
    assert argv[:4]==["gh","api","-X","POST"]
    assert "--input" in argv and kw.get("input")
    body=json.loads(kw["input"])
    assert body=={
        "ref":"main",
        "inputs":{"hs_task":"compare_board_revisions","request_id":"hs-aaaaaaaaaaaaaaaa"},
    }
    assert kw.get("shell") is None
    with pytest.raises(WorkerStateError):
        api.dispatch(task="run_arbitrary_shell",request_id="hs-bbbbbbbbbbbbbbbb")


def test_workflow_has_unique_run_label_and_skip_other_task():
    source=(ROOT/".github/workflows/hs-github-signal-capability.yml").read_text()
    assert "run-name: HS GitHub Signal / " in source
    assert "inputs.hs_task == 'review_schematic'" in source
    assert "inputs.hs_task == 'compare_board_revisions'" in source
    assert "inputs.request_id" in source
