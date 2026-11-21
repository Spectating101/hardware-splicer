"""Read-only live Linux bench-enumeration proof for existing workstation.

A live OS inventory is NOT a salvage/refurbishment pass. No machine serials,
MAC addresses, hostname, IP addresses, mount paths, unique hardware IDs or user
files are read or written. Do not claim SMART/POST/stress or repairs occurred.
No commands that write to disks, reset firmware, or load-test the workstation.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import subprocess

SCHEMA="hs.read_only_linux_host_control.v1"

def summarize_cpu(text:str)->dict:
    model=next((line.split(":",1)[1].strip() for line in text.splitlines()
            if line.lower().startswith("model name") and ":" in line),None)
    processors=sum(1 for line in text.splitlines() if re.fullmatch(r"processor\s*:\s*\d+",line))
    # Model is generic CPU type, not any unique serial number.
    return {"cpu_model_generic":model,"logical_cpu_count":processors,"live_os_read_only":True}

def summarize_memory(text:str)->dict:
    m=re.search(r"^MemTotal:\s*(\d+)\s+kB$",text,re.M)
    if not m: return {"memory_total_gib":None}
    return {"memory_total_gib":round(int(m.group(1))/1048576,2)}

def summarize_disks(text:str)->dict:
    result=json.loads(text)
    rows=result.get("blockdevices",[])
    disks=[x for x in rows if x.get("type")=="disk" and isinstance(x.get("size"),int)]
    # Do not copy device name, serial, UUID, mount point, WWN or filesystem labels.
    return {"physical_block_device_count":len(disks),
            "disk_capacity_gib_sorted":sorted(round(x["size"]/2**30,1) for x in disks),
            "disk_health_verified":False,"smart_verified":False,"storage_data_wiped":False}

def run_control_probe(proc_root:Path=Path("/proc"))->dict:
    cpu=summarize_cpu((proc_root/"cpuinfo").read_text(encoding="utf-8",errors="replace"))
    mem=summarize_memory((proc_root/"meminfo").read_text(encoding="utf-8",errors="replace"))
    try:
        done=subprocess.run(["lsblk","--json","--bytes","--nodeps","-o","TYPE,SIZE"],
                    check=True,capture_output=True,text=True,timeout=6)
        disks=summarize_disks(done.stdout)
    except (OSError,subprocess.SubprocessError,ValueError):
        disks={"physical_block_device_count":None,"disk_capacity_gib_sorted":[],
               "disk_health_verified":False,"smart_verified":False,"storage_data_wiped":False}
    return {
        "schema":SCHEMA,
        "time_utc":datetime.now(timezone.utc).isoformat(),
        "control_source":"AUTHORIZED_RUNNING_OPTIPLEX_HOST_NOT_A_SALVAGED_LOT",
        "inspection_scope":"Read-only operating system self-description, not board-level validation",
        "cpu":cpu,"memory":mem,"block_storage":disks,
        "claim_gates":{"host_os_is_running":True,"real_salvage_observed":False,
            "a_salvaged_product_works":False,"physical_repair_performed":False,
            "post_recorded_on_target_salvage":False,"memory_memtest_passed":False,
            "disk_smart_passed":False,"network_ports_tested":False,
            "resale_approval":False},
        "prohibited_unearned_inferences":[
            "Reading /proc cannot establish a device's legal provenance or component health",
            "A live OS does not show a completed stress test or data sanitization",
            "The Optiplex used to run HS is NOT a salvaged physical product"
        ]
    }

def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    obs=run_control_probe()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(obs,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ACTUAL RUNNING HOST CPU",obs["cpu"]["cpu_model_generic"])
    print("LOGICAL_THREADS",obs["cpu"]["logical_cpu_count"],
          "RAM_GiB",obs["memory"]["memory_total_gib"],
          "DISK_COUNT",obs["block_storage"]["physical_block_device_count"])
    print("SALVAGE_PASS",obs["claim_gates"]["a_salvaged_product_works"],
          "PHYSICAL_REPAIR",obs["claim_gates"]["physical_repair_performed"],
          "SMART_PASS",obs["claim_gates"]["disk_smart_passed"])
if __name__=="__main__":
    main()
