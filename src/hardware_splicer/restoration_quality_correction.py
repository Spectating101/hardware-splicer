"""One bounded source-preserving correction for unsupported numeric repair tests.

No creator outcomes; the previous real model receipt stays immutable.
One correction attempt only, never silent rerolling or physical action.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping

from .restoration_numeric_truth_gate import unsourced_thresholds
from .restoration_reasoning_agent import (
    agy_chat, build_messages, diagnose, sha
)

def correct_unsourced_thresholds(
    context: Mapping[str, Any], previous: Mapping[str, Any], *,
    inference: Callable[...,dict[str,Any]]=agy_chat,
    model: str="gemini-3.8-flash-low", timeout_s:int=60,
) -> dict[str, Any]:
    original=sha({k:v for k,v in previous.items()
                  if k not in ("receipt_sha256","elapsed_seconds")})
    if previous.get("receipt_sha256")!=original:
        raise ValueError("prior model prediction receipt was modified")
    if previous.get("status")!="proposed_unverified_differential" or not isinstance(previous.get("plan"),dict):
        raise ValueError("only a sealed original model diagnostic is eligible")
    if previous.get("evidence_sha256")!=context.get("evidence_sha256"):
        raise ValueError("signed source evidence does not match prior model result")
    if previous.get("prompt_sha256")!=sha(build_messages(context)):
        raise ValueError("previous prompt hash does not match unmodified case evidence")
    if previous.get("model_requested")!=model:
        raise ValueError("model changed between original and correction")
    if previous.get("hs_source_graph_sha256")!=context.get("hs_engineering_ledger",{}).get("graph_sha256"):
        raise ValueError("source graph changed between original and correction")
    issues=unsourced_thresholds(previous["plan"],context["hs_engineering_ledger"])
    if not issues:
        raise ValueError("previous response contains no unsupported numeric cutoffs; do not reroll")
    follow=deepcopy(dict(context))
    follow["quality_feedback"]={
        "parent_receipt_sha256":previous["receipt_sha256"],
        "kind":"unsupported_numeric_diagnostic_cutoff",
        "issue_count":len(issues),
    }
    if follow["evidence"]!=context["evidence"] or follow["evidence_sha256"]!=context["evidence_sha256"]:
        raise ValueError("quality repair attempted to change native source evidence")
    result=diagnose(follow,model=model,inference=inference,timeout_s=timeout_s)
    return {
        "schema":"hs.restoration.one_turn_quantitative_truth_correction.v1",
        "original_receipt_sha256":previous["receipt_sha256"],
        "source_evidence_sha256":context["evidence_sha256"],
        "graph_sha256":context["hs_engineering_ledger"]["graph_sha256"],
        "original_hypothesis_remains_unverified":True,
        "original_violations":issues,
        "correction_attempt_count":1,
        "source_evidence_unchanged":True,
        "physical_action_authorized":False,
        "correction":result,
    }
