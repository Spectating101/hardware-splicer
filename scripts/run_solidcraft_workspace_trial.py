"""Generate a concept-only SolidCraft script; optionally execute pinned CLI.

No purchase, GPIO, physical motor control or fabrication. Requires exact
explicit concept_envelope_mm values. CLI execution is sandboxed to output
directory and does not grant physical manufacturing approval.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess

from hardware_splicer.functional_architecture import derive_functional_architecture
from hardware_splicer.solidcraft_workspace_bridge import build_solidcraft_workspace_handoff


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--case",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--cli",type=Path,help="Optional existing SolidCraft 0.16.2 CLI binary, no automatic download or install")
    args=parser.parse_args()
    case=json.loads(args.case.read_text(encoding="utf-8"))
    intake=case.get("intake") or {}
    functional=derive_functional_architecture(intake)
    handoff=build_solidcraft_workspace_handoff(intake,functional)
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"SOLIDCRAFT_HANDOFF.json").write_text(json.dumps(handoff,indent=2,ensure_ascii=False)+"\n")
    if not handoff["script_ready"]:
        print(json.dumps({"ready":False,"blocker":handoff["blocker"]}))
        return 0
    path=args.out/"SOLIDCRAFT_CONCEPT.commands.json"
    path.write_text(json.dumps(handoff["command_script"],indent=2)+"\n")
    result={"ready":True,"script":str(path),"native_cli_executed":False,"physical_design":False}
    if args.cli:
        cli=args.cli.resolve(strict=True)
        step=args.out/"SOLIDCRAFT_CONCEPT.step"
        editable=args.out/"SOLIDCRAFT_CONCEPT.solidcraft"
        # The command script contains ONLY four predetermined CAD actions
        # on an empty design. Never accept arbitrary source page commands.
        run=subprocess.run(
            [str(cli),"run",str(path),"--out",str(step),"--save",str(editable),"--results"],
            cwd=str(args.out),timeout=40,capture_output=True,text=True,check=False,
        )
        result.update({"native_cli_executed":True,"returncode":run.returncode,
                       "stdout_tail":run.stdout[-1500:],"stderr_tail":run.stderr[-1500:]})
        result["model_exists"]=step.exists() and step.stat().st_size>100
        result["editable_design_exists"]=editable.exists() and editable.stat().st_size>100
        result["editable_design_path"]=str(editable)
        if run.returncode!=0 or not result["model_exists"] or not result["editable_design_exists"]:
            result["ready"]=False
    (args.out/"SOLIDCRAFT_EXECUTION.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    return 0 if result["ready"] else 2


if __name__=="__main__":
    raise SystemExit(main())
