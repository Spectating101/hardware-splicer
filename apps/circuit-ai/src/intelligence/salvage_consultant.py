"""
Salvage Consultant Module (Final Commercial Edition)

1. Identifies Functional Modules (Upcycling).
2. Alerts on High-Value Silicon (Reselling).
3. Suggests 'Project Recipes' (Value-Add).
"""

from typing import List, Dict, Any
from loguru import logger

class SalvageConsultant:
    """The 'Appraiser' of the Intelligence Stack."""

    # 1. RECIPES: What can you build with these parts?
    PROJECT_RECIPES = {
        "Smart WiFi Switch": {
            "requires": ["Relay Switching Block", "Wireless/RF Module"],
            "value_add": "Sell as 'IoT Relay Kit' ($15) instead of scrap ($1)."
        },
        "Bluetooth Speaker": {
            "requires": ["Audio Amplifier Stage", "Wireless/RF Module"],
            "value_add": "Sell as 'DIY Audio Kit' ($20) instead of scrap."
        },
        "Bench Power Supply": {
            "requires": ["Power Supply Stage", "connector"],
            "value_add": "Useful lab tool. Worth keeping."
        },
        "Robot Controller": {
            "requires": ["Motor Driver Stage", "Wireless/RF Module"],
            "value_add": "High value for robotics hobbyists."
        }
    }

    # 2. MODULE SIGNATURES (How to recognize blocks)
    MODULE_SIGNATURES = {
        "Power Supply Stage": {
            "required": ["Transformer", "Cap4"], 
            "reuse_difficulty": "Medium",
            "extraction_tip": "Saw off HV section. Use as 12V source."
        },
        "Audio Amplifier Stage": {
            "keywords": ["audio", "amp", "speaker", "vol"],
            "reuse_difficulty": "Easy",
            "extraction_tip": "Keep audio IC and headers intact."
        },
        "Relay Switching Block": {
            "keywords": ["relay", "no", "nc"],
            "reuse_difficulty": "Easy",
            "extraction_tip": "Desolder whole relay + transistor unit."
        },
        "Wireless/RF Module": {
            "keywords": ["wifi", "bt", "bluetooth", "rf", "esp32", "esp8266"],
            "reuse_difficulty": "Medium",
            "extraction_tip": "Often a daughterboard. Keep antenna."
        },
        "Motor Driver Stage": {
            "required": ["MOSFET"],
            "min_count": {"MOSFET": 2},
            "reuse_difficulty": "Medium",
            "extraction_tip": "H-Bridge circuit for motors."
        }
    }

    # 3. JACKPOT KEYWORDS (Reseller Mode)
    HIGH_VALUE_KEYWORDS = {
        "xilinx": {"type": "FPGA", "est_value": "$40+", "reason": "Programmable Logic"},
        "altera": {"type": "FPGA", "est_value": "$40+", "reason": "Programmable Logic"},
        "stm32": {"type": "MCU", "est_value": "$10", "reason": "High demand MCU"},
        "atmega": {"type": "MCU", "est_value": "$5", "reason": "Arduino compatible"},
        "esp32": {"type": "WiFi/BT", "est_value": "$6", "reason": "IoT Standard"},
        "nvidia": {"type": "GPU", "est_value": "$$$", "reason": "Graphics Silicon"},
        "gold": {"type": "Metal", "est_value": "Scrap", "reason": "Plating detected"}
    }

    def __init__(self):
        logger.info("SalvageConsultant initialized (Commercial Edition)")

    def evaluate_harvest_potential(self, detections: List[Any], board_type: str, quality: str = "high") -> Dict[str, Any]:
        """
        Full appraisal: Modules, Jackpots, and Project Ideas.
        """
        if quality not in ("high", "medium"):
            return {
                "summary": "Detection quality too low for salvage recommendations.",
                "modules": [],
                "jackpots": [],
                "projects": []
            }

        # Inventory Build
        inventory = {}
        all_text = ""
        for det in detections:
            inventory[det.class_name] = inventory.get(det.class_name, 0) + 1
            if det.text_content:
                all_text += " " + det.text_content.lower()

        # A. Detect Functional Modules
        modules_found = []
        found_module_names = set()
        
        for mod_name, sig in self.MODULE_SIGNATURES.items():
            # Check requirements
            match = True
            if "required" in sig:
                if not all(inventory.get(req, 0) > 0 for req in sig["required"]):
                    match = False
            
            if match and "min_count" in sig:
                for comp, count in sig["min_count"].items():
                    if inventory.get(comp, 0) < count:
                        match = False; break
            
            if match and "keywords" in sig:
                if not any(k in all_text for k in sig["keywords"]):
                    match = False
            
            if match:
                modules_found.append({
                    "name": mod_name,
                    "difficulty": sig["reuse_difficulty"],
                    "tip": sig["extraction_tip"]
                })
                found_module_names.add(mod_name)

        # B. Detect Jackpots (Reseller)
        jackpots = []
        for kw, data in self.HIGH_VALUE_KEYWORDS.items():
            if kw in all_text:
                jackpots.append(data)

        # C. Generate Project Recipes (The "Builder" Feature)
        project_ideas = []
        for project, recipe in self.PROJECT_RECIPES.items():
            # Check if we have all required modules
            if all(req in found_module_names for req in recipe["requires"]):
                project_ideas.append({
                    "name": project,
                    "value_proposition": recipe["value_add"]
                })
            # Also suggest if we are just missing ONE thing (Upsell opportunity)
            else:
                missing = [req for req in recipe["requires"] if req not in found_module_names]
                if len(missing) == 1:
                     project_ideas.append({
                        "name": f"Build {project} (Need {missing[0]})",
                        "value_proposition": "You are 1 part away from this kit."
                    })

        return {
            "summary": self._generate_summary(modules_found, jackpots, project_ideas),
            "modules": modules_found,
            "jackpots": jackpots,
            "projects": project_ideas
        }

    def _generate_summary(self, modules: List[Dict], jackpots: List[Dict], projects: List[Dict]) -> str:
        summary = ""
        
        # 1. The Money Shot (Jackpots)
        if jackpots:
            summary += "🚨 $$$ JACKPOT ALERT $$$:\n"
            for j in jackpots:
                summary += f"  - {j['type']} found! Est: {j['est_value']}\n"
            summary += "\n"

        # 2. The Upcycle Shot (Modules)
        if modules:
            summary += "🛠️ Usable Modules:\n"
            for m in modules:
                summary += f"  - {m['name']} ({m['difficulty']})\n"
        
        # 3. The Builder Shot (Projects)
        if projects:
            summary += "\n💡 Project Ideas (Upcycle Value):\n"
            for p in projects:
                summary += f"  - {p['name']}: {p['value_proposition']}\n"

        if not summary:
            summary = "No significant value detected. Standard scrap."
            
        return summary
