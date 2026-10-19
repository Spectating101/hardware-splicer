"""Evidence-bounded comparison of normalized mouse observations and a proposed adapter.

The trace is either a synthetic fixture or an unverified operator-supplied
capture. Neither mode is physical evidence, USB identity, or a safety verdict.
No files, machine input devices, networks or project records are touched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Literal

from .intact_reuse_adapter import Adapter

TRACE_SCHEMA = "hardware_splicer.mouse_observation_assessment.v1"
MAX_BYTES = 1_048_576
MAX_EVENTS = 10_002
ORIGINS = {"synthetic_fixture", "operator_supplied_unverified_host_capture"}


class ObservationAssessmentRefused(ValueError):
    pass


def _parse(trace: bytes) -> tuple[list[dict[str, str]], str]:
    if not isinstance(trace, bytes) or not trace or len(trace) > MAX_BYTES:
        raise ObservationAssessmentRefused("trace must be 1-1048576 bytes")
    try:
        lines = trace.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise ObservationAssessmentRefused("trace must be UTF-8 JSONL") from exc
    if len(lines) < 2 or len(lines) > MAX_EVENTS or any(not line.strip() for line in lines):
        raise ObservationAssessmentRefused("trace must have 2-10002 nonempty events")
    result = []
    for index, line in enumerate(lines):
        try:
            def unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                value: dict[str, Any] = {}
                for key, item in pairs:
                    if key in value:
                        raise ObservationAssessmentRefused(f"duplicate JSON field at event {index}")
                    value[key] = item
                return value

            value = json.loads(line, object_pairs_hook=unique_fields)
        except ObservationAssessmentRefused:
            raise
        except (json.JSONDecodeError, ValueError) as exc:
            raise ObservationAssessmentRefused(f"invalid JSONL event {index}") from exc
        if not isinstance(value, dict) or not isinstance(value.get("type"), str):
            raise ObservationAssessmentRefused(f"invalid normalized event {index}")
        kind = value["type"]
        if kind not in {"connected", "disconnected", "pressed", "released"}:
            raise ObservationAssessmentRefused(f"unexpected event kind at {index}")
        expected = {"type", "device"} | ({"button"} if kind in {"pressed", "released"} else set())
        if set(value) != expected:
            raise ObservationAssessmentRefused(f"wrong fields at event {index}")
        device = value.get("device")
        if not isinstance(device, str) or not 1 <= len(device) <= 64 or not all(
            c.isascii() and (c.isalnum() or c in "_-") for c in device
        ):
            raise ObservationAssessmentRefused(f"invalid alias at event {index}")
        if "button" in expected and value.get("button") != "left":
            raise ObservationAssessmentRefused(f"unexpected button at event {index}")
        result.append(value)
    if result[0]["type"] != "connected" or result[-1]["type"] != "disconnected":
        raise ObservationAssessmentRefused("capture must begin connected and end disconnected")
    alias = result[0]["device"]
    if any(item["device"] != alias for item in result):
        raise ObservationAssessmentRefused("capture mixes aliases; device identity not established")
    active = False
    count = 0
    for index, event in enumerate(result):
        kind = event["type"]
        if kind == "connected":
            if active or index != 0:
                raise ObservationAssessmentRefused("unexpected extra connection")
            active = True
        elif kind == "disconnected":
            if not active or index != len(result) - 1:
                raise ObservationAssessmentRefused("unexpected disconnection")
            active = False
        elif not active:
            raise ObservationAssessmentRefused("button event outside connection")
        else:
            count += 1
    if count > 10000:
        raise ObservationAssessmentRefused("button event budget exceeded")
    return result, alias


def assess_observation(
    trace: bytes,
    *,
    interface: dict[str, str],
    origin: Literal["synthetic_fixture", "operator_supplied_unverified_host_capture"],
    expected_actions: int,
    project_id: str,
    mission_id: str,
    candidate_id: str,
) -> dict[str, Any]:
    """Hash-bound, deterministic *software* evaluation; never promote physical evidence.

    expected_actions is a test assertion given by the operator/fixture, not a
    measurement of the real-world intended number of button activations.
    """
    if origin not in ORIGINS:
        raise ObservationAssessmentRefused("origin must disclose simulated or unverified operator input")
    if not isinstance(expected_actions, int) or isinstance(expected_actions, bool) or not 0 <= expected_actions <= 10000:
        raise ObservationAssessmentRefused("expected_actions must be a bounded integer")
    if not all(isinstance(v, str) and v and len(v) <= 64 for v in (project_id, mission_id, candidate_id)):
        raise ObservationAssessmentRefused("project, mission and candidate binding required")
    if not isinstance(interface, dict) or set(interface) != {"device_alias", "button", "action"}:
        raise ObservationAssessmentRefused("interface must specify device_alias, button and action")
    if not all(isinstance(x, str) and 0 < len(x) <= 64 for x in interface.values()):
        raise ObservationAssessmentRefused("invalid interface")
    if interface["button"] != "left":
        raise ObservationAssessmentRefused("this observer has only left-button coverage")
    events, observed_alias = _parse(trace)
    adapter = Adapter(**interface)
    actions = []
    for event in events:
        actions.extend(adapter.feed(event))
    alias_matches = observed_alias == interface["device_alias"]
    has_pressed = any(e["type"] == "pressed" for e in events)
    status = ("proposed_alias_mismatch" if not alias_matches else
              "insufficient_activation_evidence" if not has_pressed else
              "expected_action_mismatch" if len(actions) != expected_actions else
              "software_binding_matches_trace")
    return {
        "schema_version": TRACE_SCHEMA,
        "scope": "SOFTWARE_COMPARISON_ONLY",
        "origin": origin,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "source_authenticity_verified": False,
        "human_review_required": True,
        "project_id": project_id,
        "mission_id": mission_id,
        "candidate_id": candidate_id,
        "capture_sha256": hashlib.sha256(trace).hexdigest(),
        "capture_bytes": len(trace),
        "event_count": len(events),
        "observed_alias": observed_alias,
        "alias_semantics": "Operator-declared normalized alias, not a physical device identity.",
        "alias_is_verified_hardware_identity": False,
        "interface": dict(interface),
        "alias_matches": alias_matches,
        "expected_actions": expected_actions,
        "symbolic_actions": len(actions),
        "assessment": status,
        "next_action": ("Propose a software binding with the observed alias, but do not treat the alias as verified donor identity."
                        if not alias_matches else
                        "Keep actual donor identity, button mapping, electrical condition, mechanism travel and force blocked."),
        "open_physical_questions": [
            "Actual donor specimen identity and HID binding have not been independently established.",
            "Actual mechanical force, travel, stability, independent return and cable strain are unmeasured.",
            "An explicitly consenting person must inspect the specimen before any build or operation.",
        ],
    }


def assessment_bytes(report: dict[str, Any]) -> bytes:
    """Deterministic evidence artifact bytes for a registered declared source."""
    if report.get("schema_version") != TRACE_SCHEMA:
        raise ObservationAssessmentRefused("not an observation assessment")
    return (json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    """Assess an *existing* explicitly named capture file; never collect host input."""
    parser = argparse.ArgumentParser(description="Read-only software comparison of an existing normalized JSONL trace.")
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--device-alias", required=True, help="proposed adapter's logical alias")
    parser.add_argument("--button", default="left")
    parser.add_argument("--action", default="activate")
    parser.add_argument("--origin", choices=sorted(ORIGINS), default="synthetic_fixture")
    parser.add_argument("--expected-actions", type=int, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--output", type=Path, help="optional output report; no project mutation")
    args = parser.parse_args(argv)
    try:
        # A named existing file is not an instruction to capture a live device.
        if not args.trace.is_file() or args.trace.stat().st_size > MAX_BYTES:
            raise ObservationAssessmentRefused("trace must be an existing bounded regular file")
        report = assess_observation(
            args.trace.read_bytes(),
            interface={"device_alias": args.device_alias, "button": args.button, "action": args.action},
            origin=args.origin, expected_actions=args.expected_actions,
            project_id=args.project_id, mission_id=args.mission_id, candidate_id=args.candidate_id,
        )
        data = assessment_bytes(report)
        if args.output:
            args.output.write_bytes(data)
        sys.stdout.buffer.write(data)
    except (OSError, ObservationAssessmentRefused) as exc:
        print("observation comparison refused: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
