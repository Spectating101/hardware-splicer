"""
Circuit-AI Supply Chain Validator (Draft)
=========================================
Ensures AI recommendations are actually purchasable.
Checks "Cheap Silicon" sources (LCSC, AliExpress) vs "Reliable" sources (DigiKey).
"""

import random
from typing import Dict, List

class SupplyChainValidator:
    def __init__(self):
        # Mock Database of "Real" Stock Status for Demo
        self.stock_db = {
            "CH32V003": {"lcsc": True, "digikey": False, "price": 0.15},
            "STM32F103": {"lcsc": True, "digikey": True, "price": 5.50},
            "RP2040": {"lcsc": True, "digikey": True, "price": 0.80},
            "FakeChip9000": {"lcsc": False, "digikey": False, "price": 0.00}
        }

    def validate_component(self, part_number: str) -> Dict:
        print(f"[SupplyChain] Checking availability for: {part_number}...")
        
        # 1. Lookup (Mock API Call)
        stock_info = self.stock_db.get(part_number)
        
        if not stock_info:
            # Fallback for unknown parts (Simulate "Not Found")
            return {
                "status": "UNKNOWN",
                "risk": "HIGH",
                "message": f"Part {part_number} not found in major catalogues."
            }

        # 2. Analyze Sourcing Risk
        if stock_info["digikey"]:
            return {
                "status": "VERIFIED",
                "risk": "LOW",
                "source": "DigiKey (US Stock)",
                "price": stock_info["price"]
            }
        elif stock_info["lcsc"]:
            return {
                "status": "VERIFIED",
                "risk": "MEDIUM",
                "source": "LCSC (China Stock - 2 week shipping)",
                "price": stock_info["price"],
                "note": "Great for cost reduction, verify shipping time."
            }
        else:
            return {
                "status": "UNAVAILABLE",
                "risk": "CRITICAL",
                "message": "Out of stock globally."
            }

if __name__ == "__main__":
    validator = SupplyChainValidator()
    
    # Test Cases
    parts = ["STM32F103", "CH32V003", "FakeChip9000"]
    
    for p in parts:
        result = validator.validate_component(p)
        print(f"Part: {p} -> Status: {result['status']} | Risk: {result['risk']}")
        if 'source' in result:
            print(f"   Source: {result['source']} @ ${result['price']}")
        print("-" * 40)
