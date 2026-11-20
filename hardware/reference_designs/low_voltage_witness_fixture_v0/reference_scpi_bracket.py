#!/usr/bin/env python3
"""Read-only two-instrument SCPI witness capture with honest clock uncertainty.

Supplies zero control commands, and cannot authorize power-on. The host
timestamps bracket query/response, *not* the physical ADC integration aperture.
A Siglent-style MEAS:VOLT:DC? command permits explicit voltage range, but
its completion time and external sync remain uncharacterized without hardware.
No physical reference or pyvisa was available when this module was developed.

A fully mock TEST_FIXTURE mode exercises the actual capture mechanics.
Explicit --transport visa requires two independent already-safe DCV meters,
optional PyVISA + vendor drivers and an operator-supplied authorization flag.
Even then this module outputs PREVIEW, never physical-approval evidence.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time

SHUNT_COMMAND="MEAS:VOLT:DC? 0.2"  # voltage across reference 10 milliohm (~4mV)
BUS_COMMAND="MEAS:VOLT:DC? 20"     # separate bus meter at J2 (~5V)
MAX_SAMPLES=600
MAX_ROUNDTRIP_MS=750.0
MAX_CENTER_SKEW_MS=250.0


class ReferenceCaptureError(RuntimeError):
    pass


def utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="microseconds").replace("+00:00","Z")


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def parse_voltage(raw: str, *, max_abs_v: float) -> float:
    if not isinstance(raw,str) or not re.fullmatch(
            r"\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\s*",raw):
        raise ReferenceCaptureError("Malformed or nonnumeric scalar DCV SCPI response")
    value=float(raw)
    if not math.isfinite(value) or abs(value)>max_abs_v:
        raise ReferenceCaptureError("DMM returned overrange, impossible, or unsafe DCV")
    return value


class FakeMeter:
    """Synthetic responses only. Not a device emulator with calibration claims."""
    def __init__(self, name: str, voltage_v: float):
        self.name=name
        self.voltage_v=voltage_v
        self.commands=[]
        self.close_called=False

    def query(self, command: str) -> str:
        self.commands.append(command)
        if command=="*IDN?":
            return "SYNTHETIC,NOT_A_METER,"+self.name+",SIMULATED"
        if command in (SHUNT_COMMAND,BUS_COMMAND):
            return "%.11e" % self.voltage_v
        raise ReferenceCaptureError("Unsupported mock command")

    def close(self):
        self.close_called=True


def _query_once(instrument, role: str, command: str, max_v: float) -> dict:
    utc_start=time.time()
    m_start=time.monotonic()
    response=instrument.query(command)
    m_end=time.monotonic()
    utc_end=time.time()
    elapsed_ms=(m_end-m_start)*1000
    if not (0 <= elapsed_ms<=MAX_ROUNDTRIP_MS):
        raise ReferenceCaptureError(role+" exceeded query-bracket threshold")
    value=parse_voltage(str(response),max_abs_v=max_v)
    # Single host clock may be offset, stepped or otherwise wrong.
    if not (utc_end>=utc_start):
        raise ReferenceCaptureError("Host UTC time moved backward")
    return {
        "role":role,"command":command,"response_raw":str(response),
        "voltage_v":value,
        "query_start_utc":utc(utc_start),
        "query_end_utc":utc(utc_end),
        "query_start_mono_s":m_start,"query_end_mono_s":m_end,
        "query_latency_ms":elapsed_ms,
        "host_midpoint_epoch_s":(utc_start+utc_end)/2,
        "host_midpoint_mono_s":(m_start+m_end)/2,
        "aperture_time_verified":False,
    }


def capture_dual(shunt_meter,bus_meter,out: Path,*,samples:int=183,
                 period_s:float=1.0,capture_kind:str="TEST_FIXTURE",
                 requested_resource_ids:tuple[str,str]|None=None) -> dict:
    if type(samples) is not int or not (3<=samples<=MAX_SAMPLES):
        raise ValueError("samples must be 3..600")
    if (not isinstance(period_s,(float,int)) or not math.isfinite(period_s) or
            not .05<=period_s<=30):
        raise ValueError("period must be finite between 0.05 and 30 seconds")
    if capture_kind not in ("TEST_FIXTURE","DECLARED_REFERENCE_BRACKETED_UNVERIFIED"):
        raise ValueError("Unknown capture type")
    if capture_kind!="TEST_FIXTURE" and (isinstance(shunt_meter,FakeMeter) or isinstance(bus_meter,FakeMeter)):
        raise ValueError("A fake meter cannot be presented as a declared physical reference")
    if requested_resource_ids and (len(requested_resource_ids)!=2 or
                                   requested_resource_ids[0]==requested_resource_ids[1]):
        raise ValueError("Two independent resource strings required")
    # Reserve the directory before contacting devices or starting output.
    out.mkdir(parents=True,exist_ok=False)
    csv_path=out/"reference-preview.csv"
    raw_path=out/"reference-query-raw.jsonl"
    receipt_path=out/"reference-session.json"
    session={
        "schema":"hardware_splicer.bracketed_scpi_reference.v1",
        "status":"STARTING","capture_kind":capture_kind,
        "source_kind":"two_mock_scpi_meters" if capture_kind=="TEST_FIXTURE" else "dual_scpi_meters",
        "sample_count_requested":samples,"samples_captured":0,
        "reference_meter_paths_distinct":bool(requested_resource_ids and requested_resource_ids[0]!=requested_resource_ids[1]),
        "measurement_boundary":"Kelvin voltage across R1 (J5) and independent J2 VBUS (J6)",
        "shunt_command":SHUNT_COMMAND,"bus_command":BUS_COMMAND,
        "maximum_query_bracket_ms":MAX_ROUNDTRIP_MS,
        "maximum_pair_center_skew_ms":MAX_CENTER_SKEW_MS,
        "clock_source":"host UTC + monotonic query bracketing (NOT external absolute clock proof)",
        "clock_synchronization_verified":False,
        "instrument_aperture_times_verified":False,
        "calibration_status_verified":False,
        "reference_independence_physically_verified":False,
        "metrological_agreement_proven":False,
        "physical_ready":False,"fabrication_allowed":False,
        "timestamp_policy":"CSV midpoint of host query brackets; NEVER true ADC aperture",
    }
    receipt_path.write_text(json.dumps(session,indent=2)+"\n")
    failure=None
    try:
        shunt_idn=str(shunt_meter.query("*IDN?")).strip()
        bus_idn=str(bus_meter.query("*IDN?")).strip()
        if not shunt_idn or not bus_idn or shunt_idn==bus_idn:
            raise ReferenceCaptureError("Missing/identical instrument identity strings")
        if requested_resource_ids and not all(requested_resource_ids):
            raise ReferenceCaptureError("Empty VISA resource identifier")
        session["identifiers"]={"shunt_idn":shunt_idn,"bus_idn":bus_idn,
                                "resource_names_claimed":requested_resource_ids,
                                "identity_authenticity_verified":False}
        session["status"]="CAPTURING"
        with csv_path.open("x",newline="",encoding="utf-8") as c, \
             raw_path.open("x",encoding="utf-8") as raw, \
             ThreadPoolExecutor(max_workers=2) as executor:
            writer=csv.writer(c)
            writer.writerow(("timestamp_utc","voltage_v","shunt_voltage_v"))
            start=time.monotonic()
            for index in range(samples):
                deadline=start+index*period_s
                delay=deadline-time.monotonic()
                if delay>0:
                    time.sleep(delay)
                elif index>0 and abs(delay)>period_s*.5:
                    raise ReferenceCaptureError("Capture period missed; no invented samples")
                fs=executor.submit(_query_once,shunt_meter,"shunt",SHUNT_COMMAND,.2)
                fb=executor.submit(_query_once,bus_meter,"bus",BUS_COMMAND,20)
                a,b=fs.result(timeout=5),fb.result(timeout=5)
                if a["voltage_v"]<=0 or b["voltage_v"]<=0 or b["voltage_v"]>5.25:
                    raise ReferenceCaptureError("Positive low-voltage station input validation failed")
                skew=abs(a["host_midpoint_mono_s"]-b["host_midpoint_mono_s"])*1000
                if skew>MAX_CENTER_SKEW_MS:
                    raise ReferenceCaptureError("Two DMM query brackets have excessive center skew")
                t=(a["host_midpoint_epoch_s"]+b["host_midpoint_epoch_s"])/2
                sample={"index":index,"shunt":a,"bus":b,
                        "host_query_center_skew_ms":skew,
                        "host_reference_midpoint_utc":utc(t),
                        "true_instrument_aperture_proven":False}
                raw.write(json.dumps(sample,sort_keys=True,allow_nan=False)+"\n")
                raw.flush()
                writer.writerow((utc(t),"%.11g" % b["voltage_v"],
                                 "%.11g" % a["voltage_v"]))
                c.flush()
                session["samples_captured"]+=1
        session["status"]="COMPLETE_SOFTWARE_TIMESTAMP_BRACKETED_ONLY"
    except (Exception,KeyboardInterrupt) as exc:
        failure=exc
        session["status"]="FAILED_RETAINED_PARTIAL"
        session["error"]=type(exc).__name__+": "+str(exc)
    finally:
        session["files"]={
            f.name:{"sha256":sha256(f),"bytes":f.stat().st_size}
            for f in (csv_path,raw_path) if f.is_file()
        }
        receipt_path.write_text(json.dumps(session,sort_keys=True,indent=2)+"\n")
        for meter in (shunt_meter,bus_meter):
            try:
                meter.close()
            except Exception:
                pass
    if failure is not None:
        raise ReferenceCaptureError("Reference capture failed; retained partial evidence: "+str(failure)) from failure
    return session


def _visa_pair(shunt_resource: str,bus_resource: str):
    try:
        import pyvisa  # type: ignore  # completely optional, intentionally NOT installed
    except ImportError as exc:
        raise ReferenceCaptureError("Optional PyVISA dependency unavailable; only TEST_FIXTURE is usable") from exc
    manager=pyvisa.ResourceManager()
    # Only open EXPLICIT named resources. Do not scan internal /dev/i2c buses.
    shunt=manager.open_resource(shunt_resource)
    shunt.timeout=1200
    bus=manager.open_resource(bus_resource)
    bus.timeout=1200
    return shunt,bus


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--samples",type=int,default=183)
    ap.add_argument("--period-s",type=float,default=1)
    ap.add_argument("--transport",choices=["fixture","visa"],default="fixture")
    ap.add_argument("--shunt-resource")
    ap.add_argument("--bus-resource")
    ap.add_argument("--physical-read-only-authorized",action="store_true")
    args=ap.parse_args(argv)
    if args.out.exists():
        ap.error("Output directory exists")
    if args.transport=="fixture":
        if args.shunt_resource or args.bus_resource or args.physical_read_only_authorized:
            ap.error("Fixture capture must not pretend to be a VISA instrument")
        shunt=FakeMeter("SHUNT_FAKE",.004137)
        bus=FakeMeter("BUS_FAKE",4.969)
        kind="TEST_FIXTURE"
        ids=None
    else:
        if not args.physical_read_only_authorized:
            ap.error("Explicit laboratory operator authorization required for real read-only SCPI")
        if not args.shunt_resource or not args.bus_resource or args.shunt_resource==args.bus_resource:
            ap.error("Two distinct explicit instrument resources required")
        ids=(args.shunt_resource,args.bus_resource)
        shunt,bus=_visa_pair(*ids)
        kind="DECLARED_REFERENCE_BRACKETED_UNVERIFIED"
    result=capture_dual(shunt,bus,args.out,samples=args.samples,
                        period_s=args.period_s,capture_kind=kind,
                        requested_resource_ids=ids)
    print(json.dumps({"status":result["status"],
                      "samples_captured":result["samples_captured"],
                      "physical_ready":False,"timebase_verified":False,
                      "out":str(args.out)}))
    return 2  # No synchronized calibrated physical metrology or release approval


if __name__=="__main__":
    raise SystemExit(main())
