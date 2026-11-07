"""Native HS MachineProject acceptance of real touch-to-SSH loopback workflow.

Grounded on captured actual OpenSSH, headless Chrome, Nano and tmux evidence.
Never upgrades browser and loopback testing to physical screen/power readiness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

from .machine_project import (
    AuthorityState, EvidenceRef, MachineProject, ReleaseState, Requirement,
    RequirementKind, VerificationMethod, VerificationStatus, VerificationType,
)

SCHEMA="hs.pocket_terminal_real_ssh_touch_benchmark.v1"
OUT="hardware_splicer.pocket_terminal_workflow_acceptance.v1"


def _digest(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _need(test:bool,message:str)->None:
    if not test:raise ValueError("HS workflow evidence invalid: "+message)


def evaluate(benchmark:dict,previous:dict,screenshot:bytes)->dict:
    _need(benchmark.get("schema")==SCHEMA,"benchmark schema")
    _need(benchmark.get("result")=="SOFTWARE_WORKFLOW_ON_REAL_SANDBOXED_LOCAL_SSH_PASSED",
          "no runtime-reported real SSH workflow pass")
    _need(benchmark.get("actual_physical_cyberdeck_built") is False
          and benchmark.get("actual_CM4_or_DSI_tested") is False
          and benchmark.get("marketing_or_company_required") is False,
          "physical product/business status falsely promoted")
    security=benchmark.get("security",{})
    for k in ("no_token_http_rejected","invalid_token_http_rejected",
              "cross_origin_websocket_rejected","no_token_websocket_rejected",
              "wrong_pinned_host_key_rejected_before_commands",
              "openssh_only_listens_on_loopback","filesystem_home_and_network_namespace_isolated"):
        _need(security.get(k) is True,k)
    _need(security.get("reused_user_ssh_keys") is False,"user key reuse")
    w=benchmark.get("workflow",{})
    _need(w.get("connection_and_command_on_real_sshd") is True,
          "faked backend")
    _need(w.get("screen_mocked_hardware") is True,
          "browser viewport is not physical dual touch")
    _need(w.get("network")=="127.0.0.1 local OpenSSH only",
          "only loopback was tested")
    _need(w.get("viewport_px")==[1280,1440]
          and w.get("two_surface_layout")=="one top terminal, one lower touch-keyboard",
          "untracked screen geometry")
    _need(w.get("virtual_key_touches",0)>=20,
          "too few actual Playwright tap events")
    for k in ("tmux_started_and_ctrl_b_d_detached",
              "nano_file_saved_using_touch_ctrl_o_ctrl_x",
              "ctrl_c_interrupts_running_command",
              "same_sandbox_workspace_file_survives_new_ssh_connection"):
        _need(w.get(k) is True,k)
    _need(w.get("nano_arrow_insertion_file")=="axbc",
          "arrow input did not alter a real file")
    _need(w.get("same_tmux_server_survives_reconnect") is False,
          "fixture-only tmux persistence cannot be claimed")
    _need(w.get("console_js_errors")==[],"browser JS errors")
    ms=w.get("input_output_loopback_ms",{})
    samples=ms.get("samples",[])
    _need(isinstance(samples,list) and len(samples)>=8
          and all(type(n) in (float,int) and 0<n<5000 for n in samples),
          "no measured 8+ localhost SSH probe samples")
    _need("NOT WiFi/CM4/touch-panel latency" in ms.get("interpretation",""),
          "bench RTT must not become display, WiFi, or device performance")
    _need(w.get("screenshot")=="evidence/touch_ssh_bench.png","unrecognized browser screenshot path")
    _need(len(screenshot)>1000 and screenshot[:8]==b"\x89PNG\r\n\x1a\n",
          "browser visual evidence must be a valid PNG")
    wd,ht=struct.unpack(">II",screenshot[16:24])
    _need([wd,ht]==w["viewport_px"],"screenshot must actually match measured browser geometry")

    _need(previous.get("schema")=="hs.cm4_two_panel_feasibility_result.v1",
          "upstream source must be HS exact-panel feasibility report")
    _need(previous["display"]["vendor_panel_software_gate"]=="BLOCKED",
          "actual CM4/DSI driver was not tested")
    _need(previous["protected_pack_comparison"]["new_protected_5p2mm_pack_nominal_lower_bound_mm"]==18.928,
          "physical dimension blockers cannot disappear by importing UX proof")
    _need(not previous["release"]["component_purchase_authorized"]
          and not previous["release"]["manufacturing_authorized"],
          "prior HS fabrication is not authorized")

    reqs=[
       ("real-ssh","OpenSSH host-key pinning and isolated authorized terminal commands",
        RequirementKind.SAFETY,VerificationStatus.PASSED),
       ("touch","Browser on-screen lower-panel key events actually reach upper xterm.js",
        RequirementKind.FUNCTIONAL,VerificationStatus.PASSED),
       ("editor","Real Nano saves file using Ctrl+O, Ctrl+X and arrow edits",
        RequirementKind.FUNCTIONAL,VerificationStatus.PASSED),
       ("multiplexer","Real tmux Ctrl+B and D detaches live session",
        RequirementKind.FUNCTIONAL,VerificationStatus.PASSED),
       ("reconnect","SSH reconnection preserves sandboxed files",
        RequirementKind.FUNCTIONAL,VerificationStatus.PASSED),
       ("two-physical-panels","Independent real touchscreens run upper terminal and lower keyboard",
        RequirementKind.FUNCTIONAL,VerificationStatus.PLANNED),
       ("native-dual-dsi","CM4 DSI0 and DSI1 initialize exact Winstar panels and GT928 inputs",
        RequirementKind.INTERFACE,VerificationStatus.BLOCKED),
       ("fitting","Full qualified mechanical and bonded screen stack <=155x80x18mm",
        RequirementKind.CONSTRAINT,VerificationStatus.FAILED),
       ("cell","Verified protected pack, charging, boost drive and thermal under load",
        RequirementKind.SAFETY,VerificationStatus.PLANNED),
       ("ergonomics","Human editing on 5-inch physical glass during extended use",
        RequirementKind.PERFORMANCE,VerificationStatus.PLANNED),
       ("field-network","Authenticated VPN/wireless SSH to a persistent remote Optiplex tmux",
        RequirementKind.SAFETY,VerificationStatus.PLANNED),
       ("delivered-cost","Real entire Taiwan build bill of materials, assembly and rework estimate",
        RequirementKind.CONSTRAINT,VerificationStatus.PLANNED),
    ]
    ids=[f"r-{i}" for i,_,_,st in reqs if st==VerificationStatus.PASSED]
    evidence=[
        EvidenceRef(evidence_id="real-loopback",kind="Chrome/Playwright and OpenSSH measured runtime",
            basis="Browser key taps + actual OpenSSH via localhost with pinned host key and bwrap, saved Nano files, tmux control",
            ref="evidence/bench_results.json",authority=AuthorityState.MEASURED,
            simulated=False,supports=ids,
            metadata={"loopback_only":True,"not_hardware_tested":True}),
        EvidenceRef(evidence_id="browser-screenshot",kind="Chrome screenshot",
            basis="Actual xterm.js upper viewport and lower on-screen keyboard screenshot from local test",
            ref="evidence/touch_ssh_bench.png",authority=AuthorityState.OBSERVED,
            simulated=False,supports=["r-touch"],
            metadata={"screens_are_browser_areas_not_physical_panels":True}),
        EvidenceRef(evidence_id="prior-packaging",kind="HS prior native CGAL and electrical qualification",
            basis="Previous 18mm failure and exact DSI vendor missing driver proof",
            ref="../electrical_feasibility/report.json",authority=AuthorityState.PROPOSED,
            simulated=True,supports=["r-fitting","r-native-dual-dsi"]),
    ]
    mp=MachineProject(
        project_id="HS-POCKET-TERMINAL-REAL-SSH-TOUCH-MVP",
        name="HS realistic touch-SSH workflow proof",
        purpose="Value engineer a useful two-screen cyberdeck without commercialization requirements",
        requested_release_state=ReleaseState.BUILD_READY,
        requirements=[
            Requirement(requirement_id=f"r-{rid}",statement=statement,
               kind=kind,source="user" if rid in {"touch","two-physical-panels"} else "HS verification",
               authority=AuthorityState.DECLARED,verification_method_ids=[f"v-{rid}"])
            for rid,statement,kind,status in reqs
        ],
        verifications=[
            VerificationMethod(verification_id=f"v-{rid}",name=f"Validate {rid}",
                 method_type=VerificationType.DEMONSTRATION if status==VerificationStatus.PASSED
                             else VerificationType.TEST,
                 status=status,requirement_ids=[f"r-{rid}"],
                 evidence_ids=["real-loopback"] if status==VerificationStatus.PASSED else [])
            for rid,statement,kind,status in reqs
        ],
        evidence=evidence,
        metadata={
            "real_ssh_not_stub":True,"local_loopback_only":True,
            "actual_hardware_fabricated":False,"commercialization_required":False,
            "measured_median_ms":ms["median"],
        },
    )
    release=mp.assess_release()
    _need(len(release.blockers)>0 and not release.allowed,
          "source does not authorize a physical build")

    return {
      "schema":OUT,
      "status":"SOFTWARE_INTERACTION_BENCH_ACCEPTED_PHYSICAL_BUILD_BLOCKED",
      "real_software_requirements_passed":ids,
      "physical_panel_and_power_requirements_passed":[],
      "loopback_echo_median_ms":ms["median"],
      "pocket_hardware_verified":False,
      "fabrication_authorized":False,
      "procurement_authorized":False,
      "machine_project":mp.model_dump(mode="json"),
      "release_assessment":release.model_dump(mode="json"),
      "unresolved_next":"Exact CM4 dual-DSI bring-up and real physical touch on supported panel; then ergonomic test and measured full BOM",
    }


def main()->None:
    cli=argparse.ArgumentParser()
    cli.add_argument("--benchmark",required=True,type=Path)
    cli.add_argument("--prior",required=True,type=Path)
    cli.add_argument("--screenshot",required=True,type=Path)
    cli.add_argument("--out",required=True,type=Path)
    args=cli.parse_args()
    report=evaluate(json.loads(args.benchmark.read_text()),
                    json.loads(args.prior.read_text()),args.screenshot.read_bytes())
    report["provenance"]={
        "benchmark_sha256":_digest(args.benchmark),
        "prior_HS_electrical_sha256":_digest(args.prior),
        "browser_screenshot_sha256":_digest(args.screenshot),
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"status":report["status"],
        "passed_real_software_requirements":len(report["real_software_requirements_passed"]),
        "blocked_release_reasons":len(report["release_assessment"]["blockers"]),
        "physical_fabrication_authorized":report["fabrication_authorized"]},indent=2))


if __name__=="__main__":
    main()
