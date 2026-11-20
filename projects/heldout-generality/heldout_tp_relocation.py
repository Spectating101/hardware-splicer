"""Out-of-sample relocation of existing source-bound test points.
Native pcbnew edit, new copper link, native KiCad DRC. No waived rules.
"""
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess,uuid
from pathlib import Path
import pcbnew

OFFSET=[(dx,dy) for dist in (.3,.5,.8,1.2)
        for dx,dy in ((dist,0),(-dist,0),(0,dist),(0,-dist))]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def test(source:Path,out:Path,limit:int):
    original=pcbnew.LoadBoard(str(source))
    references=sorted(f.GetReference() for f in original.GetFootprints()
                      if f.GetReference().startswith("TP") and len(list(f.Pads()))==1)
    if len(references)<2:raise ValueError("UNSUPPORTED_NO_TESTPOINTS")
    out.mkdir(parents=True,exist_ok=False)
    attempts=[]
    for ref in references:
        for dx,dy in OFFSET:
            if len(attempts)>=limit:break
            trial=out/("trial-"+str(len(attempts)+1).zfill(3));trial.mkdir()
            for file in ("board.kicad_pro","board.kicad_dru"):
                if (source.parent/file).exists():shutil.copyfile(source.parent/file,trial/file)
            b=pcbnew.LoadBoard(str(source))
            fp=next(f for f in b.GetFootprints() if f.GetReference()==ref)
            pad=next(iter(fp.Pads()))
            before=pad.GetPosition()
            orig_net=pad.GetNetname()
            new=pcbnew.VECTOR2I(before.x+pcbnew.FromMM(dx),
                               before.y+pcbnew.FromMM(dy))
            fp.SetPosition(new)
            t=pcbnew.PCB_TRACK(b)
            t.SetStart(before);t.SetEnd(new)
            t.SetLayer(pcbnew.F_Cu);t.SetWidth(pcbnew.FromMM(.15));t.SetNet(pad.GetNet())
            b.Add(t)
            candidate=trial/"board.kicad_pcb";pcbnew.SaveBoard(str(candidate),b)
            result=subprocess.run(["kicad-cli","pcb","drc","--severity-error","--format","json",
                                   "--exit-code-violations","-o",str(trial/"drc.json"),str(candidate)],
                                  cwd=trial,capture_output=True,timeout=90)
            counts=json.loads((trial/"drc.json").read_text())
            receipt={"ref":ref,"net":orig_net,"offset_mm":[dx,dy],
                     "error_count":len(counts["violations"]),
                     "unconnected_count":len(counts["unconnected_items"]),
                     "exit_code":result.returncode}
            attempts.append(receipt)
            print(len(attempts),ref,dx,dy,receipt["error_count"],flush=True)
            if result.returncode==0 and receipt["error_count"]==0 and receipt["unconnected_count"]==0:
                # Compare real net membership after native KiCad reload.
                cb=pcbnew.LoadBoard(str(candidate))
                refs=[p for f in cb.GetFootprints() if f.GetReference()==ref for p in f.Pads()]
                if len(refs)!=1 or refs[0].GetNetname()!=orig_net:
                    raise ValueError("SOURCE_TP_NET_CHANGED")
                final={"status":"DIGITAL_TESTPOINT_RELOCATION_DRC_PASS","source_sha256":sha(source),
                       "revised_sha256":sha(candidate),"ref":ref,"net":orig_net,
                       "offset_mm":[dx,dy],"attempts":len(attempts),
                       "fabrication_authorized":False,"electrical_signal_integrity":"UNVERIFIED",
                       "physical_contact":"UNVERIFIED"}
                (out/"result.json").write_text(json.dumps(final,indent=2,sort_keys=True)+"\n")
                (out/"attempts.json").write_text(json.dumps(attempts,indent=2,sort_keys=True)+"\n")
                return final
        if len(attempts)>=limit:break
    final={"status":"NO_DRC_CLEAN_RELOCATION_WITHIN_SEARCH","source_sha256":sha(source),
           "attempts":len(attempts),"fabrication_authorized":False}
    (out/"attempts.json").write_text(json.dumps(attempts,indent=2,sort_keys=True)+"\n")
    (out/"result.json").write_text(json.dumps(final,indent=2,sort_keys=True)+"\n")
    return final

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--board",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--limit",type=int,default=64)
    a=p.parse_args()
    print(json.dumps(test(a.board,a.out,a.limit),indent=2))
