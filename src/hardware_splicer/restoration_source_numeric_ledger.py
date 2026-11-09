"""Fail-closed source-backed numeric claims: reported readings != verified readings.

The record extractor DOES NOT convert narrative into measurements. It
validates human-extracted quantitative statements against actual immutable
source bytes (local caption WebVTT / page HTML) and inserts source-bound
DECLARED claims into HS's existing engineering_source_graph.

Physically verified target, calibration, or live instrument capture cannot
be asserted by this importer. Contradictory observations are never averaged.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from .engineering_source_graph import build_engineering_source_graph
from .restoration_caption_ingest import parse_early_vtt
from .restoration_reasoning_agent import sha

SCHEMA = "hs.restoration.source_numeric_claims.v1"
SUPPORTED = {
    ("video_caption", "creator_reported_reading"),
    ("repair_article", "published_reference_expectation"),
}
UNITS = {"voltage":"V","resistance":"ohm","current":"A"}
NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")


def _literal_number_anchored(anchor: str, value: float) -> bool:
    # A VTT source may spell zero as "zero volts"; other numeric
    # magnitudes must appear literally as decimal/integer tokens.
    if float(value) == 0 and re.search(r"\bzero\b",anchor,re.IGNORECASE):
        return True
    return any(abs(float(m.group(0))-float(value))<1e-9
               for m in NUMBER.finditer(anchor))


def _read_local(path: Path, expected_sha256: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("raw cited source missing or symlinked")
    if not re.fullmatch(r"[a-f0-9]{64}",expected_sha256):
        raise ValueError("source checksum malformed")
    if path.stat().st_size > 2_000_000:
        raise ValueError("raw source exceeds byte limit")
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:
        raise ValueError("raw external source digest mismatch")
    return raw


def _validate_one(source: Mapping[str,Any],claim: Mapping[str,Any],artifact:Path,raw:bytes)->dict[str,Any]:
    source_type=source["source_type"]
    claim_type=claim["claim_type"]
    if (source_type,claim_type) not in SUPPORTED:
        raise ValueError("cannot promote publisher recommendations into actual meter readings")
    if claim.get("device_board_verified") is not False:
        raise ValueError("source narration cannot independently verify device board identity")
    value=claim.get("value")
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError("numeric source claim missing a finite actual quantity")
    upper=claim.get("upper_value")
    if upper is not None and (isinstance(upper,bool) or not isinstance(upper,(int,float))
                             or not math.isfinite(upper) or upper<=value):
        raise ValueError("reference range upper bound malformed")
    quantity=str(claim.get("quantity"))
    unit=str(claim.get("unit"))
    if UNITS.get(quantity)!=unit:
        raise ValueError("source units ambiguous or unsupported")
    if not isinstance(claim.get("condition_id"),str) or not re.fullmatch(r"[a-z0-9_]{8,85}",claim["condition_id"]):
        raise ValueError("reading condition identifier missing")
    if not isinstance(claim.get("condition_description"),str) or len(claim["condition_description"])<25:
        raise ValueError("measurement configuration or load condition missing")
    anchor=str(claim.get("anchor",""))
    if not 6 <= len(anchor) <= 140 or not _literal_number_anchored(anchor,float(value)):
        raise ValueError("numeric value has no matching source passage")
    if upper is not None and not _literal_number_anchored(anchor,float(upper)):
        raise ValueError("reference upper bound has no source-number anchor")
    if source_type=="video_caption":
        start,end=claim.get("window_start_s"),claim.get("window_end_s")
        if not isinstance(start,int) or not isinstance(end,int) or end<=start or end>600:
            raise ValueError("video source claim must have bounded timestamps")
        source_view=parse_early_vtt(artifact,start_s=start,cutoff_s=end,
                                    max_chunks=12,chars_per_chunk=1500)
        body=" ".join(x["auto_caption_excerpt"] for x in source_view["chunks"])
        if source_view["raw_vtt_sha256"]!=source["artifact_sha256"]:
            raise ValueError("caption parser source digest mismatch")
        locator={"start_second":start,"end_second":end,"caption_auto_generated":True}
        if claim_type!="creator_reported_reading":
            raise ValueError("video narration cannot be a manufacturer spec")
    else:
        if claim.get("window_start_s") is not None or claim.get("window_end_s") is not None:
            raise ValueError("web repair guide is not a timestamped instrument feed")
        body=raw.decode("utf-8-sig","replace")
        locator={"url":source["url"],"section":"published repair instructions"}
        if not any(token in anchor.lower() for token in ("expect","at least","below","above","should")):
            raise ValueError("published numerical statement lacks expectation wording")
    if " ".join(anchor.lower().split()) not in " ".join(body.lower().split()):
        raise ValueError("quantitative passage not present at claimed source and time")
    allowed=set(("id","claim_type","quantity","value","upper_value","unit",
                 "anchor","window_start_s","window_end_s","condition_id",
                 "condition_description","device_board_verified"))
    if set(claim)-allowed:
        raise ValueError("unrecognized claim fields may contain untrusted authority metadata")
    return {
        "claim_id":claim["id"],
        "case_id":source["case_id"],
        "source_type":source_type,
        "source_url":source["url"],
        "source_sha256":source["artifact_sha256"],
        "claim_type":claim_type,
        "quantity":quantity,
        "value":value,
        "upper_value":upper,
        "unit":unit,
        "source_anchor":anchor,
        "source_locator":locator,
        "condition_id":claim["condition_id"],
        "condition_description":claim["condition_description"],
        "authority":"declared",
        "measured_by_HS":False,
        "target_board_physically_verified":False,
        "calibrated_instrument_data_present":False,
        "manufacturer_specification_verified":False,
        "independent_bench_truth":False,
    }


def register_source_numeric_claims(
    input_data: Mapping[str,Any], *,
    local_artifacts: Mapping[str,Path]
)->dict[str,Any]:
    if input_data.get("schema")!=SCHEMA or not isinstance(input_data.get("sources"),list):
        raise ValueError("unrecognized raw-claim dossier")
    sources=input_data["sources"]
    if not sources:
        raise ValueError("empty quantitative evidence dossier")
    claims:list[dict[str,Any]]=[]
    graph_sources=[]
    for source in sources:
        if set(source)!={"id","case_id","source_type","url","artifact_sha256",
                          "raw_artifact_provenance","claims"}:
            raise ValueError("unexpected source-level authority or undeclared metadata")
        sid=source["id"]
        if source["source_type"] not in ("video_caption","repair_article"):
            raise ValueError("unsupported source kind")
        if not isinstance(sid,str) or not re.fullmatch(r"[a-z0-9_]{6,80}",sid):
            raise ValueError("source ID unsafe")
        if not str(source["url"]).startswith("https://"):
            raise ValueError("must use an attributed HTTPS public source")
        if sid not in local_artifacts:
            raise ValueError("no original raw source bytes supplied: "+sid)
        srcpath=local_artifacts[sid]
        raw=_read_local(srcpath,source["artifact_sha256"])
        derived=[_validate_one(source,c,srcpath,raw) for c in source["claims"]]
        if not derived:
            raise ValueError("source has no attributable numerical claims")
        claims.extend(derived)
        graph_sources.append({
            "source_id":sid,
            "source_type":"video" if source["source_type"]=="video_caption" else "service_note",
            "uri":source["url"],
            "content_hash":"sha256:"+source["artifact_sha256"],
            "authority_ceiling":"declared",
            "claims":[{
                "claim_id":record["claim_id"],
                "subject_id":f'{record["case_id"]}@{record["condition_id"]}',
                "predicate":(
                    f'published_reference_range_{record["quantity"]}'
                    if record["claim_type"]=="published_reference_expectation" and record["upper_value"] is not None
                    else f'published_reference_minimum_{record["quantity"]}'
                    if record["claim_type"]=="published_reference_expectation" and "at least" in record["source_anchor"].lower()
                    else f'published_reference_failure_below_{record["quantity"]}'
                    if record["claim_type"]=="published_reference_expectation" and "below" in record["source_anchor"].lower()
                    else f'{record["claim_type"]}_{record["quantity"]}'
                ),
                "value":{
                    "value":record["value"],
                    "upper_value":record["upper_value"],
                    "unit":record["unit"],
                    "condition":record["condition_description"],
                },
                "units":record["unit"],
                "authority":"declared",
                "evidence_locator":record["source_locator"],
                "metadata":{
                    "device_board_verified":False,
                    "physically_measured_by_HS":False,
                    "is_manufacturer_spec":False,
                    "claim_type":record["claim_type"],
                },
            } for record in derived],
        })
    ids=[x["claim_id"] for x in claims]
    if len(ids)!=len(set(ids)):
        raise ValueError("duplicated source numeric claim IDs")
    if len(set(x["id"] for x in sources))!=len(sources):
        raise ValueError("duplicated source IDs")
    graph=build_engineering_source_graph(
        graph_sources,
        unresolved_source_ids=[
            "no_independent_bench_measurement_or_instrument_log",
            "board_revision_not_physically_authenticated",
            "published_repair_thresholds_are_not_manufacturer_specifications",
            "no_schematic_to_target_photo_registration",
        ],
    )
    if any(c.authority.value!="declared" for c in graph.claims):
        raise ValueError("source claim promoted to independently measured/verified")
    if set(ids)!={x.claim_id for x in graph.claims}:
        raise ValueError("HS engineering source graph lost a numeric claim")
    conditions={}
    for c in claims:
        key=(c["case_id"],c["quantity"],c["unit"],c["condition_id"],c["claim_type"])
        conditions.setdefault(key,[]).append(c)
    # Values in DIFFERENT load/connection contexts are not contradictory.
    conflicts=[]
    for key,group in conditions.items():
        if key[-1]!="creator_reported_reading":
            continue
        values={x["value"] for x in group}
        if len(values)>1:
            conflicts.append({
                "case_id":key[0],"condition_id":key[3],
                "claim_ids":[x["claim_id"] for x in group],
                "disposition":"unresolved_conflicting_creator_reports",
            })
    return {
        "schema":"hs.restoration.source_numeric_evidence_ledger.v1",
        "source_manifest_sha256":sha(input_data),
        "native_HS_source_graph_sha256":sha(graph.model_dump(mode="json")),
        "native_HS_source_graph_schema":graph.schema_version,
        "source_count":len(sources),"claim_count":len(claims),
        "claims":claims,
        "conflicts":conflicts,
        "conditions_are_distinct":True,
        "source_authority_ceiling":"declared",
        "measurements_physically_taken_by_HS":False,
        "board_identity_independently_verified":False,
        "independent_verified_numeric_thresholds":False,
        "repair_authorized":False,
    }
