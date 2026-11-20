#!/usr/bin/env python3
"""Replay the Engineering Change Dossier chain on the real HS, Policy Lab and Cite code.

    HS revision 1 export -> Policy Lab review (real run.mjs) -> HS-validated proposal
    -> HS revision 2 (native rerun) -> change evidence -> Cite dossier edition
    -> Policy Lab modelled candidate on revision 2 -> HS revision 3 (native rerun) -> Cite edition
    -> each later revision makes the earlier edition stale; Cite refuses to reissue it

Negative controls: a covered file changed after export, a packet naming the wrong
run, stale Policy Lab feedback after the revision, and a change packet for a
revision that is no longer the latest. Each must be refused.

Every engineering value is modeled by the registered Fielddeck 5 digital study.
Nothing is built, measured or powered; physical authority is never granted.

Usage (needs the HS native runtime, Node 22 and the other two checkouts):
    HARDWARE_SPLICER_DIGITAL_PYTHON=.../digital-native-venv/bin/python \\
    PYTHONPATH=src python scripts/demo_change_dossier.py \\
        --policy-lab /path/to/policy-lab --cite /path/to/cite-refinery \\
        [--work .cache/hardware-splicer/change-dossier] [--evidence docs/status/generated] [--tag 20261120]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.change_dossier import (build_change_evidence, export_revision_head,  # noqa: E402
                                             write_change_evidence)
from hardware_splicer.digital_engine import DigitalStudyEngine  # noqa: E402
from hardware_splicer.policy_layer import (canonical_json_bytes, export_policy_evidence,  # noqa: E402
                                           validate_policy_feedback)
from hardware_splicer.project_store import RevisionConflict  # noqa: E402

CASE_ID = "fielddeck-5"
POLICY = "applications/hardware-policy/evidence/fielddeck-20261119/policies/runtime-4h.json"
CANDIDATE_POLICY = "applications/hardware-policy/evidence/change-dossier-20261120/policies/runtime-4h-pi-load-candidate.json"
CANDIDATE_ID = "pi-work-load-budget"


class ChainError(RuntimeError):
    pass


class Log:
    def __init__(self):
        self.lines = []

    def __call__(self, text=""):
        stamp = time.strftime("%H:%M:%S")
        for line in str(text).splitlines() or [""]:
            self.lines.append(f"[{stamp}] {line}")
            print(f"[{stamp}] {line}", flush=True)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def run(command, *, allowed=(0,), env=None, timeout=300):
    done = subprocess.run(command, text=True, capture_output=True, timeout=timeout, env=env, check=False)
    if done.returncode not in allowed:
        raise ChainError(f"{command[0:3]} exited {done.returncode}: {done.stderr[-2000:]} {done.stdout[-1000:]}")
    return done


def _commit(path: Path) -> str:
    """The checkout's commit, or "unknown" for a tree without git metadata."""
    done = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], text=True, capture_output=True, check=False)
    return done.stdout.strip() if done.returncode == 0 else "unknown"


def write_exchange(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(canonical_json_bytes(value))
    return path


def policy_review(log, policy_lab: Path, policy: Path, export: Path, out: Path, revision: int, project: str):
    cli = policy_lab / "applications/hardware-policy/run.mjs"
    raw = export.read_bytes()
    value = json.loads(raw)
    done = run(["node", str(cli), "review", "--evidence", str(export), "--sha256", sha(raw), "--policy", str(policy),
                "--project-id", project, "--revision", str(revision), "--run-id", value["run_id"],
                "--out", str(out)], allowed=(0, 2))
    review = json.loads((out / "review.json").read_bytes())
    if review["decision"] == "BLOCKED" and done.returncode != 2:
        raise ChainError("Policy Lab exit code does not match its BLOCKED decision.")
    verified = json.loads(run(["node", str(cli), "verify", "--review", str(out / "review.json"),
                               "--evidence", str(export)]).stdout)
    if verified.get("verified") is not True:
        raise ChainError("Policy Lab review did not replay.")
    (out / "replay.json").write_bytes(canonical_json_bytes(verified))
    log(f"  Policy Lab {review['policy']['id']} on r{revision}: {review['decision']} (exit {done.returncode}); "
        f"replay verified: {verified['verified']}")
    for row in review["unmet_constraints"]:
        log(f"    unmet {row['id']}: {row['explanation']}")
    log(f"    revision_requirements proposed: {json.dumps(review['revision_requirements'], sort_keys=True)}")
    return out / "review.json", review, verified


def cite(log, cite_root: Path, *args, allowed=(0,)):
    env = {**os.environ, "PYTHONPATH": str(cite_root / "src")}
    done = run([sys.executable, "-m", "cite_refinery.engineering_change_cli", *map(str, args)], allowed=allowed, env=env)
    return done.returncode, json.loads(done.stdout)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--policy-lab", type=Path, required=True)
    parser.add_argument("--cite", type=Path, required=True)
    parser.add_argument("--policy", type=Path, help=f"default: <policy-lab>/{POLICY}")
    parser.add_argument("--work", type=Path, default=ROOT / ".cache/hardware-splicer/change-dossier")
    parser.add_argument("--evidence", type=Path, default=ROOT / "docs/status/generated")
    parser.add_argument("--tag", default="20261120")
    parser.add_argument("--stale-runtime-target", type=float, default=3.0,
                        help="minimum_work_runtime_h of the further revision that makes the edition stale")
    args = parser.parse_args(argv)
    log = Log()
    started = time.monotonic()
    policy_lab, cite_root = args.policy_lab.resolve(), args.cite.resolve()
    policy = (args.policy or policy_lab / POLICY).resolve()
    work = args.work.resolve() / time.strftime("%Y%m%dT%H%M%S")
    exchange = work / "exchange"
    work.mkdir(parents=True)
    summary = {"schema": "hardware_splicer.change_dossier_replay.v1", "case_id": CASE_ID,
               "physical_authority_granted": False, "authority_level": "modeled"}
    try:
        summary.update(_chain(log, policy_lab, cite_root, policy, work, exchange, args))
        summary["ok"] = not summary["problems"]
    except ChainError as exc:
        log(f"CHAIN FAILED: {exc}")
        summary.update(ok=False, error=str(exc))
    summary["elapsed_s"] = round(time.monotonic() - started, 1)
    summary["work_dir_is_scratch"] = True
    _publish(log, summary, work, args.evidence, args.tag)
    return 0 if summary["ok"] else 1


def _chain(log, policy_lab, cite_root, policy, work, exchange, args):
    problems, negatives = [], {}
    sources = {"hs_commit": _commit(ROOT), "policy_lab_commit": _commit(policy_lab), "cite_commit": _commit(cite_root),
               "policy_file": str(policy.relative_to(policy_lab)), "policy_sha256": sha(policy.read_bytes()),
               "node": run(["node", "--version"]).stdout.strip()}
    run_mjs = policy_lab / "applications/hardware-policy/run.mjs"
    log(f"HS {sources['hs_commit'][:12]} · Policy Lab {sources['policy_lab_commit'][:12]} · "
        f"Cite {sources['cite_commit'][:12]} · node {sources['node']}")
    with DigitalStudyEngine(project_root=work / "projects", job_db=work / "jobs.sqlite3") as engine:
        log(f"1. HS: create {CASE_ID} revision 1 (native build)")
        project = engine.create(case_id=CASE_ID)["project"]["project_id"]
        r1 = engine.study(project, 1)
        log(f"  project {project} r1 run {r1['run_id']} requirements_met={r1['summary']['requirements_met']}")
        for row in r1["summary"]["constraints"]:
            log(f"    {row['id']}: {'pass' if row['passed'] else 'FAIL'} {row['actual']} {row['unit']} "
                f"vs {row['limit']} {row['unit']}")
        base_export = write_exchange(exchange / "r1-export.json", export_policy_evidence(engine, project, 1))
        log(f"  export r1-export.json sha256 {sha(base_export.read_bytes())}")

        log("2. Policy Lab: review revision 1 against its checked-in runtime policy")
        base_review, review1, replay1 = policy_review(log, policy_lab, policy, base_export, exchange / "r1-review", 1, project)
        proposal = validate_policy_feedback(engine, base_export.read_bytes(), base_review.read_bytes(),
                                            policy_lab_run=run_mjs)
        proposal_path = write_exchange(exchange / "proposal.json", proposal)
        log(f"  HS validated proposal: {json.dumps(proposal['requirement_changes'], sort_keys=True)} "
            f"(automatic_execution={proposal['automatic_execution']})")

        log("3. HS: apply the accepted proposal as a new revision (native rerun)")
        applied = engine.run_revision(project, base_revision=1, requirements=proposal["resolved_requirements"],
                                      change_request=f"Apply Policy Lab {review1['policy']['id']} proposal",
                                      request_id=str(uuid5(NAMESPACE_URL, "change-dossier:" + sha(base_review.read_bytes()))))
        if not applied.get("ok"):
            raise ChainError(f"revision 2 failed: {json.dumps(applied.get('job', {}).get('error'))[:600]}")
        r2 = engine.study(project, 2)
        log(f"  r2 run {r2['run_id']} parent {r2['parent_revision']} requirements_met={r2['summary']['requirements_met']}")
        for row in r2["summary"]["constraints"]:
            log(f"    {row['id']}: {'pass' if row['passed'] else 'FAIL'} {row['actual']} {row['unit']} "
                f"vs {row['limit']} {row['unit']}")
        candidate_export = write_exchange(exchange / "r2-export.json", export_policy_evidence(engine, project, 2))
        candidate_review, review2, replay2 = policy_review(log, policy_lab, policy, candidate_export,
                                                           exchange / "r2-review", 2, project)
        try:
            validate_policy_feedback(engine, base_export.read_bytes(), base_review.read_bytes(), policy_lab_run=run_mjs)
            problems.append("stale revision-1 feedback was accepted after revision 2")
        except RevisionConflict as exc:
            negatives["stale_policy_feedback"] = {"refused": True, "by": "HS policy_layer", "reason": str(exc)}
            log(f"  NEGATIVE stale r1 feedback refused by HS: {exc}")

        log("4. HS: package the change evidence and the current revision head")
        files = {"base_export": base_export, "base_review": base_review,
                 "base_review_replay": base_review.parent / "replay.json", "proposal": proposal_path,
                 "candidate_export": candidate_export, "candidate_review": candidate_review,
                 "candidate_review_replay": candidate_review.parent / "replay.json"}
        packet = build_change_evidence(engine.projects, project, base_revision=1, candidate_revision=2,
                                       root=exchange, files=files)
        packet_receipt = write_change_evidence(exchange / "change-evidence.json", packet)
        head2 = write_exchange(exchange / "head-r2.json", export_revision_head(engine.projects, project))
        log(f"  change-evidence.json sha256 {packet_receipt['sha256']}")
        for row in packet["check_delta"]["stale"]:
            log(f"    STALE {row['check']} from r{row['from_revision']}: passed={row['result']['passed']} "
                f"{row['result']['actual']} vs {row['result']['limit']}; rerun r{row['rerun']['revision']} "
                f"passed={row['rerun']['passed']}")
        for row in packet["check_delta"]["retained"]:
            log(f"    retained {row['check']} from r{row['from_revision']}")
        for row in packet["unresolved"]:
            log(f"    unresolved {json.dumps(row, sort_keys=True)}")

        log("5. Cite: issue the revision-2 dossier edition")
        edition = work / "cite" / "edition-r2"
        code, issued = cite(log, cite_root, "issue", "--packet", exchange / "change-evidence.json", "--root", exchange,
                            "--head", head2, "--out", edition, "--workspace", work / "cite" / "workspace")
        log(f"  issued edition {issued['edition_id']} bound to r{issued['bound_to_revision']} (exit {code})")
        dossier = json.loads((edition / "dossier.json").read_bytes())
        dossier_md = (edition / "dossier.md").read_text()
        failing = [row for row in dossier["checks"] if row["result"] == "FAIL"]
        if not failing:
            problems.append("the dossier lost the failing revision-2 check")
        lowered = dossier_md.lower() + json.dumps(dossier).lower()
        if "ready" in lowered or "approved" in lowered:
            problems.append("ready/approved wording appeared in the dossier")

        log("6. Negative controls at the Cite boundary")
        tampered = work / "exchange-tampered"
        shutil.copytree(exchange, tampered)
        raw = (tampered / "r2-export.json").read_bytes()
        (tampered / "r2-export.json").write_bytes(raw.replace(b'"passed":false', b'"passed":true', 1))
        code, result = cite(log, cite_root, "issue", "--packet", tampered / "change-evidence.json", "--root", tampered,
                            "--head", head2, "--out", work / "cite" / "tampered", allowed=(1,))
        negatives["changed_covered_file"] = {"refused": code == 1, "exit_code": code, "reason": result.get("error")}
        log(f"  NEGATIVE changed r2-export.json: exit {code} {result.get('error')}")
        wrong = json.loads((exchange / "change-evidence.json").read_bytes())
        wrong["candidate"]["run_id"] = "0" * 32
        wrong_path = work / "wrong-run-packet.json"
        wrong_path.write_bytes(canonical_json_bytes(wrong))
        code, result = cite(log, cite_root, "issue", "--packet", wrong_path, "--root", exchange, "--head", head2,
                            "--out", work / "cite" / "wrong-run", allowed=(1,))
        negatives["wrong_revision_identity"] = {"refused": code == 1, "exit_code": code, "reason": result.get("error")}
        log(f"  NEGATIVE packet naming the wrong run: exit {code} {result.get('error')}")

        log("7. Policy Lab: review failing revision 2 under a policy declaring a modelled candidate design change")
        candidate_policy = policy_lab / CANDIDATE_POLICY
        r2_candidate_review, review2c, replay2c = policy_review(log, policy_lab, candidate_policy, candidate_export,
                                                               exchange / "r2-candidate-review", 2, project)
        offered = {row["id"]: row for row in review2c.get("candidate_design_changes", [])}
        candidate = offered.get(CANDIDATE_ID)
        if candidate is None or candidate["status"] != "PROPOSED":
            raise ChainError(f"Policy Lab proposed no {CANDIDATE_ID} candidate: {json.dumps(candidate)[:400]}")
        log(f"  candidate {candidate['id']}: {candidate['input']} {candidate['before']} -> {candidate['after']} "
            f"({candidate['status']})")
        log(f"    formula: {candidate['formula']}")
        log(f"    numbers: {json.dumps(candidate['numbers'], sort_keys=True)}")
        proposal3 = validate_policy_feedback(engine, candidate_export.read_bytes(), r2_candidate_review.read_bytes(),
                                             policy_lab_run=run_mjs, candidates=(CANDIDATE_ID,))
        proposal3_path = write_exchange(exchange / "proposal-r3.json", proposal3)
        log(f"  HS validated proposal (replay: {proposal3['policy_review_verification']}): "
            f"{json.dumps(proposal3['requirement_changes'], sort_keys=True)}")

        log("8. HS: apply the candidate as revision 3 (native rerun)")
        applied3 = engine.run_revision(project, base_revision=2, requirements=proposal3["resolved_requirements"],
                                       change_request=f"Apply Policy Lab modelled candidate {CANDIDATE_ID}",
                                       request_id=str(uuid5(NAMESPACE_URL, "change-dossier:" + sha(r2_candidate_review.read_bytes()))))
        if not applied3.get("ok"):
            raise ChainError(f"revision 3 failed: {json.dumps(applied3.get('job', {}).get('error'))[:600]}")
        r3 = engine.study(project, 3)
        log(f"  r3 run {r3['run_id']} parent {r3['parent_revision']} requirements_met={r3['summary']['requirements_met']}")
        log(f"    metrics: {json.dumps(r3['summary']['metrics'], sort_keys=True)}")
        for row in r3["summary"]["constraints"]:
            log(f"    {row['id']}: {'pass' if row['passed'] else 'FAIL'} {row['actual']} {row['unit']} "
                f"vs {row['limit']} {row['unit']}")
        r3_export = write_exchange(exchange / "r3-export.json", export_policy_evidence(engine, project, 3))
        r3_review, review3, replay3 = policy_review(log, policy_lab, candidate_policy, r3_export,
                                                    exchange / "r3-review", 3, project)
        head3 = write_exchange(exchange / "head-r3.json", export_revision_head(engine.projects, project))
        try:
            build_change_evidence(engine.projects, project, base_revision=1, candidate_revision=2,
                                  root=exchange, files=files)
            problems.append("HS packaged revision 2 after revision 3 existed")
        except RevisionConflict as exc:
            negatives["hs_repackage_after_change"] = {"refused": True, "by": "HS change_dossier", "reason": str(exc)}
            log(f"  NEGATIVE HS refuses to repackage r2: {exc}")
        files3 = {"base_export": candidate_export, "base_review": r2_candidate_review,
                  "base_review_replay": r2_candidate_review.parent / "replay.json", "proposal": proposal3_path,
                  "candidate_export": r3_export, "candidate_review": r3_review,
                  "candidate_review_replay": r3_review.parent / "replay.json"}
        packet3 = build_change_evidence(engine.projects, project, base_revision=2, candidate_revision=3,
                                        root=exchange, files=files3)
        packet3_receipt = write_change_evidence(exchange / "change-evidence-r3.json", packet3)
        outcomes = {row["id"]: row["native_outcome"] for row in packet3["proposal"]["candidate_design_changes"]}
        if CANDIDATE_ID not in outcomes:
            raise ChainError(f"the revision-3 packet does not carry candidate {CANDIDATE_ID}")
        outcome = outcomes[CANDIDATE_ID]
        log(f"  change-evidence-r3.json sha256 {packet3_receipt['sha256']}")
        log(f"  NATIVE OUTCOME {outcome['fact']} = {outcome['native_value']} {outcome['unit']} "
            f"(required {outcome['operator']} {outcome['required']}): met={outcome['met']}")

        log("9. Cite: recheck the revision-2 edition against the revision-3 head")
        code, currency = cite(log, cite_root, "check", "--dossier", edition / "dossier.json", "--head", head3,
                              "--out", work / "cite" / "edition-r2-recheck", "--workspace", work / "cite" / "workspace",
                              "--cite-project-id", issued["workspace_record"]["project_id"], allowed=(3,))
        negatives["stale_edition_check"] = {"status": currency["status"], "exit_code": code, "reasons": currency["reasons"]}
        log(f"  edition {currency['edition_id'][:16]}: {currency['status']} (exit {code}); {'; '.join(currency['reasons'])}")
        code, refused = cite(log, cite_root, "issue", "--packet", exchange / "change-evidence.json", "--root", exchange,
                             "--head", head3, "--out", work / "cite" / "edition-r2-reissue", allowed=(3,))
        negatives["stale_edition_reissue"] = {"refused": refused["status"] == "refused_stale", "exit_code": code,
                                              "issued": (work / "cite" / "edition-r2-reissue").exists()}
        log(f"  reissue with r3 head: {refused['status']} (exit {code}); output written: "
            f"{negatives['stale_edition_reissue']['issued']}")
        stale_md = (work / "cite" / "edition-r2-recheck" / "dossier.md").read_text()

        log("10. Cite: issue the revision-3 (candidate) dossier edition")
        edition3 = work / "cite" / "edition-r3"
        code, issued3 = cite(log, cite_root, "issue", "--packet", exchange / "change-evidence-r3.json", "--root", exchange,
                             "--head", head3, "--out", edition3, "--workspace", work / "cite" / "workspace")
        log(f"  issued edition {issued3['edition_id']} bound to r{issued3['bound_to_revision']} (exit {code})")
        dossier3 = json.loads((edition3 / "dossier.json").read_bytes())
        dossier3_md = (edition3 / "dossier.md").read_text()
        if "unknown / not tested" not in dossier3_md:
            problems.append("the revision-3 dossier does not state the physical means as unknown")

        log(f"11. HS: a further change (revision 4, minimum_work_runtime_h={args.stale_runtime_target:g})")
        further = engine.run_revision(project, base_revision=3,
                                      requirements={**r3["summary"]["requirements"],
                                                    "minimum_work_runtime_h": args.stale_runtime_target},
                                      change_request="Further change after the revision-3 dossier was issued")
        if not further.get("ok"):
            raise ChainError("revision 4 failed")
        r4 = engine.study(project, 4)
        log(f"  r4 run {r4['run_id']} requirements_met={r4['summary']['requirements_met']}")
        head4 = write_exchange(exchange / "head-r4.json", export_revision_head(engine.projects, project))

    log("12. Cite: recheck the revision-3 (candidate) edition against the revision-4 head")
    code, currency3 = cite(log, cite_root, "check", "--dossier", edition3 / "dossier.json", "--head", head4,
                           "--out", work / "cite" / "edition-r3-recheck", "--workspace", work / "cite" / "workspace",
                           "--cite-project-id", issued3["workspace_record"]["project_id"], allowed=(3,))
    negatives["candidate_edition_stale_check"] = {"status": currency3["status"], "exit_code": code,
                                                  "reasons": currency3["reasons"]}
    log(f"  edition {currency3['edition_id'][:16]}: {currency3['status']} (exit {code}); {'; '.join(currency3['reasons'])}")
    code, refused3 = cite(log, cite_root, "issue", "--packet", exchange / "change-evidence-r3.json", "--root", exchange,
                          "--head", head4, "--out", work / "cite" / "edition-r3-reissue", allowed=(3,))
    negatives["candidate_edition_reissue"] = {"refused": refused3["status"] == "refused_stale", "exit_code": code,
                                              "issued": (work / "cite" / "edition-r3-reissue").exists()}
    log(f"  reissue with r4 head: {refused3['status']} (exit {code}); output written: "
        f"{negatives['candidate_edition_reissue']['issued']}")
    stale3_md = (work / "cite" / "edition-r3-recheck" / "dossier.md").read_text()
    for text in (dossier_md, dossier3_md, stale_md, stale3_md):
        lowered = text.lower()
        if any(re.search(pattern, lowered) for pattern in (r"\bfix(es|ed)?\b", r"\bready\b", r"\bapproved\b")):
            problems.append("fix/ready/approved wording appeared in a dossier")

    for name, row in negatives.items():
        if "status" in row:
            if row["status"] != "stale":
                problems.append(f"an edition was not marked stale after a further change: {name}")
        elif not row.get("refused") or row.get("issued"):
            problems.append(f"negative control not refused: {name}")
    if any(value["physical_authority_granted"] for value in (packet, dossier, packet3, dossier3)):
        problems.append("physical authority appeared")
    return {
        "sources": sources,
        "project_id": project,
        "revisions": {name: {"revision": row["revision"], "run_id": row["run_id"], "parent_revision": row["parent_revision"],
                             "change_request": row["change_request"], "requirements": row["summary"]["requirements"],
                             "requirements_met": row["summary"]["requirements_met"],
                             "package_sha256": row["artifact_manifest"]["STUDY.zip"]["sha256"],
                             "checks": row["summary"]["constraints"]}
                      for name, row in (("r1", r1), ("r2", r2), ("r3", r3), ("r4", r4))},
        "identity": {"base": {k: packet["base"][k] for k in ("snapshot_sha256", "seal_sha256", "package_sha256")},
                     "candidate": {k: packet["candidate"][k] for k in ("snapshot_sha256", "seal_sha256", "package_sha256")}},
        "policy_reviews": {
            "r1": {"policy": review1["policy"]["id"], "decision": review1["decision"],
                   "unmet": [row["explanation"] for row in review1["unmet_constraints"]],
                   "revision_requirements": review1["revision_requirements"], "replay_verified": replay1["verified"],
                   "review_sha256": sha(base_review.read_bytes())},
            "r2": {"policy": review2["policy"]["id"], "decision": review2["decision"],
                   "unmet": [row["explanation"] for row in review2["unmet_constraints"]],
                   "replay_verified": replay2["verified"], "review_sha256": sha(candidate_review.read_bytes())}},
        "proposal": {"requirement_changes": proposal["requirement_changes"],
                     "resolved_requirements": proposal["resolved_requirements"],
                     "sha256": sha(proposal_path.read_bytes()), "status": proposal["status"]},
        "change_evidence": {"sha256": packet_receipt["sha256"], "files": packet["files"],
                            "stale": packet["check_delta"]["stale"], "retained": packet["check_delta"]["retained"],
                            "unresolved": packet["unresolved"], "not_tested": packet["not_tested"],
                            "not_linked": packet["not_linked"]},
        "dossier": {"edition_id": dossier["edition"]["edition_id"], "bound_to": dossier["edition"]["bound_to"],
                    "failing_checks": failing, "markdown": dossier_md, "stale_markdown": stale_md,
                    "json": dossier},
        "candidate": {"policy": review2c["policy"]["id"], "policy_decision": review2c["decision"],
                      "row": {key: candidate[key] for key in ("id", "status", "input", "before", "after", "formula",
                                                              "numbers", "assumptions", "basis")},
                      "requirement_changes": proposal3["requirement_changes"],
                      "replay": proposal3["policy_review_verification"],
                      "native_outcome": outcome, "r3_metrics": r3["summary"]["metrics"],
                      "r3_review": {"decision": review3["decision"],
                                    "unmet": [row["explanation"] for row in review3["unmet_constraints"]]},
                      "change_evidence_sha256": packet3_receipt["sha256"],
                      "not_tested": packet3["not_tested"], "unresolved": packet3["unresolved"]},
        "dossier_r3": {"edition_id": dossier3["edition"]["edition_id"], "bound_to": dossier3["edition"]["bound_to"],
                       "markdown": dossier3_md, "stale_markdown": stale3_md, "json": dossier3},
        "negative_controls": negatives,
        "exchange_dir": exchange,
        "problems": problems,
    }


def _publish(log, summary, work, evidence, tag):
    evidence.mkdir(parents=True, exist_ok=True)
    stem = evidence / f"change-dossier-{tag}"
    exchange = summary.pop("exchange_dir", None)
    dossier = summary.get("dossier", {})
    if exchange is not None:
        # Keep the exact exchanged bytes so the Cite receiver can be retested on them.
        tracked = Path(str(stem) + "-exchange")
        if tracked.exists():
            shutil.rmtree(tracked)
        shutil.copytree(exchange, tracked, ignore=shutil.ignore_patterns("report.md"))
        Path(str(stem) + "-dossier.md").write_text(dossier.pop("markdown"))
        Path(str(stem) + "-dossier-stale.md").write_text(dossier.pop("stale_markdown"))
        Path(str(stem) + "-dossier.json").write_text(json.dumps(dossier.pop("json"), indent=2, sort_keys=True) + "\n")
        summary["tracked"] = {"exchange": tracked.name, "dossier": stem.name + "-dossier.md",
                              "stale_dossier": stem.name + "-dossier-stale.md", "dossier_json": stem.name + "-dossier.json"}
        dossier3 = summary["dossier_r3"]
        Path(str(stem) + "-dossier-r3.md").write_text(dossier3.pop("markdown"))
        Path(str(stem) + "-dossier-r3-stale.md").write_text(dossier3.pop("stale_markdown"))
        Path(str(stem) + "-dossier-r3.json").write_text(json.dumps(dossier3.pop("json"), indent=2, sort_keys=True) + "\n")
        summary["tracked"].update(dossier_r3=stem.name + "-dossier-r3.md", stale_dossier_r3=stem.name + "-dossier-r3-stale.md",
                                  dossier_r3_json=stem.name + "-dossier-r3.json")
    log(f"RESULT ok={summary['ok']} problems={summary.get('problems', [summary.get('error')])} "
        f"elapsed={summary['elapsed_s']} s")
    Path(str(stem) + ".json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
    Path(str(stem) + ".log").write_text("\n".join(log.lines) + "\n")
    Path(str(stem) + ".md").write_text(_markdown(summary, stem.name))


ADAPTERS = (
    ("HS export → Policy Lab review", "executable integration",
     "HS `policy_layer` export bytes are reviewed and replay-verified by Policy Lab's own `run.mjs` in this replay."),
    ("Policy Lab review → HS proposal", "executable integration",
     "HS `validate_policy_feedback` checks the decision against its rows, runs Policy Lab `verify` itself, "
     "and binds the review to the exact export bytes."),
    ("HS proposal → new HS revision", "executable integration",
     "`DigitalStudyEngine.run_revision` reruns the registered native study; the check delta comes from `study_evidence`."),
    ("Policy Lab → modelled candidate design change → HS revision 3", "executable integration",
     "Policy Lab computes the `pi_work_current_a` candidate from exported modeled numbers; HS applies the selected "
     "candidate and reruns natively; the packet reports the native value against the target."),
    ("HS change evidence → Cite dossier", "executable integration",
     "Cite's `engineering_change_cli` rereads and hash-checks every covered file and rederives the candidate outcome."),
    ("Cite stale-edition gate", "executable integration",
     "Triggered by real HS revisions 3 and 4; Cite compares each edition with HS's exported revision head."),
    ("Cite edition → Cite workspace claims", "tested isolated adapter",
     "`record_in_workspace` writes through Cite's project/claim/evidence store; exercised here, with no reader beyond the store."),
    ("Candidate load → physical means (underclock, board, peripheral)", "not linked",
     "Nothing identifies or tests how the Pi would draw the candidate current; stated as unknown / not tested."),
    ("Automatic HS → Cite revision watcher", "proposed",
     "Nothing notifies Cite of a new HS revision; the head is exported and passed by this script."),
)


def _markdown(summary, stem):
    lines = [f"# Engineering change dossier replay ({stem})", "",
             f"Result: **{'chain completed, every negative control refused' if summary['ok'] else 'FAILED'}**. "
             "All engineering values are modeled by the registered Fielddeck 5 digital study; "
             "nothing was built, measured or powered, and physical authority was never granted. "
             "This is a replay on real code, not customer use or physical proof.", ""]
    if not summary.get("revisions"):
        return "\n".join(lines + [f"Error: {summary.get('error')}", ""])
    rev, reviews, proposal = summary["revisions"], summary["policy_reviews"], summary["proposal"]

    def checks(row):
        return "; ".join(f"{c['id']} {'pass' if c['passed'] else 'FAIL'} {c['actual']} {c['unit']} "
                         f"(limit {c['limit']})" for c in row["checks"])

    lines += ["## Chain", "",
              f"- HS project `{summary['project_id']}`.",
              f"- r1 run `{rev['r1']['run_id']}`, package `{rev['r1']['package_sha256'][:16]}`: {checks(rev['r1'])}.",
              f"- Policy Lab `{reviews['r1']['policy']}` on r1: **{reviews['r1']['decision']}** "
              f"({'; '.join(reviews['r1']['unmet']) or 'no unmet targets'}); replay verified: {reviews['r1']['replay_verified']}.",
              f"- HS-validated proposal: `{json.dumps(proposal['requirement_changes'], sort_keys=True)}`.",
              f"- r2 run `{rev['r2']['run_id']}` (parent {rev['r2']['parent_revision']}), package "
              f"`{rev['r2']['package_sha256'][:16]}`: {checks(rev['r2'])}. Requirements met: {rev['r2']['requirements_met']}.",
              f"- Policy Lab on r2: **{reviews['r2']['decision']}** ({'; '.join(reviews['r2']['unmet']) or 'none'}).",
              f"- Change evidence sha256 `{summary['change_evidence']['sha256']}`.",
              f"- Cite edition `{summary['dossier']['edition_id'][:16]}` bound to r{summary['dossier']['bound_to']['revision']}; "
              f"failing checks kept: {', '.join(row['check'] for row in summary['dossier']['failing_checks'])}.",
              f"- r3 run `{rev['r3']['run_id']}` (modelled candidate applied): {checks(rev['r3'])}. "
              f"Requirements met: {rev['r3']['requirements_met']}.",
              f"- r4 run `{rev['r4']['run_id']}` (further change): {checks(rev['r4'])}.", ""]
    cand = summary["candidate"]
    row, outcome = cand["row"], cand["native_outcome"]
    lines += ["## Modelled candidate design change (revision 3)", "",
              f"Policy Lab `{cand['policy']}` on the failing revision 2 ({cand['policy_decision']}) proposed "
              f"`{row['id']}`: `{row['input']}` {row['before']} → **{row['after']}** A ({row['status']}).", "",
              f"- Formula: `{row['formula']}`.",
              "- Numbers: " + ", ".join(f"{k} = {v}" for k, v in sorted(row["numbers"].items())) + ".",
              *[f"- Assumption: {item}" for item in row["assumptions"]],
              f"- HS replay check: {cand['replay']}.",
              f"- HS requirement changes applied as revision 3: `{json.dumps(cand['requirement_changes'], sort_keys=True)}`.",
              f"- **Native rerun:** {outcome['fact']} = **{outcome['native_value']} {outcome['unit']}** against "
              f"{outcome['operator']} {outcome['required']} {outcome['unit']}: "
              f"{'meets the target' if outcome['met'] else 'does NOT meet the target'} (modeled, margin "
              f"{round(outcome['native_value'] - outcome['required'], 3)} {outcome['unit']}).",
              f"- Revision 3 metrics: `{json.dumps(cand['r3_metrics'], sort_keys=True)}`.",
              f"- Policy Lab on revision 3: {cand['r3_review']['decision']}"
              + (f" ({'; '.join(cand['r3_review']['unmet'])})" if cand["r3_review"]["unmet"] else "") + ".",
              "- Physical means of reaching this load: **unknown / not tested**. Nothing here says what would make "
              "the Pi draw this current.", "",
              "## Negative and stale controls", ""]
    for name, row in summary["negative_controls"].items():
        detail = row.get("reason") or "; ".join(row.get("reasons", [])) or ""
        outcome = row.get("status") or ("refused" if row.get("refused") else "NOT refused")
        lines.append(f"- `{name}`: {outcome}" + (f" (exit {row['exit_code']})" if "exit_code" in row else "")
                     + (f". {detail}" if detail else ""))
    lines += ["", "## Adapters", "", "| Hand-off | Classification | Evidence |", "|---|---|---|"]
    lines += [f"| {name} | {kind} | {note} |" for name, kind, note in ADAPTERS]
    tracked = summary.get("tracked", {})
    lines += ["", "## Not tested or not linked", ""] + [f"- {item}" for item in summary["change_evidence"]["not_tested"]]
    lines += [f"- {item}" for item in summary["candidate"]["not_tested"] if item not in summary["change_evidence"]["not_tested"]]
    lines += [f"- {item}" for item in summary["change_evidence"]["not_linked"]]
    lines += ["- LivePresenter: not linked (optional, skipped).", "",
              "## Files", "",
              f"- Revision-2 dossier: [`{tracked.get('dossier')}`]({tracked.get('dossier')}); "
              f"stale-marked recheck: [`{tracked.get('stale_dossier')}`]({tracked.get('stale_dossier')}).",
              f"- Revision-3 (candidate) dossier: [`{tracked.get('dossier_r3')}`]({tracked.get('dossier_r3')}); "
              f"stale-marked recheck: [`{tracked.get('stale_dossier_r3')}`]({tracked.get('stale_dossier_r3')}).",
              f"- Exact exchanged bytes: `{tracked.get('exchange')}/`.",
              f"- Log and JSON summary: `{stem}.log`, `{stem}.json`.",
              f"- Sources: HS `{summary['sources']['hs_commit'][:12]}`, Policy Lab "
              f"`{summary['sources']['policy_lab_commit'][:12]}`, Cite `{summary['sources']['cite_commit'][:12]}`.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
