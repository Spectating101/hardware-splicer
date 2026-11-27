"""HS-ROVER-A TT variant, end to end through the toolbelt; writes the project record into OUT."""
import json, shutil, sys
from pathlib import Path
from hardware_splicer import engineering_toolbelt as tb
from hardware_splicer.objective_project import ObjectiveProject

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
base = json.load(open(sys.argv[2]))  # the original bom.json
call = lambda name, args: tb.call(name, {"project_id": pid, **args})
pid = tb.call("hs_project_open", {"objective": "HS-ROVER-A on OpenBot's TT gearmotors: the same inspection rover at the cheap drive tier, "
                                   "under US$250 with every price cited, re-checked end to end."})["result"]["project_id"]
log = {}
log["prior_art"] = call("hs_prior_art_search", {"query": "TT gearmotor robot car rover OpenBot", "sources": ["hs_own"]})
call("hs_project_record", {"kind": "decision", "title": "drive tier", "choice": "2 x Adafruit 3777 TT gearmotor 48:1 on 65 mm wheels",
     "because": "OpenBot drives on TT motors; HS's drive table now carries the TT with the seller's measured stall current",
     "alternatives": ["Pololu 25D MP 47:1 (HS-ROVER-A as built)"]})
chassis = call("hs_rover_chassis", {"params": {"drive": "2wd_caster", "motor": "tt", "caster": "pololu_953", "wheel_d": 65, "wheel_w": 18,
                                               "hub_offset": 3.0, "wheel_mass_g": 31.5, "battery_mass_g": 165, "caster_mass_g": 9}})
log["chassis"] = chassis
auw = chassis["result"]["all_up_mass_g"] / 1000
drive = call("hs_size_rover_drive", {"mass_kg": round(auw, 3), "wheel_mm": 65, "driven": 2, "speed_m_s": 0.4, "slope_deg": 15})
log["drive"] = drive
tt = next(o for o in drive["result"]["passing"] if o["family"].startswith("adafruit-tt"))
cruise_w = 2 * tt["current_a"]["cruise_per_motor"] * 6.0 / 0.9   # through the 6 V step-down, 90% assumed as for the Pi rail
slope_w = 2 * tt["current_a"]["slope_per_motor"] * 6.0 / 0.9
energy = call("hs_energy_budget", {"spec": {"session_hours": 1.0, "battery": {"chemistry": "li_ion", "nominal_v": 10.8, "capacity_ah": 2.2, "max_continuous_a": 2.2},
    "loads": [{"name": "Pi Zero 2 W + Camera Module 3 streaming (2.5 W declared, through a 90% step-down)", "watts": 2.8, "hours": 1.0, "ac": False},
              {"name": f"2 x TT 48:1 cruising ({tt['current_a']['cruise_per_motor']} A each at 6 V, hs_size_rover_drive), 6 V step-down at 90%",
               "watts": round(cruise_w, 2), "hours": 0.5, "surge_watts": round(slope_w, 2), "ac": False}]}})
log["energy"] = energy
drop = ("Pololu 47:1", "Bracket Pair", "DRV8874", "Wheel 90x10", "Universal Aluminum", "Ball Caster with 1in", "M3 x 10 mm", "PLA 73.5 g")
lines = [l for l in base if not any(d in l["item"] for d in drop)]
pla_g = chassis["result"]["printed_mass_g"]
lines += [
 {"item": "Adafruit DC Gearbox Motor TT 200 RPM 3-6 V (#3777)", "qty": 2, "unit_usd": 2.95, "source": "https://www.adafruit.com/product/3777"},
 {"item": "Adafruit Thin White Wheel for TT motors, 65 mm (#3763)", "qty": 2, "unit_usd": 1.50, "source": "https://www.adafruit.com/product/3763"},
 {"item": "Adafruit DRV8833 dual motor driver breakout (#3297), both motors", "qty": 1, "unit_usd": 5.95, "source": "https://www.adafruit.com/product/3297"},
 {"item": "Pololu 6V 2.5A Step-Down Regulator D24V22F6 (#2859), motor rail", "qty": 1, "unit_usd": 27.95, "source": "https://www.pololu.com/product/2859"},
 {"item": "Pololu Ball Caster with 1/2in Metal Ball (#953)", "qty": 1, "unit_usd": 2.95, "source": "https://www.pololu.com/product/953"},
 {"item": "Pololu M3 x 25 mm screws, 25-pack (#1077): 4 TT motor bolts", "qty": 1, "unit_usd": 3.31, "source": "https://www.pololu.com/product/1077"},
 {"item": "Pololu #2-56 x 3/4 in screws, 25-pack (#2716): caster through its 7.8 mm boss", "qty": 1, "unit_usd": 2.38, "source": "https://www.pololu.com/product/2716"},
 {"item": f"PLA {pla_g} g (hs_rover_chassis printed mass) at Bambu Lab PLA Basic refill US$19.99/kg (price from a search result)", "qty": 1,
  "unit_usd": round(pla_g / 1000 * 19.99, 2), "source": "https://asia.store.bambulab.com/collections/pla/products/pla-basic-filament"}]
bom = call("hs_bom_check", {"lines": lines, "budget_usd": 250,
           "salvage_rejected_because": "This variant answers the new-parts budget; the salvaged route is HS-ROVER-SALVAGE-A and the LiDAR-vacuum donor."})
log["bom"] = bom
status = tb.call("hs_project_status", {"project_id": pid})["result"]
proj = ObjectiveProject.load(pid)
shutil.copytree(proj.root, out / "project", dirs_exist_ok=True)
(out / "bom.json").write_text(json.dumps(lines, indent=1) + "\n")
(out / "status_envelope.json").write_text(json.dumps(status, indent=1, default=str) + "\n")
print(json.dumps({"chassis": chassis["summary"], "chassis_problems": chassis["problems"], "drive": drive["summary"],
                  "tt": {k: tt[k] for k in ("ratio", "speed_at_cruise_m_s", "current_a", "slope_torque_share_of_stall", "checks")},
                  "energy": energy["summary"], "energy_problems": energy["problems"], "bom": bom["summary"], "bom_problems": bom["problems"],
                  "open": status.get("open")}, indent=1, default=str))
