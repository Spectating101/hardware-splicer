#!/usr/bin/env python3
"""
Command-line interface for functional 3D case generation.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

from src.schemas.functional import FunctionalSpec
from services.iteration_engine import IterationEngine
from services.planner import MockLLMPlanner
from services.evaluator.master import MasterEvaluator

def load_spec(spec_path: str) -> FunctionalSpec:
    """Load functional specification from file"""
    try:
        with open(spec_path, 'r') as f:
            data = json.load(f)
        return FunctionalSpec(**data)
    except Exception as e:
        print(f"Error loading spec: {e}")
        sys.exit(1)

def run_optimization(spec: FunctionalSpec, output_dir: str = "output"):
    """Run optimization and display results"""
    print(f"Starting optimization for: {spec.id}")
    print(f"Requirements: {len(spec.functional_requirements)}")
    print(f"Constraints: {len(spec.constraints)}")
    print(f"Max iterations: {spec.iteration_budget.max_iters}")
    print(f"Max time: {spec.iteration_budget.max_seconds}s")
    print()
    
    # Initialize services
    planner = MockLLMPlanner()
    evaluator = MasterEvaluator()
    engine = IterationEngine(planner, evaluator)
    
    # Run optimization
    start_time = time.time()
    result = engine.optimize(spec, output_dir)
    elapsed = time.time() - start_time
    
    # Display results
    print(f"\n{'='*60}")
    print(f"OPTIMIZATION COMPLETE")
    print(f"{'='*60}")
    print(f"Job ID: {result.job_id}")
    print(f"Success: {'✅ YES' if result.success else '❌ NO'}")
    print(f"Total time: {elapsed:.1f}s")
    print(f"Iterations: {len(result.iterations)}")
    
    if result.iterations:
        best_iter = max(result.iterations, key=lambda x: x.overall_score)
        print(f"Best score: {best_iter.overall_score:.3f}")
        print(f"All tests passed: {'✅' if best_iter.all_passed else '❌'}")
    
    print(f"\nArtifacts generated:")
    for artifact_type, path in result.artifacts.items():
        print(f"  {artifact_type}: {path}")
    
    # Show final test results
    if result.iterations:
        final_iter = result.iterations[-1]
        print(f"\nFinal test results:")
        for test_result in final_iter.evaluation:
            status = "✅ PASS" if test_result.passed else "❌ FAIL"
            print(f"  {test_result.test_id}: {status} (score: {test_result.score:.3f})")
            if test_result.details:
                print(f"    {test_result.details}")
    
    return result

def create_example_spec(output_path: str):
    """Create an example functional specification"""
    example_spec = {
        "id": "example_sensor_board",
        "context": {
            "board_bbox_mm": {
                "x": 50.0,
                "y": 30.0,
                "z": 1.6
            },
            "mounts": [
                {
                    "type": "standoff",
                    "pos": [5.0, 5.0],
                    "dia": 2.5,
                    "height": 3.0
                },
                {
                    "type": "standoff", 
                    "pos": [45.0, 25.0],
                    "dia": 2.5,
                    "height": 3.0
                }
            ],
            "io": [
                {
                    "type": "usb",
                    "edge": "south",
                    "offset_mm": 25.0,
                    "slot": [12.0, 5.0]
                }
            ],
            "keepouts": [
                {
                    "shape": "rect",
                    "at": [25.0, 15.0],
                    "size": [10.0, 8.0],
                    "z": [0.0, 4.0]
                }
            ]
        },
        "functional_requirements": [
            {
                "id": "F1",
                "goal": "drop_protection",
                "absorb_energy_J": 2.0,
                "max_strain_pct": 5.0
            },
            {
                "id": "F2",
                "goal": "thermal_clearance",
                "min_air_gap_mm": 1.5
            },
            {
                "id": "F3",
                "goal": "toolless_access",
                "max_open_time_s": 3.0
            }
        ],
        "constraints": [
            {
                "id": "C1",
                "rule": "overall_envelope_mm",
                "value": "[60, 40, 15]"
            },
            {
                "id": "C2",
                "rule": "no_geometry_in_keepouts"
            },
            {
                "id": "C3",
                "rule": "printability:overhang_angle_deg",
                "value": 45
            }
        ],
        "materials": {
            "primary": "PLA",
            "infill_pct": 20,
            "layer_height_mm": 0.2,
            "wall_count": 2
        },
        "tolerances": {
            "fit_mm": 0.3,
            "hole_dia_mm": 0.2
        },
        "iteration_budget": {
            "max_iters": 6,
            "max_seconds": 180
        },
        "outputs": {
            "stl": True,
            "glb_preview": True,
            "report": "markdown"
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(example_spec, f, indent=2)
    
    print(f"Created example specification: {output_path}")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Functional 3D case generation tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  splicer run -f spec.json                    # Run optimization
  splicer run -f spec.json -o output/         # Custom output directory
  splicer create-example example.json         # Create example spec
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run optimization')
    run_parser.add_argument('-f', '--file', required=True, help='Functional specification file')
    run_parser.add_argument('-o', '--output', default='output', help='Output directory')
    
    # Create example command
    example_parser = subparsers.add_parser('create-example', help='Create example specification')
    example_parser.add_argument('output', help='Output file path')
    
    args = parser.parse_args()
    
    if args.command == 'run':
        spec = load_spec(args.file)
        result = run_optimization(spec, args.output)
        
        if result.success:
            print(f"\n🎉 Optimization successful!")
            sys.exit(0)
        else:
            print(f"\n⚠️  Optimization completed but did not meet all requirements")
            sys.exit(1)
            
    elif args.command == 'create-example':
        create_example_spec(args.output)
        
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()
