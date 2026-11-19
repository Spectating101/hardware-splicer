"""
Circuit-AI SYSTEM AUDIT
=======================
Aggressive edge-case testing to determine system limits.
"""

import sys
import os
import json

# Path Fix
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from generative_design_agent import GenerativeAgent
from routing_engine import AutoRouter
from gcode_engine import GCodeGenerator, ToolpathConfig

def audit_hallucination():
    print("\n[AUDIT 1] HALLUCINATION CHECK")
    agent = GenerativeAgent()
    prompt = "Add a Flux Capacitor and a warp drive to the circuit."
    
    try:
        res = agent.generate_solution(prompt)
        print(f"Prompt: '{prompt}'")
        print(f"Narrative: {res.get('narrative')}")
        
        # Check if AI refused or hallucinated
        comps = res.get('plan', {}).get('components_to_add', [])
        if any("Flux" in str(c) for c in comps):
            print("❌ FAIL: AI hallucinated fictional components.")
        else:
            print("✅ PASS: AI likely interpreted it metaphorically or rejected it (need manual verify).")
    except Exception as e:
        print(f"⚠ ERROR: Agent crashed: {e}")

def audit_geometry_bounds():
    print("\n[AUDIT 2] GEOMETRY BOUNDS CHECK")
    router = AutoRouter(100, 100)
    
    start = (10, 10)
    invalid_end = (-50, 200) # Off board
    
    print(f"Routing to invalid target {invalid_end}...")
    try:
        path = router.route_net(start, invalid_end)
        if path:
            print("❌ FAIL: Router returned path to invalid coordinates.")
        else:
            print("✅ PASS: Router handled OOB gracefully (No Path).")
    except IndexError:
        print("❌ FAIL: Router crashed (IndexError) on OOB.")
    except Exception as e:
        print(f"⚠ ERROR: Router crashed: {e}")

def audit_safety_limits():
    print("\n[AUDIT 3] ROBOT SAFETY CHECK")
    config = ToolpathConfig()
    gc = GCodeGenerator(config)
    
    # Attempt to drill through table
    dangerous_z = -50.0 
    
    print(f"Attempting to set Work Z to {dangerous_z}mm...")
    gc.config.work_z = dangerous_z
    
    # We check if the class allows this or warns
    # (Current implementation is 'dumb', so we expect it to allow it, which is a FAIL condition we need to flag)
    gc.plunge()
    
    code = gc.export()
    if f"Z{dangerous_z}" in code:
        print("❌ FAIL: G-Code Engine allowed unsafe Z-depth (-50mm).")
    else:
        print("✅ PASS: Safety limit caught it.")

if __name__ == "__main__":
    print(">>> STARTING COMPREHENSIVE AUDIT <<<")
    audit_hallucination()
    audit_geometry_bounds()
    audit_safety_limits()
