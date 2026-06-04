#!/usr/bin/env python3
"""
Circuit.AI Demo Script

Demonstrates the Component Intelligence Platform functionality.
"""

import sys
import json
import argparse
from pathlib import Path
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.ingest import CircuitAnalyzer


def demo_with_file(image_path: str):
    """Run demo with actual image file."""
    print("🔍 Circuit.AI - Component Intelligence Platform")
    print("=" * 50)
    
    analyzer = CircuitAnalyzer()
    
    try:
        print(f"📁 Analyzing PCB image: {image_path}")
        results = analyzer.analyze_from_file(image_path)
        
        if "error" in results:
            print(f"❌ Error: {results['error']}")
            return
        
        # Display results
        display_results(results)
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        logger.error(f"Demo error: {e}")


def demo_with_sample_data():
    """Run demo with sample data."""
    print("🔍 Circuit.AI - Component Intelligence Platform")
    print("=" * 50)
    print("📊 Running demo with sample data...")
    
    analyzer = CircuitAnalyzer()
    results = analyzer.generate_demo_data()
    summary = analyzer.get_analysis_summary(results)
    
    # Display results
    display_results(results)
    print("\n📝 Summary:")
    print(f"   {summary['summary_text']}")


def display_results(results: dict):
    """Display analysis results in a formatted way."""
    detection_summary = results.get("detection_summary", {})
    functionality_data = results.get("functionality_analysis", {})
    recommendations = results.get("project_recommendations", [])
    
    print("\n📊 Detection Results:")
    print(f"   Total Components: {detection_summary.get('total_components', 0)}")
    print(f"   Detection Quality: {detection_summary.get('detection_quality', 'unknown')}")
    print(f"   Average Confidence: {detection_summary.get('average_confidence', 0):.2f}")
    
    # Component breakdown
    components_by_type = detection_summary.get("components_by_type", {})
    if components_by_type:
        print("\n🔧 Component Breakdown:")
        for comp_type, count in components_by_type.items():
            print(f"   • {comp_type}: {count}")
    
    # Functionality analysis
    capabilities = functionality_data.get("capabilities", [])
    if capabilities:
        print(f"\n⚡ Capabilities Detected:")
        for capability in capabilities:
            print(f"   • {capability}")
    
    project_potential = functionality_data.get("project_potential", "none")
    print(f"\n🎯 Project Potential: {project_potential.upper()}")
    
    # Recommendations
    if recommendations:
        print(f"\n💡 Top Project Recommendations:")
        for i, rec in enumerate(recommendations[:3], 1):
            print(f"   {i}. {rec['name']}")
            print(f"      Difficulty: {rec['difficulty']}")
            print(f"      Time: {rec['time_estimate']}")
            print(f"      Score: {rec['score']:.2f}")
            print(f"      Description: {rec['description']}")
            print()


def main():
    """Main demo function."""
    parser = argparse.ArgumentParser(description="Circuit.AI Demo")
    parser.add_argument("image_path", nargs="?", help="Path to PCB image file")
    parser.add_argument("--sample", action="store_true", help="Run with sample data")
    
    args = parser.parse_args()
    
    if args.sample:
        demo_with_sample_data()
    elif args.image_path:
        demo_with_file(args.image_path)
    else:
        print("🔍 Circuit.AI - Component Intelligence Platform")
        print("=" * 50)
        print("Usage:")
        print("  python scripts/demo.py <image_path>  # Analyze specific image")
        print("  python scripts/demo.py --sample      # Run with sample data")
        print("\nExample:")
        print("  python scripts/demo.py data/raw/motherboard.jpg")
        print("  python scripts/demo.py --sample")


if __name__ == "__main__":
    main() 