"""Compatibility wrapper for model-backed module selection.

Historically this module carried its own favorite-part prompt (specific power modules,
MCUs, drivers and sensor recipes). It now delegates to the two-stage semantic module
pipeline: capability interpretation is blind to product IDs, deterministic catalog
queries resolve candidates, and the second model may select only from those candidates.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Mapping

from ..semantic_module_selector import SemanticSelectionError, semantic_module_selection_pipeline
from .qwen_text_client import qwen_configured

SCHEMA_VERSION = "hardware_splicer.qwen_module_pick.v2"


def qwen_module_pick_enabled() -> bool:
    if os.environ.get("HARDWARE_SPLICER_QWEN_MODULE_PICK", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False
    return qwen_configured()


def call_qwen_module_pick(
    goal: str,
    *,
    constraints: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return a zero-authority module proposal through the typed semantic pipeline."""
    if not qwen_module_pick_enabled():
        return {"ok": False, "skipped": True, "reason": "disabled_or_no_key"}

    # A model's JSON sometimes misses the schema once and fits it on the next call (1 of 13 briefs per DeepSeek run,
    # 26 Nov 2026); one retry for that case only. Selection rules (invented parts, wrong requirements) are not retried.
    for attempt in range(2):
        try:
            trace = semantic_module_selection_pipeline(goal, constraints=constraints)
            break
        except SemanticSelectionError as exc:
            if attempt == 0 and "validation error" in str(exc):
                continue
            return {
                "ok": False,
                "skipped": False,
                "error": "semantic_module_selection_failed",
                "message": str(exc),
            }

    selection = trace.selection
    if len(selection.selected_module_ids) < 2:
        return {
            "ok": False,
            "skipped": False,
            "error": "too_few_valid_modules",
            "module_ids": list(selection.selected_module_ids),
            "unresolved_questions": list(selection.unresolved_questions),
            "authority_effect": "none",
        }

    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "reasoning": selection.rationale,
        "module_ids": list(selection.selected_module_ids),
        "unresolved_questions": list(selection.unresolved_questions),
        "assumptions": list(selection.assumptions),
        "semantic_intent": trace.intent.model_dump(mode="json"),
        "semantic_candidate_set": trace.candidate_set.model_dump(mode="json"),
        "semantic_selection": selection.model_dump(mode="json"),
        "authority_effect": "none",
        "automatic_execution": False,
    }
