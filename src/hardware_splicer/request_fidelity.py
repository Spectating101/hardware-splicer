"""Compare the parts a request listed with the parts in the compiled design.

The compiler can drop or merge a requested part (two servos compiled as one) and still
pass every board-level check, because those checks only look at what was drawn. This
check looks at the request. It is independent of the compiler and reports, never repairs.
"""

from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Dict, List, Mapping, Sequence

from .pcb.module_registry import find_module, list_canvas_modules

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

    missing = []
    for module_id, count in requested.items():
        if build_graph is None or in_design[module_id] >= count:
            continue
        unknown = find_module(module_id) is None
        missing.append(
            {
                "module_id": module_id,
                "names": names[module_id],
                "requested": count,
                "in_design": in_design[module_id],
                "unknown_module_id": unknown,
                "did_you_mean": suggest_module_ids(module_id) if unknown else [],
            }
        )
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


_WORD = re.compile(r"[a-z0-9]+")


def suggest_module_ids(guess: str, limit: int = 3) -> List[str]:
    """Known part ids a guessed id was probably meant to be; empty when nothing is plausible.

    A suggestion needs a distinctive word in common (a chip name, which contains a digit) or two words in
    common, or a near-identical spelling. Sharing only a generic word such as "module" or "rtc" is not
    enough: a wrong suggestion is worse than none.
    """
    guess_words = set(_WORD.findall(guess.lower()))
    scored = []
    for module in list_canvas_modules():
        module_id = str(module["id"])
        words = set(_WORD.findall(module_id.lower()))
        shared = guess_words & words
        distinctive = any(any(ch.isdigit() for ch in w) and len(w) >= 3 and not re.fullmatch(r"\d+v?", w) for w in shared)
        ratio = SequenceMatcher(None, guess.lower(), module_id.lower()).ratio()
        if distinctive or len(shared) >= 2 or ratio >= 0.8:
            scored.append((len(shared), ratio, module_id))
    return [module_id for _, _, module_id in sorted(scored, reverse=True)[:limit]]
