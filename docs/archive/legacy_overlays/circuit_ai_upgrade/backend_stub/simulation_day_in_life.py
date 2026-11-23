"""
Circuit-AI: DAY IN THE LIFE SIMULATION
======================================
Scenario: Retro Game Repair (Game Boy Cartridge)
User Goal: Fix save functionality.
"""

import sys
import os
import json
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from generative_design_agent import GenerativeAgent
from repair_orchestrator import RepairOrchestrator
from gcode_engine import SmartCAM

def print_step(step, msg):
    print(f"\n[{step}] {msg}")
    time.sleep(0.5) # Narrative pacing

def run_simulation():
    print(">>> SIMULATION START: USER 'RETRO_FIXER_99' LOGS IN <<<")
    
    # 1. THE USER INPUT (Simulating the UI Prompt)
    print_step("STEP 1: USER INPUT", "User types: 'My Game Boy cartridge won't save. I see a battery component BAT1. What do I do?'")
    
    agent = GenerativeAgent()
    
    # We ask the AI what to do
    response = agent.generate_solution(
        "My Game Boy cartridge won't save. I see a battery component BAT1. What should I replace it with?"
    )
    
    print(f"   AI Narrative: {response.get('narrative')}")
    
    # 2. THE DIAGNOSIS (Simulating Vision)
    print_step("STEP 2: VISION SCAN", "User places board under camera...")
    
    # We simulate the Vision Engine detecting the specific geometry of BAT1
    # Assuming Vision detects it's a 20mm coin cell pad
    vision_data = {
        "ref": "BAT1", 
        "x": 30.0, 
        "y": 45.0, 
        "detected_shape": "circle_20mm"
    }
    print(f"   Vision Engine: Detected {vision_data['ref']} at ({vision_data['x']}, {vision_data['y']})")

    # 3. THE SPECIFICATION (Closing the Loop)
    print_step("STEP 3: SPECIFICATION", "System identifying exact part number...")
    
    # Consult AI for specific part
    spec_prompt = f"I have a Game Boy cartridge battery labeled BAT1. Vision detects a 20mm diameter. What is the exact CR part number?"
    spec_res = agent.generate_solution(spec_prompt)
    
    ai_plan = spec_res.get('plan', {})
    print(f"   AI Identification: {spec_res.get('narrative')}")
    
    # Validation: Did it guess CR2025 or CR1616?
    narrative = str(spec_res.get('narrative'))
    if "2025" in narrative or "1616" in narrative:
        print("   ✅ SUCCESS: AI identified valid Coin Cell types.")
    else:
        print("   ❌ FAILURE: AI did not suggest a battery type.")

    # 4. THE ACTION (Fabrication)
    print_step("STEP 4: REPAIR EXECUTION", "Generating Desolder/Resolder Job...")
    
    cam = SmartCAM()
    # Mocking the AI's result into component data
    comps_to_fix = [{
        "ref": "BAT1", 
        "x": 30.0, 
        "y": 45.0, 
        "sensitive": True # Batteries explode if heated too much!
    }]
    
    gcode = cam.generate_optimized_probe_sequence(comps_to_fix)
    
    # Validate the G-Code specifically for SAFETY (Battery)
    if "WARNING" in gcode:
        print("   ✅ SAFETY CHECK: System flagged BAT1 as sensitive.")
    else:
        print("   ❌ DANGER: System treated Lithium Battery as normal component!")
        
    print(f"   Output: {len(gcode.splitlines())} lines of G-Code ready for Dum-E.")

    print_step("STEP 5: CLOSING", "User clicks 'Execute'. Robot creates new save battery connection.")

if __name__ == "__main__":
    run_simulation()
