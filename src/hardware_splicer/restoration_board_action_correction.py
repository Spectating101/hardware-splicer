"""One explicit source-preserving correction of unverified-board pin advice."""
from __future__ import annotations
from copy import deepcopy
from typing import Any, Callable, Mapping

from .restoration_board_action_gate import unsafe_pin_actions
from .restoration_reasoning_agent import agy_chat, build_messages, diagnose, sha

def correct_board_pin_action(
    context:Mapping[str,Any],old:Mapping[str,Any],*,
    inference:Callable[...,dict[str,Any]]=agy_chat,
    model:str="gemini-3.8-flash-low",timeout_s:int=75
)->dict[str,Any]:
    old_sha=sha({k:v for k,v in old.items() if k not in ("elapsed_seconds","receipt_sha256")})
    if old.get("receipt_sha256")!=old_sha:
        raise ValueError("original model receipt was altered after source experiment")
    if old.get("status")!="proposed_unverified_differential" or not isinstance(old.get("plan"),dict):
        raise ValueError("only sealed valid previous model plans may be corrected")
    if old.get("model_requested")!=model:
        raise ValueError("different models are not an authorized correction")
    if old.get("evidence_sha256")!=context.get("evidence_sha256"):
        raise ValueError("source symptoms changed between original and correction")
    if old.get("prompt_sha256")!=sha(build_messages(context)):
        raise ValueError("prior source-augmented model prompt was modified")
    reference=context.get("engineering_reference")
    if not reference or old.get("real_schematic_tool_result_sha256")!=sha(reference):
        raise ValueError("real KiCad evidence missing or altered")
    if reference.get("target_board_physically_verified") is not False:
        raise ValueError("this correction applies only to unverified physical boards")
    issues=unsafe_pin_actions(old["plan"],reference)
    if not issues:
        raise ValueError("no unverified physical pin action to correct; no reroll")
    follow=deepcopy(dict(context))
    follow["board_action_feedback"]={
        "parent_receipt_sha256":old_sha,
        "kind":"unverified_board_revision_pin_action",
        "violations":len(issues),
    }
    if follow["evidence"]!=context["evidence"] or follow["evidence_sha256"]!=context["evidence_sha256"]:
        raise ValueError("correction tried to introduce new device evidence")
    receipt=diagnose(follow,model=model,inference=inference,timeout_s=timeout_s)
    return {
        "schema":"hs.restoration.board_pin_action_quality_correction.v1",
        "original_receipt_sha256":old_sha,
        "source_evidence_sha256":context["evidence_sha256"],
        "real_kicad_reference_sha256":sha(reference),
        "original_unverified_pin_tests":issues,
        "one_correction_attempt_only":True,
        "source_evidence_unchanged":True,
        "target_board_physically_verified":False,
        "physical_test_or_repair_authorized":False,
        "correction":receipt,
    }
