"""
Circuit-AI EXTREME Stress Test
==============================
Pushing the agents to failure to measure robustness.
1. Cognitive Load: Complex Aerospace Design
2. Algorithmic Stress: High-Density Routing
3. Inference Stress: The "Burnt Component" Scenario
"""

import sys
import os
import random
import time

# Fix path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from repair_orchestrator import RepairOrchestrator
from generative_design_agent import GenerativeAgent
from routing_engine import AutoRouter

def test_cognitive_load(agent):
    print("\n[TEST 1] COGNITIVE LOAD: CubeSat Power System")
    print("Prompting AI for a highly constrained aerospace design...")
    
    prompt = """
    Design a Power Distribution Unit (PDU) for a 1U CubeSat.
    Requirements:
    1. Triple-junction solar input (MPPT required).
    2. Redundant 3.3V and 5V busses.
    3. Battery heater protection.
    4. Components must be radiation-tolerant equivalents if possible.
    """
    
    start = time.time()
    res = agent.generate_solution(prompt)
    duration = time.time() - start
    
    print(f"Time: {duration:.2f}s")
    print(f"Narrative: {res.get('narrative')}")
    
    # Validation: Did it get the complexity?
    plan = res.get('plan', {})
    comps = plan.get('components_to_add', [])
    
    has_mppt = any("MPPT" in str(c) for c in comps)
    has_redundancy = len([c for c in comps if "Regulator" in str(c)]) >= 2
    
    if has_mppt: print("✅ AI understood MPPT requirement.")
    else: print("❌ AI missed MPPT.")
        
    if has_redundancy: print("✅ AI implemented redundant rails.")
    else: print("❌ AI missed redundancy.")

def test_routing_stress():
    print("\n[TEST 2] ALGORITHMIC STRESS: The 'Maze of Death'")
    width, height = 100, 100
    router = AutoRouter(width, height, resolution=1.0)
    
    # Generate 400 random obstacles (simulating a dense BGA fanout or messy board)
    print("Generating 400 random obstacles...")
    random.seed(42) # Deterministic chaos
    for _ in range(400):
        x, y = random.randint(0, 90), random.randint(0, 90)
        router.add_obstacle(x, y, 2, 2)
        
    start = (5, 5)
    end = (95, 95)
    
    print(f"Attempting to route from {start} to {end} through chaos...")
    t0 = time.time()
    path = router.route_net(start, end)
    t1 = time.time()
    
    if path:
        print(f"✅ Path Found! Length: {len(path)} segments.")
        print(f"✅ Calculation Time: {t1-t0:.4f}s")
    else:
        print("❌ Router Failed (Blocked or Timeout).")

def test_inference_stress(orchestrator):
    print("\n[TEST 3] INFERENCE STRESS: The 'Burnt Component' Scenario")
    # Scenario: Vision sees a component but CANNOT read the label/refdes.
    # It only knows the location and that it looks 'black' and 'burnt'.
    # The Orchestrator must ask the AI to guess based on neighbors.
    
    print("Simulating unknown burnt component between MCU (U1) and Connector (J1)...")
    
    # We manually invoke the consultation method with a vague prompt
    # This mocks the AI having to look at the 'Netlist Context' (in prompt form)
    
    vague_prompt = """
    I have a burnt component on a PCB. I cannot read the markings.
    It is located physically between a 5V USB input connector and a 3.3V LDO Regulator input pin.
    It is a 2-pin black SMD component (0805).
    What is it most likely to be? 
    Return JSON with 'type', 'value', 'package'.
    """
    
    res = orchestrator.ai.generate_solution(vague_prompt)
    
    print(f"AI Hypothesis: {res.get('narrative')}")
    
    # Check if it guessed a Fuse or Ferrite Bead (Correct engineering answers)
    narrative = str(res).lower()
    if "fuse" in narrative or "ferrite" in narrative or "inductor" in narrative:
        print("✅ AI inferred correctly (Fuse/Protection).")
    elif "resistor" in narrative and "0" in narrative:
        print("✅ AI inferred correctly (0-ohm Jumper).")
    else:
        print("❌ AI guessed wrong (e.g., Capacitor in series is unlikely for power input).")

if __name__ == "__main__":
    print(">>> INITIALIZING EXTREME CAPABILITY TEST <<< ")
    
    # Init Agents
    try:
        agent = GenerativeAgent()
        orchestrator = RepairOrchestrator()
    except Exception as e:
        print(f"Failed to init agents: {e}")
        sys.exit(1)

    # Run Tests
    test_cognitive_load(agent)
    test_routing_stress()
    test_inference_stress(orchestrator)
    
    print("\n>>> TEST SUITE COMPLETE <<< ")
