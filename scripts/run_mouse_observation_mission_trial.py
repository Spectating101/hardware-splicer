"""Exercise the canonical API: synthetic observation -> comparison -> new proposal -> blocked review.

No physical device access. Project-store writes stay in a temporary directory.
The only lasting output, if requested, is a scrubbed evidence-bound summary.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import secrets
import tempfile

from fastapi.testclient import TestClient

from hardware_splicer.mouse_observation_assessment import (
    assess_observation, assessment_bytes,
)
from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


PROJECT = "mouse-observation-software-trial"
AGENT = {"kind": "agent", "id": "observation-trial-agent"}
DONOR = "donor:unverified:usb-mouse"
TRACE = (
    b'{"type":"connected","device":"donor_mouse"}\n'
    b'{"type":"released","device":"donor_mouse","button":"left"}\n'
    b'{"type":"pressed","device":"donor_mouse","button":"left"}\n'
    b'{"type":"pressed","device":"donor_mouse","button":"left"}\n'
    b'{"type":"released","device":"donor_mouse","button":"left"}\n'
    b'{"type":"disconnected","device":"donor_mouse"}\n'
)


def require(response, status=200):
    if response.status_code != status:
        raise AssertionError(f"{response.request.method} {response.request.url.path}: status {response.status_code} {response.text[:500]}")
    return response.json()


def trial() -> dict:
    token = secrets.token_urlsafe(48)
    import os
    old = os.environ.get("HARDWARE_SPLICER_OPERATOR_TOKENS")
    os.environ["HARDWARE_SPLICER_OPERATOR_TOKENS"] = json.dumps({
        hash_operator_token(token): {"kind": "human", "id": "synthetic-trial-operator"}
    })
    try:
        with tempfile.TemporaryDirectory(prefix="hs-observation-trial-") as directory:
            store = ProjectStore(directory)
            store.save(PROJECT, {"name": "Synthetic trace only, no real USB device"}, expected_revision=0)
            client = TestClient(create_product_app(store))
            base = f"/v1/projects/{PROJECT}"
            # This trace is registered only as a 'declared' source, NOT a physical measurement.
            trace_ingest = require(client.post(base + "/sources/ingest-file", files={
                "file": ("synthetic-host-button-events.jsonl", TRACE, "application/jsonl"),
            }, data={"expected_revision": "1", "authority_ceiling": "declared"}), 201)
            trace_source = trace_ingest["ingestion"]["source_id"]
            opened = require(client.post(base + "/missions", json={
                "intake": {
                    "goal": "Explore an intact-mouse foot control based on an explicitly synthetic normalized trace",
                    "inventory": ["Unidentified ordinary USB mouse"],
                    "donors": [{"donor_id": DONOR, "label": "No physical specimen inspected", "optional": False}],
                    "budgets": {"max_candidates": 3, "max_operator_jobs": 3, "max_repairs_per_candidate": 1},
                },
                "author": AGENT,
            }), 201)["mission"]
            mid = opened["mission_id"]
            prefix = base + "/missions/" + mid
            require(client.post(prefix + "/accept", headers={"X-HS-Operator-Token": token}))

            spec_response = require(client.get(prefix + "/intact-reuse-spec"))
            initial = spec_response["example"]
            assert initial["source_ids"] == [trace_source]
            assert initial["donors_used"] == [DONOR]
            old_spec = copy.deepcopy(initial)
            old_spec["interface"]["device_alias"] = "wrong_mouse"
            # An HS offline replay passes for the proposed alias, but that does NOT
            # mean it matches the external normalized trace.
            old_assessment = assess_observation(TRACE, interface=old_spec["interface"],
                origin="synthetic_fixture", expected_actions=1,
                project_id=PROJECT, mission_id=mid, candidate_id="initial")
            assert old_assessment["assessment"] == "proposed_alias_mismatch"
            assert old_assessment["symbolic_actions"] == 0
            assessment_source = require(client.post(base + "/sources/ingest-file", files={
                "file": ("synthetic-observation-comparison.json", assessment_bytes(old_assessment), "application/json"),
            }, data={"expected_revision": "2", "authority_ceiling": "declared"}), 201)["ingestion"]["source_id"]
            # Source ingestion changes the project revision, so the admitted
            # source IDs are read again before candidates are submitted.
            old_spec["source_ids"] = [trace_source, assessment_source]
            corrected = copy.deepcopy(old_spec)
            corrected["interface"]["device_alias"] = old_assessment["observed_alias"]
            revised_assessment = assess_observation(TRACE, interface=corrected["interface"],
                origin="synthetic_fixture", expected_actions=1,
                project_id=PROJECT, mission_id=mid, candidate_id="revised")
            assert revised_assessment["assessment"] == "software_binding_matches_trace"
            assert revised_assessment["symbolic_actions"] == 1

            def propose(event):
                state = require(client.post(prefix + "/events", json={"event": event, "author": AGENT}), 201)["mission"]
                return state

            propose({"type": "candidate_proposed", "candidate": {
                "id": "initial", "kind": "reclaim_heavy", "label": "Initial alias proposal",
                "spec": old_spec, "rationale": "An agent assumption; not checked against the synthetic trace.",
            }})
            first = require(client.post(prefix + "/candidates/initial/run", json={"operation": "intact_reuse"}))
            assert first["evaluation"]["result"]["errors"] == 0  # internally clean, externally mismatched
            propose({"type": "candidate_proposed", "candidate": {
                "id": "revised", "kind": "reclaim_heavy", "label": "Trace-aligned software alias proposal",
                "spec": corrected,
                "rationale": "Uses a synthetic host-event alias only; actual donor HID identity and mechanical facts remain unknown.",
            }})
            second = require(client.post(prefix + "/candidates/revised/run", json={"operation": "intact_reuse"}))
            assert second["evaluation"]["result"]["errors"] == 0
            need_text = (
                "SYNTHETIC-ONLY normalized trace sha256:" + old_assessment["capture_sha256"] +
                " showed an alias mismatch against initial candidate; revised software alias matches the synthetic trace. "
                "Do not treat this as measured USB or physical donor evidence. Human must identify and inspect an actual "
                "nonhazardous specimen, observe actual host button mapping with explicit consent, and measure mechanical "
                "force/travel/return/stops/strain relief before considering a physical design."
            )
            pending = propose({"type": "evidence_required", "blocker": "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT",
                               "candidate_id": "revised", "need": need_text})
            need_seq = pending["last_event_seq"]
            finished = propose({"type": "terminal_proposed", "state": "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT",
                                "candidate_id": "revised", "reason": "Software-alias revision passed synthetic check; physical specimen unverified.",
                                "cites": [need_seq]})
            assert finished["terminal"]["state"] == "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT"
            assert finished["physical_correctness"] == "UNPROVEN"
            assert finished["power_on_authorized"] is False
            assert finished["firmware_authorized"] is False
            assert len(finished["candidates"]) == 2
            assert len(finished["needs"]) == 1 and finished["needs"][0]["need_state"] == "open"
            assert finished["budgets"]["operator_jobs_used"] == 2
            delivery = require(client.get(prefix + "/delivery"))["delivery"]
            assert delivery["prototype_package"]["status"] == "blocked"
            assert delivery["inspection_generated_artifacts"] is False
            assert len([f for f in delivery["recorded_files"] if f["kind"] == "software_review_bundle"]) == 2
            assert client.post(prefix + "/package").status_code == 409
            assert client.post(prefix + "/stage", json={"author": AGENT}).status_code == 409
            assert client.post(prefix + "/events", json={"author": AGENT, "event": {
                "type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD",
                "candidate_id": "revised", "reason": "Synthetic replay matched"}}).status_code == 409

            bundles = {}
            for name, check in [("initial", first), ("revised", second)]:
                path = check["bundle_download_path"]
                data = require_bundle(client.get(path))
                expected = client.get(prefix + "/" + check["evaluation"]["artifact"]).json()["run"]["package_sha256"]
                assert hashlib.sha256(data).hexdigest() == expected
                bundles[name] = expected

            return {
                "schema_version": "hardware_splicer.observation_trial_receipt.v1",
                "scope": "SYNTHETIC_SOFTWARE_ONLY",
                "physical_correctness": finished["physical_correctness"],
                "human_review_required": True,
                "human_acceptance_on_mission": True,
                "operator": "synthetic-trial-operator",
                "operator_identity_kind": "test-only token with declared human role; not user consent for physical capture",
                "physical_human_review_completed": False,
                "physical_review_status": "AWAITING_REAL_SPECIMEN_AND_EXPLICIT_CONSENT",
                "project_id": PROJECT, "mission_id": mid,
                "source_ids": {"synthetic_trace": trace_source, "synthetic_comparison": assessment_source},
                "synthetic_trace_sha256": hashlib.sha256(TRACE).hexdigest(),
                "initial_assessment": old_assessment,
                "revised_assessment": revised_assessment,
                "tested_candidates": [row["id"] for row in finished["candidates"]],
                "software_checks": [
                    {"candidate_id": r["id"], "operation": r["evaluations"][0]["operation"],
                     "errors": r["evaluations"][0]["result"]["errors"],
                     "warnings": r["evaluations"][0]["result"]["warnings"]}
                    for r in finished["candidates"]
                ],
                "review_bundle_sha256": bundles,
                "unresolved_evidence_need": {"seq": need_seq, "blocker": finished["needs"][0]["blocker"],
                                             "need": finished["needs"][0]["need"]},
                "mission_terminal": finished["terminal"]["state"],
                "review_result": "BLOCKED_WAITING_FOR_REAL_SPECIMEN",
                "power_on_authorized": finished["power_on_authorized"],
                "firmware_authorized": finished["firmware_authorized"],
                "retained_file_count": len(delivery["recorded_files"]),
                "prototype_package_status": delivery["prototype_package"]["status"],
                "no_physical_device_access": True,
            }
    finally:
        if old is None:
            os.environ.pop("HARDWARE_SPLICER_OPERATOR_TOKENS", None)
        else:
            os.environ["HARDWARE_SPLICER_OPERATOR_TOKENS"] = old


def require_bundle(response):
    assert response.status_code == 200, response.text[:300]
    assert response.headers.get("x-hs-artifact-scope") == "software-review-only"
    return response.content


def main():
    parser = argparse.ArgumentParser(description="No hardware: synthetic HS observation mission")
    parser.add_argument("--output", type=Path, default=None, help="optional JSON receipt output")
    args = parser.parse_args()
    result = trial()
    data = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data)
    print(data)


if __name__ == "__main__":
    main()
