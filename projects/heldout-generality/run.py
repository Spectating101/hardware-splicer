"""Unseen-board HS generalization benchmark: native board checks + negative controls.

Does not produce fabrication authority. No schematic equivalence claim is made
for the corpus (schematics are not included). Preserves project-specific rules.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import freeze

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hardware_splicer.integrations.external_eda_verification import pinned_source  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def checked_bytes(repo: Path, lock: dict, case: dict, name: str) -> bytes:
    prefix = "boards/" + case["id"] + "/"
    if name not in case["files_sha256"] or "/" in name or ".." in Path(name).parts:
        raise ValueError("unlocked or unsafe input file")
    data = freeze.blob(repo, prefix + name)
    if sha(data) != case["files_sha256"][name]:
        raise ValueError("CORPUS_SOURCE_HASH_MISMATCH: " + case["id"] + "/" + name)
    return data


def verify_lock(repo: Path, lock: dict) -> None:
    if lock.get("schema") != "hs.heldout_pcb_cohort.v1":
        raise ValueError("wrong cohort schema")
    if lock.get("corpus_commit") != freeze.CORPUS_REV:
        raise ValueError("wrong pinned corpus revision")
    head = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, timeout=10,
    ).strip()
    if head != freeze.CORPUS_REV:
        raise ValueError("corpus checkout must be pinned at cohort commit")
    manifest_bytes = freeze.blob(repo, "manifest.json")
    if sha(manifest_bytes) != lock["manifest_sha256"]:
        raise ValueError("manifest differs from selection lock")
    original = json.loads(manifest_bytes)
    selected = freeze.choose(original)
    if [item["id"] for item in selected] != [item["id"] for item in lock["cases"]]:
        raise ValueError("cohort selection does not replay")
    for saved, expected in zip(lock["cases"], selected):
        if saved["metadata"] != expected["metadata"] or saved["stratum"] != expected["stratum"]:
            raise ValueError("source metadata/stratum changed")
        if not all(name in saved["files_sha256"] for name in
                   ["board.kicad_pcb", "board.kicad_pro", "SOURCE.json"]):
            raise ValueError("incomplete source lock")


def materialize(repo: Path, lock: dict, case: dict, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name in sorted(case["files_sha256"]):
        data = checked_bytes(repo, lock, case, name)
        destination = directory / name
        destination.write_bytes(data)
        hashes[name] = sha(destination.read_bytes())
    source = json.loads((directory / "SOURCE.json").read_bytes())
    if source["repo"] != case["metadata"]["repo"] or source["commit"] != case["metadata"]["commit"]:
        raise ValueError("source origin contradiction")
    return hashes


def run_command(command: list[str], work: Path, logfile: str, timeout: int = 90) -> int:
    try:
        run = subprocess.run(command, cwd=work, capture_output=True, timeout=timeout, check=False)
        out, err, rc = run.stdout, run.stderr, run.returncode
    except subprocess.TimeoutExpired as exc:
        out, err, rc = exc.stdout or b"", (exc.stderr or b"") + b"\nTIMEOUT", -1
    (work / (logfile + ".stdout")).write_bytes(out)
    (work / (logfile + ".stderr")).write_bytes(err)
    return rc


def drc(board_dir: Path, *, native_cli: str) -> dict:
    report = board_dir / "native-drc.json"
    rc = run_command([
        native_cli, "pcb", "drc", "--severity-error", "--format", "json",
        "--exit-code-violations", "--output", str(report),
        str(board_dir / "board.kicad_pcb"),
    ], board_dir, "native-drc", 150)
    try:
        data = json.loads(report.read_text())
        violations = data["violations"]
        unconnected = data["unconnected_items"]
        parity = data["schematic_parity"]
        if not (isinstance(violations, list) and isinstance(unconnected, list)
                and isinstance(parity, list)):
            raise ValueError("wrong json schema")
        # Count fingerprints, not timestamps, random tool process IDs or file locations.
        counts = dict(sorted(collections.Counter(
            str(item.get("type", "unknown")) for item in violations
        ).items()))
        def stable_finding(entry):
            return {
                "type": entry.get("type"),
                "severity": entry.get("severity"),
                "description": entry.get("description"),
                "items": sorted(
                    ({"description": p.get("description"), "pos": p.get("pos")}
                     for p in entry.get("items", [])),
                    key=canonical,
                ),
            }
        signatures = sorted(
            (stable_finding(item) for item in violations + unconnected + parity),
            key=canonical,
        )
        status = "PROCESSED" if (rc == 0 or (rc > 0 and bool(violations or unconnected or parity))) else "TOOL_FAILURE"
        return {
            "status": status,
            "exit_code": rc,
            "error_count": len(violations),
            "unconnected_count": len(unconnected),
            "schematic_parity_count": len(parity),
            "finding_types": counts,
            "semantic_finding_sha256": sha(canonical(signatures).encode()),
        }
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "TOOL_FAILURE", "exit_code": rc}


def run_kiskill(work: Path, repo: Path | None) -> dict:
    if repo is None:
        return {"status": "NOT_CONFIGURED"}
    rc = run_command([
        str(repo / "bin/kx"), "check", str(work / "board.kicad_pcb"),
    ], work, "kiskill", 90)
    return {"status": "PASS" if rc == 0 else "FAIL", "exit_code": rc}


def execute_case(
    corpus: Path, lock: dict, case: dict, out: Path, native_cli: str,
    kiskill_repo: Path | None, python_with_pcbnew: str,
) -> dict:
    case_dir = out / case["id"]
    case_dir.mkdir(parents=True, exist_ok=False)
    inputs = case_dir / "original"
    hashes = materialize(corpus, lock, case, inputs)
    original = drc(inputs, native_cli=native_cli)
    kx = run_kiskill(inputs, kiskill_repo)
    expected_clean = case["metadata"]["ref_drv"] == 0
    observed_clean = (original.get("status") == "PROCESSED"
                      and original.get("error_count") == 0
                      and original.get("unconnected_count") == 0)
    baseline_matches = (expected_clean == observed_clean
                        and original.get("status") == "PROCESSED")
    result = {
        "id": case["id"],
        "stratum": case["stratum"],
        "source_repository": case["metadata"]["repo"],
        "source_commit": case["metadata"]["commit"],
        "file_hashes": hashes,
        "baseline": original,
        "original_corpus_error_count": case["metadata"]["ref_drv"],
        "source_class_matches": baseline_matches,
        "kiskill": kx,
        "sch_pcb_equivalence": "NOT_TESTABLE_NO_SCHEMATIC",
        "physical_test_performed": False,
    }
    if expected_clean:
        invalid = case_dir / "fault-injection"
        invalid.mkdir()
        for name in ("board.kicad_pro", "board.kicad_dru"):
            if name in case["files_sha256"]:
                shutil.copyfile(inputs / name, invalid / name)
        rc = run_command([
            python_with_pcbnew, str(HERE / "mutate.py"),
            str(inputs / "board.kicad_pcb"), str(invalid / "board.kicad_pcb"),
        ], invalid, "mutation", 60)
        try:
            mutation = json.loads((invalid / "mutation.stdout").read_text()) if rc == 0 else None
        except ValueError:
            mutation = None
        invalid_drc = drc(invalid, native_cli=native_cli) if mutation else {"status": "MUTATION_FAILED"}
        detected = (mutation is not None
                    and original.get("status") == "PROCESSED"
                    and invalid_drc.get("status") == "PROCESSED"
                    and invalid_drc.get("error_count", 0) > original.get("error_count", 0))
        result["fault_injection"] = {
            "strategy": mutation if mutation else "MUTATOR_FAILED",
            "native_drc": invalid_drc,
            "introduced_error_detected": detected,
            "fabrication_authorized": False,
        }
    result["digital_gate_pass"] = bool(
        baseline_matches and kx.get("status") == "PASS"
        and (not expected_clean or result["fault_injection"]["introduced_error_detected"])
    )
    (case_dir / "receipt.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def run(args) -> dict:
    lock = json.loads(args.lock.read_text())
    verify_lock(args.corpus_repo, lock)
    if args.out.exists():
        raise FileExistsError("output already exists; never reuse a previous result directory")
    if args.rounds not in (1, 2):
        raise ValueError("rounds must be 1 or 2")
    native = shutil.which(args.native_cli)
    if not native:
        raise FileNotFoundError("KiCad CLI not installed")
    kx_repo = args.kiskill_repo.resolve(strict=True) if args.kiskill_repo else None
    if kx_repo:
        pin = json.loads((ROOT / "projects/external-eda-pilot/engine-lock.json").read_text())
        # Reuse exactly the vetted upstream source commit, not a newly installed tool.
        print("Pinned external checker:", pinned_source(kx_repo, pin["kiskill"]["commit"])["commit"])
    args.out.mkdir(parents=True)
    digests, round_results = [], []
    for round_no in range(1, args.rounds + 1):
        round_dir = args.out / f"round-{round_no}"
        round_dir.mkdir()
        results = []
        for case in lock["cases"]:
            print("ROUND", round_no, "CASE", case["id"], flush=True)
            try:
                result = execute_case(args.corpus_repo, lock, case, round_dir,
                                      native, kx_repo, args.pcbnew_python)
            except Exception as exc:
                result = {
                    "id": case["id"],
                    "status": "CASE_EXECUTION_ERROR",
                    "error": str(exc),
                    "digital_gate_pass": False,
                }
            results.append(result)
        summary = {"cases": results}
        (round_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        digests.append(sha(canonical(summary).encode()))
        round_results.append(summary)
    identical = len(set(digests)) == 1 if args.rounds == 2 else None
    first = round_results[0]["cases"]
    aggregate = {
        "schema": "hs.heldout_pcb_benchmark.v1",
        "cohort_lock_sha256": sha(args.lock.read_bytes()),
        "corpus_commit": lock["corpus_commit"],
        "kicad_version": subprocess.check_output([native, "version"], text=True).strip(),
        "rounds": args.rounds,
        "cohort_case_count": len(first),
        "distinct_source_repositories": len(set(c["metadata"]["repo"] for c in lock["cases"])),
        "baseline_clean_confirmed": sum(r.get("source_class_matches", False) and r.get("baseline", {}).get("error_count") == 0 for r in first),
        "inherited_drc_confirmed": sum(r.get("source_class_matches", False) and r.get("baseline", {}).get("error_count", 0) > 0 for r in first),
        "structural_parser_pass": sum(r.get("kiskill", {}).get("status") == "PASS" for r in first),
        "fault_injections_rejected": sum(r.get("fault_injection", {}).get("introduced_error_detected", False) for r in first),
        "all_cases_pass_digital_gate": all(r.get("digital_gate_pass", False) for r in first),
        "round_semantic_sha256": digests,
        "same_semantic_result_across_fresh_rounds": identical,
        "schematic_parity": "NOT_TESTABLE_CORPUS_HAS_NO_SCHEMATIC",
        "physical_test_performed": False,
        "fabrication_authorized": False,
    }
    aggregate["benchmark_pass"] = (
        aggregate["all_cases_pass_digital_gate"]
        and identical is True
        and aggregate["cohort_case_count"] == 8
        and aggregate["fault_injections_rejected"] == 4
    )
    (args.out / "benchmark-result.json").write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n")
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return aggregate


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--corpus-repo", type=Path, required=True)
    p.add_argument("--lock", type=Path, default=HERE / "cases.lock.json")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--kiskill-repo", type=Path)
    p.add_argument("--pcbnew-python", default="/usr/bin/python3")
    p.add_argument("--native-cli", default="kicad-cli")
    p.add_argument("--rounds", type=int, default=2)
    args = p.parse_args()
    result = run(args)
    raise SystemExit(0 if result["benchmark_pass"] else 2)
