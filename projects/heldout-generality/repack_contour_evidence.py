"""Reassemble exact-checksum portable v3 dossier from retained study evidence.

Only packages local files; it does not fabricate, contact hardware, or
upgrade digital study evidence into physical claims.
"""
from __future__ import annotations
import argparse,hashlib,json,zipfile
from pathlib import Path

def sha(data:bytes):return hashlib.sha256(data).hexdigest()

def repack(directory:Path,archive:Path,overwrite=False):
    if not directory.is_dir():raise ValueError("evidence source directory missing")
    if archive.exists() and not overwrite:raise FileExistsError("refusing ZIP overwrite")
    if not (directory/"reports/contour-study-result.json").is_file():
        raise ValueError("missing contour benchmark result")
    if not (directory/"reports/signal-study-result.json").is_file():
        raise ValueError("missing signal-route benchmark result")
    contour=json.loads((directory/"reports/contour-study-result.json").read_text())
    signal=json.loads((directory/"reports/signal-study-result.json").read_text())
    if not (contour["pilot_pass"] and signal["pilot_pass"] and
            contour["fresh_replay_identical"] and signal["same_revision_board_sha256"]):
        raise ValueError("cannot package failed or unrepeated evidence as PASS")
    files=sorted(f for f in directory.rglob("*")
                 if f.is_file() and f.name!="MANIFEST.json")
    manifest={
        "schema":"hs.source_bound_cad_routing_package.v3",
        "frozen_corpus_commit":signal["cohort_commit"],
        "original_boards_attempted":contour["frozen_original_board_count"],
        "source_to_cad_original_successes":contour["original_sources_source_to_step_pass"],
        "derived_m3_source_revision_successes":int(contour["derived_revision_source_to_step_pass"]),
        "signal_branch_native_drc_clean":signal["new_source_bound_electrical_route"],
        "signal_pilot_selected_after_diagnostics":True,
        "signal_probe_source_binding_validated":signal["independent_new_probe_cad_checks"],
        "physical_measurement":False,"fabrication_authorized":False,
        "content_sha256":{f.relative_to(directory).as_posix():sha(f.read_bytes()) for f in files}
    }
    (directory/"MANIFEST.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for file in sorted(directory.rglob("*")):
            if not file.is_file():continue
            name="contour-routing-evidence/"+file.relative_to(directory).as_posix()
            info=zipfile.ZipInfo(name,date_time=(2026,11,20,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o100644<<16)
            z.writestr(info,file.read_bytes())
    with zipfile.ZipFile(archive) as z:
        for name,digest in manifest["content_sha256"].items():
            if sha(z.read("contour-routing-evidence/"+name))!=digest:
                raise ValueError("PACKAGED_CONTENT_HASH_MISMATCH:"+name)
    return {"files":len(files),"zip_bytes":archive.stat().st_size,
            "zip_sha256":sha(archive.read_bytes()),
            "repeated_original_board_count":contour["source_revisions_tested"],
            "repeated_routing_runs":signal["replay_runs"],
            "physical_measurement":False}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--zip",type=Path,required=True)
    p.add_argument("--overwrite",action="store_true")
    args=p.parse_args()
    print(json.dumps(repack(args.source,args.zip,args.overwrite),indent=2))
