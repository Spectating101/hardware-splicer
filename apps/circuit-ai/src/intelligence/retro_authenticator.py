"""
Retro-Verify Module (The 'Downgrade' Pivot)

Specialized logic to distinguish Genuine vs Fake game cartridges.
Uses simple visual heuristics that are high-value to collectors.
"""

from typing import List, Dict, Any
from loguru import logger

class RetroAuthenticator:
    """Authenticates retro game cartridges (Pokemon, SNES, NES)."""

    # Database of Genuine Characteristics
    GENUINE_DB = {
        "pokemon_emerald": {
            "required_chips": ["Macronix", "Flash"],
            "forbidden_chips": ["Blob", "COB"], # Chip On Board (Black blob)
            "pcb_color": "Green",
            "battery_required": True,
            "golden_rectangle": True # Specific visual marker on back
        },
        "snes_generic": {
            "forbidden_text": ["Nintondo", "Ninlendo"],
            "required_text": ["Nintendo"]
        }
    }

    def __init__(self):
        logger.info("RetroAuthenticator initialized")

    def verify_cartridge(self, detections: List[Any], ocr_text: str, quality: str = "high") -> Dict[str, Any]:
        """
        Analyzes board for signs of counterfeiting.
        """
        if quality not in ("high", "medium"):
            return {
                "verdict": "UNKNOWN",
                "confidence": "0%",
                "reasons": ["Detection quality too low to authenticate."],
                "summary": "AUTHENTICATION RESULT: UNKNOWN\n- Detection quality too low to authenticate."
            }

        verdict = "LIKELY GENUINE"
        reasons = []
        confidence = 0.8
        
        # 1. The "Black Blob" Check (The #1 tell for fakes)
        # We assume 'Resestor' or 'Cap1' might be misclassified blobs if we trained a 'Blob' class,
        # but for now we look for lack of proper ICs in a sea of nothing.
        
        # In a real fork, we would train YOLO on 'Black Blob' class.
        # Here we simulate the logic:
        ic_count = sum(1 for d in detections if d.class_name in ["ic_chip", "MOSFET", "Transformer"])
        
        if ic_count == 0:
            verdict = "FAKE"
            reasons.append("No standard IC chips detected. Likely uses 'Glop-Top' (Blob) cheap manufacturing.")
            confidence = 0.95
        
        # 2. Battery Check (Pokemon games need batteries for clocks)
        battery_found = any("battery" in d.class_name.lower() or "coin" in d.class_name.lower() for d in detections)
        # Heuristic: If we OCR "Emerald" or "Ruby" but see no battery
        if ("emerald" in ocr_text.lower() or "ruby" in ocr_text.lower()) and not battery_found:
             if verdict == "LIKELY GENUINE":
                 verdict = "SUSPICIOUS"
             reasons.append("Pokemon Ruby/Emerald/Sapphire usually require a battery for the clock. None detected.")

        # 3. OCR Typos (Nintondo)
        bad_words = ["nintondo", "ninlendo", "gameoy"]
        for bad in bad_words:
            if bad in ocr_text.lower():
                verdict = "FAKE"
                reasons.append(f"Typos detected on board: '{bad}'. Nintendo does not make typos.")
                confidence = 1.0

        # 4. Board Quality (Solder Mask)
        # (This would use the FaultDetector's color analysis)
        # Fake boards often look "Yellowish" cheap, real are "Deep Green" or "Blue"
        
        return {
            "verdict": verdict,
            "confidence": f"{confidence:.0%}",
            "reasons": reasons,
            "summary": f"AUTHENTICATION RESULT: {verdict}\n" + "\n".join(f"- {r}" for r in reasons)
        }
