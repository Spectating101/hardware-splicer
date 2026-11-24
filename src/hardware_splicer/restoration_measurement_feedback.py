"""Append only time-bounded evidence to an already sealed HS diagnostic turn.

The previous response must verify against its exact input and prompt digests;
later creator *repair outcomes* are never fetched or loaded here. Captions
are unverified speech attributed to their stated time, not bench truth.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .restoration_caption_ingest import parse_early_vtt
from .restoration_reasoning_agent import build_messages, sha

PREDICTION_STATUSES = ("proposed_unverified_differential", "model_abstained")


def validate_predecessor(
    previous_context: Mapping[str, Any],
    previous_receipt: Mapping[str, Any],
) -> None:
    """Guard against a fabricated, edited or mismatched prediction chain."""
    digest = sha({
        k: v for k, v in previous_receipt.items()
        if k not in ("receipt_sha256", "elapsed_seconds")
    })
    if previous_receipt.get("receipt_sha256") != digest:
        raise ValueError("preceding receipt digest mismatch")
    for key in ("case_id", "source_url", "evidence_sha256",
                "preceding_receipt_sha256"):
        if previous_receipt.get(key) != previous_context.get(key):
            raise ValueError(f"preceding receipt/context {key} mismatch")
    if previous_receipt.get("prompt_sha256") != sha(build_messages(previous_context)):
        raise ValueError("preceding model prompt does not match source evidence")
    if previous_receipt.get("status") not in PREDICTION_STATUSES:
        raise ValueError("cannot advance from failed or unreviewed model output")
    if not isinstance(previous_receipt.get("plan"), dict):
        raise ValueError("prior valid plan missing")
    if previous_receipt.get("repair_authorized") is not False:
        raise ValueError("prior record improperly claims repair authorization")
    if previous_receipt.get("actual_video_frames_analyzed") is not False:
        raise ValueError("prior receipt claims unavailable video frame evidence")
    if previous_receipt.get("caption_provenance") != previous_context.get("caption_provenance"):
        raise ValueError("caption provenance changed after original prediction")


def extend_caption_context(
    previous_context: Mapping[str, Any], previous_receipt: Mapping[str, Any],
    *, vtt_path: Path, start_s: int, cutoff_s: int,
) -> dict[str, Any]:
    """Monotonic append of a real source's next caption segment.

    This function does not ask an LLM to invent new test observations.
    """
    validate_predecessor(previous_context, previous_receipt)
    provenance = previous_context.get("caption_provenance")
    if not isinstance(provenance, dict) or not provenance.get("raw_vtt_sha256"):
        raise ValueError("follow-up video segments require a source-verified first caption turn")
    windows = list(previous_context.get("source_windows") or [{
        "start_second": 0, "cutoff_second": provenance["cutoff_seconds"],
        "raw_vtt_sha256": provenance["raw_vtt_sha256"],
    }])
    if start_s != windows[-1]["cutoff_second"]:
        raise ValueError("caption windows must be contiguous and chronological")
    if start_s < 120 or cutoff_s > 600:
        raise ValueError("follow-up cannot alter original video stage or exceed source bound")
    parsed = parse_early_vtt(vtt_path, start_s=start_s, cutoff_s=cutoff_s)
    if parsed["raw_vtt_sha256"] != provenance["raw_vtt_sha256"]:
        raise ValueError("caption transcript changed between diagnostic stages")
    if not parsed["chunks"]:
        raise ValueError("new source window contains no evidence")
    updated = deepcopy(dict(previous_context))
    evidence = updated["evidence"]
    for ch in parsed["chunks"]:
        evidence.append({
            "id": f"E{len(evidence)+1}",
            "kind": "video_segment",
            "source": previous_context["source_url"],
            "text": (
                f"Auto-caption at {ch['start_second']}–{ch['end_second']}s "
                f"(unverified creator narration): {ch['auto_caption_excerpt']}"
            )[:800],
            "stage": f"followup_caption_{start_s}_{cutoff_s}",
        })
    updated["evidence_sha256"] = sha(evidence)
    updated["preceding_receipt_sha256"] = previous_receipt["receipt_sha256"]
    updated["prior_model_hypotheses"] = [
        str(h["mechanism"])[:200]
        for h in previous_receipt["plan"]["hypotheses"]
    ]
    windows.append({
        "start_second":start_s,
        "cutoff_second":cutoff_s,
        "raw_vtt_sha256":parsed["raw_vtt_sha256"],
        "caption_chunks":len(parsed["chunks"]),
    })
    updated["source_windows"] = windows
    updated["evidence_stage"] = f"video_caption_until_{cutoff_s}s"
    updated["repair_authorized"] = False
    return updated
