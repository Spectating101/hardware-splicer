"""Record publicly described repair cases in separated intake/outcome fixtures.

The "blind" intake files contain only observations available at that point in
the repair. Held-out creator-reported fixes live in a different directory and
are NEVER imported by the diagnostic algorithm.

This is a retrospective, author-selected replay. It is NOT a prospective or
independent generalization benchmark and is NOT transcript/video-frame analysis.
"""
from __future__ import annotations
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent
CASES=[
  {
   "id":"gbc_2020_broken_power_path",
   "device":"Nintendo Game Boy Color",
   "source":{"url":"https://www.youtube.com/watch?v=2BmGMi0IEx4",
             "creator":"Odd Tinkering","date":"2020-02-08",
             "evidence_available":"video description supplied by creator (not full video frames/transcript)"},
   "initial":{"symptoms":["No power with installed batteries",
                          "Battery compartment and terminals visibly corroded",
                          "Display has discoloration/dark damaged area"],
              "when_it_fails":"Never starts after power switch used",
              "repro_steps":["Insert correct batteries and try to turn on"],
              "observed_codes":["no_power","corrosion_visible","screen_damage"]},
   "additional_observations":{
       "symptoms":["After cleaning accessible battery contacts, still no power",
                   "Power switch checked functional",
                   "Continuity along battery positive supply path is broken"],
       "observed_codes":["contacts_cleaned_still_dead","switch_checked_good","battery_path_continuity_open"]
   },
   "source_outcome":{
       "root_cause":"open_power_trace",
       "restoration_steps":["Creator bridged a broken battery-terminal connection with wire",
                            "Creator later replaced a damaged LCD polarizer and refurbished exterior"],
       "outcome_claim":"Power returned after connection bridge; visual display subsequently restored",
       "source_type":"creator-reported outcome, not independent lab verification"
   }
  },
  {
   "id":"dmg_2016_battery_contact_corrosion",
   "device":"Nintendo Game Boy DMG-01",
   "source":{"url":"https://www.youtube.com/watch?v=mMjNzPR7nVE",
             "creator":"Retro Sales","date":"2016-08-23",
             "evidence_available":"title and short YouTube description; lacks detailed repair measurements"},
   "initial":{"symptoms":["Does not turn on with batteries",
                          "Battery terminals heavily corroded"],
              "when_it_fails":"No power at switch-on",
              "repro_steps":["Insert correct batteries and attempt power"],
              "observed_codes":["no_power","corrosion_visible"]},
   "additional_observations":{
       "symptoms":["Battery contacts visibly show substantial corrosion"],
       "observed_codes":["corrosion_visible"]
   },
   "source_outcome":{
       "root_cause":"corroded_battery_contact",
       "restoration_steps":["Video is described as a no-power battery-contact corrosion fix; detailed electrical procedure not documented in retrieved description"],
       "outcome_claim":"Repair claimed by title/description; specific measurements and causal proof not accessible",
       "source_type":"low-detail creator-description outcome (weak ground truth)"
   }
  },
  {
   "id":"switch_2024_dead_usb_c",
   "device":"Nintendo Switch (original)",
   "source":{"url":"https://www.youtube.com/watch?v=0HZSA8nZd_k",
             "creator":"Odd Tinkering","date":"2024-07-15",
             "evidence_available":"creator video description; no full frame-by-frame inspection"},
   "initial":{"symptoms":["Console will not turn on",
                          "Charging produces no visible response",
                          "USB-C cable is used for charging"],
              "when_it_fails":"At attempted power-on and charging",
              "repro_steps":["Attach known charger and observe any charge indication"],
              "observed_codes":["no_power","no_charge_response","usb_c_power_input"]},
   "additional_observations":{
       "symptoms":["Charging controller checked with multimeter and appeared functional",
                   "Physical USB-C charging connector appears damaged"],
       "observed_codes":["charge_ic_checked_good","charging_port_physically_damaged"]
   },
   "source_outcome":{
       "root_cause":"damaged_usb_c_port",
       "restoration_steps":["Creator replaced visibly damaged USB-C port",
                            "Creator separately replaced scratched digitizer"],
       "outcome_claim":"Creator reports restoration of charging/power after USB-C replacement",
       "source_type":"creator-reported outcome; no independent solder-joint verification"
   }
  },
  {
   "id":"ps2_2021_disc_no_read",
   "device":"Sony PlayStation 2 Slim",
   "source":{"url":"https://www.youtube.com/watch?v=8hGGVW_mGEI",
             "creator":"Odd Tinkering","date":"2021-01-06",
             "evidence_available":"creator video description; no frame-by-frame viewing"},
   "initial":{"symptoms":["Console powers on",
                          "Game discs do not load or read",
                          "Device obtained as junk or for spares"],
              "when_it_fails":"When attempting to read disc media",
              "repro_steps":["Power on console and try a known working game disc"],
              "observed_codes":["boots_normally","disc_read_failure"]},
   "additional_observations":{
       "symptoms":["Optical disc mechanism was inspected",
                   "Replacing optical pickup or drive considered reasonable"],
       "observed_codes":["optical_pickup_suspected"]
   },
   "source_outcome":{
       "root_cause":"optical_pickup_failure",
       "restoration_steps":["Creator replaced the disc drive/laser assembly",
                            "Creator adjusted optical mechanism screws afterward"],
       "outcome_claim":"Creator reports restoring disc reading after drive/laser replacement and adjustment",
       "source_type":"creator-reported outcome; exact failing electronic component not instrumented"
   }
  }
]

def generate():
    (HERE/"cases").mkdir(parents=True,exist_ok=True)
    (HERE/"hidden_outcomes").mkdir(parents=True,exist_ok=True)
    for v in CASES:
        x={
          "schema":"hs.restoration.video_blind_intake.v1",
          "case_id":v["id"],"device":v["device"],
          "repair_intake":{
            "symptoms":v["initial"]["symptoms"],
            "when_it_fails":v["initial"]["when_it_fails"],
            "device_hint":v["device"],
            "repro_steps":v["initial"]["repro_steps"],
          },
          "initial_codes":v["initial"]["observed_codes"],
          "followup_repair_intake":{
            "symptoms":v["additional_observations"]["symptoms"],
            "device_hint":v["device"],
          },
          "followup_codes":v["additional_observations"]["observed_codes"],
          "source_context":{
            "url":v["source"]["url"],"creator":v["source"]["creator"],
            "date":v["source"]["date"],
            "retrieval_limit":v["source"]["evidence_available"],
          },
        }
        y={
          "schema":"hs.restoration.video_heldout_outcome.v1",
          "case_id":v["id"],"device":v["device"],
          "root_cause":v["source_outcome"]["root_cause"],
          "repair_steps":v["source_outcome"]["restoration_steps"],
          "reported_outcome":v["source_outcome"]["outcome_claim"],
          "evidence_quality":v["source_outcome"]["source_type"],
          "source_url":v["source"]["url"],
        }
        (HERE/"cases"/f'{v["id"]}.json').write_text(json.dumps(x,indent=2)+"\n")
        (HERE/"hidden_outcomes"/f'{v["id"]}.json').write_text(json.dumps(y,indent=2)+"\n")
    print("wrote",len(CASES),"source-separated fixtures")

if __name__=="__main__":generate()
