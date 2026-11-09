"""Real HS engineering source graph as an auditable, outcome-free LLM aide.

No reverse engineered board schematics or fake manufacturer data. Every
claim comes from native video-caption evidence, with DECLARED source
authority, not OBSERVED, MEASURED or VERIFIED.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Mapping

from .engineering_source_graph import build_engineering_source_graph
from .restoration_reasoning_agent import sha

CAPTION_TIME = re.compile(r"(?P<start>\d+(?:\.\d+)?)\s*[–-]\s*(?P<end>\d+(?:\.\d+)?)s")


def source_ledger(context: Mapping[str, Any]) -> dict[str, Any]:
    """Register case evidence with actual HS engineering-source-graph runtime."""
    evidence = context["evidence"]
    if not evidence or sha(evidence) != context["evidence_sha256"]:
        raise ValueError("source evidence differs from signed native intake")
    provenance = context.get("caption_provenance")
    if not isinstance(provenance, dict) or not provenance.get("raw_vtt_sha256"):
        raise ValueError("graph A/B requires real first-window caption provenance")
    claims = []
    for e in evidence:
        e_id = str(e["id"])
        match = CAPTION_TIME.search(str(e["text"]))
        locator: dict[str, Any] = {"evidence_id": e_id, "source_stage": e.get("stage")}
        if match:
            locator.update({
                "timestamp_start": float(match["start"]),
                "timestamp_end": float(match["end"]),
            })
        claims.append({
            "claim_id": e_id,
            "subject_id": context["case_id"],
            "predicate": "reported_statement_" + e_id,
            "value": e["text"],
            "authority": "declared",
            "evidence_locator": locator,
            "metadata": {"origin": "auto_caption_or_video_title",
                         "inference_derived": False,
                         "independent_instrument_reading": False},
        })
    graph = build_engineering_source_graph([{
        "source_id": "video-" + context["case_id"],
        "source_type": "video",
        "uri": context["source_url"],
        "content_hash": "sha256:" + provenance["raw_vtt_sha256"],
        "authority_ceiling": "declared",
        "claims": claims,
    }], unresolved_source_ids=[
        "no_schematic_or_boardview_provided",
        "no_verified_meter_observations",
        "no_component_datasheet_provided",
    ])
    assert len(graph.claims) == len(evidence)
    assert graph.source_provenance_complete
    if any(c.authority.value != "declared" for c in graph.claims):
        raise ValueError("video narration was incorrectly upgraded to verified measurement")
    if set(c.claim_id for c in graph.claims) != set(e["id"] for e in evidence):
        raise ValueError("source graph lost evidence references")
    return {
        "hs_engineering_graph_schema": graph.schema_version,
        "graph_sha256": sha(graph.model_dump(mode="json")),
        "raw_source_sha256": provenance["raw_vtt_sha256"],
        "authority_ceiling": "declared",
        "source_graph_claim_count": len(graph.claims),
        "unresolved_source_ids": graph.unresolved_source_ids,
        "claims": [{
            "evidence_id": c.claim_id,
            "authority": c.authority.value,
            "timestamp_s": c.evidence_locator.get("timestamp_start"),
            "video_source": context["source_url"],
        } for c in graph.claims],
        "no_documentation_retrieved": True,
        "no_bench_measurements_by_HS": True,
        "claims_verified_by_HS": 0,
    }


def add_engineering_assistance(context: Mapping[str, Any]) -> dict[str, Any]:
    """Enrich actual same raw evidence; no new factual fault content."""
    updated = deepcopy(dict(context))
    ledger = source_ledger(updated)
    updated["hs_engineering_ledger"] = ledger
    if updated["evidence"] != context["evidence"] or updated["evidence_sha256"] != context["evidence_sha256"]:
        raise ValueError("engineering assistance cannot modify symptoms")
    return updated


def augmented_prompt(messages: list[dict[str,str]], ledger: Mapping[str,Any]) -> list[dict[str,str]]:
    """Source-graph assisted engineering instructions, same model and output schema."""
    system = (
        "HS ENGINEERING EVIDENCE MODE. The attached source ledger was built by "
        "hardware_splicer.engineering_source_graph, not invented by the model. "
        "All video statements have authority DECLARED: nobody here verified "
        "a circuit, schematic, or physical measurement. Do not assume one "
        "initial suspected fault is correct. Multiple simultaneous faults "
        "are possible. Prioritize the NEXT SAFE, EXTERNALLY ACCESSIBLE, "
        "NON-DESTRUCTIVE check that would best discriminate at least TWO "
        "plausible causes. Explicitly name what result would favor one "
        "mechanism over another in your test description. "
        "Do not recommend internal AC PSU access, bypass of safety interlocks, "
        "battery pack opening, or destructive repair. If missing genuine "
        "schematic or measured data make fault isolation impossible, "
        "state this uncertainty and choose the least risky observation. "
        "A model statement cannot upgrade source authority. "
        "Keep the ORIGINAL required JSON output schema. "
        "SOURCE_LEDGER_JSON=" + json.dumps(ledger,sort_keys=True)
    )
    return [
        {"role": "system", "content": messages[0]["content"] + "\n\n" + system},
        *messages[1:]
    ]
