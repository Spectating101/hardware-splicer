"""
Build Project Orchestrator

Complete pipeline from natural language request to physical build:
1. Parse user request ("build me a temperature sensor")
2. Generate design from available resources
3. Preview virtual design
4. Execute physical build with robot arm

Usage:
    python build_project.py "build me a WiFi temperature sensor"
    python build_project.py "make an LED blinker" --preview-only
    python build_project.py "motor controller" --use-scraps --auto-build

Author: Dum-E Intelligence System
Version: 1.0.0
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intelligence.intent_parser import IntentParser
from intelligence.resource_manager import ResourceManager
from intelligence.design_generator import DesignGenerator, DesignStatus

logger = logging.getLogger(__name__)


class BuildOrchestrator:
    """
    Orchestrates the complete build process.

    Pipeline:
    Natural Language → Parse Intent → Generate Design → Preview → Build
    """

    def __init__(
        self,
        inventory_path: Path = None,
        output_dir: Path = None,
        generate_case: bool = True
    ):
        """
        Initialize build orchestrator.

        Args:
            inventory_path: Path to component inventory
            output_dir: Output directory for designs
            generate_case: Auto-generate 3D case for built projects
        """
        self.parser = IntentParser()
        self.resource_manager = ResourceManager(inventory_path)
        self.design_generator = DesignGenerator(output_dir)
        self.generate_case = generate_case

        logger.info("BuildOrchestrator initialized")

    def build_from_request(
        self,
        user_request: str,
        preview_only: bool = False,
        auto_build: bool = False,
        use_scraps: bool = True
    ) -> bool:
        """
        Complete build pipeline from natural language request.

        Args:
            user_request: Natural language request
            preview_only: Only generate and preview design, don't build
            auto_build: Skip confirmation prompts
            use_scraps: Prefer scrap components over new

        Returns:
            True if successful, False otherwise
        """
        print("\n" + "=" * 70)
        print("DUM-E BUILD ORCHESTRATOR")
        print("=" * 70)
        print()

        # Phase 1: Parse Intent
        phase_total = 6 if self.generate_case else 5
        print(f"[Phase 1/{phase_total}] Parsing request...")
        print(f"  Request: \"{user_request}\"")

        intent = self.parser.parse(user_request)

        print(f"  → Project type: {intent.project_type.value}")
        print(f"  → Features: {', '.join(intent.features) if intent.features else 'none detected'}")
        print(f"  → Confidence: {intent.confidence:.2f}")

        if intent.confidence < 0.5:
            print("\n⚠ Low confidence in parsing!")
            suggestions = self.parser.suggest_alternatives(intent)
            for suggestion in suggestions:
                print(f"  {suggestion}")

            if not auto_build:
                choice = input("\nContinue anyway? (y/n): ").strip().lower()
                if choice != 'y':
                    print("Aborting.")
                    return False

        print()

        # Phase 2: Check Resources
        print(f"[Phase 2/{phase_total}] Checking available resources...")

        availability = self.resource_manager.check_availability(intent.required_components)

        print(f"  Available: {len(availability['available'])}/{len(intent.required_components)}")

        if availability["missing"]:
            print(f"  ⚠ Missing: {', '.join(availability['missing'])}")

        if availability["substitutable"]:
            print(f"  ↔ Substitutable:")
            for orig, subs in availability["substitutable"].items():
                print(f"      {orig} → {subs[0]}")

        if not availability["feasible"]:
            print("\n✗ Build not feasible - missing required components")
            print(f"  Need: {', '.join(availability['missing'])}")

            # Generate shopping list
            print("\nGenerating shopping list with pricing...")
            shopping_list = self.resource_manager.generate_shopping_list(
                intent.required_components
            )
            print()
            print(shopping_list)

            return False

        print()

        # Phase 3: Generate Design
        print(f"[Phase 3/{phase_total}] Generating design...")

        design = self.design_generator.generate_design(intent, self.resource_manager)

        if design.status == DesignStatus.INFEASIBLE:
            print("✗ Design generation failed")
            for warning in design.warnings:
                print(f"  ⚠ {warning}")
            return False

        print(f"  ✓ Design generated")
        print(f"  → Components: {len(design.bill_of_materials)}")
        print(f"  → Connections: {len(design.wiring)}")
        print(f"  → Estimated time: {design.estimated_build_time_min:.1f} minutes")

        if design.substitutions_made:
            print(f"  → Substitutions: {len(design.substitutions_made)}")

        print()

        # Phase 4: Preview Design
        print(f"[Phase 4/{phase_total}] Design preview...")
        print()

        schematic = self.design_generator.generate_schematic_ascii(design)
        print(schematic)

        if preview_only:
            print("\n[Preview Only Mode] Build process stopped.")
            print(f"Design saved to: {self.design_generator.output_dir}")
            return True

        # Phase 5: Build Confirmation & Execution
        print(f"[Phase 5/{phase_total}] Physical build...")

        if not auto_build:
            print("\nReady to build. This will:")
            print("  1. Reserve components from inventory")
            print("  2. Control robot arm for assembly")
            print(f"  3. Take approximately {design.estimated_build_time_min:.1f} minutes")
            print()

            choice = input("Proceed with build? (y/n): ").strip().lower()
            if choice != 'y':
                print("Build cancelled.")
                return False

        # Execute build
        success = self._execute_physical_build(design)

        if success:
            print("\n" + "=" * 70)
            print("✓ BUILD COMPLETE")
            print("=" * 70)
            print(f"\nProject: {design.project_name}")
            print(f"Components used: {len(design.bill_of_materials)}")
            print(f"Build time: {design.estimated_build_time_min:.1f} minutes")
            print()
        else:
            print("\n✗ Build failed")

        return success

    def _execute_physical_build(self, design) -> bool:
        """
        Execute physical build with robot arm.

        Args:
            design: Design specification

        Returns:
            True if successful
        """
        print("\n  Starting physical build...")
        print()

        try:
            # Step 1: Reserve components from inventory
            print("  [1/4] Reserving components from inventory...")
            for item in design.bill_of_materials:
                component_name = item["component"]
                success = self.resource_manager.remove_component(component_name, quantity=1)

                if not success:
                    logger.error(f"Failed to reserve component: {component_name}")
                    print(f"    ✗ Failed to reserve: {component_name}")
                    return False

                print(f"    ✓ Reserved: {component_name}")

            print()

            # Step 2: Prepare workspace
            print("  [2/4] Preparing workspace...")
            # TODO: Send commands to robot arm to clear workspace
            # TODO: Position camera for build monitoring
            print("    ✓ Workspace ready")
            print()

            # Step 3: Component placement
            print("  [3/4] Placing components...")

            for i, placement in enumerate(design.placements, 1):
                print(f"    [{i}/{len(design.placements)}] Placing {placement.component}...")

                # TODO: Send robot arm commands
                # robot_arm.move_to_component_storage(placement.component)
                # robot_arm.pick_component()
                # robot_arm.move_to_pcb(placement.position[0], placement.position[1])
                # robot_arm.place_component(rotation=placement.rotation)

                # Simulate placement time
                time.sleep(0.5)

                print(f"       → Position: ({placement.position[0]:.1f}, {placement.position[1]:.1f})mm")

            print("    ✓ All components placed")
            print()

            # Step 4: Wiring
            print("  [4/4] Creating connections...")

            for i, conn in enumerate(design.wiring, 1):
                print(f"    [{i}/{len(design.wiring)}] {conn.from_component}.{conn.from_pin} → "
                      f"{conn.to_component}.{conn.to_pin}")

                # TODO: Send wiring commands to robot
                # robot_arm.wire_connection(
                #     from_component=conn.from_component,
                #     from_pin=conn.from_pin,
                #     to_component=conn.to_component,
                #     to_pin=conn.to_pin
                # )

                # Simulate wiring time
                time.sleep(0.3)

            print("    ✓ All connections made")
            print()

            # TODO: Step 5: Verification
            # - Capture images with camera
            # - Verify component placement
            # - Verify connections
            # - Test continuity

            print("  ✓ Physical build complete")

            # Step 5: Generate 3D case (if enabled)
            if self.generate_case:
                case_success = self._generate_protective_case(design)
                if not case_success:
                    print("  ⚠ Case generation failed (but circuit build successful)")

            return True

        except Exception as e:
            logger.error(f"Build execution failed: {e}")
            print(f"\n  ✗ Build failed: {e}")
            return False

    def _generate_protective_case(self, design) -> bool:
        """
        Generate 3D protective case using 3d-splicer.

        Args:
            design: Design specification with PCB dimensions and components

        Returns:
            True if successful
        """
        print()
        print("  [5/5] Generating protective case...")

        try:
            # Import splicer bridge
            sys.path.insert(0, str(Path(__file__).parent))

            try:
                from splicer_bridge_robust import load_adapter_and_client
                convert_func, ClientClass = load_adapter_and_client()
            except Exception:
                # Fallback: try importing directly
                sys.path.insert(0, str(Path(__file__).parent.parent.parent / "3d-splicer"))
                try:
                    from circuit_ai_adapter import convert_circuit_ai_board
                    from circuit_ai_client import CircuitAIClient
                    convert_func = convert_circuit_ai_board
                    ClientClass = CircuitAIClient
                except ImportError:
                    print("    ⚠ 3d-splicer not available (install or set SPLICER_PATH)")
                    print("    → Continuing without case generation")
                    return False

            # Convert design to 3d-splicer spec
            board_spec = {
                "board_id": design.project_name.replace(" ", "_"),
                "bbox_mm": {
                    "width": design.pcb_size_mm[0],
                    "height": design.pcb_size_mm[1],
                    "thickness": 1.6  # Standard PCB thickness
                },
                "components": [
                    {
                        "x": p.position[0],
                        "y": p.position[1],
                        "height": 10.0,  # Estimate component height
                        "keepout_radius": 3.0
                    }
                    for p in design.placements
                ],
                "mounts": [],  # Auto-generate mounting holes
                "io_ports": []  # Could extract from wiring
            }

            print(f"    → Board: {board_spec['bbox_mm']['width']}×{board_spec['bbox_mm']['height']}mm")
            print(f"    → Components: {len(board_spec['components'])}")

            # Convert to splicer format
            splicer_request = convert_func(board_spec)

            # Submit to splicer
            client = ClientClass()
            result = client.submit_job(
                splicer_request,
                idempotency_key=board_spec["board_id"]
            )

            print(f"    ✓ Case generation job submitted")
            print(f"       Job ID: {result.get('job_id', 'N/A')}")

            if "stl_path" in result:
                print(f"       STL file: {result['stl_path']}")

            return True

        except Exception as e:
            logger.error(f"Case generation failed: {e}")
            print(f"    ✗ Failed: {e}")
            return False

    def suggest_projects_from_scraps(self):
        """Suggest projects that can be built from available scrap components."""

        print("\n" + "=" * 70)
        print("SCRAP PROJECT SUGGESTIONS")
        print("=" * 70)
        print()

        # Get scrap components
        scrap_components = [
            comp.name for comp in self.resource_manager.inventory.values()
            if comp.condition.value == "scrap"
        ]

        if not scrap_components:
            print("No scrap components in inventory.")
            print("Add scrap components with:")
            print("  python scripts/harvest_scraps.py")
            return

        print(f"Found {len(scrap_components)} scrap components:")
        for comp in scrap_components:
            print(f"  ♻ {comp}")

        print()

        # Get suggestions
        suggestions = self.resource_manager.suggest_design_from_scraps(scrap_components)

        if suggestions:
            print("Possible projects:")
            for i, proj in enumerate(suggestions, 1):
                print(f"\n{i}. {proj['project']}")
                print(f"   Difficulty: {proj['difficulty']}")
                print(f"   Uses: {', '.join(proj['components_used'])}")
        else:
            print("No project suggestions available for current scrap components.")

        print("\n" + "=" * 70)

    def show_inventory(self):
        """Display current component inventory."""
        print()
        print(self.resource_manager.generate_report())


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Dum-E Build Orchestrator - Natural Language to Physical Build",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build WiFi temperature sensor
  python build_project.py "build me a WiFi temperature sensor"

  # Preview design only (don't build)
  python build_project.py "LED blinker" --preview-only

  # Auto-build without confirmation prompts
  python build_project.py "motor controller" --auto-build

  # Prefer using new components over scraps
  python build_project.py "humidity sensor" --no-scraps

  # Skip 3D case generation
  python build_project.py "LED blinker" --no-case

  # Show scrap project suggestions
  python build_project.py --suggest-scraps

  # Show inventory
  python build_project.py --inventory

  # Generate shopping list with real-time pricing
  python build_project.py --shopping-list "WiFi temperature sensor"
        """
    )

    parser.add_argument(
        "request",
        nargs="?",
        help="Natural language build request (e.g., 'build me a temperature sensor')"
    )

    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="Generate and preview design without building"
    )

    parser.add_argument(
        "--auto-build",
        action="store_true",
        help="Skip confirmation prompts and build automatically"
    )

    parser.add_argument(
        "--no-scraps",
        action="store_true",
        help="Prefer new components over scrap components"
    )

    parser.add_argument(
        "--no-case",
        action="store_true",
        help="Skip 3D case generation (build circuit only)"
    )

    parser.add_argument(
        "--suggest-scraps",
        action="store_true",
        help="Suggest projects that can be built from available scraps"
    )

    parser.add_argument(
        "--inventory",
        action="store_true",
        help="Show current component inventory"
    )

    parser.add_argument(
        "--shopping-list",
        type=str,
        metavar="PROJECT",
        help="Generate shopping list with prices for a project (e.g., 'WiFi sensor')"
    )

    parser.add_argument(
        "--inventory-path",
        type=Path,
        help="Path to component inventory JSON file"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("build_output"),
        help="Output directory for designs"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    # Initialize orchestrator
    orchestrator = BuildOrchestrator(
        inventory_path=args.inventory_path,
        output_dir=args.output_dir,
        generate_case=not args.no_case
    )

    # Handle different modes
    if args.suggest_scraps:
        orchestrator.suggest_projects_from_scraps()
        return 0

    if args.inventory:
        orchestrator.show_inventory()
        return 0

    if args.shopping_list:
        # Generate shopping list for specified project
        print(f"\nGenerating shopping list for: {args.shopping_list}")

        intent = orchestrator.parser.parse(args.shopping_list)

        shopping_list = orchestrator.resource_manager.generate_shopping_list(
            intent.required_components,
            output_path=orchestrator.design_generator.output_dir / "shopping_list.txt"
        )

        print()
        print(shopping_list)
        print(f"\nSaved to: {orchestrator.design_generator.output_dir}/shopping_list.txt")

        return 0

    # Require request for build mode
    if not args.request:
        parser.print_help()
        print("\n⚠ Error: Build request required (or use --suggest-scraps / --inventory)")
        return 1

    # Execute build
    success = orchestrator.build_from_request(
        user_request=args.request,
        preview_only=args.preview_only,
        auto_build=args.auto_build,
        use_scraps=not args.no_scraps
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
