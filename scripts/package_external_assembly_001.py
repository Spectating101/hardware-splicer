#!/usr/bin/env python3
"""Publish a sourced complex model into HS React ONLY after visible native browser proof."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil

def digest(f):
    return hashlib.sha256(f.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--public",type=Path,required=True)
    p.add_argument("--hardware-license",type=Path,required=True)
    args=p.parse_args()
    src=args.source
    proof=json.loads((src/"BROWSER_PROOF.json").read_text())
    model=json.loads((src/"MODEL_INPUT.json").read_text())
    html=src/"dist/machine.html"
    receipt=json.loads((src/"SOURCE_RECEIPT.json").read_text())
    if not(all([
        proof.get("schema_version")=="hardware_splicer.external_assembly_browser_proof.v1",
        proof.get("actual_glb_nodes_mapped",0)>=500,
        proof.get("imported_components")==model.get("total_parts")==542,
        proof.get("full_model_visible") is True,
        proof.get("visible_cad_pixels",0)>=1500,
        proof.get("physical_motion_verified") is False,
        proof.get("geometry_authored_by_hs") is False,
        proof.get("no_browser_errors") is True,
        proof.get("no_network_requests") is True,
        proof.get("source_revision")==model.get("source_ref")==receipt.get("source_ref"),
        proof.get("html_sha256")==digest(html),
        receipt.get("raw_glb_sha256")==digest(src/"machine/machine.glb"),
        model.get("hardware_license")=="CERN-OHL-S-2.0",
        args.hardware_license.stat().st_size>10000
    ])):
        raise SystemExit("REFUSED: cannot publish an incomplete/misattributed CAD model")
    dest=args.public
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit("REFUSED: external reference would overwrite an existing asset")
    dest.mkdir(parents=True,exist_ok=True)
    shutil.copy2(html,dest/"machine.html")
    shutil.copy2(args.hardware_license,dest/"CERN-OHL-S-2.0-LICENSE.txt")
    (dest/"manifest.json").write_text(json.dumps(proof,sort_keys=True,indent=2)+"\n")
    (dest/"SOURCE_AND_MODIFICATIONS.md").write_text(
        "# External hardware CAD reference\n\n"
        "Original OpenArm hardware is owned by its respective rights holders and "
        "published under CERN-OHL-S-2.0. The derived follower GLB and original "
        "explosion metadata were retrieved from the pinned public GitHub source: "
        +model["source_repo"]+"/tree/"+model["source_ref"]+".\n\n"
        "Official hardware source: "+model["original_hardware_source"]+".\n\n"
        "HS did not design this hardware or physically test its motion. "
        "HS packaged this GLB into a custom interactive web stage; rendered material "
        "colors, orbit camera, component search, and visibility controls differ from "
        "the original CAD. All assembly explode vectors originate from metadata "
        "provided by the external publisher. This is not manufacturing or motion verification.\n"
    )
    print(json.dumps({"published":str(dest),"original_parts":model["total_parts"],
        "native_mapped":proof["actual_glb_nodes_mapped"],"html_sha256":digest(html)}))

if __name__=="__main__":
    main()
