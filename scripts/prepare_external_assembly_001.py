#!/usr/bin/env python3
"""Generic externally sourced, *real* complex assembly -> Teardown adapter.

Does not author parts, invent physical validation, or run arbitrary upstream code.
The imported GLB is a display asset linked to original public hardware/CAD sources.
Usage: python scripts/prepare_external_assembly_001.py --glb ... --metadata ...
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct

SCHEMA = "hardware_splicer.external_assembly_showcase.v1"
TOKEN = "__HS_EXTERNAL_MODEL_JSON__"

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def fail(msg):
    raise ValueError("external assembly refused: "+msg)

def prepare(glb: Path, metadata: Path, output: Path, *, source_repo: str,
            source_ref: str, hardware_source: str, hardware_license: str,
            min_parts: int=20) -> dict:
    glb=Path(glb); metadata=Path(metadata);output=Path(output)
    if output.exists() and any(output.iterdir()):
        fail("refusing to overwrite an existing output directory")
    raw=glb.read_bytes()
    if len(raw)<100000 or raw[:4]!=b"glTF" or struct.unpack_from("<II",raw,4)!=(2,len(raw)):
        fail("not a native binary glTF 2.0 model")
    original=metadata.read_bytes()
    source=json.loads(original)
    if not isinstance(source,dict) or not isinstance(source.get("parts"),list):
        fail("invalid parts metadata")
    parts=source["parts"]
    if len(parts)<min_parts or source.get("totalParts")!=len(parts):
        fail("source is not a documented complete multi-part assembly")
    node_ids=set(); good=[]
    for p in parts:
        if not isinstance(p,dict) or not all(isinstance(p.get(k),str) and p[k]
                                          for k in ["node","name","category","subassembly"]):
            fail("source part has no stable identity")
        if p["node"] in node_ids:
            fail("duplicate source native mesh node")
        node_ids.add(p["node"])
        for vector in ["explodeVec","center","extents"]:
            v=p.get(vector)
            if not isinstance(v,list) or len(v)!=3 or not all(
                isinstance(x,(int,float)) and not isinstance(x,bool) and
                math.isfinite(x) and abs(x)<100000 for x in v):
                fail("source part missing finite "+vector)
        if any(x<=0 for x in p["extents"]):
            fail("source part with invalid physical envelope")
        good.append({
            "id":p["node"], "name":p["name"], "category":p["category"],
            "subassembly":p["subassembly"],"joint":str(p.get("joint") or ""),
            "side":str(p.get("side") or ""), "extents_mm":p["extents"],
            "explode_vector":p["explodeVec"],
        })
    if not source_repo.startswith("https://github.com/") or len(source_ref)!=40 or not all(
        c in "0123456789abcdef" for c in source_ref.lower()):
        fail("upstream repository/ref must be exact GitHub source commit")
    if not hardware_source.startswith("https://github.com/") or not hardware_license:
        fail("source and license must be explicit")
    manifest={
        "schema_version":SCHEMA,
        "product_id":"openarm_v1_1_follower_external_reference",
        "title":"OpenArm · Full mechanical assembly",
        "source_repo":source_repo,"source_ref":source_ref,
        "original_hardware_source":hardware_source,
        "hardware_license":hardware_license,
        "display_geometry_sha256":sha(raw),
        "parts_metadata_sha256":sha(original),
        "total_parts":len(good),"parts":good,
        "model_source_kind":"external_cad_derived_glb",
        "hs_authored_original_cad":False,
        "hs_verified_vendor_geometry":False,
        "physical_release_authorized":False,
        "physical_motion_verified":False,
        "disassembly_motion_source":"upstream author-provided conceptual explode vectors",
    }
    machine=output/"machine"
    machine.mkdir(parents=True)
    source_js=Path(__file__).resolve().parents[1]/"assets/teardown/hs_external_assembly_main.js"
    template=source_js.read_text()
    if template.count(TOKEN)!=1:
        fail("viewer template source corrupted")
    (machine/"main.js").write_text(template.replace(TOKEN,json.dumps(
        manifest,sort_keys=True,separators=(",",":"),ensure_ascii=True).replace("</","<\\/")))
    shutil.copy2(glb,machine/"machine.glb")
    (output/"MODEL_INPUT.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
    receipt={
        "schema_version":"hardware_splicer.external_assembly_input_receipt.v1",
        "source_ref":source_ref,"source_url":source_repo,
        "raw_glb_sha256":sha(raw),"raw_metadata_sha256":sha(original),
        "parts_count":len(good),"authored_by_hs":False,
        "actual_native_teardown_rendered":False,"physical_release_authorized":False,
    }
    (output/"SOURCE_RECEIPT.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    return receipt

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glb",required=True,type=Path)
    parser.add_argument("--metadata",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--source-repo",required=True)
    parser.add_argument("--source-ref",required=True)
    parser.add_argument("--hardware-source",required=True)
    parser.add_argument("--hardware-license",required=True)
    parser.add_argument("--min-parts",type=int,default=20)
    args=parser.parse_args()
    try:
        print(json.dumps(prepare(args.glb,args.metadata,args.output,source_repo=args.source_repo,
            source_ref=args.source_ref,hardware_source=args.hardware_source,
            hardware_license=args.hardware_license,min_parts=args.min_parts),indent=2))
    except (OSError,ValueError,TypeError,KeyError) as exc:
        parser.exit(1,str(exc)+"\n")
