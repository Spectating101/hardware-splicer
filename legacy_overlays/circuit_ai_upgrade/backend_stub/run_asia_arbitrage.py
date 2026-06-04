"""
Circuit-AI: ASIA MARKET ARBITRAGE TEST
======================================
Target Markets: Taiwan (Shopee TW), Indonesia (Tokopedia).
Strategy: Source locally (cheap), Upcycle, Sell Globally (USD) or Locally (High End).
"""

import sys
import os

# --- 1. THE LOCAL SUPPLY (What we find in Taipei/Jakarta Junk Bins)
# Prices in Local Currency converted to approx USD for comparison
# 1 USD ~= 32 TWD ~= 16,000 IDR

LOCAL_JUNK_STREAM = [
    {
        "name": "Broken Gogoro ECU / Controller",
        "source": "Shopee TW / Scooter Shop",
        "cost_usd": 15.00,  # ~480 TWD (Scrap price)
        "type": "automotive_module",
        "contains": ["High Power MOSFETs", "STM32 MCU", "CAN Bus Driver"]
    },
    {
        "name": "Internet Cafe GTX 1060 (Dead Fan/Overheated)",
        "source": "Tokopedia / Glodok",
        "cost_usd": 30.00,  # ~480,000 IDR
        "type": "pc_hardware",
        "contains": ["VRM Modules", "GDDR Memory", "GPU Core (Maybe dead)"]
    },
    {
        "name": "Industrial PLC (Mitsubishi FX Series - Dead)",
        "source": "Taiwan Factory Liquidation",
        "cost_usd": 20.00, # ~640 TWD
        "type": "industrial",
        "contains": ["Optocouplers", "Relays", "24V Power Supply"]
    }
]

# --- 2. THE GLOBAL/UPCYCLED VALUE (What Circuit-AI creates)
GLOBAL_MARKET_VALUE = {
    # Gogoro Upcycle: "Electric Go-Kart Controller"
    "automotive_module": {
        "product_name": "Generic 3kW BLDC Driver (Refurbished)",
        "sale_price": 120.00,
        "difficulty": "High"
    },
    # GPU Upcycle: "VRM Power Board" or "Crypto Mining Riser" parts
    # Or just fixing it and selling as "Refurbished GPU"
    "pc_hardware": {
        "product_name": "Refurbished GTX 1060",
        "sale_price": 90.00, # Lower than new, but profitable
        "difficulty": "Medium"
    },
    # PLC Upcycle: "Home Automation Relay Board"
    "industrial": {
        "product_name": "Industrial Grade 8-Channel Relay Module",
        "sale_price": 85.00,
        "difficulty": "Low"
    }
}

class AsiaArbitrageEngine:
    def evaluate_opportunities(self):
        print(f"{'SOURCE ITEM':<35} | {'COST':<8} | {'PRODUCT TARGET':<35} | {'SELL':<8} | {'PROFIT':<8} | {'ROI'}")
        print("-" * 115)
        
        total_profit = 0
        
        for item in LOCAL_JUNK_STREAM:
            target = GLOBAL_MARKET_VALUE.get(item['type'])
            
            cost = item['cost_usd']
            revenue = target['sale_price']
            
            # Estimate Repair/Labor Cost (Local labor/robot power is cheap)
            # Let's say $10 for consumables/electricity
            overhead = 10.00
            
            profit = revenue - cost - overhead
            roi = (profit / (cost + overhead)) * 100
            
            print(f"{item['name']:<35} | ${cost:<7.2f} | {target['product_name']:<35} | ${revenue:<7.2f} | ${profit:<7.2f} | {roi:.0f}%")
            total_profit += profit

        print("-" * 115)
        print(f"POTENTIAL BATCH PROFIT: ${total_profit:.2f}")
        print("STRATEGY: Buy local trash, sell global functionality.")

if __name__ == "__main__":
    engine = AsiaArbitrageEngine()
    engine.evaluate_opportunities()
