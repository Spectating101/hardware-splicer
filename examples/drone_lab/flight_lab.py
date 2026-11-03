#!/usr/bin/env python3
"""HS Drone Lab: fly an actual upstream Crazyflie dynamics model, not a mock.

Powered by learnsyslab/gym-pybullet-drones (PyBullet + DSLPIDControl). In
--serve mode, exposes only loopback controls and streams PyBullet's own rendered
camera. In --demo mode, flies a square and writes GIF + per-motor flight logs.
No motors on physical hardware can be addressed from this program.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pybullet as p
from PIL import Image
from gym_pybullet_drones.envs.CtrlAviary import CtrlAviary
from gym_pybullet_drones.control.DSLPIDControl import DSLPIDControl
from gym_pybullet_drones.utils.enums import DroneModel, Physics

SIM_HZ = 48
PHYSICS_HZ = 240
MISSION_STEPS = (
    (0.0, (0.00, 0.00, 0.42)),
    (2.0, (0.30, 0.00, 0.42)),
    (4.0, (0.30, 0.30, 0.42)),
    (6.0, (0.00, 0.30, 0.42)),
    (8.0, (0.00, 0.00, 0.42)),
    (10.5, (0.00, 0.00, 0.10)),
    (13.0, (0.00, 0.00, 0.10)),
)

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>HS Drone Lab — live PyBullet flight</title>
<style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#0c111a;color:#e8eef9}
*{box-sizing:border-box}body{margin:0;padding:22px;max-width:1270px;margin-inline:auto}
h1{font-size:24px;margin:0 0 7px}h2{font-size:15px;color:#9db0cc;font-weight:600}
small,.muted{color:#98a9bf}.top{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:15px;flex-wrap:wrap}
.tag{background:#16283b;border:1px solid #2b5377;color:#90cefc;border-radius:18px;padding:7px 11px;font-size:12px}
.layout{display:grid;grid-template-columns:minmax(0,1.75fr) minmax(260px,1fr);gap:14px}
.panel{background:#131c29;border:1px solid #2a3548;border-radius:13px;padding:15px}
img{width:100%;height:auto;aspect-ratio:640/420;object-fit:contain;background:#1a2330;border-radius:7px}
.telemetry{display:grid;grid-template-columns:1fr 1fr;gap:10px}.stat{padding:12px;border-radius:7px;background:#1c2a3a}
.value{font-size:19px;font-variant-numeric:tabular-nums;font-weight:700}.unit{font-size:12px;color:#a4b6c7}
button{background:#263d55;color:#ecf6ff;border:1px solid #385f81;border-radius:7px;padding:11px 13px;cursor:pointer;font-weight:700}
button:hover{background:#35628c}button:focus-visible{outline:2px solid #79c8ff}
button.primary{background:#126d55;border-color:#209b7a}button.warn{background:#663d2a;border-color:#af724c}
.buttons{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}
.key{display:inline-block;background:#2a3c50;border:1px solid #536778;border-radius:4px;padding:2px 7px;margin:2px;font-size:12px}
.err{color:#ffb5a5}footer{margin-top:16px;color:#8fa0b7;font-size:12px;line-height:1.5}
@media(max-width:850px){.layout{grid-template-columns:1fr}}@media(max-width:430px){.buttons{grid-template-columns:repeat(2,1fr)}}
</style></head><body>
<div class="top"><div><h1>HS · Microdrone Flight Lab</h1><small>Crazyflie 2.x quadrotor · upstream PyBullet physics and PID · simulated motors only</small></div><span class="tag">LIVE LOCAL SIMULATOR · NO PHYSICAL HARDWARE</span></div>
<div class="layout">
<section class="panel"><h2>PYBULLET CAMERA · MOVING AIRCRAFT</h2>
<img id="flight" alt="Live render from the upstream PyBullet Crazyflie quadrotor simulation"/>
<div class="buttons">
<button class="primary" onclick="send('takeoff')">T · TAKEOFF</button><button onclick="send('hover')">SPACE · HOVER</button><button class="warn" onclick="send('land')">L · LAND</button>
<button onclick="send('mission')">M · FLY A SQUARE</button><button class="warn" onclick="send('disarm')">STOP MOTORS</button><button onclick="send('reset')">X · RESET</button>
</div>
</section>
<section class="panel">
<h2>FLIGHT TELEMETRY · ACTUAL SIMULATOR</h2><div class="telemetry">
<div class="stat"><div class="unit">FLIGHT MODE</div><div id="mode" class="value">loading</div></div>
<div class="stat"><div class="unit">SIM TIME</div><div id="seconds" class="value">—</div></div>
<div class="stat"><div class="unit">ALTITUDE</div><div id="z" class="value">—</div></div>
<div class="stat"><div class="unit">HORIZONTAL XY</div><div id="xy" class="value">—</div></div>
<div class="stat"><div class="unit">GROUND SPEED</div><div id="speed" class="value">—</div></div>
<div class="stat"><div class="unit">ROLL / PITCH</div><div id="att" class="value">—</div></div>
</div>
<h2>MOTOR RPM OUTPUTS</h2><div id="rpm" class="muted">—</div>
<h2>FLY WITH YOUR KEYBOARD</h2>
<p><span class="key">W A S D</span> move <span class="key">R / F</span> up/down <span class="key">Q / E</span> yaw</p>
<p><span class="key">T</span> takeoff <span class="key">SPACE</span> hover <span class="key">L</span> land <span class="key">M</span> automatic square</p>
<p class="muted">Controls move the desired PID position setpoint. Motor physics, sensor state and thrust come from upstream simulation. The drone remains within a small virtual work area.</p>
<p id="error" class="err"></p>
</section></div>
<footer>Software flight only. The physical DIY 65mm whoop uses Betaflight/ELRS and different hardware; this Crazyflie simulation is a control demonstration, not a validated digital twin of the DIY kit. No RC radio, USB flight controller, motor output or battery is connected.</footer>
<script>
async function send(command,payload={}){try{const r=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command,...payload})});if(!r.ok)throw new Error(await r.text());document.getElementById('error').textContent='';}catch(e){document.getElementById('error').textContent=String(e);}}
const keys={
't':'takeoff',' ':'hover','l':'land','m':'mission','x':'reset',
'w':['move',0.09,0,0,0],'s':['move',-0.09,0,0,0],
'a':['move',0,0.09,0,0],'d':['move',0,-0.09,0,0],
'r':['move',0,0,0.07,0],'f':['move',0,0,-0.07,0],
'q':['move',0,0,0,0.12],'e':['move',0,0,0,-0.12]
};
window.addEventListener('keydown',e=>{if(e.target&&['INPUT','TEXTAREA'].includes(e.target.tagName))return;const k=keys[e.key.toLowerCase()];if(!k)return;e.preventDefault();if(Array.isArray(k))send(k[0],{delta:k.slice(1)});else send(k);});
async function refresh(){try{const r=await fetch('/api/state',{cache:'no-store'});if(!r.ok)throw new Error('backend offline');const s=await r.json();
const set=(id,t)=>document.getElementById(id).textContent=t;
set('mode',s.mode);set('seconds',s.seconds.toFixed(1)+' s');set('z',s.pos[2].toFixed(2)+' m');set('xy',s.pos[0].toFixed(2)+', '+s.pos[1].toFixed(2)+' m');set('speed',Math.hypot(s.vel[0],s.vel[1]).toFixed(2)+' m/s');set('att',(s.rpy[0]*57.2958).toFixed(1)+'° / '+(s.rpy[1]*57.2958).toFixed(1)+'°');
set('rpm',s.rpms.map((n,i)=>'M'+(i+1)+': '+Math.round(n).toLocaleString()).join(' · '));
if(s.error)set('error',s.error);
}catch(e){document.getElementById('error').textContent=String(e);}}
const img=document.getElementById('flight');let frameBusy=false;
async function frame(){if(frameBusy)return;frameBusy=true;try{const resp=await fetch('/api/frame?ts='+Date.now(),{cache:'no-store'});if(resp.ok){const b=await resp.blob();const u=URL.createObjectURL(b);const old=img.src;img.src=u;if(old.startsWith('blob:'))URL.revokeObjectURL(old);}}finally{frameBusy=false;}}
setInterval(refresh,300);setInterval(frame,350);refresh();frame();
</script></body></html>"""


class DroneWorld:
    """Single small Crazyflie quadcopter, real PyBullet 240Hz dynamics."""
    def __init__(self):
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.reset_requested = False
        self.mode = "DISARMED"
        self.seconds = 0.0
        self.mission_started = 0.0
        self.yaw = 0.0
        self.target = np.array([0.0, 0.0, 0.10], dtype=float)
        self.rpms = np.zeros(4)
        self.last_state = np.zeros(20)
        self.frame = b""
        self.error = ""
        self.env = None
        self.ctrl = None
        self.action = np.zeros((1,4),dtype=float)
        self._new_world()

    def _new_world(self):
        if self.env is not None:
            self.env.close()
        self.env = CtrlAviary(
            drone_model=DroneModel.CF2X, num_drones=1,
            initial_xyzs=np.array([[0.0,0.0,0.10]]), initial_rpys=np.zeros((1,3)),
            physics=Physics.PYB, pyb_freq=PHYSICS_HZ, ctrl_freq=SIM_HZ,
            gui=False, record=False, obstacles=False, user_debug_gui=False,
        )
        self.ctrl = DSLPIDControl(drone_model=DroneModel.CF2X)
        self.action = np.zeros((1,4),dtype=float)
        self.last_state = np.zeros(20)
        self.last_state[:3] = [0,0,.10]
        self.target = np.array([0.0,0.0,0.10],dtype=float)
        self.seconds = 0.0
        self.yaw = 0.0
        self.rpms = np.zeros(4)
        self.mode = "DISARMED"
        self.mission_started = 0.0
        self.frame = self.camera()

    def camera(self):
        pos = self.last_state[:3].tolist()
        v = p.computeViewMatrixFromYawPitchRoll(
            cameraTargetPosition=pos, distance=0.58, yaw=45, pitch=-32, roll=0,
            upAxisIndex=2)
        projection = p.computeProjectionMatrixFOV(fov=58, aspect=640/420, nearVal=.01, farVal=6)
        w,h,rgba,*_ = p.getCameraImage(
            width=640,height=420,viewMatrix=v,projectionMatrix=projection,
            renderer=p.ER_TINY_RENDERER,physicsClientId=self.env.getPyBulletClient())
        pixels = np.array(rgba,dtype=np.uint8).reshape(h,w,4)
        output=io.BytesIO()
        Image.fromarray(pixels[:,:,:3],"RGB").save(output,format="JPEG",quality=78)
        return output.getvalue()

    def one_step(self):
        with self.lock:
            if self.reset_requested:
                self.reset_requested=False
                self._new_world()
            if self.mode == "MISSION":
                t = self.seconds - self.mission_started
                for when, dest in MISSION_STEPS:
                    if t >= when:
                        self.target = np.array(dest,dtype=float)
                if t >= MISSION_STEPS[-1][0]:
                    self.mode = "HOVER"
            if self.mode == "DISARMED":
                self.action[:]=0
            obs,_,_,_,_ = self.env.step(self.action)
            self.last_state = obs[0].copy()
            self.seconds += self.env.CTRL_TIMESTEP
            if self.mode not in ("DISARMED",):
                new_rpm,_,_ = self.ctrl.computeControlFromState(
                    control_timestep=self.env.CTRL_TIMESTEP,
                    state=self.last_state, target_pos=self.target,
                    target_rpy=np.array([0.0,0.0,self.yaw]),
                )
                self.action[0,:] = new_rpm
            else:
                self.action[:]=0
            self.rpms = self.action[0,:].copy()
            if self.mode=="LAND" and self.last_state[2]<=.105:
                self.mode="DISARMED"
                self.action[:]=0
            return self.last_state.copy()

    def command(self,command,delta=None):
        with self.lock:
            if command=="reset":
                self.reset_requested=True
            elif command=="takeoff":
                self.mode="FLY"
                self.target=np.array([self.last_state[0],self.last_state[1],0.45])
            elif command=="mission":
                self.mode="MISSION"
                self.mission_started=self.seconds
            elif command=="hover":
                if self.mode!="DISARMED":
                    self.mode="HOVER"
                    self.target=np.array(self.last_state[:3],dtype=float)
            elif command=="land":
                self.mode="LAND"
                self.target=np.array([self.last_state[0],self.last_state[1],0.07])
            elif command=="disarm":
                self.mode="DISARMED"
                self.action[:]=0
            elif command=="move":
                if self.mode=="DISARMED":
                    return
                if not isinstance(delta,list) or len(delta)!=4 or not all(
                    isinstance(x,(float,int)) and math.isfinite(x) and abs(x)<=0.15 for x in delta):
                    raise ValueError("move requires four small finite setpoint deltas")
                self.mode="FLY"
                self.target=np.clip(self.target+np.array(delta[:3]),[-.8,-.8,.08],[.8,.8,1.1])
                self.yaw=float((self.yaw+delta[3]+math.pi)%(2*math.pi)-math.pi)
            else:
                raise ValueError("unknown drone simulator command")

    def status(self):
        with self.lock:
            return {
                "mode":self.mode,"seconds":self.seconds,
                "pos":[float(v) for v in self.last_state[0:3]],
                "rpy":[float(v) for v in self.last_state[7:10]],
                "vel":[float(v) for v in self.last_state[10:13]],
                "rpms":[float(v) for v in self.rpms],
                "target":[float(v) for v in self.target],
                "error":self.error,
                "physics":"upstream-gym-pybullet-drones-CtrlAviary-DSLPIDControl",
                "physical_motors_connected":False,
            }

    def run(self):
        n=0
        while not self.stop.is_set():
            started=time.monotonic()
            try:
                self.one_step()
                n+=1
                if n%5==0:
                    with self.lock:
                        self.frame=self.camera()
            except Exception as exc:
                self.error=str(exc)
                self.stop.set()
                break
            time.sleep(max(0,1/SIM_HZ-(time.monotonic()-started)))

    def close(self):
        self.stop.set()
        with self.lock:
            if self.env is not None:
                self.env.close()


def demo(out_dir:Path):
    out_dir.mkdir(parents=True,exist_ok=True)
    world=DroneWorld()
    frames=[]
    rows=[]
    try:
        world.command("mission")
        for tick in range(14*SIM_HZ):
            state=world.one_step()
            rows.append({
                "seconds":round(world.seconds,4),
                "x_m":float(state[0]),"y_m":float(state[1]),"z_m":float(state[2]),
                "roll_rad":float(state[7]),"pitch_rad":float(state[8]),"yaw_rad":float(state[9]),
                "rpm_1":float(world.rpms[0]),"rpm_2":float(world.rpms[1]),
                "rpm_3":float(world.rpms[2]),"rpm_4":float(world.rpms[3]),
                "target_x":float(world.target[0]),"target_y":float(world.target[1]),
                "target_z":float(world.target[2]),
                "flight_mode":world.mode,
            })
            if tick%12==0:
                image=Image.open(io.BytesIO(world.camera())).convert("RGB")
                image.thumbnail((512,336))
                frames.append(image.quantize(colors=96))
        csv_path=out_dir/"flight_telemetry.csv"
        with csv_path.open("w",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        gif_path=out_dir/"real_pybullet_drone_flight.gif"
        frames[0].save(gif_path,save_all=True,append_images=frames[1:],
                       duration=250,loop=0,optimize=False)
        summary={
            "status":"simulation_completed",
            "real_third_party_physics_engine":True,
            "mode":"upstream_Crazyflie_PyBullet_3D_Simulator",
            "seconds_simulated":round(world.seconds,2),
            "steps":len(rows),
            "max_simulated_altitude_m":round(max(row["z_m"] for row in rows),3),
            "furthest_horizontal_m":round(max(math.hypot(row["x_m"],row["y_m"]) for row in rows),3),
            "final_position_m":[round(v,3) for v in rows[-1].values() if isinstance(v,float)][:3],
            "output_gif":str(gif_path),
            "output_telemetry":str(csv_path),
            "physical_hardware_flight":False,
            "digital_twin_of_physical_whoop":False,
        }
        (out_dir/"flight_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
        print(json.dumps(summary,indent=2))
    finally:
        world.close()


def serve(host,port):
    world=DroneWorld()
    worker=threading.Thread(target=world.run,daemon=True)
    worker.start()

    class Handler(BaseHTTPRequestHandler):
        def respond(self,status,data,mime):
            self.send_response(status)
            self.send_header("Content-Type",mime)
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def do_GET(self):
            path=urlparse(self.path).path
            if path=="/":
                self.respond(200,PAGE.encode(),"text/html; charset=utf-8")
            elif path=="/api/state":
                self.respond(200,json.dumps(world.status()).encode(),"application/json")
            elif path=="/api/frame":
                with world.lock:
                    image=world.frame
                self.respond(200,image,"image/jpeg")
            else:
                self.respond(404,b"Not found","text/plain")
        def do_POST(self):
            if self.path!="/api/command":
                self.respond(404,b"Not found","text/plain");return
            length=int(self.headers.get("Content-Length","0"))
            if length<=0 or length>1024:
                self.respond(400,b"Invalid request size","text/plain");return
            try:
                data=json.loads(self.rfile.read(length).decode("utf-8"))
                world.command(data.get("command"),data.get("delta"))
            except (ValueError,TypeError,KeyError) as exc:
                self.respond(400,str(exc).encode(),"text/plain");return
            self.respond(200,b'{"ok":true}',"application/json")
        def log_message(self,fmt,*args):
            return

    server=ThreadingHTTPServer((host,port),Handler)
    print("HS_DRONE_LAB_OPEN http://"+host+":"+str(port),flush=True)
    print("SIMULATOR_ONLY: no hardware actuators, batteries or remote flight commands",flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        world.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=["demo","serve"],default="demo")
    parser.add_argument("--out",type=Path,default=Path("results/hs-microdrone"))
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8765)
    args=parser.parse_args()
    if args.host not in ("127.0.0.1","localhost"):
        parser.error("For safety this DIY simulation cockpit binds only to localhost")
    if args.mode=="demo":
        demo(args.out)
    else:
        serve(args.host,args.port)
