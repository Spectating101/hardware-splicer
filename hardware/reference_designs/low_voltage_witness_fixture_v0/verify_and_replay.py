#!/usr/bin/env python3
"""Native KiCad + ngspice + real INA228 decoder + optional PLRS-6 FIXTURE replay.

Physical board, shunts, calibration and real instruments: NOT PRESENT.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
HS_ROOT = HERE.parents[2]
sys.path.insert(0, str(HS_ROOT / "src"))
from hardware_splicer.dc_measurement_station import StationSpec, design_station, write_design, json_bytes
from hardware_splicer.ina228_fixture import FixtureClock, FixtureI2C
from hardware_splicer.ina228_logger import INA228, capture
import generate_schematic as schematic

NAME = "low_voltage_witness_fixture_v0"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd: list[str], cwd: Path, *, env=None, timeout=35) -> str:
    result = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{cmd} exit {result.returncode}\n{result.stdout}\n{result.stderr}")
    return result.stdout + result.stderr


def original_source_check():
    # Exact electrical source pins and connected nets, independent of the PCB tool.
    root = ET.parse(HERE / "netlist.xml").getroot()
    actual = {}
    for net in root.findall("./nets/net"):
        for node in net.findall("node"):
            key = (node.get("ref"), node.get("pin"))
            if key in actual:
                raise ValueError("schematic assigned pad twice: " + repr(key))
            actual[key] = net.get("name").removeprefix("/")
    expected = {(ref, pin): net for ref, pins in schematic.NETS.items()
                for pin, net in pins.items()}
    if actual != expected:
        raise ValueError("schematic netlist differs from separately declared power/Kelvin map")
    import pcbnew as pcb
    board = pcb.LoadBoard(str(HERE / (NAME + ".kicad_pcb")))
    pads = {}
    for component in board.GetFootprints():
        if component.GetReference().startswith("H"):
            continue
        for pd in component.Pads():
            pads[(component.GetReference(), pd.GetNumber())] = pd.GetNetname().removeprefix("/")
    if pads != expected:
        raise ValueError("physical PCB pad net differs from schematic/pin map")
    # Electrical safety-relevant: J3 is a series current path, never a bypass.
    if actual[("J3","1")] == actual[("J3","2")]:
        raise ValueError("INA228 carrier path was shorted")
    if {actual[("R1",n)] for n in ("1","2","3","4")} != \
       {"ADA_OUT", "REF_SENSE_P", "REF_SENSE_N", "LOAD_PLUS"}:
        raise ValueError("reference shunt power/Kelvin paths shorted")
    bounds = board.GetBoardEdgesBoundingBox()
    if tuple(round(x/1e6,2) for x in (bounds.GetWidth(),bounds.GetHeight())) != (125.05,58.05):
        raise ValueError("board size unexpectedly changed")
    return board


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",required=True,type=Path,help="fresh output directory")
    parser.add_argument("--pl-root",type=Path,help="optional Policy Lab checkout containing PLRS-6 bridge")
    args=parser.parse_args()
    out=args.out.resolve()
    out.mkdir(parents=True,exist_ok=False)
    schematic.generate()
    run(["kicad-cli","sch","export","netlist",str(HERE/(NAME+".kicad_sch")),
         "--format","kicadxml","-o",str(HERE/"netlist.xml")],HERE)
    erc=run(["kicad-cli","sch","erc","--exit-code-violations","-o",str(out/"erc.txt"),
             str(HERE/(NAME+".kicad_sch"))],HERE)
    drc=run(["kicad-cli","pcb","drc","--schematic-parity","--exit-code-violations",
             "-o",str(out/"drc.txt"),str(HERE/(NAME+".kicad_pcb"))],HERE)
    if "ERC messages: 0" not in (out/"erc.txt").read_text():
        raise RuntimeError("native KiCad ERC not clean")
    if not all(t in (out/"drc.txt").read_text() for t in
               ("Found 0 DRC violations","Found 0 unconnected pads","Found 0 Footprint errors")):
        raise RuntimeError("native KiCad PCB DRC, connectivity or parity not clean")
    original_source_check()

    spice_output=run(["ngspice","-b",str(HERE/"spice_low_voltage_witness.cir")],HERE)
    (out/"spice-result.txt").write_text(spice_output)
    def parse(label):
        m=re.search(r"(?m)^"+re.escape(label)+r"\s*=\s*([-+0-9.eE]+)",spice_output)
        if not m:raise RuntimeError("SPICE result missing "+label)
        return float(m.group(1))
    pwr=parse("load_power_w")
    voltage=parse("v(load_plus)")
    amps=-parse("i(v_src)")
    expected_i=5/(10+.05+.015+.010)
    if not all(math.isclose(actual,expected,rel_tol=3e-6) for actual,expected in [
        (amps,expected_i),(voltage,10*expected_i),(pwr,10*expected_i**2)]):
        raise RuntimeError("SPICE and independent series-resistance arithmetic disagree")
    expected_wh=pwr*180/3600

    spec=StationSpec.from_dict(json.loads((HERE/"station-spec-5v.json").read_text()))
    design=design_station(spec)
    if (not design["design_checks_passed"] or design["physical_status"]!="UNBUILT_UNVERIFIED"
        or spec.shunt_ohm!=.015 or spec.reference_shunt_ohm!=.01):
        raise RuntimeError("design did not preserve 15mOhm primary / 10mOhm separate reference")
    write_design(out/"station",spec)

    clock=FixtureClock("2026-11-19T23:59:59Z")
    bus=FixtureI2C(clock,shunt_ohm=spec.shunt_ohm,voltage_v=voltage,current_a=amps)
    captured=capture(INA228(bus,spec,clock=clock),out/"primary",
        samples=183,period_seconds=1,
        clock_source="Synthetic fixture UTC only; NO physical clock",clock=clock)
    if captured["capture_kind"]!="TEST_FIXTURE" or captured["status"]!="COMPLETE":
        raise RuntimeError("fake I2C decoder failed or falsely granted physical status")
    first=datetime(2026,11,19,23,59,59,tzinfo=timezone.utc)
    with (out/"reference-fixture.csv").open("x",encoding="utf8",newline="") as stream:
        writer=csv.writer(stream)
        writer.writerow(("timestamp_utc","voltage_v","shunt_voltage_v"))
        for i in range(183):
            t=first+timedelta(seconds=i,microseconds=173000)
            writer.writerow((t.isoformat(timespec="microseconds").replace("+00:00","Z"),
                             f"{voltage:.9f}",f"{amps * spec.reference_shunt_ohm:.11f}"))
    config={"schema":"policylab.dc_bench_capture_config.v1",
            "capture_kind":"TEST_FIXTURE","channel":"source_dc",
            "window":{"start_utc":"2026-11-20T00:00:00Z","end_utc":"2026-11-20T00:03:00Z"},
            "maximum_sample_gap_seconds":1.5,
            "primary":{"device_id":"fixture_ada228_5v","logger_id":"fixture_ina228_logger"},
            "reference":{"device_id":"fixture_wsk2512_ref","logger_id":"fixture_analytical_logger",
                         "shunt_resistance_ohms":.01,
                         "voltage_current_pairing":"Simulated simultaneous fixture values, not a physical DMM"},
            "environment":{"solar_panel_installed":False,"battery_installed":False,
                           "utility_grid_connected":False}}
    (out/"capture-config.json").write_bytes(json_bytes(config))
    receipt=None
    if args.pl_root:
        pl=args.pl_root.resolve()
        converter=pl/"scripts/equipment/dc_bench_capture.mjs"
        if not converter.exists():raise RuntimeError("PL bridge missing")
        run(["node",str(converter),
             "--primary",str(out/"primary/samples.csv"),
             "--reference",str(out/"reference-fixture.csv"),
             "--primary-sidecar",str(out/"primary/session.json"),
             "--primary-registers",str(out/"primary/registers.jsonl"),
             "--config",str(out/"capture-config.json"),
             "--out",str(out/"policy-lab-intake")],pl)
        receipt=json.loads((out/"policy-lab-intake/intake-receipt.json").read_text())
        if receipt["decision"]!="TEST_FIXTURE_STRUCTURALLY_INGESTED_NO_PHYSICAL_CLAIMS" or \
           receipt["physical_ready"] or receipt["spk_issuance_allowed"]:
            raise RuntimeError("fixture was promoted or frozen Policy Lab intake failed")
        observed=receipt["channel_diagnostics"]["source_dc"]
        if not math.isclose(observed["primary_total_wh"],expected_wh,rel_tol=1e-4) or \
           not math.isclose(observed["reference_total_wh"],expected_wh,rel_tol=1e-5):
            raise RuntimeError("capture energies disagree with independent analog SPICE model")
    sources=[NAME+".kicad_sch",NAME+".kicad_pcb",NAME+".kicad_pro",
             "station-spec-5v.json","spice_low_voltage_witness.cir",
             "generate_schematic.py","generate_pcb.py"]
    report={"schema":"hardware_splicer.5v_witness_design_replay.v1",
            "status":"SOFTWARE_DESIGN_VALIDATED_ONLY",
            "physical_equipment_built":False,"hardware_powered":False,"calibration_verified":False,
            "fabrication_released":False,"native_erc":"ZERO_VIOLATIONS",
            "native_drc":"ZERO_VIOLATIONS_ZERO_UNCONNECTED_ZERO_PARITY_ERRORS",
            "expected_net_pads":sum(map(len,schematic.NETS.values())),
            "station_design_checks_passed":True,
            "source_voltage_v_assumed":5.0,
            "load_resistance_ohm_assumed":10.0,
            "fuse_resistance_ohm_ASSUMED":.05,
            "ada_shunt_ohm_unverified":.015,
            "reference_shunt_ohm_nominal":.01,
            "spice_current_a":amps,"spice_load_voltage_v":voltage,
            "spice_load_power_w":pwr,"spice_3min_load_energy_wh":expected_wh,
            "primary_samples_fixture":183,
            "pl_intake_decision":receipt["decision"] if receipt else "NOT_RUN",
            "pl_intake_evidence_root":receipt["evidence_root_sha256"] if receipt else None,
            "source_sha256":{name:sha(HERE/name) for name in sources},
            "limitations":["No actual carrier, shunt, fuse, power source, logger or reference DMM connected.",
                "SPICE is an idealized DC network; conductor/contact/temperature effects omitted.",
                "Shunt carrier product page and schematic disagree on tolerance; exact board revision unknown.",
                "1A fuse holder is chosen, but fuse DC clearing rating and coordination still need review.",
                "Manufacturing drill/track checks are not assembly, safety, traceability or calibration checks.",
                "No direct physical measurement, timebase proof, or observed energy/efficiency claim."]}
    (out/"verification.json").write_bytes(json_bytes(report))
    print(json.dumps({"status":report["status"],"erc":report["native_erc"],"drc":report["native_drc"],
                      "spice_load_power_w":pwr,"3_min_spice_wh":expected_wh,
                      "PL":report["pl_intake_decision"],"out":str(out)},indent=2))

if __name__=="__main__":main()
