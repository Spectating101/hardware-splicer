#!/usr/bin/env python3
"""Replay the Engineering Change Dossier chain on the real HS, Policy Lab and Cite code.

    HS revision 1 export -> Policy Lab review (real run.mjs) -> HS-validated proposal
    -> HS revision 2 (native rerun) -> change evidence -> Cite dossier edition
    -> HS revision 3 -> Cite marks the revision-2 edition stale and refuses reissue

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
    sources = {"hs_commit": run(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).stdout.strip(),
               "policy_lab_commit": run(["git", "-C", str(policy_lab), "rev-parse", "HEAD"]).stdout.strip(),
               "cite_commit": run(["git", "-C", str(cite_root), "rev-parse", "HEAD"]).stdout.strip(),
               "policy_file": str(policy.relative_to(policy_lab)), "policy_sha256": sha(policy.read_bytes()),
               "node": run(["node", "--version"]).stdout.strip()}
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
        proposal = validate_policy_feedback(engine, base_export.read_bytes(), base_review.read_bytes())
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
            validate_policy_feedback(engine, base_export.read_bytes(), base_review.read_bytes())
            problems.append("stale revision-1 feedback was accepted after revision 2")
        except RevisionConflict as exc:
            negatives["stale_policy_feedback"] = {"refused": True, "by": "HS policy_layer", "reason": str(exc)}
            log(f"  NEGATIVE stale r1 feedback refused by HS: {exc}")

        log("4. HS: package the change evidence and the current revision head")
        files = {"base_export": base_export, "base_review": base_review, "proposal": proposal_path,
                 "candidate_export": candidate_export, "candidate_review": candidate_review}
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

        log(f"7. HS: a further change (revision 3, minimum_work_runtime_h={args.stale_runtime_target:g})")
        further = engine.run_revision(project, base_revision=2,
                                      requirements={**r2["summary"]["requirements"],
                                                    "minimum_work_runtime_h": args.stale_runtime_target},
                                      change_request="Further change after the dossier was issued")
        if not further.get("ok"):
            raise ChainError("revision 3 failed")
        r3 = engine.study(project, 3)
        log(f"  r3 run {r3['run_id']} requirements_met={r3['summary']['requirements_met']}")
        head3 = write_exchange(exchange / "head-r3.json", export_revision_head(engine.projects, project))
        try:
            build_change_evidence(engine.projects, project, base_revision=1, candidate_revision=2,
                                  root=exchange, files=files)
            problems.append("HS packaged revision 2 after revision 3 existed")
        except RevisionConflict as exc:
            negatives["hs_repackage_after_change"] = {"refused": True, "by": "HS change_dossier", "reason": str(exc)}
            log(f"  NEGATIVE HS refuses to repackage r2: {exc}")

    log("8. Cite: recheck the revision-2 edition against the new head")
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

    for name, row in negatives.items():
        if name == "stale_edition_check":
            if row["status"] != "stale":
                problems.append("the revision-2 edition was not marked stale after revision 3")
        elif not row.get("refused") or row.get("issued"):
            problems.append(f"negative control not refused: {name}")
    if packet["physical_authority_granted"] or dossier["physical_authority_granted"]:
        problems.append("physical authority appeared")
    return {
        "sources": sources,
        "project_id": project,
        "revisions": {name: {"revision": row["revision"], "run_id": row["run_id"], "parent_revision": row["parent_revision"],
                             "change_request": row["change_request"], "requirements": row["summary"]["requirements"],
                             "requirements_met": row["summary"]["requirements_met"],
                             "package_sha256": row["artifact_manifest"]["STUDY.zip"]["sha256"],
                             "checks": row["summary"]["constraints"]}
                      for name, row in (("r1", r1), ("r2", r2), ("r3", r3))},
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
    log(f"RESULT ok={summary['ok']} problems={summary.get('problems', [summary.get('error')])} "
        f"elapsed={summary['elapsed_s']} s")
    Path(str(stem) + ".json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
    Path(str(stem) + ".log").write_text("\n".join(log.lines) + "\n")
    Path(str(stem) + ".md").write_text(_markdown(summary, stem.name))


ADAPTERS = (
    ("HS export → Policy Lab review", "executable integration",
     "HS `policy_layer` export bytes are reviewed and replay-verified by Policy Lab's own `run.mjs` in this replay."),
    ("Policy Lab review → HS proposal", "executable integration",
     "HS `validate_policy_feedback` binds the review to the exact export bytes and resolves the overrides."),
    ("HS proposal → new HS revision", "executable integration",
     "`DigitalStudyEngine.run_revision` reruns the registered native study; the check delta comes from `study_evidence`."),
    ("HS change evidence → Cite dossier", "executable integration",
     "Cite's `engineering_change_cli` (new receiving contract) rereads and hash-checks every covered file."),
    ("Cite stale-edition gate", "executable integration",
     "Triggered here by a real third HS revision; Cite compares the edition with HS's exported revision head."),
    ("Cite edition → Cite workspace claims", "tested isolated adapter",
     "`record_in_workspace` writes through Cite's project/claim/evidence store; exercised here, with no reader beyond the store."),
    ("Automatic HS → Cite revision watcher", "proposed",
     "Nothing notifies Cite of a new HS revision; the head is exported and passed by this script."),
    ("Policy Lab → computed design fix", "proposed",
     "Policy Lab returns the policy's declared target as the override; it does not propose a design change that meets it."),
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
              f"- r3 run `{rev['r3']['run_id']}`: {checks(rev['r3'])}.", "",
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
    lines += [f"- {item}" for item in summary["change_evidence"]["not_linked"]]
    lines += ["- LivePresenter: not linked (optional, skipped).", "",
              "## Files", "",
              f"- Readable dossier: [`{tracked.get('dossier')}`]({tracked.get('dossier')}); "
              f"stale-marked recheck: [`{tracked.get('stale_dossier')}`]({tracked.get('stale_dossier')}).",
              f"- Exact exchanged bytes: `{tracked.get('exchange')}/`.",
              f"- Log and JSON summary: `{stem}.log`, `{stem}.json`.",
              f"- Sources: HS `{summary['sources']['hs_commit'][:12]}`, Policy Lab "
              f"`{summary['sources']['policy_lab_commit'][:12]}`, Cite `{summary['sources']['cite_commit'][:12]}`.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
