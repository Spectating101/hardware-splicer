"""Public release projection of source-linked repair evidence.

The model consumes original unmodified creator captions; a PUBLIC
repository/report must not redistribute a multi-minute creator transcript.
After verifying the exact private model record, this projects it into
short editorially authored paraphrases plus original source digests.
Original model receipt hashes are not altered or recalculated.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any,Mapping

from .restoration_reasoning_agent import sha

WINDOW=re.compile(r"(?P<start>\d+(?:\.\d+)?)\s*[–-]\s*(?P<end>\d+(?:\.\d+)?)s")

def redact_for_public(
    private_record:Mapping[str,Any], manifest:Mapping[str,Any],
    public_summaries:Mapping[str,Any]
)->dict[str,Any]:
    if public_summaries.get("schema")!="hs.repair_investigator.public_source_summaries.v1":
        raise ValueError("editorial source paraphrases were not reviewed")
    if public_summaries.get("case_id")!=manifest["id"]:
        raise ValueError("human source summaries belong to another repair case")
    if public_summaries.get("source_video_sha256")!=manifest["video_auto_captions_sha256"]:
        raise ValueError("editorial paraphrases not tied to this exact video source")
    summaries=public_summaries.get("evidence")
    if not isinstance(summaries,dict) or not summaries:
        raise ValueError("no safe editorial source summaries provided")
    if sum(len(str(t).split()) for t in summaries.values())>200:
        raise ValueError("public report exceeds limited source paraphrase budget")
    result=deepcopy(dict(private_record))
    seen=set()
    for arm in ("plain","hs_circuit"):
        for row in result["results"][arm]:
            if "evidence" not in row:
                continue
            for item in row["evidence"]:
                key=item["id"]
                if key not in summaries:
                    raise ValueError("unreviewed source evidence cannot be published: "+key)
                text=str(summaries[key])
                if not 10<=len(text)<=220:
                    raise ValueError("editorial source summary missing or too extensive")
                original=item["text"]
                if original.lower().strip()==text.lower().strip():
                    raise ValueError("full original creator speech cannot be redistributed")
                item["original_source_excerpt_sha256"]=hashlib.sha256(original.encode("utf-8")).hexdigest()
                match=WINDOW.search(original)
                if match:
                    item["source_window_seconds"]=[float(match["start"]),float(match["end"])]
                item["text"]="Editorial paraphrase (NOT original transcript): "+text
                item["public_source_text_redacted"]=True
                seen.add(key)
    if set(summaries)!=seen:
        raise ValueError("public summary map includes unknown or missing evidence IDs")
    result["public_projection"]= {
        "schema":"hs.repair_investigator.copyright_safe_projection.v1",
        "original_source_evidence_is_redacted":True,
        "original_full_model_prompts_are_not_redistributed":True,
        "original_model_receipt_sha256_preserved":True,
        "independent_audit_requires_reobtaining_original_source":True,
        "source_summary_content_sha256":sha(public_summaries),
        "source_license_note":"KiCad source attributed CERN-OHL-1.2; caption evidence only summarized",
        "creator_outcomes_never_loaded":True,
    }
    return result
