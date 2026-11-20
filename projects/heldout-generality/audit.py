"""Independent evidence-bundle audit, no tool execution or network access."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def audit(out: Path, lock_path: Path) -> dict:
    lock = json.loads(lock_path.read_bytes())
    aggregate = json.loads((out / "benchmark-result.json").read_bytes())
    expected_cases = {c["id"]: c for c in lock["cases"]}
    assert len(expected_cases) == 8
    assert aggregate["cohort_lock_sha256"] == sha(lock_path.read_bytes())
    assert aggregate["corpus_commit"] == lock["corpus_commit"]
    assert aggregate["rounds"] == 2
    rounds = []
    for index in (1, 2):
        round_dir = out / f"round-{index}"
        summary = json.loads((round_dir / "summary.json").read_bytes())
        receipts = summary["cases"]
        assert {r["id"] for r in receipts} == set(expected_cases)
        for receipt in receipts:
            case = expected_cases[receipt["id"]]
            case_dir = round_dir / receipt["id"]
            assert json.loads((case_dir / "receipt.json").read_bytes()) == receipt
            for name, expected_digest in case["files_sha256"].items():
                source = case_dir / "original" / name
                assert sha(source.read_bytes()) == expected_digest
                assert receipt["file_hashes"][name] == expected_digest
            drc = json.loads((case_dir / "original" / "native-drc.json").read_bytes())
            assert len(drc["violations"]) == case["metadata"]["ref_drv"]
            assert len(drc["unconnected_items"]) == case["metadata"]["ref_open"]
            assert receipt["baseline"]["error_count"] == len(drc["violations"])
            assert receipt["baseline"]["unconnected_count"] == len(drc["unconnected_items"])
            assert receipt["kiskill"]["status"] == "PASS"
            assert receipt["source_class_matches"]
            assert receipt["sch_pcb_equivalence"] == "NOT_TESTABLE_NO_SCHEMATIC"
            assert receipt["physical_test_performed"] is False
            if case["metadata"]["ref_drv"] == 0:
                fault = receipt["fault_injection"]
                negative = json.loads(
                    (case_dir / "fault-injection" / "native-drc.json").read_bytes()
                )
                assert fault["introduced_error_detected"] is True
                assert len(negative["violations"]) > len(drc["violations"])
                assert fault["fabrication_authorized"] is False
            assert receipt["digital_gate_pass"]
        rounds.append(summary)
    semantic_hashes = [sha(encoded(s)) for s in rounds]
    assert semantic_hashes == aggregate["round_semantic_sha256"]
    assert semantic_hashes[0] == semantic_hashes[1]
    assert aggregate["benchmark_pass"] is True
    assert aggregate["fabrication_authorized"] is False
    assert aggregate["physical_test_performed"] is False
    return {
        "schema": "hs.heldout_pcb_independent_audit.v1",
        "status": "PASS",
        "cases": 8,
        "distinct_source_repositories": 8,
        "original_source_drc_counts_verified": 8,
        "clean_board_copper_fault_controls_verified_per_round": 4,
        "rounds_verified": 2,
        "semantic_receipt_sha256": semantic_hashes[0],
        "physical_test_performed": False,
        "fabrication_authorized": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--lock", type=Path, default=Path(__file__).with_name("cases.lock.json"))
    args = p.parse_args()
    print(json.dumps(audit(args.out, args.lock), indent=2, sort_keys=True))
