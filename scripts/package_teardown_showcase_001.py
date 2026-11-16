#!/usr/bin/env python3
"""Package ONLY native-browser-verified Teardown HTML into the actual HS React UI."""
import argparse, json, shutil, hashlib
from pathlib import Path

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--public",type=Path,required=True)
    a=p.parse_args()
    proof=json.loads((a.source/"TEARDOWN_NATIVE_ACCEPTANCE.json").read_text())
    html=a.source/"dist/machine.html"
    visual=json.loads((a.source/"BROWSER_PROOF.json").read_text())
    inp=json.loads((a.source/"TEARDOWN_INPUT.json").read_text())
    if not (proof.get("native_browser_executed") is True and
        proof.get("assembled_first_hero_and_guided_stages") is True and
        proof.get("actual_cad_pixels_observed",0)>=400 and
        proof.get("physical_release_authorized") is False and
        proof.get("native_html_sha256")==sha(html) and
        visual.get("source_spec_sha256")==proof.get("source_spec_sha256") and
        inp.get("source_spec_sha256")==proof.get("source_spec_sha256")):
        raise SystemExit("REFUSED: No visually verified source-bound engineering explorer")
    public=a.public
    if public.exists() and any(public.iterdir()):
        raise SystemExit("REFUSED: Existing showcase artifacts cannot be silently overwritten")
    public.mkdir(parents=True,exist_ok=True)
    shutil.copy2(html,public/"machine.html")
    manifest={
        "schema_version":"hardware_splicer.showcase_bundle.v1",
        "product_id":inp["product_id"],"source_spec_sha256":inp["source_spec_sha256"],
        "parts":len(inp["parts"]),"native_browser_executed":True,
        "actual_cad_pixels_observed":proof["actual_cad_pixels_observed"],
        "machine_html_sha256":sha(public/"machine.html"),
        "physical_release_authorized":False
    }
    (public/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    print(json.dumps(manifest,indent=2))
if __name__=="__main__":main()
