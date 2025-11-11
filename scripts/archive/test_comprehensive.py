#!/usr/bin/env python3
"""
Circuit.AI Comprehensive Test Suite

Consolidates all testing functionality including:
- Core pipeline testing
- API endpoint testing
- LLM integration testing
- Demo functionality testing
- Performance benchmarking
"""

import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.ingest import CircuitAnalyzer
from src.core.database import DatabaseManager
from src.vision.detector import PCBDetector
from src.llm.mapper import FunctionalMapper
from src.llm.llm_integration import CircuitLLMIntegration


class ComprehensiveTester:
    """Comprehensive test suite for Circuit.AI platform."""
    
    def __init__(self):
        self.analyzer = CircuitAnalyzer()
        self.db = DatabaseManager()
        self.detector = PCBDetector()
        self.mapper = FunctionalMapper()
        
        # Test results storage
        self.results = {
            "core_tests": {},
            "api_tests": {},
            "llm_tests": {},
            "performance_tests": {},
            "integration_tests": {}
        }
    
    def test_core_pipeline(self) -> Dict[str, Any]:
        """Test the core analysis pipeline."""
        print("🔍 Testing Core Pipeline...")
        
        # Test with sample data
        start_time = time.time()
        results = self.analyzer.generate_demo_data()
        end_time = time.time()
        
        # Validate results structure
        required_keys = ["detection_summary", "functionality_analysis", "project_recommendations"]
        structure_valid = all(key in results for key in required_keys)
        
        # Check detection results
        detection_summary = results.get("detection_summary", {})
        components_detected = detection_summary.get("total_components", 0) > 0
        
        # Check functionality analysis
        functionality = results.get("functionality_analysis", {})
        capabilities_found = len(functionality.get("capabilities", [])) > 0
        
        # Check recommendations
        recommendations = results.get("project_recommendations", [])
        recommendations_found = len(recommendations) > 0
        
        test_results = {
            "success": structure_valid and components_detected and capabilities_found and recommendations_found,
            "processing_time": end_time - start_time,
            "components_detected": detection_summary.get("total_components", 0),
            "capabilities_found": len(functionality.get("capabilities", [])),
            "recommendations_found": len(recommendations),
            "structure_valid": structure_valid
        }
        
        self.results["core_tests"] = test_results
        return test_results
    
    def test_detection_backends(self) -> Dict[str, Any]:
        """Test different detection backends."""
        print("🔍 Testing Detection Backends...")
        
        # Test classical CV
        classical_results = self.detector.detect_components(
            image=None,  # Will use demo data
            backend="classical",
            enable_ocr=False
        )
        
        # Test demo backend
        demo_results = self.detector.detect_components(
            image=None,
            backend="demo",
            enable_ocr=False
        )
        
        test_results = {
            "classical_cv": {
                "success": len(classical_results) > 0,
                "detections": len(classical_results),
                "avg_confidence": sum(d.get("confidence", 0) for d in classical_results) / len(classical_results) if classical_results else 0
            },
            "demo_backend": {
                "success": len(demo_results) > 0,
                "detections": len(demo_results),
                "avg_confidence": sum(d.get("confidence", 0) for d in demo_results) / len(demo_results) if demo_results else 0
            }
        }
        
        self.results["detection_tests"] = test_results
        return test_results
    
    def test_llm_integration(self) -> Dict[str, Any]:
        """Test LLM integration functionality."""
        print("🤖 Testing LLM Integration...")
        
        try:
            # Test LLM integration initialization
            llm_integration = CircuitLLMIntegration()
            
            # Test component analysis
            sample_component = {
                "type": "ic_chip",
                "confidence": 0.85,
                "bbox": [100, 100, 200, 150],
                "class_name": "ic_chip"
            }
            
            start_time = time.time()
            analysis = llm_integration.analyze_component_advanced(sample_component)
            end_time = time.time()
            
            test_results = {
                "success": analysis is not None,
                "processing_time": end_time - start_time,
                "analysis_structure": isinstance(analysis, dict),
                "has_functionality": "functionality" in analysis if analysis else False
            }
            
        except Exception as e:
            logger.warning(f"LLM integration test failed: {e}")
            test_results = {
                "success": False,
                "error": str(e),
                "processing_time": 0,
                "analysis_structure": False,
                "has_functionality": False
            }
        
        self.results["llm_tests"] = test_results
        return test_results
    
    def test_database_operations(self) -> Dict[str, Any]:
        """Test database operations."""
        print("💾 Testing Database Operations...")
        
        try:
            # Test recent analyses retrieval
            recent_analyses = self.db.get_recent_analyses(limit=5)
            
            # Test statistics
            stats = self.db.get_performance_stats()
            
            test_results = {
                "success": True,
                "recent_analyses_retrieved": len(recent_analyses),
                "stats_available": stats is not None,
                "total_analyses": stats.get("total_analyses", 0) if stats else 0
            }
            
        except Exception as e:
            logger.error(f"Database test failed: {e}")
            test_results = {
                "success": False,
                "error": str(e),
                "recent_analyses_retrieved": 0,
                "stats_available": False,
                "total_analyses": 0
            }
        
        self.results["database_tests"] = test_results
        return test_results
    
    def test_performance(self) -> Dict[str, Any]:
        """Test system performance."""
        print("⚡ Testing Performance...")
        
        # Test multiple analyses
        start_time = time.time()
        results = []
        
        for i in range(3):
            result = self.analyzer.generate_demo_data()
            results.append(result)
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / 3
        
        test_results = {
            "total_time": total_time,
            "average_time": avg_time,
            "throughput": 3 / total_time,  # analyses per second
            "success": avg_time < 5.0  # Should complete in under 5 seconds
        }
        
        self.results["performance_tests"] = test_results
        return test_results
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all comprehensive tests."""
        print("🚀 Circuit.AI Comprehensive Test Suite")
        print("=" * 50)
        
        # Run all test categories
        self.test_core_pipeline()
        self.test_detection_backends()
        self.test_llm_integration()
        self.test_database_operations()
        self.test_performance()
        
        # Calculate overall success
        all_tests = []
        for category, results in self.results.items():
            if isinstance(results, dict) and "success" in results:
                all_tests.append(results["success"])
        
        overall_success = all(all_tests) if all_tests else False
        
        # Generate summary
        summary = {
            "overall_success": overall_success,
            "tests_passed": sum(all_tests),
            "total_tests": len(all_tests),
            "success_rate": sum(all_tests) / len(all_tests) if all_tests else 0,
            "detailed_results": self.results
        }
        
        return summary
    
    def display_results(self, summary: Dict[str, Any]):
        """Display test results in a formatted way."""
        print("\n📊 Test Results Summary")
        print("=" * 50)
        
        success_rate = summary["success_rate"] * 100
        print(f"Overall Success: {'✅ PASS' if summary['overall_success'] else '❌ FAIL'}")
        print(f"Success Rate: {success_rate:.1f}% ({summary['tests_passed']}/{summary['total_tests']})")
        
        print("\n📋 Detailed Results:")
        for category, results in summary["detailed_results"].items():
            if isinstance(results, dict) and "success" in results:
                status = "✅ PASS" if results["success"] else "❌ FAIL"
                print(f"  {category.replace('_', ' ').title()}: {status}")
                
                # Show additional details for failed tests
                if not results["success"] and "error" in results:
                    print(f"    Error: {results['error']}")
        
        # Performance summary
        perf_results = summary["detailed_results"].get("performance_tests", {})
        if perf_results:
            print(f"\n⚡ Performance:")
            print(f"  Average Analysis Time: {perf_results.get('average_time', 0):.2f}s")
            print(f"  Throughput: {perf_results.get('throughput', 0):.2f} analyses/sec")
        
        print("\n" + "=" * 50)


def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Circuit.AI Comprehensive Test Suite")
    parser.add_argument("--category", choices=["core", "detection", "llm", "database", "performance", "all"], 
                       default="all", help="Test category to run")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--output", "-o", help="Output results to JSON file")
    
    args = parser.parse_args()
    
    tester = ComprehensiveTester()
    
    if args.category == "all":
        summary = tester.run_all_tests()
    else:
        # Run specific category
        if args.category == "core":
            summary = {"core_tests": tester.test_core_pipeline()}
        elif args.category == "detection":
            summary = {"detection_tests": tester.test_detection_backends()}
        elif args.category == "llm":
            summary = {"llm_tests": tester.test_llm_integration()}
        elif args.category == "database":
            summary = {"database_tests": tester.test_database_operations()}
        elif args.category == "performance":
            summary = {"performance_tests": tester.test_performance()}
    
    # Display results
    if args.category == "all":
        tester.display_results(summary)
    else:
        print(f"📊 {args.category.title()} Test Results:")
        for category, results in summary.items():
            if isinstance(results, dict) and "success" in results:
                status = "✅ PASS" if results["success"] else "❌ FAIL"
                print(f"  {status}")
                if args.verbose:
                    for key, value in results.items():
                        if key != "success":
                            print(f"    {key}: {value}")
    
    # Save results if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"\n💾 Results saved to {args.output}")
    
    # Exit with appropriate code
    if args.category == "all":
        exit_code = 0 if summary["overall_success"] else 1
    else:
        exit_code = 0 if any(results.get("success", False) for results in summary.values()) else 1
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
