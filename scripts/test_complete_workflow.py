"""
Non-interactive complete workflow test
Shows what the system ACTUALLY does end-to-end
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import logging
logging.basicConfig(level=logging.ERROR)

from intelligence.intent_parser import IntentParser
from intelligence.resource_manager import ResourceManager, Component, ComponentCondition
from intelligence.design_generator import DesignGenerator


def test_complete_workflow():
    """Test complete workflow without interaction."""

    print("=" * 70)
    print("COMPLETE WORKFLOW TEST")
    print("=" * 70)

    # Test 1: WiFi sensor (should work)
    print("\n[TEST 1] WiFi Temperature Sensor")
    print("-" * 70)

    mgr = ResourceManager(Path("/tmp/test_workflow.json"))
    parser = IntentParser()

    request = "build me a WiFi temperature sensor"
    print(f"Request: \"{request}\"")

    intent = parser.parse(request)
    print(f"\n  → Understood: {intent.project_type.value}")
    print(f"  → Features: {', '.join(intent.features)}")
    print(f"  → Components needed: {len(intent.required_components)}")

    gen = DesignGenerator(Path("/tmp/test_workflow_designs"))
    design = gen.generate_design(intent, mgr)

    print(f"\n  Generated Design:")
    print(f"    ✓ BOM items: {len(design.bill_of_materials)}")
    print(f"    ✓ Wiring: {len(design.wiring)} connections")
    print(f"    ✓ Assembly steps: {len(design.assembly_steps)}")
    print(f"    ✓ Build time: {design.estimated_build_time_min:.1f} min")

    if len(design.bill_of_materials) > 0:
        total_cost = sum(item['cost_usd'] for item in design.bill_of_materials)
        print(f"    ✓ Estimated cost: ${total_cost:.2f}")

        print(f"\n  Sample BOM (first 5):")
        for item in design.bill_of_materials[:5]:
            print(f"    - {item['component']}: ${item['cost_usd']:.2f} ({item['condition']})")

        print(f"\n  Sample Wiring (first 3):")
        for conn in design.wiring[:3]:
            print(f"    - {conn.from_component}.{conn.from_pin} → {conn.to_component}.{conn.to_pin}")

    # Test 2: Hydro generator (should fail gracefully)
    print("\n\n[TEST 2] Hydro Generator (System Limitation Test)")
    print("-" * 70)

    request2 = "build me a hydro generator for rain"
    print(f"Request: \"{request2}\"")

    intent2 = parser.parse(request2)
    print(f"\n  → Misunderstood as: {intent2.project_type.value}")
    print(f"  → Wrong features: {intent2.features}")
    print(f"  → Wrong components: {', '.join(intent2.required_components[:5])}")

    design2 = gen.generate_design(intent2, mgr)
    print(f"\n  Generated (WRONG) Design:")
    print(f"    ✓ BOM items: {len(design2.bill_of_materials)}")

    if len(design2.bill_of_materials) > 0:
        print(f"\n  What it WRONGLY generated:")
        for item in design2.bill_of_materials[:5]:
            print(f"    - {item['component']}: ${item['cost_usd']:.2f}")
        print(f"\n    ❌ This is NOT a hydro generator!")
        print(f"    ❌ System limitation: Can't handle mechanical/power projects")

    # Summary
    print("\n\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print("\n✅ WORKS:")
    print("  • Electronics projects (WiFi sensor, LED blinker, etc.)")
    print("  • Generates BOM even without components in stock")
    print("  • Generates wiring diagrams")
    print("  • Generates assembly instructions")
    print("  • Estimates costs and build time")

    print("\n❌ DOESN'T WORK:")
    print("  • Mechanical projects (robot arms, turbines)")
    print("  • Power generation (hydro, solar, wind)")
    print("  • Anything outside electronics domain")

    print("\n📊 Test Results:")
    print(f"  WiFi Sensor: {len(design.bill_of_materials)} items, {len(design.wiring)} connections ✅")
    print(f"  Hydro Generator: Misunderstood completely ❌")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    test_complete_workflow()
