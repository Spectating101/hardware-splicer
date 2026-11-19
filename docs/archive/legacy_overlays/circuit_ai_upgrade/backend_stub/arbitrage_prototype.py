"""
Circuit-AI ARBITRAGE PROTOTYPE (Draft)
======================================
Tests the "Dual-Use" Value Extraction Logic.
Prioritizes components that are either Valuable ($) or Useful to Us (Utility).
"""

import json

# 1. THE "INTERNAL UTILITY" DATABASE
# Components we need for our own robots (Dum-E repairs, etc.)
INTERNAL_WISHLIST = {
    "stepper_driver": {"utility": 10, "reason": "Robot arm joints"},
    "microcontroller": {"utility": 9, "reason": "Brain for new nodes"},
    "voltage_regulator": {"utility": 8, "reason": "Power management"},
    "sensor_imu": {"utility": 7, "reason": "Motion tracking"},
    "mosfet": {"utility": 6, "reason": "High power switching"},
    "resistor": {"utility": 1, "reason": "Too cheap, waste of time"},
    "capacitor": {"utility": 1, "reason": "Too cheap, risk of aging"}
}

# 2. THE MOCK SUPPLY (What Vision "Sees" on a Junk Board)
JUNK_BOARD_SCAN = [
    {"ref": "U1", "type": "microcontroller", "part": "STM32F103", "condition": "good"},
    {"ref": "U2", "type": "stepper_driver", "part": "A4988", "condition": "good"},
    {"ref": "C1", "type": "capacitor", "part": "100uF", "condition": "aged"},
    {"ref": "Q1", "type": "mosfet", "part": "IRF540", "condition": "good"},
    {"ref": "R1", "type": "resistor", "part": "10k", "condition": "good"}
]

# 3. THE MOCK MARKET (What eBay says)
MARKET_PRICES = {
    "STM32F103": 5.50,
    "A4988": 1.20, # Cheap on market, but HIGH utility for us
    "100uF": 0.05,
    "IRF540": 0.80,
    "10k": 0.01
}

class ArbitrageEngine:
    def evaluate_board(self, components):
        print(f"{'PART':<15} | {'MARKET ($)':<10} | {'UTILITY':<8} | {'ACTION':<10} | {'REASON'}")
        print("-" * 70)
        
        total_value = 0
        actions = []

        for comp in components:
            part = comp['part']
            ctype = comp['type']
            
            # Get Data
            market_price = MARKET_PRICES.get(part, 0.0)
            utility_info = INTERNAL_WISHLIST.get(ctype, {"utility": 0, "reason": "Unknown"})
            utility_score = utility_info['utility']
            
            # DECISION LOGIC (The "Dual-Use" Strategy)
            action = "IGNORE"
            reason = "Low Value"
            
            # Rule 1: High Market Value (Sell it)
            if market_price > 2.00:
                action = "HARVEST"
                reason = "$$$ Profit"
            
            # Rule 2: High Internal Utility (Keep it)
            # Even if cheap (like A4988), if we need it, we harvest it to save shipping time/cost.
            elif utility_score >= 7:
                action = "HARVEST"
                reason = "Build Stock"
                
            # Rule 3: Condition Check
            if comp['condition'] == "bad":
                action = "SCRAP"
                reason = "Damaged"

            print(f"{part:<15} | ${market_price:<9.2f} | {utility_score:<8} | {action:<10} | {reason}")
            
            if action == "HARVEST":
                total_value += market_price
                actions.append(comp)

        print("-" * 70)
        print(f"TOTAL HARVEST VALUE: ${total_value:.2f}")
        print(f"ITEMS TO HARVEST: {len(actions)}")

if __name__ == "__main__":
    engine = ArbitrageEngine()
    engine.evaluate_board(JUNK_BOARD_SCAN)
