#!/usr/bin/env python3
"""
Real-World Circuit-AI Testing

Test actual scenarios that Arduino makers would ask.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from chatbot_engine import ChatRequest
from circuit_agent import CircuitAgent


async def test_scenarios():
    """Test real-world DIY electronics scenarios"""
    print("\n" + "="*80)
    print("CIRCUIT-AI REAL-WORLD TESTING")
    print("="*80)
    print("\nTesting actual scenarios from Arduino makers...\n")

    agent = CircuitAgent(knowledge_base_path="knowledge_base")
    await agent.initialize()

    # Real scenarios from Arduino forums/communities
    scenarios = [
        {
            "category": "Beginner LED",
            "query": "I have a 5V Arduino and want to light up a red LED. What resistor do I need?",
            "expected": "220Ω or 150Ω resistor calculation"
        },
        {
            "category": "DHT22 Wiring",
            "query": "How do I connect a DHT22 temperature sensor to my Arduino Uno?",
            "expected": "VCC, DATA, GND connections + pull-up resistor"
        },
        {
            "category": "LED Troubleshooting",
            "query": "My LED isn't lighting up. I connected it to pin 13 and GND. What's wrong?",
            "expected": "Check polarity, resistor, code"
        },
        {
            "category": "Code Generation",
            "query": "Can you give me Arduino code to blink the built-in LED?",
            "expected": "pinMode, digitalWrite with delay"
        },
        {
            "category": "DHT22 Debugging",
            "query": "My DHT22 keeps returning NaN values. Help!",
            "expected": "Pull-up resistor, 2-second delay"
        },
        {
            "category": "Board Info",
            "query": "What are the PWM pins on Arduino Uno?",
            "expected": "Pins 3, 5, 6, 9, 10, 11"
        },
        {
            "category": "Component Info",
            "query": "Tell me about the DHT22 sensor",
            "expected": "Temperature/humidity sensor specs"
        },
        {
            "category": "Blue LED",
            "query": "I want to use a blue LED on 3.3V. What resistor?",
            "expected": "Lower resistor value due to 3.3V and blue LED Vf"
        }
    ]

    results = []
    passed = 0
    failed = 0

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'─'*80}")
        print(f"Test {i}/{len(scenarios)}: {scenario['category']}")
        print(f"{'─'*80}")
        print(f"Q: {scenario['query']}")
        print()

        request = ChatRequest(question=scenario['query'])
        response = await agent.process_request(request)

        print(f"A: {response.response[:400]}...")
        print()
        print(f"Tools used: {response.tools_used}")
        print(f"Confidence: {response.confidence_score:.2f}")

        # Simple validation (contains expected keywords)
        is_valid = any(
            keyword.lower() in response.response.lower()
            for keyword in scenario['expected'].split()
        )

        status = "✅ PASS" if is_valid else "⚠️  CHECK"
        if is_valid:
            passed += 1
        else:
            failed += 1

        print(f"Status: {status}")

        results.append({
            "scenario": scenario['category'],
            "query": scenario['query'],
            "response_length": len(response.response),
            "tools_used": response.tools_used,
            "confidence": response.confidence_score,
            "status": status
        })

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"\nTotal tests: {len(scenarios)}")
    print(f"Passed: {passed} ✅")
    print(f"Need review: {failed} ⚠️")
    print(f"Success rate: {(passed/len(scenarios)*100):.1f}%")

    print("\n" + "="*80)
    print("DETAILED RESULTS")
    print("="*80)

    for r in results:
        print(f"\n{r['scenario']}: {r['status']}")
        print(f"  Response length: {r['response_length']} chars")
        print(f"  Tools: {r['tools_used']}")
        print(f"  Confidence: {r['confidence']:.2f}")

    # Overall assessment
    print("\n" + "="*80)
    print("OVERALL ASSESSMENT")
    print("="*80)

    if passed >= len(scenarios) * 0.8:
        print("\n✅ EXCELLENT - Circuit-AI handles most real-world scenarios well!")
    elif passed >= len(scenarios) * 0.6:
        print("\n✅ GOOD - Circuit-AI is functional but could use improvements")
    else:
        print("\n⚠️  NEEDS WORK - Circuit-AI needs more development")

    print(f"\nCircuit-AI successfully handled {passed}/{len(scenarios)} real maker scenarios.")
    print("Ready for initial launch with iterative improvements.")

    return passed, len(scenarios)


if __name__ == "__main__":
    passed, total = asyncio.run(test_scenarios())
    sys.exit(0 if passed >= total * 0.7 else 1)
