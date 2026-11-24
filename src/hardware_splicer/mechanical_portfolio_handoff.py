"""Optional Cite–Refinery receiver for exact-revision HS and Policy Lab evidence.

The native Cite graph and Citation Engine run only when explicit checked roots
are supplied. This adapter has no write access to the long-running Atlas tenant.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import types
import importlib
from pathlib import Path
from typing import Any


class HandoffError(ValueError):
    pass


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    try:
        value=json.loads(path.read_bytes())
    except (OSError,ValueError) as err:
        raise HandoffError("Invalid or unavailable handoff JSON: "+str(path)) from err
    if not isinstance(value,dict):
        raise HandoffError("Handoff content must be an object")
    return value


def verify_inputs(evidence_file: Path, review_file: Path, source_file: Path, artifact_root: Path) -> dict:
    from .mechanical_fixture_handoff import EVIDENCE_SCHEMA
    e=_load(evidence_file)
    r=_load(review_file)
    if e.get("schema")!=EVIDENCE_SCHEMA or r.get("schema")!="policylab.mechanical_fixture_review.v1":
        raise HandoffError("Incompatible mechanical/policy schemas")
    if e.get("physical_authority_granted") is not False or r.get("physical_authority_granted") is not False:
        raise HandoffError("No physical authorization may be promoted")
    binding=r.get("source_binding",{})
    if binding.get("evidence_sha256")!=_hash(evidence_file) or binding.get("project_id")!=e.get("project_id") or binding.get("revision")!=e.get("revision"):
        raise HandoffError("Policy review is stale or belongs to another HS revision")
    if binding.get("original_source_sha256")!=_hash(source_file) or e.get("source",{}).get("sha256")!=_hash(source_file):
        raise HandoffError("Original reference source differs from both handoffs")
    if r.get("decision") not in {"BLOCKED","ADMIT_WITH_LIMIT"}:
        raise HandoffError("Unrecognized Policy Lab decision")
    if e.get("verification",{}).get("physical_status")!="UNVERIFIED":
        raise HandoffError("Mechanical evidence must retain physical unverified status")
    for name,meta in e.get("artifacts",{}).items():
        if "/" in name or "\\" in name or name.startswith("."):
            raise HandoffError("Artifact name is unsafe")
        file=artifact_root/name
        if not file.is_file() or file.is_symlink() or file.resolve().parent!=artifact_root.resolve():
            raise HandoffError("Artifact unavailable: "+name)
        if _hash(file)!=meta.get("sha256") or file.stat().st_size!=meta.get("bytes"):
            raise HandoffError("Artifact bytes do not match HS receipt: "+name)
    return {"evidence":e,"review":r,
            "digest":_hash(evidence_file),"policy_digest":_hash(review_file),
            "source_digest":_hash(source_file)}


def run(evidence_file: Path, review_file: Path, source_file: Path, cite_root: Path,
        citation_source: Path, out: Path, *, policy_root: Path | None = None) -> dict:
    if out.exists():
        raise HandoffError("Output directory already exists")
    v=verify_inputs(evidence_file,review_file,source_file,evidence_file.parent)
    if policy_root is not None:
        verifier=policy_root/"applications/mechanical-fixture-policy/run.mjs"
        result=subprocess.run(["node",str(verifier),"verify","--evidence",str(evidence_file),
                               "--review",str(review_file)],capture_output=True,text=True,timeout=30)
        if result.returncode!=0 or not json.loads(result.stdout).get("verified"):
            raise HandoffError("Native Policy Lab verification failed")
    sys.path.insert(0,str(cite_root/"src"))
    from cite_refinery.hosted_store import WorkspaceDB,StateConflict,_MemoryStore
    from cite_refinery.semantic import SemanticGraph
    # Execute the captured original evidence object implementation, not a fake serializer.
    pkg=types.ModuleType("citation_engine")
    pkg.__path__=[str(citation_source)]
    sys.modules["citation_engine"]=pkg
    models=importlib.import_module("citation_engine.models")
    serialization=importlib.import_module("citation_engine.serialization")
    ev=v["evidence"]
    review=v["review"]
    out.mkdir(parents=True,exist_ok=False)
    payload={"project":ev["project_id"],"revision":ev["revision"],
             "source_sha256":v["source_digest"],"engineering_sha256":v["digest"],
             "policy_review_sha256":v["policy_digest"],"mechanism":ev["strategy"]["selected"],
             "strategy_candidates":ev["strategy"]["alternatives"],
             "geometry":ev["verification"]["geometry"],"digital_checks_passed":ev["verification"]["digital_checks_passed"],
             "policy_decision":review["decision"],"unmet_targets":review["unmet_constraints"],
             "physical_status":"UNVERIFIED","physical_blockers":ev["verification"]["physical_blockers"]}
    artifact=models.Artifact("mechanical-project-"+ev["project_id"],"revision_bound_mechanical_decision",payload,
                            models.Provenance("original_source_and_HS_export","policy_lab_review",parent_refs=(
                                v["source_digest"],v["digest"],v["policy_digest"])))
    obj=serialization.serialize_object(artifact)
    if serialization.deserialize_object(obj).digest!=artifact.digest:
        raise HandoffError("Canonical evidence could not roundtrip")
    (out/"evidence-object.json").write_text(json.dumps(obj,indent=2)+"\n")
    database=out/"cite-isolated.sqlite3"
    db=WorkspaceDB(database)
    owner=db.create_tenant("isolated mechanical pilot","test operator")
    uid=owner["owner_user_id"]
    project=db.create_project(uid,owner["tenant_id"],"Mechanical evidence handoff","Source-bound digital engineering review")
    records=[
        ("source","Original manufacturer source: "+v["source_digest"],str(source_file)),
        ("strategy","Selected hole-safe strategy: "+ev["strategy"]["selected"],str(evidence_file)),
        ("design","Saved HS CAD artifacts with verified receipts: "+v["digest"],str(evidence_file)),
        ("policy","Policy Lab decision: "+review["decision"]+" "+v["policy_digest"],str(review_file)),
        ("report","Bounded revision decision: "+artifact.digest,str(out/"evidence-object.json"))
    ]
    packet={"schema":"cite_refinery.semantic_graph.v1","source_system":"hs_mechanical_portfolio_handoff_v1",
            "clusters":[{"key":"engineering","title":"Source-bound mechanical engineering"}],
            "nodes":[{"key":key,"statement":value,"kind":"fixture_artifact","layer":"neutral",
                      "clusters":["engineering"],"source_refs":[ref]} for key,value,ref in records],
            "edges":[{"source":a,"target":b,"relation":"DERIVED_OUTPUT","status":"qualified"}
                     for a,b in [("source","strategy"),("strategy","design"),("design","policy"),("policy","report")]]}
    before=db.project_state(uid,project)
    preview=db.preview(uid,project,packet)
    if before!=db.project_state(uid,project):
        raise HandoffError("Cite preview unexpectedly changed native state")
    job=db.enqueue(uid,project,packet,preview["project_revision"],preview["packet_digest"])
    db.run_one_job()
    if db.get_job(uid,job)["status"]!="succeeded":
        raise HandoffError("Cite native import failed")
    if not db.preview(uid,project,packet)["already_imported"]:
        raise HandoffError("Cite import is not repeat-safe")
    state=db.project_state(uid,project)
    ids={n["external_key"].split(":")[-1]:n["id"] for n in state["semantic_nodes"].values()}
    graph=SemanticGraph(_MemoryStore(state))
    trace=graph.trace_pattern(project,ids["source"],[{"relation":"DERIVED_OUTPUT","status":"qualified"}]*4)
    if not any(p["nodes"][-1]["id"]==ids["report"] for p in trace.get("completed_paths",[])):
        raise HandoffError("Cite cannot reconstruct source→report relation")
    findings=review["unmet_constraints"]
    dims=ev["verification"]["geometry"]
    limitations=[
        "CAD checks use nominal/assumed geometry, not a measured physical device",
        "Exact connector, antenna, board thickness, electrical contact and fabrication fit remain unverified",
        "This is an explicitly invoked isolated cross-project adapter, not an installed change watcher or automatic factory",
        "The original reference file is not included in the deliverable",
        "No observed labor savings, external operator, customer, sale or physical acceptance"
    ]
    report="\n".join([
        "% Mechanical design decision: "+ev["project_id"],
        "# Actual design and policy result","",
        "Source: "+ev["source"]["url"],
        "HS revision: "+str(ev["revision"]),
        "Selected strategy: **"+ev["strategy"]["selected"]+"**.",
        "Policy decision: **"+review["decision"]+"** (digital-only).","",
        "| Check | Digital result |","|---|---:|",
        "| Nominal board intersection | "+str(dims["nominal_board_collision_mm3"])+" mm³ |",
        "| Provisional USB corridor intersection | "+str(dims["usb_corridor_collision_mm3"])+" mm³ |",
        "| Nominal edge gap | "+str(dims["nominal_edge_gap_mm"])+" mm |",
        "| Base dimensions | "+str(dims["base_width_mm"])+" × "+str(dims["base_depth_mm"])+" mm |",
        "",
        "## Strategies rejected or held","",
        *[("- "+x["id"]+": "+x["reason"]) for x in ev["strategy"]["alternatives"] if not x["eligible"]],
        "",
        "## Current policy blockers","",
        *[("- "+x["id"]+": "+x["explanation"]) for x in findings],
        "",
        "## Physical limits","",
        *["- "+x for x in ev["verification"]["physical_blockers"]],
        "",
        "## Hash-bound evidence","",
        "- Original source SHA-256: "+v["source_digest"],
        "- HS evidence SHA-256: "+v["digest"],
        "- Policy review SHA-256: "+v["policy_digest"],
        "- Citation Engine object digest: "+artifact.digest,
        "",
        "This report preserves the source, alternative and review paths but does **not** authorize fabrication.",
    ])+"\n"
    (out/"decision.md").write_text(report)
    html=out/"decision.html"
    converted=subprocess.run(["pandoc","--standalone","--metadata","title=Mechanical decision",
                              str(out/"decision.md"),"-o",str(html)],capture_output=True,text=True,timeout=20)
    if converted.returncode!=0 or artifact.digest not in html.read_text():
        raise HandoffError("Report export missing canonical evidence digest")
    result={"schema":"hardware_splicer.portfolio_mechanical_handoff_result.v1",
            "source_sha256":v["source_digest"],"hs_sha256":v["digest"],"policy_sha256":v["policy_digest"],
            "canonical_evidence_digest":artifact.digest,
            "graph_trace_completed":True,
            "native_cite_import_succeeded":True,
            "native_policy_review_verified":policy_root is not None,
            "policy_decision":review["decision"],"physical_authority_granted":False,
            "artifacts":{name:{"sha256":_hash(out/name),"bytes":(out/name).stat().st_size}
                         for name in ("decision.md","decision.html","evidence-object.json")},
            "limitations":limitations}
    (out/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    return result
