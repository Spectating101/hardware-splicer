"""Independent KiCad native audit of a source-bound signal-testpoint branch."""
from __future__ import annotations
import argparse,hashlib,json,math,shutil,subprocess
from pathlib import Path
import pcbnew

def mm(n):return round(pcbnew.ToMM(n),6)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def objects(board):
    pads={(f.GetReference(),str(p.GetNumber()),p.GetNetname(),
           mm(p.GetPosition().x),mm(p.GetPosition().y))
          for f in board.GetFootprints() for p in f.Pads()}
    tracks={(t.GetClass(),t.GetNetname(),t.GetLayer(),
             mm(t.GetStart().x),mm(t.GetStart().y),
             mm(t.GetEnd().x),mm(t.GetEnd().y)) for t in board.GetTracks()}
    poly=pcbnew.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(poly):raise ValueError("SOURCE_OUTLINE_BROKEN")
    shape=[]
    for i in range(poly.OutlineCount()):
        outline=[(mm(poly.Outline(i).CPoint(k).x),mm(poly.Outline(i).CPoint(k).y))
                 for k in range(poly.Outline(i).PointCount())]
        holes=[[(mm(poly.Hole(i,j).CPoint(k).x),mm(poly.Hole(i,j).CPoint(k).y))
               for k in range(poly.Hole(i,j).PointCount())] for j in range(poly.HoleCount(i))]
        shape.append((outline,holes))
    return pads,tracks,shape

def audit(source:Path,edited:Path,receipt:dict):
    if sha(source)!=receipt["original_source_sha256"] or sha(edited)!=receipt["edited_sha256"]:
        raise ValueError("SOURCE_SHA_MISMATCH")
    a=pcbnew.LoadBoard(str(source));b=pcbnew.LoadBoard(str(edited))
    ap,at,ag=objects(a);bp,bt,bg=objects(b)
    if ag!=bg:raise ValueError("SOURCE_CONTOUR_CHANGED")
    if not ap.issubset(bp) or len(bp)!=len(ap)+1:raise ValueError("EXISTING_PAD_NET_CHANGED")
    if not at.issubset(bt) or len(bt)!=len(at)+1:raise ValueError("EXISTING_COPPER_CHANGED")
    changed=bt-at
    if len(changed)!=1:raise ValueError("EXPECTED_SINGLE_NEW_COPPER_BRANCH")
    _,net,layer,x1,y1,x2,y2=next(iter(changed))
    if net!=receipt["source_anchor_net"] or layer!=pcbnew.F_Cu:raise ValueError("BRANCH_NET_OR_LAYER_WRONG")
    if {(x1,y1),(x2,y2)}!={tuple(receipt["branch_start_mm"]),tuple(receipt["branch_end_mm"])}:
        raise ValueError("BRANCH_COORDINATES_NOT_REPORTED")
    start,end=receipt["source_anchor_start_mm"],receipt["source_anchor_end_mm"]
    original=[t for t in a.GetTracks() if t.GetClass()=="PCB_TRACK" and t.GetLayer()==pcbnew.F_Cu
              and t.GetNetname()==net and {(mm(t.GetStart().x),mm(t.GetStart().y)),
                 (mm(t.GetEnd().x),mm(t.GetEnd().y))}=={tuple(start),tuple(end)}]
    if len(original)!=1:raise ValueError("ANCHOR_SOURCE_TRACE_MISSING")
    mid=receipt["branch_start_mm"]
    if abs((end[0]-start[0])*(mid[1]-start[1])-(end[1]-start[1])*(mid[0]-start[0]))>.0001:
        raise ValueError("BRANCH_TAP_NOT_COLLINEAR")
    if math.dist(start,mid)+math.dist(mid,end)-math.dist(start,end)>.0001:
        raise ValueError("BRANCH_TAP_NOT_ON_ORIGINAL_SEGMENT")
    f=[f for f in b.GetFootprints() if f.GetReference()==receipt["new_testpoint"]]
    if len(f)!=1 or len(list(f[0].Pads()))!=1:raise ValueError("TESTPOINT_NOT_UNIQUE")
    pad=list(f[0].Pads())[0]
    if pad.GetNetname()!=net or not pad.IsOnLayer(pcbnew.F_Cu) or not pad.IsOnLayer(pcbnew.F_Mask):
        raise ValueError("TESTPOINT_NET_OR_EXPOSURE_WRONG")
    dx,dy=mm(pad.GetSize().x),mm(pad.GetSize().y)
    if pad.GetShape()!=pcbnew.PAD_SHAPE_CIRCLE or abs(dx-dy)>.00001 or abs(dx-1.0)>.00001:
        raise ValueError("SOURCE_TESTPOINT_PAD_DIAMETER_UNSUPPORTED")
    if (mm(pad.GetPosition().x),mm(pad.GetPosition().y))!=tuple(receipt["branch_end_mm"]):
        raise ValueError("TESTPOINT_NOT_AT_BRANCH_END")
    if receipt["fabrication_authorized"] is not False:raise ValueError("FALSE_FAB_AUTHORITY")
    return {"schema":"hs.independent_native_track_tap.v1","status":"PASS",
            "original_pad_identities_preserved":len(ap),"original_copper_items_preserved":len(at),
            "new_signal_branch_count":1,"new_exposed_testpoints":1,
            "source_contour_and_cutouts_preserved":True,
            "exposed_testpoint_diameter_mm":dx,
            "original_sha256":sha(source),"revised_sha256":sha(edited),
            "branch_net":net,"new_access_xy":receipt["branch_end_mm"],
            "physical_measurement":False,"fabrication_authorized":False}

def wrong_net(edited:Path,receipt:dict,folder:Path):
    folder.mkdir(parents=True,exist_ok=False)
    b=pcbnew.LoadBoard(str(edited))
    tp=next(f for f in b.GetFootprints() if f.GetReference()==receipt["new_testpoint"])
    pad=list(tp.Pads())[0]
    foreign=next(p.GetNet() for f in b.GetFootprints() for p in f.Pads()
                 if p.GetNetCode()>0 and p.GetNetname()!=receipt["source_anchor_net"])
    pad.SetNet(foreign)
    shutil.copyfile(edited.with_suffix(".kicad_pro"),folder/"board.kicad_pro")
    pcbnew.SaveBoard(str(folder/"board.kicad_pcb"),b)
    cp=subprocess.run(["kicad-cli","pcb","drc","--severity-error","--format","json",
                      "--exit-code-violations","-o",str(folder/"drc.json"),
                      str(folder/"board.kicad_pcb")],cwd=folder,capture_output=True,timeout=90)
    d=json.loads((folder/"drc.json").read_text())
    if not d["violations"] and not d["unconnected_items"]:
        raise ValueError("WRONG_NET_NOT_DETECTED")
    return {"rejected":True,"native_error_count":len(d["violations"]),
            "native_unconnected":len(d["unconnected_items"]),"exit_code":cp.returncode}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--revised",type=Path,required=True)
    p.add_argument("--receipt",type=Path,required=True)
    p.add_argument("--negative",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();rec=json.loads(a.receipt.read_text())
    result=audit(a.source,a.revised,rec)
    result["wrong_net_negative"]=wrong_net(a.revised,rec,a.negative)
    a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps(result,sort_keys=True,indent=2))
