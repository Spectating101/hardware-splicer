"""Structured module catalog context for model prompts.

Catalog visibility must not be semantically pre-decided by keyword scoring. Product
selection should be narrowed through typed capability requirements and deterministic
catalog queries, not by a hidden prose-ranking layer.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from ..pcb.module_registry import find_module, find_modules_by_capabilities


@lru_cache(maxsize=1)
def all_module_ids() -> tuple[str, ...]:
    from ..pcb.module_registry import _load_library

    return tuple(sorted(_load_library().keys()))


def build_salvage_catalog_context(*, max_entries: int = 200) -> str:
    """Stable catalog inventory for salvage/model prompts — id, label, capabilities."""
    lines: List[str] = []
    for module_id in all_module_ids()[:max_entries]:
        module = find_module(module_id) or {}
        label = str(module.get("label") or module_id)
        category = str(module.get("category") or "")
        tags = ", ".join(str(t) for t in (module.get("capabilityTags") or [])[:5])
        summary = str(module.get("summary") or "")[:120]
        lines.append(f"- {module_id}: {label} | {category} | {tags} | {summary}")
    return "\n".join(lines)


def catalog_context_for_goal(goal: str, *, max_entries: int = 200) -> str:
    """Compatibility name for a stable, goal-independent catalog view.

    ``goal`` is intentionally ignored. The previous implementation ranked modules by
    tokens in the user's prose and manually boosted motor/sensor families, meaning the
    model only saw a Python-curated semantic shortlist. Keeping this function stable
    and deterministic removes that hidden reasoning layer while avoiding a breaking
    import change. New semantic selection should prefer ``modules_for_capabilities``.
    """
    del goal
    return build_salvage_catalog_context(max_entries=max_entries)


def modules_for_capabilities(requires_any: List[List[str]], *, limit: int = 24) -> str:
    """Capability-filtered catalog slice from explicit typed requirements."""
    hits = find_modules_by_capabilities(requires_any)[:limit]
    return "\n".join(
        f"- {m.get('id')}: {m.get('label')} | {', '.join((m.get('capabilityTags') or [])[:4])}"
        for m in hits
    )
