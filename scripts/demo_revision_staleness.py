#!/usr/bin/env python3
"""Replay one requirement change on a saved Fielddeck 5 study through the public API.

    requirement -> new revision -> rerun study -> stale earlier checks + retained failure

Steps, all over HTTP on the one served app (``make serve`` / ``hs-serve``):

1. Find the saved Fielddeck 5 study (``--project-id`` or the first one whose latest
   revision still has a different runtime target). With ``--create``, make one first
   through ``POST /v1/digital/projects``.
2. Record the base revision: requirements, checks, snapshot/seal/package hashes.
3. Submit the changed runtime target as a new revision (``POST .../digital/runs``)
   and wait for the native rerun of the study.
4. Re-read the base revision and require its hashes to be unchanged.
5. Ask the evidence delta which base checks are stale, which are retained, and
   which rerun checks fail. Exit non-zero unless at least one check is stale and at
   least one fails, and no physical authority appears anywhere.

Usage:
    PYTHONPATH=src python scripts/demo_revision_staleness.py --base-url http://127.0.0.1:8797 [--create]
        [--project-id ID] [--runtime-target 3.5] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

CASE_ID = "fielddeck-5"
REQUIREMENT = "minimum_work_runtime_h"


class ChainError(RuntimeError):
    pass


def http_transport(base_url):
    base_url = base_url.rstrip("/")

    def call(method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(base_url + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                return response.status, json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")
    return call


def http_job_waiter(call, *, timeout_s=1200):
    def wait(job_id):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            status, body = call("GET", f"/v1/jobs/{job_id}")
            if status == 200 and body.get("status") not in {"queued", "running"}:
                return body
            time.sleep(2.5)
        raise ChainError(f"job {job_id} did not finish in {timeout_s} s")
    return wait


def _ok(result, expected, what):
    status, body = result
    if status != expected:
        raise ChainError(f"{what}: HTTP {status} {json.dumps(body)[:600]}")
    return body


def find_study(call, target):
    projects = _ok(call("GET", "/v1/projects"), 200, "list projects").get("projects", [])
    for row in projects:
        status, body = call("GET", f"/v1/projects/{row['project_id']}/digital")
        study = body.get("study") if status == 200 else None
        if study and study["summary"].get("case_id") == CASE_ID and study["summary"]["requirements"][REQUIREMENT] != target:
            return row["project_id"]
    return None


def assurance(call, project_id, revision):
    body = _ok(call("GET", f"/v1/projects/{project_id}/engineering/assurance?revision={revision}"), 200,
               f"assurance r{revision}")
    return body["assurance"]


def run_chain(call, wait_for_job, *, project_id=None, create=False, target=3.5):
    if project_id is None:
        project_id = find_study(call, target)
    if project_id is None:
        if not create:
            raise ChainError(f"no saved {CASE_ID} study with {REQUIREMENT} != {target}; pass --create")
        created = _ok(call("POST", "/v1/digital/projects", {"case_id": CASE_ID}), 201, "create Fielddeck 5 study")
        project_id = created["project"]["project_id"]
    state = _ok(call("GET", f"/v1/projects/{project_id}/digital"), 200, "read study")
    base = state["study"]
    if base["summary"].get("case_id") != CASE_ID:
        raise ChainError(f"{project_id} is not a {CASE_ID} study")
    base_revision = base["revision"]
    before = base["summary"]["requirements"]
    if before[REQUIREMENT] == target:
        raise ChainError(f"revision {base_revision} already has {REQUIREMENT} = {target}")
    base_graph = assurance(call, project_id, base_revision)

    changed = {**before, REQUIREMENT: target}
    submitted = _ok(call("POST", f"/v1/projects/{project_id}/digital/runs", {
        "base_revision": base_revision, "requirements": changed, "request_id": str(uuid.uuid4()),
        "change_request": f"Raise the work-runtime target from {before[REQUIREMENT]:g} h to {target:g} h",
    }), 202, "submit requirement change")
    job = wait_for_job(submitted["job"]["job_id"])
    if job.get("status") != "succeeded":
        raise ChainError(f"rerun {job.get('status')}: {json.dumps(job.get('error'))[:600]}")
    history = _ok(call("GET", f"/v1/projects/{project_id}/digital"), 200, "read changed study")["history"]
    published = [row for row in history if row.get("job_id") == job["job_id"]]
    if len(published) != 1:
        raise ChainError(f"job {job['job_id']} did not publish exactly one revision")
    candidate = published[0]
    candidate_revision = candidate["revision"]
    candidate_graph = assurance(call, project_id, candidate_revision)
    base_again = assurance(call, project_id, base_revision)
    immutable = all(base_again["study"][key] == base_graph["study"][key]
                    for key in ("snapshot_sha256", "seal_sha256", "run_id", "package"))
    delta = _ok(call("POST", f"/v1/projects/{project_id}/engineering/assurance/evidence-delta",
                     {"base_revision": base_revision, "candidate_revision": candidate_revision}), 200, "evidence delta")
    checks = delta["evidence_delta"]["study_checks"]
    report = {
        "project_id": project_id,
        "case_id": CASE_ID,
        "input": {"revision": base_revision, "run_id": base["run_id"], "requirements": before,
                  "snapshot_sha256": base_graph["study"]["snapshot_sha256"],
                  "seal_sha256": base_graph["study"]["seal_sha256"],
                  "package_sha256": base_graph["study"]["package"]["sha256"],
                  "checks": base["summary"]["constraints"]},
        "change": {"requirement": REQUIREMENT, "before": before[REQUIREMENT], "after": target,
                   "job_id": job["job_id"]},
        "revision": {"revision": candidate_revision, "run_id": candidate["run_id"],
                     "parent_revision": candidate["parent_revision"], "change_request": candidate["change_request"],
                     "snapshot_sha256": candidate_graph["study"]["snapshot_sha256"],
                     "seal_sha256": candidate_graph["study"]["seal_sha256"],
                     "package_sha256": candidate_graph["study"]["package"]["sha256"],
                     "requirements_met": candidate["summary"]["requirements_met"],
                     "checks": candidate["summary"]["constraints"]},
        "base_revision_unchanged": immutable,
        "assessment": {
            "changed_dependencies": checks["changed_dependencies"],
            "stale": [_row(row) for row in checks["stale_outputs"]],
            "retained": [_row(row) for row in checks["retained_outputs"]],
            "blocked": [_row(row) for row in checks["blocked_outputs"]],
            "failing": checks["failing_outputs"],
            "packages": checks["packages"],
            "stale_counted_as_passing": checks["stale_counted_as_passing"],
            "candidate_assurance_status": candidate_graph["status"],
        },
        "rerun_scope": "The whole Fielddeck 5 study (its registered native stages) was rerun; no other project or study.",
        "physical_authority_granted": any(
            value is not False for value in (delta.get("physical_authority_granted"),
                                             checks.get("physical_authority_granted"),
                                             candidate_graph["authority_state"]["physical_authority_granted"],
                                             candidate["summary"].get("physical_authority_granted", False))),
        "ready": any(candidate_graph["authority_state"][key] for key in
                     ("fabrication_ready", "power_on_ready", "evidence_complete")),
    }
    problems = []
    if not immutable:
        problems.append("base revision hashes changed")
    if not report["assessment"]["stale"]:
        problems.append("no earlier check was marked stale")
    if not report["assessment"]["failing"]:
        problems.append("no check fails after the change")
    if any(row["counts_for_candidate"] for row in report["assessment"]["stale"]):
        problems.append("a stale check counts for the new revision")
    if report["physical_authority_granted"] or report["ready"]:
        problems.append("physical authority or readiness appeared")
    if candidate["summary"]["requirements_met"] is not False or candidate_graph["status"] != "blocked":
        problems.append("the failing revision was not kept as failing")
    report["problems"] = problems
    return report


def _row(row):
    meta = row["metadata"]
    return {"check": meta["node_id"], "from_revision": meta["revision"], "run_id": meta["run_id"],
            "result": {key: meta[key] for key in ("passed", "actual", "limit", "unit")},
            "rerun": meta["rerun"], "reasons": row["reasons"], "declaration": meta["dependency_declaration"],
            "counts_for_candidate": meta["counts_for_candidate"]}


def render(report):
    def check(row):
        return f"{row['passed'] and 'pass' or 'FAIL'} {row['actual']:g} {row['unit']} vs limit {row['limit']:g} {row['unit']}"
    lines = [f"Project {report['project_id']} ({report['case_id']})", "",
             f"INPUT     revision {report['input']['revision']} · run {report['input']['run_id']}",
             f"          snapshot {report['input']['snapshot_sha256'][:16]} · seal {report['input']['seal_sha256'][:16]}"
             f" · STUDY.zip {report['input']['package_sha256'][:16]}",
             f"          {report['change']['requirement']} = {report['change']['before']:g}"]
    lines += [f"          {row['id']}: {check(row)}" for row in report["input"]["checks"]]
    lines += ["", f"CHANGE    {report['change']['requirement']} {report['change']['before']:g} -> {report['change']['after']:g}"
              f" · job {report['change']['job_id']}",
              f"REVISION  revision {report['revision']['revision']} (parent {report['revision']['parent_revision']})"
              f" · run {report['revision']['run_id']}",
              f"          snapshot {report['revision']['snapshot_sha256'][:16]} · seal {report['revision']['seal_sha256'][:16]}"
              f" · STUDY.zip {report['revision']['package_sha256'][:16]}",
              f"          base revision unchanged: {report['base_revision_unchanged']}", "", "ASSESSMENT"]
    lines += [f"  changed  {row['dependency_id']}: {row['before']} -> {row['after']}"
              for row in report["assessment"]["changed_dependencies"]]
    for row in report["assessment"]["stale"]:
        lines.append(f"  STALE    {row['check']} from revision {row['from_revision']} (run {row['run_id'][:12]}):"
                     f" {check(row['result'])}; rerun r{row['rerun']['revision']}: {check(row['rerun'])}")
    for row in report["assessment"]["retained"]:
        lines.append(f"  retained {row['check']} from revision {row['from_revision']}: inputs unchanged, rerun matches"
                     f" ({check(row['rerun'])})")
    for row in report["assessment"]["failing"]:
        lines.append(f"  FAILING  {row['node_id']} in revision {row['revision']}: {check(row)} ({row['transition']}, kept)")
    lines += [f"  assurance status r{report['revision']['revision']}: {report['assessment']['candidate_assurance_status']}"
              f" · requirements met: {report['revision']['requirements_met']}",
              f"  physical authority granted: {report['physical_authority_granted']} · ready: {report['ready']}",
              f"  rerun scope: {report['rerun_scope']}"]
    if report["problems"]:
        lines += ["", "PROBLEMS: " + "; ".join(report["problems"])]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8787")
    parser.add_argument("--project-id")
    parser.add_argument("--create", action="store_true", help="create a Fielddeck 5 study if none qualifies")
    parser.add_argument("--runtime-target", type=float, default=3.5)
    parser.add_argument("--json", help="also write the chain report as JSON here")
    args = parser.parse_args(argv)
    call = http_transport(args.base_url)
    try:
        report = run_chain(call, http_job_waiter(call), project_id=args.project_id, create=args.create,
                           target=args.runtime_target)
    except ChainError as exc:
        print(f"chain failed: {exc}", file=sys.stderr)
        return 2
    print(render(report))
    if args.json:
        with open(args.json, "w") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
