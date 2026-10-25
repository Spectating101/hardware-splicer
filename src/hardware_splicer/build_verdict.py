"""A compact verdict for an agent: what a build found and what can be done about it.

A full build result is tens of kilobytes. An agent reads it through one tool call, so the full
result costs more than the conversation it serves. This projects what has already been computed:
nothing here is a new claim, and nothing is hidden. Everything it leaves out is still in the
artifacts under out_dir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping

SCHEMA_VERSION = "hardware_splicer.agent_verdict.v1"


def agent_verdict(result: Mapping[str, Any]) -> Dict[str, Any]:
    gate = dict(result.get("design_quality_gate") or {})
    summary = dict(gate.get("summary") or {})
    issues = [i for i in summary.get("electrical_issues") or [] if isinstance(i, Mapping)]
    fidelity = gate.get("request_fidelity")
    coverage = result.get("firmware_coverage")
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(result.get("ok")),
        "build_ready": bool(gate.get("build_ready")),
        "fabrication_ready": bool(gate.get("fabrication_ready")),
        "blockers": _blockers(gate, issues),
        # Findings with repair options: an exact wire patch each, and whether a person must act.
        "repairable_findings": list(gate.get("repairable_findings") or []),
        # What only a person can do or confirm; HS cannot see or verify these.
        "needs_a_person": _needs_a_person(issues),
        "request_fidelity": _pick(fidelity, ("status", "missing_parts", "unmapped_requests")),
        "firmware_coverage": _pick(coverage, ("status", "uncovered_pins")),
        "notes": [str(n) for n in summary.get("notes") or []],
        "physical_correctness": "UNPROVEN",
        "claim_boundary": "Software checks only. Nothing here shows the design works on real hardware.",
        "out_dir": _out_dir(result),
    }


_GENERIC_ELECTRICAL = "Electrical safety checks failed on the compiled build graph."


def _blockers(gate: Mapping[str, Any], issues: List[Mapping[str, Any]]) -> List[str]:
    """The gate's blockers, minus the generic electrical line when specific errors explain it.

    Left in, an agent read the generic line as a second, unexplained problem. The full gate keeps it,
    because records that read the gate expect it.
    """
    blockers = [str(b) for b in gate.get("blockers") or []]
    if any(i.get("level") == "error" and i.get("message") for i in issues):
        blockers = [b for b in blockers if b != _GENERIC_ELECTRICAL]
    return blockers


def _needs_a_person(issues: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {"node": i.get("node_id"), "code": i.get("code"), "message": str(i.get("message") or "")}
        for i in issues
        if i.get("requires_person")
    ]


def _pick(source: Any, keys: tuple[str, ...]) -> Dict[str, Any] | None:
    if not isinstance(source, Mapping):
        return None
    return {key: source[key] for key in keys if key in source}


def _out_dir(result: Mapping[str, Any]) -> str | None:
    if result.get("out_dir"):
        return str(result["out_dir"])
    for path in (result.get("artifacts") or {}).values():
        if path:
            return str(Path(str(path)).parent)
    return None
