"""PCB source mutation: four original M2.5 clearance bores -> M3 review candidate.
Never silently changes net/copper or grants fabrication authority.
"""
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess
from collections import Counter
from pathlib import Path
import pcbnew
from functional_edit import outline,original_items,mm

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def execute(original_dir:Path, out:Path, new_dia:float=3.2):
    original=original_dir/"board.kicad_pcb"
    if not 3.0<=new_dia<=3.3:raise ValueError("M3 clearance only, 3.0–3.3mm")
    orig=pcbnew.LoadBoard(str(original))
    bounds=outline(orig)
    oldpads,oldtracks=original_items(orig)
    mount=[]
    for fp in orig.GetFootprints():
        if not fp.GetFPIDAsString().startswith("MountingHole:"):continue
        pads=list(fp.Pads())
        if len(pads)!=1:raise ValueError("MOUNT_UNKNOWN_PAD_COUNT")
        p=pads[0]
        d=mm(p.GetDrillSize().x)
        if abs(d-mm(p.GetDrillSize().y))>.01 or p.GetNetCode()>0:
            raise ValueError("MOUNT_NOT_ROUND_NONPLATED")
        mount.append((fp.GetReference(),mm(p.GetPosition().x),mm(p.GetPosition().y),d))
    mount=sorted(mount)
    if len(mount)!=4 or any(abs(m[3]-2.7)>.01 for m in mount):
        raise ValueError("UNSUPPORTED_MOUNT_PATTERN:four source 2.7mm NPTHs required")
    out.mkdir(parents=True,exist_ok=False)
    for name in ("board.kicad_pro","board.kicad_dru"):
        if (original_dir/name).exists():shutil.copyfile(original_dir/name,out/name)
    for fp in orig.GetFootprints():
        if fp.GetReference() in {m[0] for m in mount}:
            p=list(fp.Pads())[0]
            p.SetDrillSize(pcbnew.VECTOR2I(pcbnew.FromMM(new_dia),pcbnew.FromMM(new_dia)))
            # Original footprint-library identity is deliberately retained,
            # and must be revised before any actual fabrication release.
    edited=out/"board.kicad_pcb"
    pcbnew.SaveBoard(str(edited),orig)
    check=pcbnew.LoadBoard(str(edited))
    revised_pads,revised_tracks=original_items(check)
    if oldpads!=revised_pads or oldtracks!=revised_tracks:
        raise ValueError("ORIGINAL_PAD_NETS_OR_COPPER_ALTERED")
    seen=[]
    for fp in check.GetFootprints():
        if fp.GetReference() in {m[0] for m in mount}:
            pad=list(fp.Pads())[0]
            seen.append((fp.GetReference(),mm(pad.GetPosition().x),mm(pad.GetPosition().y),
                         mm(pad.GetDrillSize().x)))
    if len(seen)!=4 or any(abs(m[3]-new_dia)>.0001 for m in seen):
        raise ValueError("M3_DRILL_MODIFICATION_NOT_RETAINED")
    rc=subprocess.run(
        ["kicad-cli","pcb","drc","--format","json","--severity-all","--exit-code-violations",
         "-o",str(out/"all-severities.json"),str(edited)],cwd=out,
        capture_output=True,check=False,timeout=90)
    d=json.loads((out/"all-severities.json").read_text())
    errors=[v for v in d["violations"] if v.get("severity")=="error"]
    warnings=[v for v in d["violations"] if v.get("severity")=="warning"]
    if errors or d["unconnected_items"]:
        raise ValueError("REVISED_DRC_ERRORS:"+str(Counter(x["type"] for x in errors)))
    # The KiCad CLI uses exit 5 even for warnings with --severity-all.
    record={
        "schema":"hs.heldout_mechanical_edit.v1",
        "edit_kind":"ALL_FOUR_MOUNTING_DRILLS_M2.5_TO_M3_CANDIDATE",
        "source_sha256":sha(original),"edited_sha256":sha(edited),
        "original_copper_count":len(oldtracks),"revised_copper_count":len(revised_tracks),
        "original_pad_count":len(oldpads),"revised_pad_count":len(revised_pads),
        "outline":bounds,
        "original_holes":[{"ref":r,"x":x,"y":y,"drill":dia} for r,x,y,dia in mount],
        "revised_holes":[{"ref":r,"x":x,"y":y,"drill":dia} for r,x,y,dia in sorted(seen)],
        "native_drc_error_count":len(errors),"native_drc_unconnected":len(d["unconnected_items"]),
        "native_drc_warning_count":len(warnings),
        "native_drc_warning_types":dict(sorted(Counter(v["type"] for v in warnings).items())),
        "footprint_library_mismatch":"REVIEW_HOLD:old M2.5 library identity retained while pad bore revised",
        "mechanical_fastener_head_and_keepouts":"UNVERIFIED",
        "physical_fit":"UNVERIFIED","fabrication_authorized":False
    }
    (out/"edit-receipt.json").write_text(json.dumps(record,sort_keys=True,indent=2)+"\n")
    return record

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source-dir",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(execute(args.source_dir,args.out),indent=2))
