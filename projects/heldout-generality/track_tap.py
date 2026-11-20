"""Conservative source-bound F.Cu track-tap branch onto a *new* signal testpoint.

Frozen-board, bounded search with REAL KiCad 9 DRC and no relaxed checks.
No manufacturing/powered-test approval, no signal-integrity proof.
"""
from __future__ import annotations
import argparse,hashlib,json,math,re,shutil,subprocess,uuid
from collections import Counter
from pathlib import Path
import pcbnew
# Legacy KiCad source uses (tstamp UUID), while KiCad 9 writes (uuid "UUID").
# Both formats identify existing objects. Do not rewrite original identities!
UUID_RE=re.compile(r'\((?:uuid|tstamp)\s+"?([0-9a-f-]{36})"?\)')
LIB="/usr/share/kicad/footprints/TestPoint.pretty"

def mm(v):return round(pcbnew.ToMM(v),6)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def geometric_dist_point_to_segment(x,y,a,b):
    ax,ay=a; bx,by=b
    sq=(bx-ax)**2+(by-ay)**2
    ratio=min(1,max(0,((x-ax)*(bx-ax)+(y-ay)*(by-ay))/sq)) if sq else 0
    return math.hypot(x-(ax+ratio*(bx-ax)),y-(ay+ratio*(by-ay)))

def candidates(board):
    poly=pcbnew.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(poly) or poly.OutlineCount()!=1:
        raise ValueError("UNSUPPORTED_EDGE_CUTS")
    fps=list(board.GetFootprints())
    original_refs={f.GetReference() for f in fps}
    number=1
    while "TP"+str(number) in original_refs:number+=1
    new_ref="TP"+str(number)
    footprint_boxes=[]
    for f in fps:
        bb=f.GetBoundingBox(False,False)
        footprint_boxes.append((mm(bb.GetLeft()),mm(bb.GetTop()),mm(bb.GetRight()),mm(bb.GetBottom())))
    pads=[(mm(p.GetPosition().x),mm(p.GetPosition().y),p.GetNetname())
          for f in fps for p in f.Pads() if p.GetNetCode()>0]
    tracks=[]
    for t in board.GetTracks():
        if t.GetClass()!="PCB_TRACK" or t.GetNetCode()<=0 or t.GetLayer()!=pcbnew.F_Cu:continue
        name=t.GetNetname()
        if any(s in name.lower() for s in ("gnd","vcc","vbat","battery","vbus","power","shield")):
            continue
        a=(mm(t.GetStart().x),mm(t.GetStart().y))
        b=(mm(t.GetEnd().x),mm(t.GetEnd().y))
        d=math.dist(a,b)
        if 3.5<=d<=25:
            tracks.append((name,a,b,t))
    existing=[(t.GetNetname(),
               (mm(t.GetStart().x),mm(t.GetStart().y)),
               (mm(t.GetEnd().x),mm(t.GetEnd().y)))
              for t in board.GetTracks() if t.GetClass()=="PCB_TRACK"
              and t.GetLayer()==pcbnew.F_Cu and t.GetNetCode()>0]
    choices=[]
    for net,a,b,t in tracks:
        dx,dy=b[0]-a[0],b[1]-a[1]
        norm=math.hypot(dx,dy)
        unit=(-dy/norm,dx/norm)
        mx,my=(a[0]+b[0])/2,(a[1]+b[1])/2
        for radial in (2.25,3.5,4.75):
            for side in (1,-1):
                x,y=round(mx+side*radial*unit[0],6),round(my+side*radial*unit[1],6)
                if not poly.Contains(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))):
                    continue
                if any(l-1.0<=x<=r+1.0 and z-1.0<=y<=bottom+1.0
                       for l,z,r,bottom in footprint_boxes):
                    continue
                nearest_pad=min((math.hypot(px-x,py-y) for px,py,pnet in pads if pnet!=net),
                                default=100.)
                nearest_track=min((geometric_dist_point_to_segment(x,y,ta,tb)
                    for tnet,ta,tb in existing if tnet!=net),default=100.)
                if min(nearest_pad,nearest_track)<1.7:continue
                score=(-round(min(nearest_pad,nearest_track),3),radial,net,x,y)
                choices.append((score,net,a,b,(mx,my),(x,y),t))
    choices.sort(key=lambda x:x[0])
    return choices,new_ref

def stabilize(source:Path,edited:Path,payload):
    orig=set(UUID_RE.findall(source.read_text(errors="replace")))
    code=edited.read_text()
    # Assign deterministic identities by source serialization *order*, not
    # by sorting the newly generated RANDOM UUID strings.
    unseen=set(UUID_RE.findall(code))-orig
    added=list(dict.fromkeys(value for value in UUID_RE.findall(code) if value in unseen))
    if len(added)<2:raise ValueError("NEW_SOURCE_BOUND_ITEMS_NOT_SERIALIZED")
    for i,old in enumerate(added):
        safe=str(uuid.uuid5(uuid.NAMESPACE_URL,sha(source)+"|"+repr(payload)+"|"+str(i)))
        code=code.replace('(uuid "'+old+'")','(uuid "'+safe+'")')
    edited.write_text(code)
    # Reload/save once after fixing UUIDs so pcbnew's canonical object order
    # cannot depend on original random in-memory UUID insertion order.
    normalized=pcbnew.LoadBoard(str(edited))
    pcbnew.SaveBoard(str(edited),normalized)
    return len(added)

def check(folder:Path):
    argv=["kicad-cli","pcb","drc","--format","json","--severity-error",
          "--exit-code-violations","-o",str(folder/"native-drc.json"),
          str(folder/"board.kicad_pcb")]
    cp=subprocess.run(argv,cwd=folder,capture_output=True,timeout=75)
    data=json.loads((folder/"native-drc.json").read_text())
    return {"exit_code":cp.returncode,"errors":len(data["violations"]),
            "unconnected":len(data["unconnected_items"]),
            "finding_types":dict(sorted(Counter(v["type"] for v in data["violations"]).items()))}

def run(source_dir:Path,out:Path,limit=60):
    original=source_dir/"board.kicad_pcb"
    board=pcbnew.LoadBoard(str(original))
    choices,ref=candidates(board)
    if not choices:raise ValueError("NO_SOURCE_BACKED_TRACK_TAP_CANDIDATES")
    out.mkdir(parents=True,exist_ok=False)
    original_pads={(f.GetReference(),str(p.GetNumber()),p.GetNetname()) for f in board.GetFootprints() for p in f.Pads()}
    original_tracks={(t.GetClass(),t.GetNetname(),mm(t.GetStart().x),mm(t.GetStart().y),
                      mm(t.GetEnd().x),mm(t.GetEnd().y)) for t in board.GetTracks()}
    trials=[]
    for i,c in enumerate(choices[:limit],1):
        _,net,a,b,mid,target,t=c
        folder=out/("trial-"+str(i).zfill(3));folder.mkdir()
        for n in ("board.kicad_pro","board.kicad_dru"):
            if (source_dir/n).exists():shutil.copyfile(source_dir/n,folder/n)
        clone=pcbnew.LoadBoard(str(original))
        anchor=next((tr for tr in clone.GetTracks()
                     if tr.GetClass()=="PCB_TRACK" and tr.GetLayer()==pcbnew.F_Cu
                     and tr.GetNetname()==net
                     and (mm(tr.GetStart().x),mm(tr.GetStart().y))==a
                     and (mm(tr.GetEnd().x),mm(tr.GetEnd().y))==b),None)
        if anchor is None:raise ValueError("ANCHOR_TRACK_CHANGED")
        point=pcbnew.VECTOR2I(pcbnew.FromMM(target[0]),pcbnew.FromMM(target[1]))
        start=pcbnew.VECTOR2I(pcbnew.FromMM(mid[0]),pcbnew.FromMM(mid[1]))
        fp=pcbnew.FootprintLoad(LIB,"TestPoint_Pad_D1.0mm")
        if fp is None:raise ValueError("MISSING_REAL_TESTPOINT_FOOTPRINT")
        fp.SetReference(ref);fp.SetValue("UNPOWERED_SIGNAL_TEST_ACCESS");fp.SetPosition(point)
        p=list(fp.Pads())
        if len(p)!=1:raise ValueError("TESTPOINT_LIBRARY_NOT_ONE_PAD")
        p[0].SetNet(anchor.GetNet());clone.Add(fp)
        added=pcbnew.PCB_TRACK(clone)
        added.SetStart(start);added.SetEnd(point);added.SetLayer(pcbnew.F_Cu)
        added.SetWidth(pcbnew.FromMM(.2));added.SetNet(anchor.GetNet());clone.Add(added)
        revised=folder/"board.kicad_pcb"
        pcbnew.SaveBoard(str(revised),clone)
        stabilized=stabilize(original,revised,(net,a,b,mid,target))
        drc=check(folder)
        attempt={"index":i,"source_net":net,"source_track_start":a,"source_track_end":b,
                 "tap_center":mid,"new_access_xy":target,"drc":drc}
        trials.append(attempt)
        if drc["exit_code"] or drc["errors"] or drc["unconnected"]:continue
        check_board=pcbnew.LoadBoard(str(revised))
        pads={(f.GetReference(),str(p.GetNumber()),p.GetNetname()) for f in check_board.GetFootprints() for p in f.Pads()}
        tracks={(t.GetClass(),t.GetNetname(),mm(t.GetStart().x),mm(t.GetStart().y),
                 mm(t.GetEnd().x),mm(t.GetEnd().y)) for t in check_board.GetTracks()}
        if not original_pads.issubset(pads) or not original_tracks.issubset(tracks):
            raise ValueError("ORIGINAL_SOURCE_CONNECTIONS_NOT_PRESERVED")
        candidates_fp=[f for f in check_board.GetFootprints() if f.GetReference()==ref]
        if len(candidates_fp)!=1 or len(list(candidates_fp[0].Pads()))!=1:
            raise ValueError("NEW_TESTPOINT_NOT_PRESERVED")
        v=list(candidates_fp[0].Pads())[0]
        if v.GetNetname()!=net or not v.IsOnLayer(pcbnew.F_Mask):
            raise ValueError("TESTPOINT_INVALID_COPPER_OR_MASK")
        if len(tracks)!=len(original_tracks)+1:
            raise ValueError("EXPECTED_EXACTLY_ONE_NEW_COPPER_TRACK")
        receipt={"schema":"hs.heldout_track_tap.v1","status":"DIGITAL_DRC_ZERO",
                 "original_source_sha256":sha(original),"edited_sha256":sha(revised),
                 "new_testpoint":ref,"source_anchor_net":net,"source_anchor_start_mm":a,
                 "source_anchor_end_mm":b,"branch_start_mm":mid,
                 "branch_end_mm":target,"source_original_track_count":len(original_tracks),
                 "new_track_count":len(tracks),"stable_created_ids":stabilized,
                 "native_drc":drc,"candidate_attempts":i,
                 "signal_integrity_unverified":True,
                 "fabrication_authorized":False,"physical_probe_tested":False}
        (out/"result.json").write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
        (out/"attempts.json").write_text(json.dumps(trials,sort_keys=True,indent=2)+"\n")
        return receipt,revised
    (out/"attempts.json").write_text(json.dumps(trials,sort_keys=True,indent=2)+"\n")
    raise ValueError("NO_DRC_ZERO_BOUNDED_TRACK_TAP:"+str(len(trials)))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source-dir",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--limit",type=int,default=60)
    a=p.parse_args()
    print(json.dumps(run(a.source_dir,a.out,a.limit)[0],indent=2))
