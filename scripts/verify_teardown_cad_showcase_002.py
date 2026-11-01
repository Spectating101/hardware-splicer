#!/usr/bin/env python3
"""Independently compare screenshot pixels, GLB provenance and closed physical gates."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
from PIL import Image

def hash_file(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def check(ok,message):
    if not ok:raise ValueError("HS visual showroom gate REFUSED: "+message)

def compare(a,b):
    with Image.open(a) as first, Image.open(b) as second:
        left=np.asarray(first.convert("RGB"),dtype=np.int16)
        right=np.asarray(second.convert("RGB"),dtype=np.int16)
    check(left.shape==right.shape,"screenshots do not share viewport dimensions")
    changed=np.any(np.abs(left-right)>22,axis=2)
    return round(float(changed.mean()),5)

def validate(root:Path):
    root=Path(root)
    product=json.loads((root/"SHOWCASE_INPUT.json").read_text())
    receipt=json.loads((root/"SHOWCASE_RECEIPT.json").read_text())
    proof=json.loads((root/"BROWSER_PROOF.json").read_text())
    html=root/"dist/machine.html"
    glb=root/"machine/machine.glb"
    js=root/"machine/main.js"
    css=root/"machine/style.css"
    check(product["schema_version"]=="hardware_splicer.teardown_cad_showcase.v1"
          and product["visualization_only"] is True
          and product["real_step_surface_geometry"] is True
          and product["fabrication_authorized"] is False
          and product["physical_fit_verified"] is False
          and product["real_operation_simulated"] is False
          and product["release_blockers_count"]>=6,
          "source CAD geometry authority was promoted")
    check(product["source_spec_sha256"]==receipt["source_spec_sha256"]==proof["source_spec_sha256"]
          and product["product_id"]==proof["product_id"],"source identity mismatch")
    check(hash_file(root/"SHOWCASE_INPUT.json")==receipt["input_sha256"]
          and hash_file(glb)==product["glb_sha256"]==receipt["glb_sha256"]
          and hash_file(js)==receipt["main_js_sha256"]
          and hash_file(css)==receipt["theme_sha256"],
          "native CAD, JS or theme has changed after source derivation")
    check(len(product["parts"])==receipt["part_count"]==proof["part_count"]
          and all(p["mesh_triangles"]>=12 and p["mesh_vertices"]>=8
                  and p["source_step_verified"] for p in product["parts"]),
          "incomplete native CAD surface coverage")
    check(html.is_file() and html.stat().st_size>100000
          and hash_file(html)==proof["html_sha256"]
          and product["source_spec_sha256"].encode() in html.read_bytes(),
          "upstream native offline bundle absent or stale")
    check(proof["upstream_teardown_used"] is True
          and proof["native_browser_rendered"] is True
          and proof["real_step_surface_geometry"] is True
          and proof["visual_pixel_changes_verified"] is True
          and proof["mobile_viewport_usable"] is True
          and proof["no_external_requests"] is True
          and proof["no_browser_exceptions"] is True
          and proof["real_operation_simulated"] is False
          and receipt["release_authorized"] is False,
          "browser acceptance or physical gate falsified")
    shots=proof["screenshots"]
    checks={
        "assembled_exploded":("assembled","exploded",0.003),
        "assembled_top":("assembled","top",0.003),
        "assembled_section":("assembled","section",0.001),
        "assembled_isolate":("assembled","isolate",0.001),
    }
    differences={}
    for key,(a,b,minimum) in checks.items():
        first=root/"screens"/(a+".png")
        second=root/"screens"/(b+".png")
        check(first.is_file() and second.is_file()
              and hash_file(first)==shots[a] and hash_file(second)==shots[b],
              "missing or tampered source-bound visual result "+key)
        value=compare(first,second)
        check(value>minimum, "visual state changed only in code, not pixels: "+key+" "+str(value))
        differences[key]=value
    mobile=root/"screens/mobile.png"
    check(hash_file(mobile)==shots["mobile"],"mobile viewport proof missing or changed")
    with Image.open(root/"screens/assembled.png") as image:
        rgb=np.asarray(image.convert("RGB"),dtype=np.int16)
    brightness=np.max(rgb,axis=2)
    bright_fraction=float(np.count_nonzero(brightness>65)/brightness.size)
    check(bright_fraction>0.02,"actual machine viewer essentially blank")
    result={
        "schema_version":"hardware_splicer.teardown_visual_acceptance.v2",
        "product_id":product["product_id"],"source_spec_sha256":product["source_spec_sha256"],
        "real_step_glb_sha256":product["glb_sha256"],
        "real_step_geometry_verified_in_browser":True,
        "screenshots_compared_by_actual_RGB_pixels":True,
        "pixel_change_fractions":differences,
        "bright_fraction":round(bright_fraction,5),
        "mobile_viewport_tested":True,
        "real_motion_physics_verified":False,
        "physical_release_authorized":False
    }
    (root/"VISUAL_ACCEPTANCE.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    try:print(json.dumps(validate(a.out),indent=2))
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print(str(exc),file=sys.stderr)
        raise SystemExit(1)
