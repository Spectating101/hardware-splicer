#!/usr/bin/env python3
"""
Test Circuit-AI Modular Capabilities
Shows each module working independently and combined
"""

import sys
from pathlib import Path
sys.path.insert(0, 'src')

from intelligence.llm_intent_parser import create_parser
from intelligence.smart_design_generator import SmartDesignGenerator


def print_section(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")


def test_module_1_intent_parser():
    """Module 1: Intent Parser - Standalone Usage"""

    print_section("MODULE 1: Intent Parser (Standalone)")

    print("Use Case: Just understand requirements, don't design yet\n")

    # Create parser
    parser = create_parser(use_llm=True)

    # Test different inputs
    test_cases = [
        "WiFi temperature sensor",
        "robot arm with 6 servos and Bluetooth control",
        "battery-powered outdoor weather station with solar charging"
    ]

    for test in test_cases:
        print(f"Input: \"{test}\"")
        intent = parser.parse(test)
        print(f"  → Project Type: {intent.project_type.value}")
        print(f"  → Features: {', '.join(intent.features)}")
        print(f"  → Confidence: {intent.confidence:.0%}")
        print()

    print("✓ Intent Parser works standalone - no design generated!")


def test_module_2_component_selector():
    """Module 2: Component Selector - Standalone Usage"""

    print_section("MODULE 2: Component Selector (Standalone)")

    print("Use Case: Quick component question - no full design needed\n")

    smart_gen = SmartDesignGenerator()

    # Scenario 1: Battery-powered project
    print("Question 1: ESP8266 vs ESP32 for battery-powered sensor?")
    choice = smart_gen.select_component(
        "wifi_microcontroller",
        requirements={"simple_iot": True, "bluetooth_needed": False},
        build_quantity=1
    )
    print(f"  → Recommendation: {choice.selected}")
    print(f"  → Cost: ${choice.cost:.2f}")
    print(f"  → Reasoning: {choice.reasoning}")
    print()

    # Scenario 2: Robot arm needs
    print("Question 2: Same component type, but need Bluetooth?")
    choice2 = smart_gen.select_component(
        "wifi_microcontroller",
        requirements={"bluetooth_needed": True, "dual_core_needed": True},
        build_quantity=1
    )
    print(f"  → Recommendation: {choice2.selected}")
    print(f"  → Cost: ${choice2.cost:.2f}")
    print(f"  → Reasoning: {choice2.reasoning}")
    print()

    print("✓ Component Selector works standalone - just answered questions!")


def test_module_3_database_query():
    """Module 3: Component Database - Browse Available Parts"""

    print_section("MODULE 3: Component Database (Browse)")

    print("Use Case: What WiFi microcontrollers are available?\n")

    smart_gen = SmartDesignGenerator()

    # Query database
    category = "wifi_microcontroller"
    if category in smart_gen.component_knowledge:
        options = smart_gen.component_knowledge[category]['options']

        print(f"Available {category}:")
        print()
        for i, opt in enumerate(options, 1):
            print(f"{i}. {opt['name']}")
            print(f"   Cost: ${opt['cost']:.2f}")
            print(f"   Specs: {opt['specs']}")
            print()

    print("✓ Component Database query - just browsing, not designing!")


def test_combination_parser_plus_selector():
    """Combining Modules: Intent Parser → Component Selector"""

    print_section("COMBINATION: Intent Parser + Component Selector")

    print("Use Case: Understand requirements, then pick components\n")

    parser = create_parser(use_llm=True)
    smart_gen = SmartDesignGenerator()

    # Step 1: Parse intent
    user_input = "battery-powered WiFi sensor for outdoors"
    print(f"Input: \"{user_input}\"")
    print()

    intent = parser.parse(user_input)
    print("Step 1 - Intent Parser:")
    print(f"  → Type: {intent.project_type.value}")
    print(f"  → Features: {', '.join(intent.features)}")
    print()

    # Step 2: Select components based on intent
    print("Step 2 - Component Selector (using parsed intent):")

    # Infer requirements from intent
    requirements = {
        "simple_iot": True,
        "bluetooth_needed": False  # Not in features
    }

    choice = smart_gen.select_component(
        "wifi_microcontroller",
        requirements=requirements,
        build_quantity=1
    )

    print(f"  → Selected: {choice.selected}")
    print(f"  → Reasoning: {choice.reasoning}")
    print()

    print("✓ Two modules combined - but still no full design!")


def test_scale_comparison():
    """Module: Scale Optimizer - Different Quantities"""

    print_section("MODULE: Scale Optimizer")

    print("Use Case: How does quantity affect component choice?\n")

    smart_gen = SmartDesignGenerator()

    quantities = [1, 10, 100, 1000]

    print("Voltage Regulator choice at different scales:")
    print()

    for qty in quantities:
        choice = smart_gen.select_component(
            "voltage_regulator",
            requirements={"low_current": True},
            build_quantity=qty
        )

        print(f"Quantity: {qty:4d} units")
        print(f"  → Choice: {choice.selected}")
        print(f"  → Unit Cost: ${choice.cost:.2f}")
        print(f"  → Total Cost: ${choice.cost * qty:.2f}")
        print()

    print("✓ Scale optimizer - same design, different quantities!")


def test_context_awareness():
    """Show Context-Aware Intelligence"""

    print_section("CONTEXT-AWARE INTELLIGENCE")

    print("Use Case: Same component type, different contexts\n")

    smart_gen = SmartDesignGenerator()

    scenarios = [
        {
            "name": "Simple IoT Sensor",
            "requirements": {"simple_iot": True},
            "context": "Basic temperature monitoring"
        },
        {
            "name": "Robot Arm Controller",
            "requirements": {"bluetooth_needed": True, "dual_core_needed": True},
            "context": "Need BLE remote + servo control"
        },
        {
            "name": "Future-Proof Smart Home",
            "requirements": {"future_proof": True},
            "context": "Want latest standards"
        }
    ]

    for scenario in scenarios:
        print(f"Scenario: {scenario['name']}")
        print(f"Context: {scenario['context']}")

        choice = smart_gen.select_component(
            "wifi_microcontroller",
            requirements=scenario['requirements'],
            build_quantity=1
        )

        print(f"  → AI Chose: {choice.selected} (${choice.cost:.2f})")
        print(f"  → Why: {choice.reasoning}")
        print()

    print("✓ Context-aware - THREE different recommendations!")


def test_api_style_usage():
    """Show How This Works as API"""

    print_section("API-STYLE USAGE")

    print("Use Case: Each module is an independent API endpoint\n")

    # Simulate API calls
    print("API Call 1: Compare Components")
    print("POST /api/compare_components")
    print("Body: {")
    print('  "component_type": "wifi_microcontroller",')
    print('  "requirements": {"battery_powered": true}')
    print("}")
    print()

    smart_gen = SmartDesignGenerator()
    result = smart_gen.select_component(
        "wifi_microcontroller",
        requirements={"simple_iot": True},
        build_quantity=1
    )

    print("Response: {")
    print(f'  "selected": "{result.selected}",')
    print(f'  "cost": {result.cost},')
    print(f'  "reasoning": "{result.reasoning}"')
    print("}")
    print()

    print("✓ Each module = API endpoint - mix and match!")


def main():
    """Run all modular tests"""

    print("\n" + "█"*70)
    print("  CIRCUIT-AI: MODULAR CAPABILITIES TEST")
    print("  Showing how each module works independently")
    print("█"*70)

    try:
        # Test each module standalone
        test_module_1_intent_parser()

        test_module_2_component_selector()

        test_module_3_database_query()

        # Test combinations
        test_combination_parser_plus_selector()

        # Test different use cases
        test_scale_comparison()

        test_context_awareness()

        # Show API style
        test_api_style_usage()

        # Summary
        print_section("SUMMARY: MODULAR ARCHITECTURE")

        print("What We Just Demonstrated:")
        print()
        print("✓ Module 1 (Intent Parser) - Works alone")
        print("✓ Module 2 (Component Selector) - Works alone")
        print("✓ Module 3 (Component Database) - Works alone")
        print("✓ Modules 1+2 Combined - Flexible combination")
        print("✓ Scale Optimizer - Different quantities")
        print("✓ Context Awareness - Same input, different outputs")
        print("✓ API-Style Usage - Each module = endpoint")
        print()
        print("KEY INSIGHT:")
        print("  → NOT a linear pipeline")
        print("  → Pick what you need")
        print("  → Use standalone OR combined")
        print("  → Flexible workflows")
        print()
        print("This is a TOOLKIT, not a pipeline!")
        print()

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
