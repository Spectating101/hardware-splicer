#!/usr/bin/env python3
"""Integrate the original upstream OpenArm viewer unchanged, not a new renderer."""
from pathlib import Path
import argparse, hashlib, json, shutil, struct

REV="0c0852bd76ee7026f97875d6eac789d189a0012a"
URL="https://github.com/Utsav92/openarm-3d-cad-assembly"
FILES=("index.html","README.md","libs/tailwind.min.js","libs/three.min.js",
       "libs/OrbitControls.js","libs/GLTFLoader.js","libs/DRACOLoader.js",
       "models/metadata.js","models/follower_metadata.json",
       "models/leader_metadata.json","models/openarm_follower.glb",
       "models/openarm_leader.glb")
EXPECTED={
    "models/openarm_follower.glb":"767baf3450d758da2cfc14173d669e1ad5e49407d40a2007c88bdaf6ea156e65",
    "models/follower_metadata.json":"8785708507a17a0fea8023b5d2de3a16719c047907a57001eb37b6a085bcb58c",
}
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):h.update(block)
    return h.hexdigest()
def vendor(src,dst,proof=None):
    src,dst=Path(src),Path(dst)
    if dst.exists() and any(dst.iterdir()):raise ValueError("refusing overwrite")
    checks={}
    for name in FILES:
        file=src/name
        if not file.is_file() or not file.stat().st_size:raise ValueError("missing "+name)
        hash=sha(file)
        if name in EXPECTED and EXPECTED[name]!=hash:raise ValueError("source hash mismatch "+name)
        checks[name]={"sha256":hash,"bytes":file.stat().st_size}
        if name.endswith(".glb"):
            with file.open("rb") as f:header=f.read(12)
            if header[:4]!=b"glTF" or struct.unpack("<II",header[4:])!=(2,file.stat().st_size):
                raise ValueError("invalid original model "+name)
        if name.endswith("_metadata.json"):
            data=json.loads(file.read_text())
            if data.get("totalParts")!=len(data.get("parts",[])) or len(data["parts"])<500:
                raise ValueError("incomplete original model metadata")
    html=(src/"index.html").read_text()
    if not all(x in html for x in ("models/openarm_","libs/GLTFLoader.js",
                                  "switchArm('leader')","select-explode-scope")):
        raise ValueError("upstream application changed")
    if "MIT License" not in (src/"README.md").read_text():
        raise ValueError("original viewer license claim changed")
    license=src/"CERN-OHL-S-2.0-LICENSE.txt"
    if not license.is_file() or not license.read_text().startswith("CERN Open Hardware Licence Version 2"):
        raise ValueError("missing hardware license")
    if proof:
        evidence=json.loads(Path(proof).read_text())
        if not (evidence.get("upstream_viewer_rendered") is True and
                evidence.get("source_ref")==REV and
                evidence.get("both_source_models_load") is True and
                evidence.get("source_viewer_original") is True):
            raise ValueError("original source interface not verified in browser")
    for name in FILES:
        target=dst/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src/name,target)
        if sha(target)!=checks[name]["sha256"]:
            raise ValueError("unexpected modification of upstream "+name)
    shutil.copy2(license,dst/license.name)
    manifest={
       "schema_version":"hardware_splicer.upstream_viewer_adapter.v1",
       "viewer_origin":"upstream_unmodified",
       "source_viewer_original":True,"upstream_url":URL,"upstream_ref":REV,
       "follower_parts":542,"leader_parts":516,
       "geometry_authored_by_hs":False,"physical_motion_verified":False,
       "hardware_source":"https://github.com/enactic/openarm_hardware",
       "hardware_license":"CERN-OHL-S-2.0","source_files":checks,
    }
    (dst/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    (dst/"ATTRIBUTION.md").write_text(
       "# Original upstream CAD viewer, unchanged\n\n"
       f"Original interactive implementation: {URL}/tree/{REV}. "
       "The upstream README states MIT for the viewer. "
       "Original hardware: https://github.com/enactic/openarm_hardware, "
       "CERN-OHL-S-2.0, whose license is included alongside this manifest.\n\n"
       "HS merely packages the original model and interface as a pinned reference "
       "inside its own React application. It does not claim to have created any "
       "of the viewer controls or robot hardware, nor physically verified motion.\n")
    return manifest
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--destination",type=Path,required=True)
    p.add_argument("--proof",type=Path)
    a=p.parse_args()
    m=vendor(a.source,a.destination,a.proof)
    print(json.dumps({"upstream_ref":m["upstream_ref"],"copied_source_files":len(m["source_files"])}))
