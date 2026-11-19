"""
Circuit-AI REAL WORLD SIMULATION
================================
Benchmarking the AI against real Internet questions from Reddit/StackExchange.
"""

import sys
import os
import json
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from generative_design_agent import GenerativeAgent

QUESTIONS = [
    {
        "source": "StackExchange (Repair)",
        "prompt": "I have a burnt PCB track on a washing machine board. The copper is lifted and carbonized. How do I repair this track properly?",
        "expected_keywords": ["scrape", "solder mask", "jumper wire", "bridge", "epoxy"]
    },
    {
        "source": "Reddit r/AskElectronics (Identification)",
        "prompt": "I have a burnt 2-pin component on the power input of a graphics card. It is black and has no visible markings. It connects the 12V rail to the main circuit. Is it a resistor or a diode?",
        "expected_keywords": ["fuse", "shunt", "inductor", "ferrite", "protection"]
    },
    {
        "source": "Reddit r/PrintedCircuitBoard (Design Review)",
        "prompt": "Review my schematic for a complex STM32 design. I am new to hardware. What are the most common mistakes I should avoid before ordering?",
        "expected_keywords": ["decoupling", "capacitor", "test points", "simulation", "ground"]
    }
]

def run_real_world_test():
    print(">>> CIRCUIT-AI VS. THE INTERNET <<<")
    agent = GenerativeAgent()
    
    score = 0
    
    for q in QUESTIONS:
        print(f"\n[TEST] Source: {q['source']}")
        print(f"User Question: '{q['prompt']}'")
        
        start = time.time()
        res = agent.generate_solution(q['prompt'], mode="detailed")
        duration = time.time() - start
        
        narrative = str(res.get('narrative')).lower()
        print(f"AI Answer ({duration:.2f}s): {res.get('narrative')}")
        
        # Grading
        hits = [k for k in q['expected_keywords'] if k in narrative]
        print(f"   > Keywords Matched: {hits} / {len(q['expected_keywords'])}")
        
        if len(hits) >= 2:
            print("   ✅ PASS: Advice aligns with expert consensus.")
            score += 1
        else:
            print("   ❌ FAIL: Advice too generic or incorrect.")

    print(f"\nFINAL SCORE: {score}/{len(QUESTIONS)}")

if __name__ == "__main__":
    run_real_world_test()
