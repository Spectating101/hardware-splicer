#!/usr/bin/env python3
"""Run an actual CPU Crazyflow reference-simulation smoke test.

Uses stock Crazyflow Crazyflie model, NOT a calibrated 2.1+ sensor-deck
modification. It verifies the external dynamics backend executes and records
the state/provenance; no motor commands or physical flight are permitted.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
from crazyflow.sim import Sim
from crazyflow.control import Control


def run(design_path:Path,out_dir:Path)->dict:
    design=json.loads(design_path.read_text())
    if design.get("schema_version")!="hardware_splicer.microdrone_design.v1":
        raise ValueError("Unknown HS design input")
    version=importlib.metadata.version("crazyflow")
    if version!="0.4.0":
        raise ValueError(f"Crazyflow version changed: {version}")
    sim=Sim(n_worlds=1,n_drones=1,control=Control.state)
    sim.reset()
    before=np.asarray(sim.data.states.pos[0,0],dtype=float).tolist()
    cmd=np.zeros((1,1,16),dtype=np.float32)
    cmd[...,9:13]=Rotation.from_euler("z",0).as_quat().astype(np.float32)
    cmd[0,0,2]=0.5
    ticks=max(1,int(sim.freq//sim.control_freq))
    sim.state_control(cmd)
    sim.step(ticks)
    after=np.asarray(sim.data.states.pos[0,0],dtype=float).tolist()
    if len(after)!=3 or not all(math.isfinite(float(x)) for x in after):
        raise ValueError("Simulated Crazyflie position became non-finite")
    if abs(after[2])>10 or abs(after[0])>10 or abs(after[1])>10:
        raise ValueError("Simulation departed an unusually large smoke-test envelope")
    receipt={
      "schema_version":"hardware_splicer.crazyflow_smoke.v1",
      "design_input_sha256":hashlib.sha256(design_path.read_bytes()).hexdigest(),
      "simulation":"Crazyflow",
      "version":version,
      "backend":"JAX CPU",
      "command_z_m":0.5,
      "steps":ticks,
      "position_before_m":before,
      "position_after_m":after,
      "finite_result":True,
      "real_simulation_executed":True,
      "dynamics_model":"crazyflow_library_default_Crazyflie_reference_not_calibrated_to_HS_deck",
      "deck_mass_override_executed":False,
      "flight_firmware_executed_in_simulation":False,
      "physical_thrust_verified":False,
      "real_flight_authorized":False,
    }
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError("Refusing to overwrite previous simulation results")
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/"SIMULATION_SMOKE_EVIDENCE.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    return receipt


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args()
    print(json.dumps(run(a.design,a.out),indent=2))
