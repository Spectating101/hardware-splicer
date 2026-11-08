"""HS canonical release gate for one integrated dual-surface bench.

Pass only what the machine ACTUALLY did: two independent Chrome surfaces,
separate input/output WS roles, and real sandboxed OpenSSH actions. Real CM5,
both DSI/touch controllers, power, thermal and fold packaging are absent.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path

from .machine_project import (
 AuthorityState,EvidenceRef,MachineProject,ReleaseState,Requirement,
 RequirementKind,VerificationMethod,VerificationStatus,VerificationType,
)

SCHEMA="hs.integrated_dual_portrait_prototype_gate.v1"


def _need(v,why):
    if not v:raise ValueError("HS integration gate refused: "+why)


def evaluate(bench:dict,hardware:dict,manifest:dict,upper:bytes,lower:bytes)->dict:
    _need(bench.get("schema")=="hs.two_independent_surface_local_ssh_integration.v1"
          and bench.get("result")=="TWO_SEPARATE_BROWSER_SURFACES_TO_REAL_OPENSSH_PASSED",
          "real cross-surface browser/SSH experiment absent")
    _need(all(bench.get("security",{}).values())
          and len(bench.get("security",{}))==4,
          "missing access control measurements")
    p=bench.get("browser",{})
    for name in ("two_separate_720x1280_browser_pages","two_distinct_websockets",
                  "symbol_layer_to_real_shell","tmux_detach",
                  "terminal_has_no_input_API","keyboard_has_no_output_API"):
        _need(p.get(name) is True,name)
    _need(p.get("real_nano_file")=="hs dual" and p.get("lower_touch_events",0)>=20
          and p.get("upper_output_bytes",0)>=300 and p.get("javascript_errors")==[],
          "real Nano/editor/terminal output proof absent")
    _need(p.get("physical_dual_DSI_tested") is False
          and bench.get("actual_CM5_tested") is False
          and bench.get("actual_DSI_pair_tested") is False
          and bench.get("battery_power_applied") is False
          and bench.get("fabrication_authorized") is False,
          "browser result cannot be promoted to a physical CM5 build")
    for png in (upper,lower):
        _need(png[:8]==b"\x89PNG\r\n\x1a\n"
              and len(png)>10_000
              and struct.unpack(">II",png[16:24])==(720,1280),
              "no authentic sized Chrome screenshot for both surfaces")
    _need(hardware.get("schema")=="hs.cm5_two_DSI_first_boot_probe.v1"
          and hardware.get("source")=="read_only_actual_Linux_sysfs_and_procfs",
          "real device discovery required")
    _need(hardware.get("cm5_identified_from_device_tree") is False
          and hardware.get("drm_two_DSI_ports_with_720x1280") is False
          and hardware.get("has_two_distinct_touch_like_handlers") is False
          and hardware.get("ready_for_handheld_fabrication") is False,
          "this host does NOT contain qualified dual DSI hardware")
    _need(manifest.get("schema")=="hs.cm5_dual_portrait_bench_contract.v1",
          "missing source-backed integrated bench parts")
    t=manifest["unverified_and_blocking"]
    _need(len(t)>=8 and all(value is False for value in t.values()),
          "cannot fabricate hardware validation facts")
    _need(all(v is False for v in manifest["release"].values()),
          "unapproved battery/build/procurement authority")
    _need(manifest["bench"]["board_dimensions_mm"]==[160,90]
          and manifest["bench"]["display"]["quantity"]==2,
          "real CM5IO oversized bench board and screen count required")

    verification=[
      ("separate-surfaces","Two independent browser windows, 720x1280 each, connected to independent WS roles",RequirementKind.FUNCTIONAL,VerificationStatus.PASSED),
      ("real-terminal","Touch on lower window runs shell actions in upper xterm via OpenSSH",RequirementKind.FUNCTIONAL,VerificationStatus.PASSED),
      ("actual-editing","Two browser surfaces edit a real file in Nano",RequirementKind.FUNCTIONAL,VerificationStatus.PASSED),
      ("tmux-controls","Lower touch controls real tmux detach",RequirementKind.FUNCTIONAL,VerificationStatus.PASSED),
      ("local-security","Wrong token/cross origin and blind input connection rejected",RequirementKind.SAFETY,VerificationStatus.PASSED),
      ("physical-cm5","Boot real Raspberry Pi CM5 on its official carrier",RequirementKind.FUNCTIONAL,VerificationStatus.BLOCKED),
      ("dual-720x1280-DSI","Both physical portrait panels have independent DRM outputs",RequirementKind.FUNCTIONAL,VerificationStatus.BLOCKED),
      ("touch-mapping","Two physical touch digitizers independently map to each display",RequirementKind.INTERFACE,VerificationStatus.PLANNED),
      ("local-workstation","Run native on-device Git/Python/compiler workload and measure memory, power and thermal",RequirementKind.PERFORMANCE,VerificationStatus.PLANNED),
      ("hinge-screen","Complete protected screen, cable and enclosure product, not virtual glass",RequirementKind.CONSTRAINT,VerificationStatus.FAILED),
      ("power","Protected and qualified battery, correct power delivery and thermal safety",RequirementKind.SAFETY,VerificationStatus.PLANNED),
      ("cost","Complete verified delivered BOM with carrier, screens, enclosure, power and rework",RequirementKind.CONSTRAINT,VerificationStatus.PLANNED),
    ]
    ids=[f"r-{rid}" for rid,_,_,s in verification if s==VerificationStatus.PASSED]
    evidence=[
      EvidenceRef(evidence_id="real-two-pages",kind="Real Chrome/Playwright + SSH interaction",
          basis="Two independent Chrome windows, WS role separation, sandboxed OpenSSH, Nano and tmux",
          ref="evidence/dual_surface_integration.json",authority=AuthorityState.MEASURED,
          simulated=False,supports=ids,metadata={"simulated_touch":True,"actual_CM5":False}),
      EvidenceRef(evidence_id="two-browser-pngs",kind="Chrome screenshots",
          basis="Separate upper and lower 720x1280 screenshots, not photographed hardware",
          ref="evidence/",authority=AuthorityState.OBSERVED,
          simulated=False,supports=["r-separate-surfaces"]),
    ]
    project=MachineProject(project_id="HS-CYBERDECK-INTEGRATED-BENCH-V1",
       name="HS CM5 two-portrait first powered development bench",
       purpose="Build practical personal two-screen Linux workstation, no product company",
       requested_release_state=ReleaseState.BUILD_READY,
       requirements=[
         Requirement(requirement_id=f"r-{rid}",statement=statement,
             kind=kind,authority=AuthorityState.DECLARED,
             verification_method_ids=[f"v-{rid}"])
         for rid,statement,kind,st in verification],
       verifications=[
         VerificationMethod(verification_id=f"v-{rid}",name=f"Check {rid}",
             method_type=VerificationType.DEMONSTRATION if st==VerificationStatus.PASSED
                         else VerificationType.TEST,status=st,
             requirement_ids=[f"r-{rid}"],
             evidence_ids=["real-two-pages"] if st==VerificationStatus.PASSED else [])
         for rid,statement,kind,st in verification],
       evidence=evidence,
       metadata={"actual_CM5_connected":False,"battery_power_applied":False,
                 "commercialization_required":False,
                 "software_BENCH_not_physical_product":True},
    )
    release=project.assess_release()
    _need(not release.allowed and len(release.blockers)>0,
          "simulated screen panes cannot authorize product build")
    return {
      "schema":SCHEMA,
      "status":"DUAL_INDEPENDENT_SOFTWARE_SURFACES_PASS_CM5_HARDWARE_GATE_BLOCKED",
      "verified_real_software_requirements":ids,
      "physical_component_verified":False,
      "connected_cm5_detected":False,
      "two_720x1280_physical_DSI_displays":False,
      "hardware_fabrication_authorized":False,
      "battery_wiring_authorized":False,
      "first_physical_bench_requires":[
        "CM5 + manufacturer CM5IO board + known regulated USB-C 5V5A",
        "one supported DSI LCD (D) + correct cable and single panel check",
        "second LCD (D) + DSI0/DSI1 simultaneous output and independent touch mapping",
        "local Linux compiler/SSH session, fan, power and sustained thermal evidence",
      ],
      "release_assessment":release.model_dump(mode="json"),
      "machine_project":project.model_dump(mode="json"),
    }

def run(root:Path,out:Path)->dict:
    paths={
       "bench":root/"evidence/dual_surface_integration.json",
       "hardware":root/"evidence/optiplex_first_boot_probe.json",
       "manifest":root/"bench_contract.json",
       "upper":root/"evidence/upper_terminal_720x1280.png",
       "lower":root/"evidence/lower_keyboard_720x1280.png",
    }
    p={k:path.read_bytes() for k,path in paths.items()}
    result=evaluate(json.loads(p["bench"]),json.loads(p["hardware"]),
                    json.loads(p["manifest"]),p["upper"],p["lower"])
    result["provenance_sha256"]={k:hashlib.sha256(v).hexdigest() for k,v in p.items()}
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n")
    return result

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--root",required=True,type=Path)
    cli.add_argument("--out",required=True,type=Path)
    args=cli.parse_args()
    r=run(args.root,args.out)
    print(json.dumps({"status":r["status"],
      "real_software_checks_passed":len(r["verified_real_software_requirements"]),
      "manufacturing_authorized":r["hardware_fabrication_authorized"],
      "release_blockers":len(r["release_assessment"]["blockers"])},indent=2))

if __name__=="__main__":main()
