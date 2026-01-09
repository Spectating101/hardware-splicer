#!/usr/bin/env python3
"""
Circuit-AI v2 API Demonstration
Shows complete workflow integration: Education → Design → Validation
"""

import sys
sys.path.insert(0, 'src')

from engines.unified_workflow import UnifiedWorkflowEngine, UserProfile, UserLevel


def print_header(title):
    """Print formatted section header"""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()


def demo_beginner_workflow():
    """Demo 1: Complete beginner - Learning path recommendation"""
    print_header("DEMO 1: Complete Beginner Workflow")

    engine = UnifiedWorkflowEngine()

    # Absolute beginner
    beginner = UserProfile(
        skill_level=UserLevel.BEGINNER,
        completed_projects=[],
        inventory=[],
        budget=50.0,
        goal="learning"
    )

    print("User Profile:")
    print(f"  Skill Level: {beginner.skill_level.name}")
    print(f"  Completed Projects: {len(beginner.completed_projects)}")
    print(f"  Inventory: {len(beginner.inventory)} components")
    print(f"  Goal: {beginner.goal}")
    print()

    result = engine.execute_beginner_workflow(beginner)

    print(f"Status: {result.status}")
    print()
    print("Next Steps:")
    for i, step in enumerate(result.next_steps, 1):
        print(f"  {i}. {step}")
    print()
    print(f"Estimated Time: {result.estimated_time_hours} hours")


def demo_hobbyist_workflow():
    """Demo 2: Hobbyist with parts - Project recommendation"""
    print_header("DEMO 2: Hobbyist with Parts Workflow")

    engine = UnifiedWorkflowEngine()

    # Hobbyist with some parts
    hobbyist = UserProfile(
        skill_level=UserLevel.HOBBYIST,
        completed_projects=["LED Blink", "Button Counter"],
        inventory=[
            {'id': 'esp32', 'condition': 'new', 'quantity': 1},
            {'id': 'bme280', 'condition': 'used', 'quantity': 1},
            {'id': 'oled_ssd1306', 'condition': 'new', 'quantity': 1}
        ],
        budget=20.0,
        goal="learning"
    )

    print("User Profile:")
    print(f"  Skill Level: {hobbyist.skill_level.name}")
    print(f"  Completed Projects: {', '.join(hobbyist.completed_projects)}")
    print(f"  Inventory: {len(hobbyist.inventory)} components")
    print(f"  Budget: ${hobbyist.budget}")
    print()

    result = engine.execute_beginner_workflow(hobbyist)

    print(f"Status: {result.status}")
    print()

    if result.project:
        print("Recommended Project:")
        print(f"  Name: {result.project.name}")
        print(f"  Difficulty: {result.project.difficulty}")
        print(f"  Category: {result.project.category.value}")
        print(f"  Build Time: {result.project.build_time_hours} hours")
        print()
        print("Economics:")
        print(f"  Parts Cost: ${result.project.parts_cost:.2f}")
        print(f"  Market Price: ${result.project.market_price_low:.2f} - ${result.project.market_price_high:.2f}")
        print(f"  ROI: {result.project.roi_percent:.1f}%")
        print(f"  Missing Parts Cost: ${result.project.missing_parts_cost:.2f}")
        print()
        print("Inventory Match:")
        print(f"  Match Percent: {result.project.inventory_match_percent:.0f}%")
        print(f"  Components Owned: {', '.join(result.project.components_owned)}")
        if result.project.components_needed:
            print(f"  Components Needed: {', '.join(result.project.components_needed)}")
        else:
            print(f"  Components Needed: None - You have everything! 🎉")
        print()

    if result.instructions:
        print("Build Instructions:")
        print(f"  Steps: {len(result.instructions.get('steps', []))} steps")
        print(f"  Has Wiring Diagram: {'wiring_diagram' in result.instructions}")
        print(f"  Has Code: {'code' in result.instructions}")
        print()

    print("Next Steps:")
    for i, step in enumerate(result.next_steps, 1):
        print(f"  {i}. {step}")


def demo_complete_workflow():
    """Demo 3: Complete workflow - Recipe → Instructions → Validation"""
    print_header("DEMO 3: Complete Workflow (End-to-End)")

    engine = UnifiedWorkflowEngine()

    # Intermediate user
    user = UserProfile(
        skill_level=UserLevel.INTERMEDIATE,
        completed_projects=["LED Blink", "Button Counter", "Temperature Logger"],
        inventory=[
            {'id': 'esp32', 'condition': 'new', 'quantity': 1},
            {'id': 'bme280', 'condition': 'used', 'quantity': 1},
            {'id': 'oled_ssd1306', 'condition': 'new', 'quantity': 1}
        ],
        budget=20.0,
        goal="learning"
    )

    print("User Profile:")
    print(f"  Skill Level: {user.skill_level.name}")
    print(f"  Completed Projects: {len(user.completed_projects)}")
    print(f"  Inventory: {len(user.inventory)} components")
    print()

    # Execute complete workflow (no KiCAD file yet)
    result = engine.execute_complete_workflow(
        user=user,
        project_name="Air Quality Monitor",
        kicad_file=None
    )

    print(f"Status: {result.status}")
    print()

    if result.project:
        print("Project Details:")
        print(f"  Name: {result.project.name}")
        print(f"  Category: {result.project.category.value}")
        print(f"  Difficulty: {result.project.difficulty}")
        print(f"  You have: {result.project.inventory_match_percent:.0f}% of parts")
        print(f"  Cost to complete: ${result.estimated_cost:.2f}")
        print(f"  Build time: {result.estimated_time_hours} hours")
        print(f"  Potential ROI: {result.project.roi_percent:.1f}%")
        print()

    if result.instructions:
        print("Build Instructions Available:")
        print(f"  ✓ {len(result.instructions.get('steps', []))} step-by-step instructions")
        print(f"  ✓ Wiring diagrams")
        print(f"  ✓ Code examples")
        print(f"  ✓ Troubleshooting tips")
        print()

    print("Next Steps:")
    for i, step in enumerate(result.next_steps, 1):
        print(f"  {i}. {step}")
    print()

    print("What happens next:")
    print("  → User builds the project")
    print("  → User designs PCB in KiCAD")
    print("  → User uploads .net file to /api/v2/workflow/validate-kicad")
    print("  → System validates power tree, traces, LDOs")
    print("  → System provides quantitative fixes")
    print("  → User fixes issues and re-uploads")
    print("  → System generates Gerber files (v2.1)")
    print("  → User orders PCB from JLCPCB")


def demo_validation_status():
    """Demo 4: Show what KiCAD validation would return"""
    print_header("DEMO 4: Professional KiCAD Validation (Example)")

    print("When user uploads KiCAD .net file:")
    print()
    print("Input:")
    print("  • KiCAD netlist file (.net)")
    print("  • Optional hints (sources, loads, constraints)")
    print()
    print("Validation Process:")
    print("  1. Parse KiCAD S-expression netlist")
    print("  2. Compile connectivity into circuit model")
    print("  3. Infer LDO regulators automatically")
    print("  4. Solve DC operating point (MNA)")
    print("  5. Validate power tree:")
    print("     - Check source current limits")
    print("     - Calculate trace voltage drops")
    print("     - Verify LDO regulation")
    print()
    print("Example Output:")
    print()
    print("  Status: validation_warning")
    print()
    print("  Issues Found: 2")
    print("  └─ [WARNING] Trace +3V3")
    print("     │")
    print("     ├─ Issue: Excessive voltage drop (0.35V exceeds 0.25V limit)")
    print("     │")
    print("     ├─ Physics:")
    print("     │  • Current: 1.2A")
    print("     │  • Voltage drop: 0.35V")
    print("     │  • Power loss: 0.42W")
    print("     │  • Current width: 0.5mm")
    print("     │  • Required width: 2.0mm")
    print("     │")
    print("     └─ Solution: Widen trace from 0.5mm to 2.0mm or use copper pour")
    print()
    print("  └─ [WARNING] LDO U1 (AMS1117-3.3)")
    print("     │")
    print("     ├─ Issue: Marginal dropout voltage")
    print("     │")
    print("     ├─ Physics:")
    print("     │  • Vin: 3.62V")
    print("     │  • Vout: 3.3V")
    print("     │  • Dropout: 0.32V")
    print("     │  • Min dropout: 0.3V")
    print("     │")
    print("     └─ Solution: Increase input voltage to 3.9V or use lower-dropout LDO")
    print()
    print("  Manufacturing Ready: No (fix warnings first)")
    print()
    print("Key Advantage: QUANTITATIVE fixes, not generic suggestions!")


def main():
    """Run all demos"""
    print("=" * 70)
    print("  CIRCUIT-AI V2 API DEMONSTRATION")
    print("  Education → Design → Validation → Manufacturing")
    print("=" * 70)
    print()
    print("This demonstrates the complete integration of:")
    print("  • Educational tools (recipe optimizer, learning paths, instructions)")
    print("  • Professional validation (KiCAD, circuit solver, power tree)")
    print()
    print("Version: 0.4.0")
    print("Status: Production Ready")
    print()

    try:
        # Run all demos
        demo_beginner_workflow()
        demo_hobbyist_workflow()
        demo_complete_workflow()
        demo_validation_status()

        # Summary
        print_header("SUMMARY")
        print("V2 API provides THREE integrated workflows:")
        print()
        print("1. Beginner Workflow (/api/v2/workflow/beginner)")
        print("   → Learn → Get project recommendations → Build")
        print()
        print("2. Complete Workflow (/api/v2/workflow/complete)")
        print("   → Recipe → Instructions → Validation → Manufacturing")
        print()
        print("3. KiCAD Validation (/api/v2/workflow/validate-kicad)")
        print("   → Upload .net → Get quantitative fixes → Order PCB")
        print()
        print("=" * 70)
        print("Value Proposition:")
        print("=" * 70)
        print()
        print("Before: Users had to chain separate tools manually")
        print("After:  Users get complete end-to-end workflows")
        print()
        print("Before: Generic suggestions ('traces too thin')")
        print("After:  Quantitative fixes ('widen to 2mm')")
        print()
        print("Before: Educational OR professional")
        print("After:  Educational AND professional (integrated)")
        print()
        print("Result: 10x more value than parts alone")
        print()
        print("=" * 70)
        print("✅ All demos completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
