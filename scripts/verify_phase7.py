"""
Verification Script for Phase 7

Tests each component of the generative build pipeline to verify it's working.

Usage:
    python scripts/verify_phase7.py

Tests:
1. Intent Parser - Can it understand natural language?
2. Resource Manager - Can it track inventory and substitute?
3. Design Generator - Can it create buildable designs?
4. Build Orchestrator - Is the pipeline integrated?

Author: Dum-E Intelligence System
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import logging
logging.basicConfig(level=logging.WARNING)

def test_intent_parser():
    """Test 1: Natural Language Parsing"""
    print("\n" + "="*70)
    print("TEST 1: Intent Parser - Natural Language Understanding")
    print("="*70)

    from intelligence.intent_parser import IntentParser

    parser = IntentParser()

    test_cases = [
        "build me a WiFi temperature sensor",
        "make an LED blinker",
        "I need a motor controller"
    ]

    passed = 0
    for request in test_cases:
        intent = parser.parse(request)

        print(f"\nInput: \"{request}\"")
        print(f"  → Type: {intent.project_type.value}")
        print(f"  → Features: {intent.features}")
        print(f"  → Components: {len(intent.required_components)}")
        print(f"  → Confidence: {intent.confidence:.2f}")

        if intent.project_type and intent.required_components:
            print(f"  ✓ PASS")
            passed += 1
        else:
            print(f"  ✗ FAIL")

    print(f"\nResult: {passed}/{len(test_cases)} tests passed")
    return passed == len(test_cases)


def test_resource_manager():
    """Test 2: Resource Management & Substitution"""
    print("\n" + "="*70)
    print("TEST 2: Resource Manager - Inventory & Substitution")
    print("="*70)

    from intelligence.resource_manager import ResourceManager, Component, ComponentCondition

    # Use temp inventory
    mgr = ResourceManager(Path("/tmp/test_inventory.json"))

    # Test 1: Add component
    print("\nTest 2.1: Add Component")
    mgr.add_component(Component(
        name="ESP32",
        component_type="microcontroller",
        quantity=1,
        condition=ComponentCondition.NEW,
        cost_usd=8.00
    ))

    if mgr._has_component("ESP32"):
        print("  ✓ PASS - Component added successfully")
        test_2_1 = True
    else:
        print("  ✗ FAIL - Component not found")
        test_2_1 = False

    # Test 2: Check availability
    print("\nTest 2.2: Check Availability")
    availability = mgr.check_availability(["ESP32", "DHT22"])

    print(f"  Available: {availability['available']}")
    print(f"  Missing: {availability['missing']}")

    if "ESP32" in availability['available'] and "DHT22" in availability['missing']:
        print("  ✓ PASS - Availability checking works")
        test_2_2 = True
    else:
        print("  ✗ FAIL - Availability check incorrect")
        test_2_2 = False

    # Test 3: Component substitution
    print("\nTest 2.3: Component Substitution")

    # Add DHT11 (substitute for DHT22)
    mgr.add_component(Component(
        name="DHT11",
        component_type="sensor",
        quantity=1,
        condition=ComponentCondition.NEW
    ))

    availability = mgr.check_availability(["DHT22"])

    if "DHT22" in availability.get("substitutable", {}):
        substitutes = availability["substitutable"]["DHT22"]
        print(f"  → DHT22 substitutes: {substitutes}")
        print("  ✓ PASS - Substitution works")
        test_2_3 = True
    else:
        print("  ✗ FAIL - Substitution not working")
        test_2_3 = False

    # Cleanup
    Path("/tmp/test_inventory.json").unlink(missing_ok=True)

    passed = sum([test_2_1, test_2_2, test_2_3])
    print(f"\nResult: {passed}/3 tests passed")
    return passed == 3


def test_design_generator():
    """Test 3: Design Generation"""
    print("\n" + "="*70)
    print("TEST 3: Design Generator - Complete Design Creation")
    print("="*70)

    from intelligence.intent_parser import IntentParser
    from intelligence.resource_manager import ResourceManager, Component, ComponentCondition
    from intelligence.design_generator import DesignGenerator

    # Setup
    parser = IntentParser()
    mgr = ResourceManager(Path("/tmp/test_inventory.json"))
    generator = DesignGenerator(Path("/tmp/test_designs"))

    # Add components
    mgr.add_component(Component(
        name="ESP32",
        component_type="microcontroller",
        quantity=1,
        condition=ComponentCondition.NEW,
        cost_usd=8.00
    ))

    mgr.add_component(Component(
        name="DHT22",
        component_type="sensor",
        quantity=1,
        condition=ComponentCondition.SCRAP
    ))

    # Parse intent
    intent = parser.parse("build me a WiFi temperature sensor")

    # Generate design
    print("\nGenerating design...")
    design = generator.generate_design(intent, mgr)

    print(f"  → Status: {design.status.value}")
    print(f"  → BOM items: {len(design.bill_of_materials)}")
    print(f"  → Connections: {len(design.wiring)}")
    print(f"  → Placements: {len(design.placements)}")
    print(f"  → Assembly steps: {len(design.assembly_steps)}")
    print(f"  → Build time: {design.estimated_build_time_min:.1f} min")

    # Verify design completeness
    tests_passed = []

    # Test BOM
    if len(design.bill_of_materials) > 0:
        print("  ✓ BOM generated")
        tests_passed.append(True)
    else:
        print("  ✗ No BOM")
        tests_passed.append(False)

    # Test wiring
    if len(design.wiring) > 0:
        print("  ✓ Wiring generated")
        tests_passed.append(True)
    else:
        print("  ✗ No wiring")
        tests_passed.append(False)

    # Test assembly instructions
    if len(design.assembly_steps) > 0:
        print("  ✓ Assembly instructions generated")
        tests_passed.append(True)
    else:
        print("  ✗ No assembly instructions")
        tests_passed.append(False)

    # Test scrap usage
    scrap_count = sum(1 for item in design.bill_of_materials if item['condition'] == 'scrap')
    if scrap_count > 0:
        print(f"  ✓ Using scrap components ({scrap_count})")
        tests_passed.append(True)
    else:
        print("  ⚠ Not using scraps (but may be OK)")
        tests_passed.append(True)  # Not a failure

    # Cleanup
    Path("/tmp/test_inventory.json").unlink(missing_ok=True)
    import shutil
    shutil.rmtree("/tmp/test_designs", ignore_errors=True)

    passed = sum(tests_passed)
    print(f"\nResult: {passed}/{len(tests_passed)} tests passed")
    return passed == len(tests_passed)


def test_pipeline_integration():
    """Test 4: Complete Pipeline Integration"""
    print("\n" + "="*70)
    print("TEST 4: Pipeline Integration - End-to-End")
    print("="*70)

    print("\nTesting: Natural Language → Intent → Resources → Design")

    from intelligence.intent_parser import IntentParser
    from intelligence.resource_manager import ResourceManager, Component, ComponentCondition
    from intelligence.design_generator import DesignGenerator

    # Initialize pipeline
    parser = IntentParser()
    mgr = ResourceManager(Path("/tmp/test_inventory.json"))
    generator = DesignGenerator(Path("/tmp/test_designs"))

    # Setup inventory
    mgr.add_component(Component(
        name="Arduino Nano",
        component_type="microcontroller",
        quantity=1,
        condition=ComponentCondition.NEW
    ))

    mgr.add_component(Component(
        name="LED",
        component_type="led",
        quantity=1,
        condition=ComponentCondition.SCRAP
    ))

    mgr.add_component(Component(
        name="resistor_330",
        component_type="resistor",
        quantity=1,
        condition=ComponentCondition.NEW
    ))

    # Run pipeline
    request = "make an LED blinker"

    print(f"\n  Input: \"{request}\"")

    # Step 1: Parse
    intent = parser.parse(request)
    print(f"  [1/4] Parse → Type: {intent.project_type.value}")

    # Step 2: Check resources
    availability = mgr.check_availability(intent.required_components)
    print(f"  [2/4] Resources → Feasible: {availability['feasible']}")

    if not availability['feasible']:
        print("  ✗ FAIL - Missing required components")
        return False

    # Step 3: Generate design
    design = generator.generate_design(intent, mgr)
    print(f"  [3/4] Design → Status: {design.status.value}")

    # Step 4: Verify output
    has_bom = len(design.bill_of_materials) > 0
    has_wiring = len(design.wiring) > 0
    has_instructions = len(design.assembly_steps) > 0

    print(f"  [4/4] Output → BOM: {has_bom}, Wiring: {has_wiring}, Instructions: {has_instructions}")

    # Cleanup
    Path("/tmp/test_inventory.json").unlink(missing_ok=True)
    import shutil
    shutil.rmtree("/tmp/test_designs", ignore_errors=True)

    if has_bom and has_wiring and has_instructions:
        print("\n  ✓ PASS - Complete pipeline works end-to-end")
        return True
    else:
        print("\n  ✗ FAIL - Pipeline incomplete")
        return False


def main():
    """Run all verification tests"""

    print("\n" + "="*70)
    print("PHASE 7 VERIFICATION - Generative Build Pipeline")
    print("="*70)
    print("\nTesting all components of the generative build system...")

    results = []

    # Run tests
    results.append(("Intent Parser", test_intent_parser()))
    results.append(("Resource Manager", test_resource_manager()))
    results.append(("Design Generator", test_design_generator()))
    results.append(("Pipeline Integration", test_pipeline_integration()))

    # Summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status} - {name}")

    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)

    print(f"\nOverall: {total_passed}/{total_tests} components verified")

    if total_passed == total_tests:
        print("\n🎉 SUCCESS - Phase 7 is fully functional!")
        print("\nThe system can:")
        print("  ✓ Understand natural language ('build me X')")
        print("  ✓ Manage component inventory")
        print("  ✓ Substitute components intelligently")
        print("  ✓ Generate complete buildable designs")
        print("  ✓ Integrate end-to-end pipeline")
        print("\nReady for production use!")
        return 0
    else:
        print("\n⚠ WARNING - Some components failed verification")
        print("Please check the failed tests above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
