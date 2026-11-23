"""
TOY CORE v1: The "Soul" Generator
=================================
Validates the capability to design cheap, "Alive" circuits for plushies.
Target: <$3 BOM, Reacts to Sound, Moves Servos.
"""

import sys
import os
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from generative_design_agent import GenerativeAgent

def generate_toy_soul():
    print(">>> DESIGNING 'LIVING TOY' CORE <<<")
    agent = GenerativeAgent()
    
    prompt = """
    Design a tiny, ultra-low-cost PCB (The 'Soul Core') to be stuffed inside a small plush toy. 
    
    Requirements:
    1.  **Brain:** Cheapest possible MCU that can handle I/O (e.g., CH32V003 or ATTiny).
    2.  **Movement:** Drive 2x SG90 Micro Servos (PWM).
    3.  **Senses:** One Electret Microphone (Analog Input) to detect loud noises.
    4.  **Power:** Single LiPo Cell (3.7V) with a simple LDO regulator.
    5.  **Behavior:** When mic detects sound -> Wiggle servos randomly. 
    
    Constraint: Keep BOM cost under $2.00.
    """
    
    # We use detailed mode to get the reasoning
    res = agent.generate_solution(prompt, mode="detailed")
    
    print("-" * 50)
    print(f"NARRATIVE:\n{res.get('narrative')}")
    print("-" * 50)
    
    plan = res.get('plan', {})
    comps = plan.get('components_to_add', [])
    
    print("\n[BOM CHECK]")
    for c in comps:
        print(f" - {c['type']} ({c['value']})")

if __name__ == "__main__":
    generate_toy_soul()
