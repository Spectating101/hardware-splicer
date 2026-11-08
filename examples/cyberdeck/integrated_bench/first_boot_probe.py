"""Read-only HS on-device hardware discovery gate.

NEVER powers electronics, changes boot config, runs i2c scans, or reads
private SSH material. Only an actual CM5 with TWO connected DSI modes may
proceed to a hands-on physical touch and safe-power bench; this script alone
does not authorize purchase, battery, or fabrication.
"""
from __future__ import annotations
import argparse,json,platform,re
from pathlib import Path
from datetime import datetime,timezone

HERE=Path(__file__).resolve().parent

def _safe_text(path:Path)->str:
    try:return path.read_text(errors="replace").strip().replace("\x00","")
    except (OSError,ValueError):return ""

def collect(sysfs:Path=Path("/sys"),proc:Path=Path("/proc"))->dict:
    model=_safe_text(proc/"device-tree/model")
    cpu=platform.machine()
    cm5=("Compute Module 5" in model or
         bool(re.search(r"Raspberry Pi CM5\b",model)))
    connections=[]
    for status in sorted((sysfs/"class/drm").glob("card*-*/status")):
        name=status.parent.name
        value=_safe_text(status)
        modes=_safe_text(status.parent/"modes").splitlines()
        if not name or value not in ("connected","disconnected","unknown"):
            continue
        connections.append({
          "port":name,"state":value,
          "advertised_720x1280":any(m.strip()=="720x1280" for m in modes),
          "mode_count":len(modes),
          "dsi_port":("-DSI-" in name or "DSI" in name),
        })
    # Kernel-reported input names alone don't establish independent touch.
    # They are discovered for human follow-up; no automatic green release.
    input_blobs=_safe_text(proc/"bus/input/devices").split("\n\n")
    inputs=[]
    for blob in input_blobs:
        names=re.findall(r'^N:\s+Name="([^"]+)"',blob,re.M)
        handlers=re.findall(r'^H:\s+Handlers=(.*)$',blob,re.M)
        if not names or not handlers:continue
        if ("touch" in names[0].lower() or "goodix" in names[0].lower()
                or "ft5" in names[0].lower()) and "event" in handlers[0]:
            inputs.append({"name":names[0][:120],
                 "event_handlers":[x for x in handlers[0].split() if x.startswith("event")]})
    connected_dsi=[c for c in connections if c["dsi_port"] and c["state"]=="connected"]
    two_dsi_modes=sum(1 for c in connected_dsi if c["advertised_720x1280"])>=2
    blockers=[]
    if not cm5:blockers.append("host_is_not_Raspberry_Pi_Compute_Module_5")
    if not two_dsi_modes:blockers.append("two_720x1280_physical_DSI_modes_not_detected")
    if len(inputs)<2:blockers.append("two_independent_touch_event_devices_not_detected")
    # The Linux input names/DRM output modes alone do NOT prove exact vendor
    # overlays, touch-coordinate mapping, power, or hinge durability.
    blockers.extend([
       "physical_touch_coordinate_mapping_requires_manual_per_panel_test",
       "measured_power_and_thermal_load_not_recorded",
       "mechanical_and_battery_qualification_not_performed",
    ])
    return {
       "schema":"hs.cm5_two_DSI_first_boot_probe.v1",
       "date":datetime.now(timezone.utc).date().isoformat(),
       "source":"read_only_actual_Linux_sysfs_and_procfs",
       "processor_architecture":cpu,
       "board_model":model or "not_available_x86_non_device_tree",
       "cm5_identified_from_device_tree":cm5,
       "drm_connectors":connections,
       "drm_two_DSI_ports_with_720x1280":two_dsi_modes,
       "touch_like_kernel_inputs":inputs,
       "has_two_distinct_touch_like_handlers":len(inputs)>=2,
       "ready_for_manual_powered_display_validation":cm5 and two_dsi_modes and len(inputs)>=2,
       "tested_display_color_patterns":False,
       "tested_each_touch_coordinate_input":False,
       "tested_CM5_compile_thermal_and_power":False,
       "mobile_battery_pack_safe":False,
       "ready_for_handheld_fabrication":False,
       "no_dsi_or_touch_emulation_substituted":True,
       "blockers":blockers,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args()
    report=collect()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"cm5":report["cm5_identified_from_device_tree"],
       "physical_DSI_pair_modes":report["drm_two_DSI_ports_with_720x1280"],
       "two_touch_inputs":report["has_two_distinct_touch_like_handlers"],
       "hardware_powered_and_qualified":False,"blockers":report["blockers"]},indent=2))

if __name__=="__main__":main()
