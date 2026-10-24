"""Compare the parts a request listed with the parts in the compiled design.

The compiler can drop or merge a requested part (two servos compiled as one) and still
pass every board-level check, because those checks only look at what was drawn. This
check looks at the request. It is independent of the compiler and reports, never repairs.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Mapping, Sequence

SCHEMA_VERSION = "hardware_splicer.request_fidelity.v1"
CLAIM_BOUNDARY = (
    "Compares the parts the request listed with the parts in the compiled design, by module and count. "
    "It does not check wiring, firmware or whether the design performs the requested function."
)


def assess_request_fidelity(
    requested_parts: Sequence[Mapping[str, Any]],
    build_graph: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    requested: Counter[str] = Counter()
    names: Dict[str, list[str]] = {}
    unmapped: list[str] = []
    for part in requested_parts:
        module_id = str(part.get("module_id") or "").strip()
        name = str(part.get("name") or module_id or "unnamed part")
        if not module_id:
            unmapped.append(name)
            continue
        requested[module_id] += 1
        names.setdefault(module_id, []).append(name)

    in_design: Counter[str] = Counter()
    if build_graph is not None:
        in_design.update(str(node.get("moduleId") or "") for node in build_graph.get("nodes") or [])

    missing = [
        {
            "module_id": module_id,
            "names": names[module_id],
            "requested": count,
            "in_design": in_design[module_id],
        }
        for module_id, count in requested.items()
        if in_design[module_id] < count
    ]
    unrequested = [
        {"module_id": module_id, "count": count}
        for module_id, count in in_design.items()
        if module_id and module_id not in requested
    ]

    if build_graph is None or not (requested or unmapped):
        status = "not_assessable"
    elif missing:
        status = "mismatch"
    elif unmapped:
        status = "not_assessable"
    else:
        status = "matches"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "missing_parts": missing,
        "unmapped_requests": unmapped,
        "unrequested_in_design": unrequested,
        "claim_boundary": CLAIM_BOUNDARY,
    }
