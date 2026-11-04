#!/usr/bin/env python3
"""Source-pin existing OpenArm CAD as assets for upstream Teardown's runtime.

This is a packaging adapter. OpenArm and Teardown remain original upstream
software. HS only authors the sorting workcell-specific application layer.
"""
from __future__ import annotations
import argparse,hashlib,json,shutil,struct
from pathlib import Path

SOURCE_REF="0c0852bd76ee7026f97875d6eac789d189a0012a"
SOURCE_SHA="767baf3450d758da2cfc14173d669e1ad5e49407d40a2007c88bdaf6ea156e65"
VIEWER_REPO="https://github.com/Utsav92/openarm-3d-cad-assembly"
TEARDOWN_REF="a91262ac1109051e014662d42ecb0b7bc1f113b1"
TEARDOWN_REPO="https://github.com/elvarofficial/teardown"

def sha(path):
 h=hashlib.sha256()
 with open(path,"rb") as f:
  for part in iter(lambda:f.read(1<<20),b""):h.update(part)
 return h.hexdigest()

def build(glb:Path,metadata:Path,out:Path,root:Path)->dict:
 out=Path(out)
 if out.exists() and any(out.iterdir()):
  raise ValueError("Will not overwrite another product artifact")
 raw=Path(glb).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA:raise ValueError("OpenArm source revision/content mismatch")
 if raw[:4]!=b"glTF" or struct.unpack("<II",raw[4:12])!=(2,len(raw)):
  raise ValueError("invalid source glTF")
 info=json.loads(Path(metadata).read_text())
 parts=info.get("parts")
 if info.get("totalParts")!=542 or not isinstance(parts,list) or len(parts)!=542:
  raise ValueError("not 542 original CAD parts")
 ids=[p.get("node") for p in parts]
 if not all(isinstance(n,str) and n for n in ids) or len(set(ids))!=542:
  raise ValueError("invalid original OpenArm part identities")
 out.mkdir(parents=True,exist_ok=False)
 machine=out/"machine";machine.mkdir()
 sources={
   "main.js":root/"assets/teardown/hs_sort_workcell_main.js",
   "hs_product_studio.js":root/"assets/teardown/hs_product_studio.js",
   "robot.glb":Path(glb),"robot_metadata.json":Path(metadata),
 }
 checks={}
 for name,file in sources.items():
  shutil.copy2(file,machine/name)
  checks[name]={"sha256":sha(machine/name),"bytes":(machine/name).stat().st_size}
 (machine/"build.json").write_text(json.dumps({"external":{"robot.glb":"robot.glb"}})+"\n")
 receipt={
  "schema_version":"hardware_splicer.sortcell_source_receipt.v1",
  "product_id":"sortcell_s1_openarm",
  "source_cad":VIEWER_REPO,"source_cad_commit":SOURCE_REF,
  "openarm_component_count":542,
  "teardown_engine":TEARDOWN_REPO,"teardown_engine_commit":TEARDOWN_REF,
  "geometry_authored_by_hs":False,
  "task_animation_physical_kinematics_verified":False,
  "machine_vision_executed":False,
  "pick_and_place_physically_verified":False,
  "fabrication_authorized":False,
  "files":checks,
 }
 (out/"SOURCE_RECEIPT.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
 (out/"ATTRIBUTION.md").write_text(
  "# SORTCELL / S1 — reuse-first application prototype\n\n"
  f"Original OpenArm v1.1 542-part CAD, mesh metadata: {VIEWER_REPO}/tree/{SOURCE_REF}\n\n"
  f"Original Teardown engine: {TEARDOWN_REPO}/tree/{TEARDOWN_REF} (MIT)\n\n"
  "Original OpenArm CAD files are separately governed by the original hardware license; "
  "this package does not claim authorship of source CAD. "
  "HS adds a workcell stage and illustrative task animation only. "
  "It does not execute real computer vision, physically solved robotic IK, "
  "collision detection, motion calibration, or validated sorting hardware.\n")
 return receipt

if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--glb",type=Path,required=True)
 p.add_argument("--metadata",type=Path,required=True)
 p.add_argument("--out",type=Path,required=True)
 p.add_argument("--repo",type=Path,default=Path.cwd())
 a=p.parse_args()
 print(json.dumps(build(a.glb,a.metadata,a.out,a.repo),indent=2))
