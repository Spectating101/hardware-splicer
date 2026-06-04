"""
Demo: LLM vs Keywords - Side by Side Comparison

Shows what WOULD happen with LLM vs what ACTUALLY happens with keywords.

Since API keys are expired, this simulates LLM responses based on
what a smart LLM (like Llama 3.3 70B or Copilot) would understand.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intelligence.intent_parser import IntentParser
from intelligence.design_generator import DesignGenerator
from intelligence.resource_manager import ResourceManager


# Simulated LLM responses (what Copilot/Llama would understand)
SIMULATED_LLM_RESULTS = {
    "make a water-powered electricity maker": {
        "project_type": "power_generation",
        "features": ["hydro"],
        "reasoning": "Water-powered electricity = hydro generator"
    },
    "I need a manipulator for PCB assembly": {
        "project_type": "mechanical",
        "features": ["pick_and_place", "gripper"],
        "reasoning": "Manipulator = robot arm, PCB assembly = pick-and-place"
    },
    "build something that harvests energy from rain": {
        "project_type": "power_generation",
        "features": ["hydro"],
        "reasoning": "Energy from rain = hydro power generation"
    },
    "create a gripper system with servo actuation": {
        "project_type": "mechanical",
        "features": ["gripper", "servo"],
        "reasoning": "Gripper with servos = mechanical actuator system"
    },
    "6-DOF articulated mechanism for assembly": {
        "project_type": "mechanical",
        "features": ["degrees_of_freedom", "pick_and_place"],
        "reasoning": "6-DOF articulated = robot arm"
    },
}


def test_comparison():
    """Compare keyword matching vs LLM understanding."""

    print("=" * 70)
    print("KEYWORD MATCHING vs LLM UNDERSTANDING")
    print("=" * 70)
    print()
    print("Testing edge cases where keywords FAIL but LLM succeeds")
    print()

    keyword_parser = IntentParser()

    for request, llm_expected in SIMULATED_LLM_RESULTS.items():
        print(f"{'=' * 70}")
        print(f"Request: \"{request}\"")
        print(f"{'=' * 70}")

        # Keyword approach (ACTUAL)
        keyword_result = keyword_parser.parse(request)

        print(f"\n❌ KEYWORD MATCHING (current):")
        print(f"   Project Type: {keyword_result.project_type.value}")
        print(f"   Features: {keyword_result.features}")

        if keyword_result.project_type.value != llm_expected["project_type"]:
            print(f"   ❌ WRONG! Doesn't understand the request")
        else:
            print(f"   ✅ Correct (got lucky with keywords)")

        # LLM approach (SIMULATED - what it WOULD do)
        print(f"\n✅ LLM UNDERSTANDING (would do with API):")
        print(f"   Project Type: {llm_expected['project_type']}")
        print(f"   Features: {llm_expected['features']}")
        print(f"   Reasoning: {llm_expected['reasoning']}")
        print(f"   ✅ CORRECT! Understands natural language")
        print()


def test_full_pipeline_comparison():
    """Show complete design generation with both approaches."""

    print("\n" + "=" * 70)
    print("FULL PIPELINE COMPARISON")
    print("=" * 70)

    request = "make a water-powered electricity maker"
    print(f"\nRequest: \"{request}\"")
    print(f"\nUser wants a HYDRO GENERATOR")
    print()

    keyword_parser = IntentParser()
    mgr = ResourceManager(Path('/tmp/demo_test.json'))
    gen = DesignGenerator(Path('/tmp/demo_designs'))

    # Test with keywords
    print(f"{'─' * 70}")
    print("WITH KEYWORDS (current):")
    print(f"{'─' * 70}")

    keyword_intent = keyword_parser.parse(request)
    keyword_design = gen.generate_design(keyword_intent, mgr)

    print(f"\nParsed as: {keyword_intent.project_type.value}")
    print(f"BOM items: {len(keyword_design.bill_of_materials)}")
    print(f"Wiring: {len(keyword_design.wiring)} connections")

    if len(keyword_design.bill_of_materials) > 0:
        print(f"\nGenerated components:")
        for item in keyword_design.bill_of_materials[:5]:
            print(f"  - {item['component']}")

        has_turbine = any('turbine' in item['component'].lower() for item in keyword_design.bill_of_materials)
        if has_turbine:
            print(f"\n✅ Correct! Generated hydro generator")
        else:
            print(f"\n❌ WRONG! This is NOT a hydro generator!")
            print(f"   System didn't understand \"water-powered electricity maker\"")

    # Simulate with LLM
    print(f"\n{'─' * 70}")
    print("WITH LLM (would happen with API key):")
    print(f"{'─' * 70}")

    # Manually set what LLM would understand
    print(f"\nLLM would parse as: power_generation")
    print(f"LLM reasoning: 'water-powered electricity maker' = hydro generator")
    print(f"\nThen generates:")
    print(f"  - turbine")
    print(f"  - dc_motor_as_generator")
    print(f"  - rectifier")
    print(f"  - voltage_regulator")
    print(f"  - battery")
    print(f"\n✅ CORRECT! Full hydro generator design")


def show_scalability():
    """Show why LLM scales better."""

    print("\n\n" + "=" * 70)
    print("SCALABILITY: Keywords vs LLM")
    print("=" * 70)

    print("""
To handle these 10 variations of "robot arm":

1. "robot arm"
2. "manipulator"
3. "articulated mechanism"
4. "gripper system"
5. "pick and place system"
6. "6-DOF actuator"
7. "mechanical arm"
8. "servo-driven gripper"
9. "automated assembly arm"
10. "robotic manipulator"

KEYWORD APPROACH:
  - Need to hardcode ALL variations: ["robot", "arm", "manipulator",
    "articulated", "mechanism", "gripper", "pick and place", "6-dof",
    "actuator", "servo-driven", "assembly", "robotic", ...]
  - That's 20+ keywords just for ONE project type!
  - For 100 project types = 2,000+ hardcoded keywords
  - Still breaks on: "I need something to grab circuit boards"

LLM APPROACH:
  - Describe once: "mechanical: Robot arms, grippers, pick-and-place"
  - LLM understands ALL variations naturally
  - Works on creative phrasings automatically
  - Understands: "something to grab circuit boards" = robot arm
  - 100 project types = 100 descriptions (not 2,000 keywords!)
""")


def main():
    """Run demonstration."""

    print("\n")
    print("█" * 70)
    print("DEMONSTRATION: Why LLM Beats Keyword Matching")
    print("█" * 70)
    print()
    print("Note: API keys expired, so showing SIMULATED LLM results")
    print("(This is what Copilot/Llama would understand)")
    print()

    test_comparison()
    test_full_pipeline_comparison()
    show_scalability()

    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print("""
KEYWORD MATCHING:
  ❌ Fails on synonyms ("manipulator", "water-powered")
  ❌ Requires hardcoding thousands of keywords
  ❌ Breaks on creative phrasing
  ❌ Not maintainable at scale

LLM UNDERSTANDING:
  ✅ Understands synonyms naturally
  ✅ Works on any phrasing
  ✅ Handles complex requests
  ✅ Scales to 100+ project types easily

TO ENABLE LLM:
  1. Get API key: https://console.groq.com (free!)
  2. export GROQ_API_KEY=your_key_here
  3. System automatically uses LLM instead of keywords
""")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
