"""Independent native KiCad inspection; no calls to the design generator."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import pcbnew

def mm(x):return round(pcbnew.ToMM(x),4)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def inspect(path):
    b=pcbnew.LoadBoard(str(path))
    pads=sorted((f.GetReference(),str(p.GetNumber()),p.GetNetname(),
                 mm(p.GetPosition().x),mm(p.GetPosition().y))
                for f in b.GetFootprints() for p in f.Pads())
    segments=sorted((t.GetClass(),t.GetNetname(),
                     mm(t.GetStart().x),mm(t.GetStart().y),
                     mm(t.GetEnd().x),mm(t.GetEnd().y),
                     str(t.GetLayer()))
                    for t in b.GetTracks())
    holes={}
    for f in b.GetFootprints():
        if f.GetReference() in {"H1","H2","H3","H4"}:
            p=list(f.Pads())
            if len(p)!=1:raise ValueError("ambiguous hole")
            d=mm(p[0].GetDrillSize().x)
            holes[f.GetReference()]={"x":mm(p[0].GetPosition().x),
                                     "y":mm(p[0].GetPosition().y),"drill":d,
                                     "net":p[0].GetNetname()}
    edges=sorted((str(e.GetShape()),mm(e.GetStart().x),mm(e.GetStart().y),
                  mm(e.GetEnd().x),mm(e.GetEnd().y))
                 for e in b.GetDrawings() if e.GetLayer()==pcbnew.Edge_Cuts)
    return {"sha256":sha(path),"pads":pads,"tracks":segments,"holes":holes,"outline_edges":edges}

def audit(source,edited,receipt):
    orig=inspect(source);new=inspect(edited)
    if orig["pads"]!=new["pads"] or orig["tracks"]!=new["tracks"]:
        raise ValueError("ORIGINAL_COPPER_OR_PAD_NET_CHANGED")
    if orig["outline_edges"]!=new["outline_edges"]:
        raise ValueError("ORIGINAL_BOARD_OUTLINE_CHANGED")
    if set(orig["holes"])!={"H1","H2","H3","H4"} or set(new["holes"])!=set(orig["holes"]):
        raise ValueError("MOUNT_HOLE_SET_CHANGED")
    for ref in orig["holes"]:
        a,b=orig["holes"][ref],new["holes"][ref]
        if abs(a["drill"]-2.7)>.001 or abs(b["drill"]-3.2)>.001:
            raise ValueError("BORE_REVISION_MISMATCH")
        if (a["x"],a["y"],a["net"])!=(b["x"],b["y"],b["net"]):
            raise ValueError("MOUNT_POSITION_OR_NET_CHANGED")
    if orig["sha256"]!=receipt["source_sha256"] or new["sha256"]!=receipt["edited_sha256"]:
        raise ValueError("SOURCE_REVISION_DIGEST_MISMATCH")
    if len(orig["pads"])!=receipt["original_pad_count"] or len(orig["tracks"])!=receipt["original_copper_count"]:
        raise ValueError("RECEIPT_SOURCE_COUNT_MISMATCH")
    if len(new["pads"])!=receipt["revised_pad_count"] or len(new["tracks"])!=receipt["revised_copper_count"]:
        raise ValueError("RECEIPT_EDIT_COUNT_MISMATCH")
    if receipt["fabrication_authorized"] is not False:raise ValueError("FALSE_PHYSICAL_AUTHORITY")
    return {"status":"PASS","source_sha256":orig["sha256"],"revised_sha256":new["sha256"],
            "source_nets_and_pads_preserved":len(orig["pads"]),
            "source_tracks_preserved":len(orig["tracks"]),
            "all_four_hole_positions_preserved":True,
            "original_holes":orig["holes"],"edited_holes":new["holes"],
            "outline_edges":orig["outline_edges"],
            "original_outline_preserved":True,"fabrication_authorized":False}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--edited",type=Path,required=True)
    p.add_argument("--receipt",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=audit(a.source,a.edited,json.loads(a.receipt.read_text()))
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("original_holes","edited_holes")},indent=2))
