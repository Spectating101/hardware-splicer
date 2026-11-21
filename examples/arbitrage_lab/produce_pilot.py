"""Reproducible HS-native market/product pilot, no equipment control or orders."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile

from mecha_splicer.bundle import generate_bundle

HERE=Path(__file__).resolve().parent
MESH_DENSITY=1.27  # estimated PETG density g/cm3; not a measured print weight.


def audit_binary_stl(path:Path)->dict:
    data=path.read_bytes()
    if len(data)<84:
        raise ValueError("STL too small")
    n=struct.unpack_from("<I",data,80)[0]
    if not n or len(data)!=84+50*n:
        raise ValueError("Expected well-formed BINARY STL")
    edges={}
    bmin=[math.inf]*3
    bmax=[-math.inf]*3
    vol=0.
    for i in range(n):
        off=84+i*50
        v=[
            struct.unpack_from("<fff",data,off+12),
            struct.unpack_from("<fff",data,off+24),
            struct.unpack_from("<fff",data,off+36)]
        # signed tetrahedron volume
        a,b,c=v
        cross=(b[1]*c[2]-b[2]*c[1],b[2]*c[0]-b[0]*c[2],b[0]*c[1]-b[1]*c[0])
        vol+=sum(a[k]*cross[k] for k in range(3))/6.
        q=[]
        for x in v:
            q.append(tuple(round(t,4) for t in x))
            for k in range(3):
                bmin[k]=min(bmin[k],x[k]);bmax[k]=max(bmax[k],x[k])
        for u,w in ((0,1),(1,2),(2,0)):
            e=tuple(sorted((q[u],q[w])))
            edges[e]=edges.get(e,0)+1
    bad=sum(1 for count in edges.values() if count!=2)
    if bad:
        raise ValueError(f"CAD topology has {bad} non-2-valence edges; not cleared for quoting")
    solid_vol_cm3=abs(vol)/1000.
    return {
        "status":"native_HS_CAD_mesh_only",
        "sha256":hashlib.sha256(data).hexdigest(),
        "triangles":n,
        "non_2_manifold_edges":bad,
        "bbox_mm":[round(bmax[i]-bmin[i],3) for i in range(3)],
        "volume_cm3_per_bracket":round(solid_vol_cm3,5),
        "assumed_solid_PETG_grams_each":round(solid_vol_cm3*MESH_DENSITY,5),
        "assumed_solid_PETG_grams_for_pair":round(solid_vol_cm3*MESH_DENSITY*2,5),
        "assumed_density_g_cm3":MESH_DENSITY,
        "limitations":"NOT sliced mass, printed part, fit, load test, hardware installation or vendor quote."
    }


def run()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--openscad",default=shutil.which("openscad"),
                        help="OpenSCAD executable or Linux AppImage; required for STL rendering")
    parser.add_argument("--output",type=Path,default=HERE/"outputs")
    args=parser.parse_args()
    if not args.openscad:
        raise SystemExit("OpenSCAD required; no simulated STLs or invented geometry")
    spec=json.loads((HERE/"router3_indoor_mount.json").read_text())
    native=args.output/"native_router3"
    bundle=generate_bundle(spec,out_dir=native)
    if bundle["blockers"] or bundle["outputs"]!=["indoor_router_mount.scad"]:
        raise ValueError(f"HS native engine did not produce expected engineering part: {bundle}")
    src=native/"indoor_router_mount.scad"
    dst=native/"indoor_router_mount.stl"
    cmd=[args.openscad]
    if args.openscad.endswith(".AppImage"):
        cmd.append("--appimage-extract-and-run")
    cmd += ["--export-format","binstl","-o",str(dst),str(src)]
    subprocess.run(cmd,check=True,timeout=120)
    geom=audit_binary_stl(dst)
    (native/"native_mesh_audit.json").write_text(json.dumps(geom,indent=2)+"\n")
    screen=[sys.executable,str(HERE/"profit_screen.py"),
            "--snapshot",str(HERE/"market_snapshot_20261105.json"),
            "--out",str(args.output),
            "--router-mass-g",str(geom["assumed_solid_PETG_grams_for_pair"])]
    subprocess.run(screen,check=True,timeout=30)
    z=args.output/"HS_INDOOR_ROUTER3_MARKET_PILOT.zip"
    files=[native/x for x in ["indoor_router_mount.scad","indoor_router_mount.stl",
            "native_mesh_audit.json","mecha_splicer.bundle.json","bom.csv","README.md"]]
    files += [args.output/x for x in ["market_screen.json","market_screen.csv"]]
    files += [HERE/x for x in ["market_snapshot_20261105.json","router3_indoor_mount.json"]]
    with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as pack:
        for file in files:
            pack.write(file,arcname=file.name)
    with zipfile.ZipFile(z) as pack:
        if pack.testzip() is not None:
            raise ValueError("Proof bundle ZIP failed integrity test")
    print(f"HS native CAD, real OpenSCAD mesh, scenario screen: {z}")
    print("No physical manufacture, quote, order, sale, or margin validation claimed.")


if __name__=="__main__":
    run()
