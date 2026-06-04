"""
Demo: Generative Build Capability

Demonstrates the complete pipeline:
Natural Language → Design → Physical Build

This script:
1. Sets up a demo inventory with some components
2. Shows natural language parsing
3. Generates designs with resource optimization
4. Demonstrates scrap component usage

Run with:
    python scripts/demo_generative_build.py

Author: Dum-E Intelligence System
Version: 1.0.0
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intelligence.intent_parser import IntentParser
from intelligence.resource_manager import ResourceManager, Component, ComponentCondition
from intelligence.design_generator import DesignGenerator

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def setup_demo_inventory(resource_mgr: ResourceManager):
    """Set up demo inventory with some components."""

    print("\n" + "=" * 70)
    print("SETTING UP DEMO INVENTORY")
    print("=" * 70)
    print()

    # Add some new components
    resource_mgr.add_component(Component(
        name="ESP32",
        component_type="microcontroller",
        quantity=2,
        condition=ComponentCondition.NEW,
        cost_usd=8.00,
        source="purchased"
    ))

    resource_mgr.add_component(Component(
        name="Arduino Nano",
        component_type="microcontroller",
        quantity=1,
        condition=ComponentCondition.NEW,
        cost_usd=5.00,
        source="purchased"
    ))

    # Add some scrap components (harvested from broken boards)
    resource_mgr.add_component(Component(
        name="DHT22",
        component_type="sensor",
        quantity=1,
        condition=ComponentCondition.SCRAP,
        source="scavenged",
        notes="Harvested from broken weather station"
    ))

    resource_mgr.add_component(Component(
        name="LED",
        component_type="led",
        quantity=5,
        condition=ComponentCondition.SCRAP,
        source="scavenged",
        notes="Harvested from old display board"
    ))

    resource_mgr.add_component(Component(
        name="resistor_330",
        component_type="resistor",
        quantity=10,
        condition=ComponentCondition.NEW,
        cost_usd=0.05,
        source="purchased"
    ))

    print(resource_mgr.generate_report())


def demo_build(request: str):
    """Demonstrate complete build from natural language request."""

    print("\n" + "=" * 70)
    print(f"DEMO BUILD REQUEST: \"{request}\"")
    print("=" * 70)
    print()

    # Initialize components
    parser = IntentParser()
    resource_mgr = ResourceManager(Path("/tmp/demo_inventory.json"))
    generator = DesignGenerator(Path("/tmp/demo_designs"))

    # Set up inventory if empty
    if not resource_mgr.inventory:
        setup_demo_inventory(resource_mgr)

    # Phase 1: Parse Intent
    print("[Phase 1/4] Parsing natural language request...")
    intent = parser.parse(request)

    print(f"  → Project type: {intent.project_type.value}")
    print(f"  → Features detected: {', '.join(intent.features)}")
    print(f"  → Required components: {', '.join(intent.required_components[:5])}...")
    print(f"  → Parsing confidence: {intent.confidence:.2f}")
    print()

    # Phase 2: Check Resources
    print("[Phase 2/4] Checking available resources...")
    availability = resource_mgr.check_availability(intent.required_components)

    print(f"  → Available: {len(availability['available'])}/{len(intent.required_components)}")

    if availability["missing"]:
        print(f"  ⚠ Missing: {', '.join(availability['missing'])}")

    if availability["substitutable"]:
        print("  ↔ Can substitute:")
        for orig, subs in availability["substitutable"].items():
            print(f"      {orig} → {subs[0]}")

    print(f"  → Build feasible: {'✓ Yes' if availability['feasible'] else '✗ No'}")
    print()

    if not availability["feasible"]:
        print("✗ Cannot proceed - missing required components")
        print()
        return

    # Phase 3: Generate Design
    print("[Phase 3/4] Generating design...")
    design = generator.generate_design(intent, resource_mgr)

    print(f"  ✓ Design generated successfully")
    print(f"  → Status: {design.status.value}")
    print(f"  → Components in BOM: {len(design.bill_of_materials)}")
    print(f"  → Wire connections: {len(design.wiring)}")
    print(f"  → Using scraps: {sum(1 for c in design.bill_of_materials if c['condition'] == 'scrap')}")
    print(f"  → Using new: {sum(1 for c in design.bill_of_materials if c['condition'] == 'new')}")
    print(f"  → Estimated build time: {design.estimated_build_time_min:.1f} minutes")

    if design.substitutions_made:
        print(f"  → Substitutions made: {len(design.substitutions_made)}")

    print()

    # Phase 4: Display Design
    print("[Phase 4/4] Design preview...")
    print()

    schematic = generator.generate_schematic_ascii(design)
    print(schematic)

    # Cost analysis
    total_cost = sum(c["cost_usd"] for c in design.bill_of_materials)
    scrap_savings = sum(
        3.0  # Estimated component value
        for c in design.bill_of_materials
        if c["condition"] == "scrap"
    )

    print()
    print("=" * 70)
    print("COST ANALYSIS")
    print("=" * 70)
    print(f"  Total cost (new components only): ${total_cost:.2f}")
    print(f"  Savings from scrap components: ${scrap_savings:.2f}")
    print(f"  Net cost: ${max(0, total_cost):.2f}")
    print("=" * 70)
    print()


def main():
    """Run demos for different project types."""

    print("\n" + "=" * 70)
    print("DUM-E GENERATIVE BUILD DEMONSTRATION")
    print("=" * 70)
    print()
    print("This demo shows Dum-E's ability to:")
    print("  ✓ Understand natural language build requests")
    print("  ✓ Generate complete designs from scratch")
    print("  ✓ Optimize for available resources")
    print("  ✓ Use scrap components to save cost")
    print("  ✓ Substitute components when needed")
    print()

    # Demo 1: WiFi Temperature Sensor
    demo_build("build me a WiFi temperature sensor")

    input("\nPress Enter to continue to next demo...\n")

    # Demo 2: LED Blinker
    demo_build("make an LED blinker")

    input("\nPress Enter to see scrap project suggestions...\n")

    # Show scrap suggestions
    print("\n" + "=" * 70)
    print("SCRAP PROJECT SUGGESTIONS")
    print("=" * 70)
    print()

    resource_mgr = ResourceManager(Path("/tmp/demo_inventory.json"))

    scrap_components = [
        comp.name for comp in resource_mgr.inventory.values()
        if comp.condition == ComponentCondition.SCRAP
    ]

    print(f"Available scrap components: {', '.join(scrap_components)}")
    print()

    suggestions = resource_mgr.suggest_design_from_scraps(scrap_components)

    if suggestions:
        print("Possible projects from scraps:")
        for i, proj in enumerate(suggestions, 1):
            print(f"\n  {i}. {proj['project']}")
            print(f"     Difficulty: {proj['difficulty']}")
            print(f"     Components: {', '.join(proj['components_used'])}")
    else:
        print("No project suggestions for current scrap components.")

    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print()
    print("To build a real project, run:")
    print('  python scripts/build_project.py "build me a WiFi temperature sensor"')
    print()


if __name__ == "__main__":
    main()
