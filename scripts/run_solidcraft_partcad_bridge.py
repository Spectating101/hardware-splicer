"""Generate a conditional PartCAD package from HS's real SolidCraft demo.

Use --pc for the installed genuine PartCAD CLI; --solidcraft-cli for
independent geometry comparison after a successful PartCAD native export.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from hardware_splicer.partcad_assembly_bridge import build_partcad_assembly_package,verify_native_solidcraft_roundtrip

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_SOURCE=ROOT/"examples/solidcraft/native_trial/SOLIDCRAFT_CONCEPT.step"


def _invoke(binary:Path, argv:list[str], workspace:Path, timeout:int=120)->dict:
    result=subprocess.run(
        [str(binary),*argv],cwd=str(workspace),capture_output=True,text=True,
        timeout=timeout,check=False,
        env=None,
    )
    return {"returncode":result.returncode,"stdout_tail":result.stdout[-4500:],
            "stderr_tail":result.stderr[-1800:]}


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,default=DEFAULT_SOURCE)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--pc",type=Path)
    parser.add_argument("--solidcraft-cli",type=Path,
                        help="Optional real SolidCraft CLI; triggers PartCAD STEP export and independent geometric evaluation")
    args=parser.parse_args()
    if args.solidcraft_cli and not args.pc:
        parser.error("--solidcraft-cli requires a real --pc executable")

    record=build_partcad_assembly_package(
        solidcraft_step=args.source,
        destination=args.out,
        declared_envelope_mm={"width":120,"depth":80,"height":25},
    )
    outputs={"authority_record":record,"partcad_cli_ran":False,
             "partcad_bom_verified":False,"roundtrip_step_verified":False,
             "cad_geometry_verified":False}
    if args.pc:
        pc=args.pc.resolve(strict=True)
        common=["--no-ansi","--offline","--telemetry-type","none","--internal-state-dir",str(args.out/".pc-state")]
        parts=_invoke(pc,common+["list","parts"],args.out)
        assemblies=_invoke(pc,common+["list","assemblies"],args.out)
        bom=_invoke(pc,common+["bom","-j","conceptual_station"],args.out)
        outputs.update({"partcad_cli_ran":True,"parts":parts,"assemblies":assemblies,"bom":bom})
        assert parts["returncode"]==0 and assemblies["returncode"]==0 and bom["returncode"]==0
        m=re.search(r'(\{\s*"assembly"\s*:\s*"[^"]+"[\s\S]*?\})\s*$',bom["stdout_tail"])
        if not m:
            raise ValueError("PartCAD BOM output could not be parsed")
        parsed=json.loads(m.group(1))
        if not (parsed.get("total")==1
                and len(parsed.get("items",[]))==1
                and parsed["items"][0]["name"].endswith(":concept_envelope")
                and parsed["items"][0]["count"]==1):
            raise ValueError("PartCAD BOM differs from designed package")
        outputs["partcad_bom_verified"]=True
        # Real CAD roundtrip is optional: PartCAD may need a separate
        # sandbox and additional CAD kernel installation on first invocation.
        if args.solidcraft_cli:
            cli=args.solidcraft_cli.resolve(strict=True)
            export_dir=args.out/"roundtrip"
            export_dir.mkdir(exist_ok=True)
            result=_invoke(pc,common+[
                "export","-a","-t","step","-O",str(export_dir),"conceptual_station"
            ],args.out,timeout=240)
            outputs["partcad_export"]=result
            target=export_dir/"conceptual_station.step"
            outputs["roundtrip_step_verified"]=(
                result["returncode"]==0 and target.is_file()
                and target.stat().st_size>500
            )
            if not outputs["roundtrip_step_verified"]:
                raise RuntimeError("Native PartCAD STEP roundtrip failed")
            native_path=args.out/"roundtrip_native_solidcraft_eval.json"
            evaluated=_invoke(cli,["eval",str(target),"--json-out",str(native_path)],
                              args.out,timeout=45)
            outputs["solidcraft_eval"]=evaluated
            if evaluated["returncode"]!=0 or not native_path.exists():
                raise RuntimeError("Native SolidCraft geometry evaluator failed")
            native=json.loads(native_path.read_text())
            oracle=verify_native_solidcraft_roundtrip(
                native,record["declared_concept_envelope_mm"]
            )
            outputs["cad_geometry_verified"]=oracle["geometry_checked"]
            outputs["independent_roundtrip_geometry"]=oracle
            body=(native.get("bodies") or [{}])[0]
            outputs["native_step_name_identity_preserved"]=body.get("name")=="HS_ConceptEnvelope"
            outputs["editable_solidcraft_feature_tree_preserved_in_step"]=False
            if not outputs["cad_geometry_verified"]:
                raise ValueError("Native PartCAD/SolidCraft roundtrip geometry diverged")
    (args.out/"HS_PARTCAD_EXECUTION.json").write_text(json.dumps(outputs,indent=2,sort_keys=True)+"\n")
    print(json.dumps({
        "output":str(args.out),
        "step_hash_verified":record["solidcraft_step_source_sha256"]==record["partcad_source_step_sha256"],
        "partcad_cli_ran":outputs["partcad_cli_ran"],
        "bom_verified":outputs["partcad_bom_verified"],
        "roundtrip_step_verified":outputs["roundtrip_step_verified"],
        "geometry_verified":outputs["cad_geometry_verified"],
        "physical_inventory_quantity":0,
    },indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
