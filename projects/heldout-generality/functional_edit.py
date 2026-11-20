"""Add a source-bound exposed test pad on a previously unrepresented net.
Only four-arc rounded-rectangle outlines and zero-error DRC edits are supported.
Digital engineering only; never fabrication or powered-use approval.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, shutil, subprocess, uuid
from collections import Counter
from pathlib import Path
import pcbnew

LIB="/usr/share/kicad/footprints/TestPoint.pretty"
UUID_RE=re.compile(r'\(uuid\s+"([0-9a-f-]{36})"\)')
OFFSETS=[(dx,dy) for d in (2.5,3.5,5.0) for dx,dy in ((d,0),(-d,0),(0,d),(0,-d),(d,d),(-d,d),(d,-d),(-d,-d))]
def mm(x): return round(pcbnew.ToMM(x),5)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def outline(b):
    edges=[e for e in b.GetDrawings() if e.GetLayer()==pcbnew.Edge_Cuts]
    lines=[e for e in edges if e.GetShape()==pcbnew.SHAPE_T_SEGMENT]
    arcs=[e for e in edges if e.GetShape()==pcbnew.SHAPE_T_ARC]
    if len(edges)!=8 or len(lines)!=4 or len(arcs)!=4:
        raise ValueError("UNSUPPORTED_OUTLINE:requires four lines and four round corners")
    counts=Counter((mm(q.x),mm(q.y)) for e in edges for q in (e.GetStart(),e.GetEnd()))
    if set(counts.values())!={2}:raise ValueError("UNSUPPORTED_OUTLINE:edges do not close")
    # KiCad's general bounding box includes line stroke width. A source
    # outline is defined by the actual Edge.Cuts endpoints, not by its ink.
    endpoints=list(counts)
    x,y=min(p[0] for p in endpoints),min(p[1] for p in endpoints)
    w,h=round(max(p[0] for p in endpoints)-x,5),round(max(p[1] for p in endpoints)-y,5)
    radii=[mm(a.GetRadius()) for a in arcs];r=radii[0]
    if not (0<r<min(w,h)/3 and max(radii)-min(radii)<.01):
        raise ValueError("UNSUPPORTED_OUTLINE:corner radii mismatch")
    found={(round(mm(a.GetCenter().x),2),round(mm(a.GetCenter().y),2)) for a in arcs}
    expected={(round(cx,2),round(cy,2)) for cx in (x+r,x+w-r) for cy in (y+r,y+h-r)}
    if found!=expected:raise ValueError("UNSUPPORTED_OUTLINE:corner centers mismatch")
    return {"x":x,"y":y,"width":w,"height":h,"radius":r}

def original_items(b):
    pads=sorted((f.GetReference(),str(p.GetNumber()),p.GetNetname(),
                 mm(p.GetPosition().x),mm(p.GetPosition().y))
                 for f in b.GetFootprints() for p in f.Pads())
    tracks=sorted((t.GetNetname(),mm(t.GetStart().x),mm(t.GetStart().y),
                   mm(t.GetEnd().x),mm(t.GetEnd().y),
                   (mm(t.GetWidth()) if t.GetClass()!="PCB_VIA" else 0.0),
                   str(t.GetLayer())) for t in b.GetTracks())
    return pads,tracks

def candidates(b,o):
    existing={p.GetNetname() for f in b.GetFootprints()
              if re.fullmatch(r"TP\d+",f.GetReference()) for p in f.Pads()}
    pads=[(f,p) for f in b.GetFootprints() for p in f.Pads()]
    sources=sorted((p.GetNetname(),f.GetReference(),str(p.GetNumber()),p)
             for f,p in pads if p.GetNetCode()>0 and p.IsOnLayer(pcbnew.F_Cu)
             and p.IsOnLayer(pcbnew.F_Mask) and p.GetNetname() not in existing
             and not any(t in p.GetNetname().lower()
               for t in ("gnd","vbus","vcc","vbat","battery","+3v","+5v","power","shield")))
    boxes=[]
    for f in b.GetFootprints():
        bb=f.GetBoundingBox(False,False)
        boxes.append(tuple(mm(v) for v in (bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom())))
    other=[(mm(p.GetPosition().x),mm(p.GetPosition().y),p.GetNetname()) for _,p in pads if p.GetNetCode()>0]
    c=[]
    for net,ref,pad,p in sources:
        ox,oy=mm(p.GetPosition().x),mm(p.GetPosition().y)
        for dx,dy in OFFSETS:
            x,y=round(ox+dx,3),round(oy+dy,3)
            if not(o["x"]+3<x<o["x"]+o["width"]-3 and o["y"]+3<y<o["y"]+o["height"]-3):continue
            if any(l-.6<=x<=r+.6 and t-.6<=y<=d+.6 for l,t,r,d in boxes):continue
            foreign=[math.hypot(x-xx,y-yy) for xx,yy,n in other if n!=net]
            near=min(foreign,default=100)
            if near<1.5:continue
            density=sum(math.hypot(x-xx,y-yy)<4 for xx,yy,_ in other)
            c.append((density,-round(near,3),net,ref,pad,x,y))
    return sorted(c)

def stable_uuids(original:Path,changed:Path,choice):
    orig=set(UUID_RE.findall(original.read_text(errors="replace")))
    edited=changed.read_text()
    created=sorted(set(UUID_RE.findall(edited))-orig)
    if len(created)<2:raise ValueError("NEW_IDS_MISSING")
    for i,item in enumerate(created):
        stable=str(uuid.uuid5(uuid.NAMESPACE_URL,sha(original)+"|"+repr(choice)+"|"+str(i)))
        edited=edited.replace('(uuid "'+item+'")','(uuid "'+stable+'")')
    changed.write_text(edited)
    return len(created)

def test_drc(folder:Path):
    cmd=["kicad-cli","pcb","drc","--severity-error","--format","json",
         "--exit-code-violations","-o",str(folder/"drc.json"),str(folder/"board.kicad_pcb")]
    run=subprocess.run(cmd,cwd=folder,capture_output=True,timeout=90)
    d=json.loads((folder/"drc.json").read_text())
    return {"exit":run.returncode,"errors":len(d["violations"]),
            "unconnected":len(d["unconnected_items"]),
            "types":dict(sorted(Counter(x["type"] for x in d["violations"]).items()))}

def apply(original:Path,out:Path,limit=96):
    source=pcbnew.LoadBoard(str(original)); o=outline(source)
    orig_pads,orig_tracks=original_items(source)
    used={f.GetReference() for f in source.GetFootprints()}
    n=1
    while "TP"+str(n) in used:n+=1
    new_ref="TP"+str(n)
    options=candidates(source,o)
    out.mkdir(parents=True,exist_ok=False)
    tried=[]
    for i,choice in enumerate(options[:limit],1):
        _,_,net,ref,pad_number,x,y=choice
        folder=out/("trial-"+str(i).zfill(3));folder.mkdir()
        for name in ("board.kicad_pro","board.kicad_dru"):
            if (original.parent/name).exists():shutil.copyfile(original.parent/name,folder/name)
        b=pcbnew.LoadBoard(str(original))
        ref_pad=next(p for f in b.GetFootprints() if f.GetReference()==ref
                     for p in f.Pads() if str(p.GetNumber())==pad_number and p.GetNetname()==net)
        fp=pcbnew.FootprintLoad(LIB,"TestPoint_Pad_D1.5mm")
        if fp is None:raise ValueError("KICAD_LIBRARY_UNAVAILABLE")
        fp.SetReference(new_ref);fp.SetValue("UNPOWERED_TEST_ACCESS")
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)))
        new_pad=list(fp.Pads())
        if len(new_pad)!=1:raise ValueError("BAD_TESTPOINT_LIBRARY")
        new_pad[0].SetNet(ref_pad.GetNet());b.Add(fp)
        track=pcbnew.PCB_TRACK(b);track.SetStart(ref_pad.GetPosition())
        track.SetEnd(fp.GetPosition());track.SetLayer(pcbnew.F_Cu)
        track.SetWidth(pcbnew.FromMM(.2));track.SetNet(ref_pad.GetNet());b.Add(track)
        candidate=folder/"board.kicad_pcb";pcbnew.SaveBoard(str(candidate),b)
        new_ids=stable_uuids(original,candidate,choice)
        drc=test_drc(folder)
        tried.append({"trial":i,"net":net,"ref":ref,"pad":pad_number,"xy":[x,y],"drc":drc})
        if drc["exit"] or drc["errors"] or drc["unconnected"]:continue
        edited=pcbnew.LoadBoard(str(candidate))
        edited_pads,edited_tracks=original_items(edited)
        if not set(orig_pads).issubset(set(edited_pads)) or not set(orig_tracks).issubset(set(edited_tracks)):
            raise ValueError("ORIGINAL_NET_OR_COPPER_CHANGED")
        added=[f for f in edited.GetFootprints() if f.GetReference()==new_ref]
        if len(added)!=1:raise ValueError("NEW_TP_MISSING")
        p=list(added[0].Pads())
        if len(p)!=1 or p[0].GetNetname()!=net or not p[0].IsOnLayer(pcbnew.F_Mask):
            raise ValueError("TESTPOINT_NET_OR_MASK_WRONG")
        record={"schema":"hs.heldout_functional_edit.v1","status":"DIGITAL_CANDIDATE_VALIDATED",
                "source_sha256":sha(original),"revised_sha256":sha(candidate),
                "source_pad_count":len(orig_pads),"source_track_count":len(orig_tracks),
                "revised_pad_count":len(edited_pads),"revised_track_count":len(edited_tracks),
                "source_ref":ref,"source_pad":pad_number,"net":net,
                "new_testpoint_ref":new_ref,"new_testpoint_xy":[x,y],
                "source_outline":o,"attempts":i,"stabilized_new_uuids":new_ids,"drc":drc,
                "signal_integrity":"UNTESTED","physical_contact":"UNTESTED",
                "fabrication_authorized":False}
        (out/"edit-receipt.json").write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")
        (out/"attempts.json").write_text(json.dumps(tried,indent=2,sort_keys=True)+"\n")
        return record,candidate
    (out/"attempts.json").write_text(json.dumps(tried,indent=2,sort_keys=True)+"\n")
    raise ValueError("NO_DRC_CLEAN_EDIT_WITHIN_LIMIT:"+str(len(tried)))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source-dir",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--limit",type=int,default=96)
    args=p.parse_args()
    r,_=apply(args.source_dir/"board.kicad_pcb",args.out,args.limit)
    print(json.dumps(r,indent=2))
