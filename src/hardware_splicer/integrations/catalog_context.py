"""Structured module catalog text for LLM prompts (not regex matching)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List

from ..pcb.module_registry import find_module, find_modules_by_capabilities


@lru_cache(maxsize=1)
def all_module_ids() -> tuple[str, ...]:
    from ..pcb.module_registry import _load_library

    return tuple(sorted(_load_library().keys()))


def build_salvage_catalog_context(*, max_entries: int = 160) -> str:
    """Compact catalog for salvage mapping prompts — id, label, capabilities."""
    lines: List[str] = []
    for module_id in all_module_ids()[:max_entries]:
        module = find_module(module_id) or {}
        label = str(module.get("label") or module_id)
        category = str(module.get("category") or "")
        tags = ", ".join(str(t) for t in (module.get("capabilityTags") or [])[:5])
        summary = str(module.get("summary") or "")[:120]
        lines.append(f"- {module_id}: {label} | {category} | {tags} | {summary}")
    return "\n".join(lines)


def catalog_context_for_goal(goal: str, *, max_entries: int = 80) -> str:
    """Smaller catalog slice ranked by goal keywords (still validated against full library)."""
    from ..pcb.module_registry import _load_library

    library = _load_library()
    goal_l = goal.lower()
    scored: List[tuple[int, str, Dict[str, Any]]] = []
    for module_id, module in library.items():
        text = " ".join(
            [
                module_id,
                str(module.get("label") or ""),
                str(module.get("category") or ""),
                " ".join(str(t) for t in (module.get("capabilityTags") or [])),
                str(module.get("summary") or ""),
            ]
        ).lower()
        score = sum(1 for token in goal_l.split() if len(token) > 3 and token in text)
        if any(k in goal_l for k in ("motor", "rover", "wheel", "drive")) and "motor" in text:
            score += 3
        if any(k in goal_l for k in ("sensor", "temp", "water", "soil", "plant")) and "sensor" in text:
            score += 3
        scored.append((score, module_id, module))

    scored.sort(key=lambda row: (-row[0], row[1]))
    picked = scored[:max_entries]
    if len(picked) < 40:
        picked = [(0, mid, library[mid]) for mid in sorted(library.keys())[:max_entries]]

    lines: List[str] = []
    for _score, module_id, module in picked:
        label = str(module.get("label") or module_id)
        tags = ", ".join(str(t) for t in (module.get("capabilityTags") or [])[:5])
        lines.append(f"- {module_id}: {label} | {tags}")
    return "\n".join(lines)


def modules_for_capabilities(requires_any: List[List[str]], *, limit: int = 24) -> str:
    """Capability-filtered catalog slice."""
    hits = find_modules_by_capabilities(requires_any)[:limit]
    return "\n".join(
        f"- {m.get('id')}: {m.get('label')} | {', '.join((m.get('capabilityTags') or [])[:4])}"
        for m in hits
    )
