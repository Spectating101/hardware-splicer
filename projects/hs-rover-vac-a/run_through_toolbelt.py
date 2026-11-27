"""HS-ROVER-VAC-A: a mapping and camera rover from a faulty Xiaomi Mi robot vacuum and a cracked phone, through the toolbelt."""
import json, shutil, sys
from pathlib import Path
from hardware_splicer import engineering_toolbelt as tb
from hardware_splicer.objective_project import ObjectiveProject

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
NT = 32.91  # NT$ per US$, the rate HS-ROVER-A used (2026-11-25)
RU = "https://www.ruten.com.tw/item/show?"
pid = tb.call("hs_project_open", {"objective": "A mapping and live-camera rover built from a faulty Xiaomi Mi robot vacuum (1st gen) and a cracked "
              "Android phone: maps a room with the vacuum's laser scanner, drives on its own wheels and battery, streams video "
              "on the local network; cheaper than a new pet camera robot."})["result"]["project_id"]
call = lambda name, args: tb.call(name, {"project_id": pid, **args})
log = {"prior_art": call("hs_prior_art_search", {"query": "robot vacuum lidar salvage ROS2 OOMWOO Valetudo", "sources": ["hs_own"]})}
log["junk"] = call("hs_junk_lookup", {"needs": ["lidar_2d", "drive_motors_encoded", "battery_pack", "bump_cliff_sensors", "camera", "wifi_compute"]})
call("hs_project_record", {"kind": "decision", "title": "keep the vacuum body",
     "choice": "Keep the vacuum's own chassis, wheels, laser scanner, pack, bumper and cliff sensors in place; replace only what is dead",
     "because": "The body already holds every module at the right height and the scanned STEP models are too coarse to place mounting holes on a new chassis",
     "alternatives": ["strip the modules onto a printed chassis (needs the modules' mounting holes measured)", "OOMWOO One (in development, ~US$200 of new spares)"]})
call("hs_project_record", {"kind": "decision", "title": "route by what the donor's main board does",
     "choice": "Route A: board works -> Valetudo (local control and map) plus the phone as camera. Route B: board dead -> ESP32-S3 with two DRV8871 for the wheels and a MOSFET for the scanner motor",
     "because": "Route A needs no new electronics; route B uses the measured wheel module pinout and kaiaai/LDS, which needs an external motor driver for the LDS02RR",
     "alternatives": ["Raspberry Pi with ROS2 on board (more power, more cost)"]})
drive = call("hs_size_rover_drive", {"mass_kg": 4.0, "wheel_mm": 71.5, "driven": 2, "speed_m_s": 0.25, "slope_deg": 5})
log["drive"] = drive
wm = next(o for o in drive["result"]["passing"] if o["family"].startswith("salvaged-roborock"))
motors_w = round(2 * wm["current_a"]["cruise_per_motor"] * 14.4, 2)
surge_w = round(2 * wm["current_a"]["slope_per_motor"] * 14.4, 2)
energy = call("hs_energy_budget", {"spec": {"session_hours": 2.0,
    "battery": {"chemistry": "li_ion", "nominal_v": 14.4, "capacity_ah": 5.2, "max_continuous_a": 5.0},
    "loads": [{"name": "LDS02RR laser scanner, motor and electronics (declared 2.0 W, not measured)", "watts": 2.0, "hours": 2.0, "ac": False},
              {"name": "ESP32-S3 over Wi-Fi (declared 0.6 W) through a 5 V buck at 90%", "watts": 0.67, "hours": 2.0, "ac": False},
              {"name": "phone streaming its camera, charged from the pack (declared 3.0 W) through the buck at 90%", "watts": 3.33, "hours": 2.0, "ac": False},
              {"name": f"2 wheel modules cruising ({wm['current_a']['cruise_per_motor']} A each at 14.4 V, hs_size_rover_drive)",
               "watts": motors_w, "hours": 1.0, "surge_watts": surge_w, "ac": False}]}})
log["energy"] = energy
lines = [
 {"item": "Faulty Xiaomi Mi Robot Vacuum SDJQR02RR, untested (body, LDS02RR scanner, two wheel modules, 14.4 V pack, bumper, cliff sensors) [NT$1,000]",
  "qty": 1, "unit_usd": round(1000 / NT, 2), "source": RU + "22423679030413", "origin": "salvaged", "donor": "robot-vacuum-lidar-xiaomi-roborock", "mass_g": 3800},
 {"item": "Cracked Android phone that boots (camera and Wi-Fi streaming) [NT$199]", "qty": 1, "unit_usd": round(199 / NT, 2),
  "source": RU + "22232046931329", "origin": "salvaged", "donor": "phone-android-cracked", "mass_g": 170},
 {"item": "ESP32-S3 DevKitC-1 compatible board (route B) [NT$78]", "qty": 1, "unit_usd": round(78 / NT, 2), "source": RU + "22333501822078"},
 {"item": "DRV8871 3.6 A motor driver module (route B; one per wheel) [NT$49]", "qty": 2, "unit_usd": round(49 / NT, 2), "source": RU + "22638650977151"},
 {"item": "MP1584 5 V 3 A buck module (ESP32, scanner, phone) [NT$21]", "qty": 1, "unit_usd": round(21 / NT, 2), "source": RU + "21404237374108"},
 {"item": "MOSFET PWM switch module for the LDS02RR motor (route B) [NT$8]", "qty": 1, "unit_usd": round(8 / NT, 2), "source": RU + "22634436500713"},
 {"item": "ZH 1.5 mm 7-pin single-ended lead to the wheel modules (route B) [NT$20]", "qty": 2, "unit_usd": round(20 / NT, 2), "source": RU + "22646141315847"},
 {"item": "4S Li-ion charger 16.8 V 1 A (route B: with the main board dead the dock no longer charges the pack; the pack's BMS stays in line) [NT$75]",
  "qty": 1, "unit_usd": round(75 / NT, 2), "source": RU + "21903578185010"},
 {"item": "10 kOhm resistors, 10-pack (encoder pull-ups) [NT$2]", "qty": 1, "unit_usd": round(2 / NT, 2), "source": RU + "21946839995601"},
 {"item": "PLA for a phone clamp on the top cover, about 30 g (declared) at Bambu Lab US$19.99/kg (search result)", "qty": 1, "unit_usd": 0.60,
  "source": "https://asia.store.bambulab.com/collections/pla/products/pla-basic-filament"}]
# Against the cheapest wheeled camera robot sold (the "Blinky Bot", US$30-50, about NT$1,500 on Shopee; HS-ROVER-A README)
route_a = [l for l in lines if "route B" not in l["item"] and "buck" not in l["item"]]
log["bom_a"] = call("hs_bom_check", {"lines": route_a, "budget_usd": 50.0})
bom = call("hs_bom_check", {"lines": lines, "budget_usd": 50.0})
log["bom"] = bom
status = tb.call("hs_project_status", {"project_id": pid})["result"]
shutil.copytree(ObjectiveProject.load(pid).root, out / "project", dirs_exist_ok=True)
(out / "bom.json").write_text(json.dumps({"route_a": route_a, "route_b": lines}, indent=1, ensure_ascii=False) + "\n")
(out / "status_envelope.json").write_text(json.dumps(status, indent=1, default=str, ensure_ascii=False) + "\n")
print(json.dumps({"junk": [(s["device"], s["covers"]) for s in log["junk"]["result"]["donor_plan"]], "drive": drive["summary"],
                  "wm": {k: wm[k] for k in ("speed_at_cruise_m_s", "current_a", "slope_torque_share_of_stall", "checks")},
                  "energy": energy["summary"], "energy_problems": energy["problems"], "bom_a": log["bom_a"]["summary"], "bom": bom["summary"], "bom_problems": bom["problems"],
                  "open": status.get("open")}, indent=1, default=str, ensure_ascii=False))
