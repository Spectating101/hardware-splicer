import asyncio
import re
from typing import Dict, Any

class ComponentForensicsEngine:
    """
    Applies OSINT-style multi-pivot logic to Component Verification.
    Instead of checking Sanctions, we check Manufacturing Validity.
    """
    
    def __init__(self):
        # 1. The "Truth Database" (Simulated Datasheet/Manufacturer Specs)
        self.specs = {
            "ATMEGA328P-PU": {
                "manufacturer": "Microchip/Atmel",
                "package": "DIP-28",
                "valid_date_codes": r"^(1[8-9]|2[0-5])[0-5][0-9]$", # 2018-2025
                "font_style": "Laser_Serif",
                "pin_1_indicator": "Dimple"
            },
            "STM32F103C8T6": {
                "manufacturer": "STMicroelectronics",
                "package": "LQFP-48",
                "valid_date_codes": r"^(2[0-4])[0-5][0-9]$",
                "font_style": "Laser_Sans",
                "pin_1_indicator": "Laser_Dot"
            }
        }
        
        # 2. The "Risk Database" (Simulated Counterfeit Alerts)
        self.known_fakes = {
            "ATMEGA328P-PU": ["9901", "2155"], # Impossible dates or bad batches
            "STM32F103C8T6": ["9999", "CHN_GH"]
        }

    async def investigate_component(self, part_number: str, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        print(f"--- 🕵️‍♂️ Forensic Audit: {part_number} ---")
        
        # Pivot 1: Specification Match
        spec = self.specs.get(part_number)
        if not spec:
            return {"status": "UNKNOWN", "reason": "No spec data found for part."}
            
        flags = []
        
        # Check 1: Package Consistency
        if extracted_data.get("package") != spec["package"]:
            flags.append(f"📦 PACKAGE MISMATCH: Saw {extracted_data.get('package')}, Expected {spec['package']}")
            
        # Check 2: Date Code Logic (The "Temporal Conflict" Check)
        date_code = extracted_data.get("date_code", "")
        if not re.match(spec["valid_date_codes"], date_code):
            flags.append(f"📅 INVALID DATE CODE: {date_code} does not match factory format.")
            
        # Check 3: Known Counterfeit DB (The "Sanctions" Check)
        if date_code in self.known_fakes.get(part_number, []):
            flags.append(f"⚠️ KNOWN FAKE BATCH: Date code {date_code} is linked to counterfeits.")
            
        # Check 4: Visual Anomaly (The "Deep Vision" Check)
        if extracted_data.get("font_style") != spec["font_style"]:
            flags.append(f"🎨 FONT ANOMALY: Saw {extracted_data.get('font_style')}, Expected {spec['font_style']}")

        # Final Verdict
        if not flags:
            return {"status": "✅ AUTHENTIC", "confidence": 0.95, "details": "Matches all factory specs."}
        else:
            return {"status": "⛔ SUSPICIOUS", "confidence": 0.10, "flags": flags}

async def run_demo():
    engine = ComponentForensicsEngine()
    
    # Case A: A Real Chip
    real_chip = {
        "package": "DIP-28",
        "date_code": "2140", # 40th week of 2021
        "font_style": "Laser_Serif"
    }
    print(await engine.investigate_component("ATMEGA328P-PU", real_chip))
    
    print("\n" + "="*30 + "\n")
    
    # Case B: A "Remarked" Fake (Wrong font, impossible date)
    fake_chip = {
        "package": "DIP-28",
        "date_code": "9901", # Known fake batch
        "font_style": "Printed_White" # Wrong marking style
    }
    print(await engine.investigate_component("ATMEGA328P-PU", fake_chip))

if __name__ == "__main__":
    asyncio.run(run_demo())
