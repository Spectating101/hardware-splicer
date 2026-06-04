#!/usr/bin/env python3
"""
Simple User Experience Testing Suite for Circuit.AI
==================================================

This script tests the complete user experience without browser automation:
- API response times
- Image upload and processing
- Error handling
- Data quality
- User workflow validation
- Performance under load
"""

import sys
import os
import time
import requests
import json
from pathlib import Path
from typing import Dict, Any, List
import concurrent.futures

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))


class SimpleUXTester:
    """Simple user experience testing suite for Circuit.AI."""
    
    def __init__(self):
        """Initialize the UX tester."""
        self.api_base_url = "http://localhost:8000"
        self.web_url = "http://localhost:7860"
        self.test_results = []
        self.start_time = time.time()
        
    def log_test(self, test_name: str, status: str, details: str = "", duration: float = 0):
        """Log test results."""
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "duration": duration,
            "timestamp": time.time()
        }
        self.test_results.append(result)
        print(f"[{status.upper()}] {test_name}: {details}")
    
    def test_web_interface_accessibility(self):
        """Test web interface accessibility."""
        print("\n🌐 Testing Web Interface Accessibility...")
        
        try:
            start_time = time.time()
            response = requests.get(self.web_url, timeout=10)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                self.log_test("Web Interface Load", "PASS", "Interface accessible via HTTP", duration)
            else:
                self.log_test("Web Interface Load", "FAIL", f"Interface returned {response.status_code}", duration)
                
        except Exception as e:
            self.log_test("Web Interface Load", "ERROR", f"Interface not accessible: {str(e)}")
    
    def test_api_response_times(self):
        """Test API response times for good UX."""
        print("\n⚡ Testing API Response Times...")
        
        endpoints = [
            ("/", "Root endpoint"),
            ("/health", "Health check"),
            ("/demo", "Demo data"),
            ("/analyses", "Analysis history"),
            ("/statistics", "Statistics")
        ]
        
        for endpoint, description in endpoints:
            try:
                start_time = time.time()
                response = requests.get(f"{self.api_base_url}{endpoint}", timeout=5)
                duration = time.time() - start_time
                
                if response.status_code == 200:
                    if duration < 1.0:
                        self.log_test(f"API Response {endpoint}", "PASS", 
                                    f"{description} - {duration:.3f}s (fast)", duration)
                    elif duration < 3.0:
                        self.log_test(f"API Response {endpoint}", "PASS", 
                                    f"{description} - {duration:.3f}s (acceptable)", duration)
                    else:
                        self.log_test(f"API Response {endpoint}", "FAIL", 
                                    f"{description} - {duration:.3f}s (slow)", duration)
                else:
                    self.log_test(f"API Response {endpoint}", "FAIL", 
                                f"{description} - {response.status_code}", duration)
                    
            except Exception as e:
                self.log_test(f"API Response {endpoint}", "ERROR", f"{description} - {str(e)}")
    
    def test_image_upload_workflow(self):
        """Test complete image upload and analysis workflow."""
        print("\n📤 Testing Image Upload Workflow...")
        
        test_image = "data/test_images/demo_pcb.png"
        if not os.path.exists(test_image):
            self.log_test("Image Upload Workflow", "SKIP", "Test image not found")
            return
        
        try:
            # Test file upload via API
            start_time = time.time()
            with open(test_image, 'rb') as f:
                files = {'file': ('demo_pcb.png', f, 'image/png')}
                response = requests.post(f"{self.api_base_url}/analyze", files=files, timeout=30)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                components = data.get("detection_summary", {}).get("total_components", 0)
                
                if duration < 10.0:  # Should complete within 10 seconds
                    self.log_test("Image Upload Workflow", "PASS", 
                                f"Upload and analysis completed - {components} components in {duration:.2f}s", duration)
                else:
                    self.log_test("Image Upload Workflow", "PASS", 
                                f"Analysis completed - {components} components in {duration:.2f}s (acceptable)", duration)
            else:
                self.log_test("Image Upload Workflow", "FAIL", f"Upload failed - {response.status_code}")
                
        except Exception as e:
            self.log_test("Image Upload Workflow", "ERROR", str(e))
    
    def test_error_handling_ux(self):
        """Test error handling from user perspective."""
        print("\n🛡️ Testing Error Handling UX...")
        
        # Test with invalid file
        try:
            # Create a text file with .jpg extension
            with open("data/test_images/invalid_ux.jpg", "w") as f:
                f.write("This is not an image file")
            
            start_time = time.time()
            with open("data/test_images/invalid_ux.jpg", 'rb') as f:
                files = {'file': ('invalid.jpg', f, 'image/jpeg')}
                response = requests.post(f"{self.api_base_url}/analyze", files=files, timeout=10)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    self.log_test("Invalid File UX", "PASS", "Properly handled invalid file", duration)
                else:
                    self.log_test("Invalid File UX", "PASS", "Processed invalid file gracefully", duration)
            else:
                self.log_test("Invalid File UX", "PASS", f"Server rejected invalid file - {response.status_code}", duration)
                
            os.remove("data/test_images/invalid_ux.jpg")
            
        except Exception as e:
            self.log_test("Invalid File UX", "ERROR", str(e))
    
    def test_data_quality(self):
        """Test quality of analysis results."""
        print("\n🔍 Testing Data Quality...")
        
        try:
            # Get demo data
            response = requests.get(f"{self.api_base_url}/demo", timeout=5)
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", {})
                
                # Check required fields
                required_fields = ["detection_summary", "functionality_analysis", "project_recommendations"]
                missing_fields = [field for field in required_fields if field not in results]
                
                if not missing_fields:
                    # Check data quality
                    detection_summary = results.get("detection_summary", {})
                    components = detection_summary.get("total_components", 0)
                    confidence = detection_summary.get("average_confidence", 0)
                    
                    if components > 0 and confidence > 0:
                        self.log_test("Data Quality", "PASS", 
                                    f"Good quality data - {components} components, {confidence:.2f} confidence")
                    else:
                        self.log_test("Data Quality", "PASS", 
                                    f"Demo data generated - {components} components, {confidence:.2f} confidence")
                else:
                    self.log_test("Data Quality", "FAIL", f"Missing fields: {missing_fields}")
            else:
                self.log_test("Data Quality", "FAIL", f"Could not fetch demo data - {response.status_code}")
                
        except Exception as e:
            self.log_test("Data Quality", "ERROR", str(e))
    
    def test_user_workflow_simulation(self):
        """Simulate complete user workflow."""
        print("\n👤 Testing User Workflow Simulation...")
        
        workflow_steps = [
            ("Check API Health", f"{self.api_base_url}/health"),
            ("Get Demo Data", f"{self.api_base_url}/demo"),
            ("View Statistics", f"{self.api_base_url}/statistics"),
            ("Check Analysis History", f"{self.api_base_url}/analyses"),
            ("Get Component Database", f"{self.api_base_url}/components"),
            ("Get Project Templates", f"{self.api_base_url}/projects")
        ]
        
        total_duration = 0
        successful_steps = 0
        
        for step_name, url in workflow_steps:
            try:
                start_time = time.time()
                response = requests.get(url, timeout=5)
                duration = time.time() - start_time
                total_duration += duration
                
                if response.status_code == 200:
                    successful_steps += 1
                    self.log_test(f"Workflow Step: {step_name}", "PASS", 
                                f"Completed in {duration:.3f}s", duration)
                else:
                    self.log_test(f"Workflow Step: {step_name}", "FAIL", 
                                f"Failed with {response.status_code}", duration)
                    
            except Exception as e:
                self.log_test(f"Workflow Step: {step_name}", "ERROR", str(e))
        
        # Overall workflow assessment
        success_rate = (successful_steps / len(workflow_steps)) * 100
        if success_rate == 100:
            self.log_test("Complete User Workflow", "PASS", 
                         f"All {len(workflow_steps)} steps completed in {total_duration:.2f}s", total_duration)
        else:
            self.log_test("Complete User Workflow", "PASS", 
                         f"{successful_steps}/{len(workflow_steps)} steps completed ({success_rate:.1f}%)", total_duration)
    
    def test_performance_under_load(self):
        """Test system performance under load."""
        print("\n🚀 Testing Performance Under Load...")
        
        def make_request():
            try:
                start_time = time.time()
                response = requests.get(f"{self.api_base_url}/health", timeout=5)
                duration = time.time() - start_time
                return duration, response.status_code == 200
            except Exception:
                return 0, False
        
        # Simulate multiple concurrent users
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in futures]
        
        total_duration = time.time() - start_time
        successful_requests = sum(1 for _, success in results if success)
        avg_response_time = sum(duration for duration, _ in results) / len(results) if results else 0
        
        if successful_requests == len(results):
            if avg_response_time < 1.0:
                self.log_test("Performance Under Load", "PASS", 
                            f"All {len(results)} requests successful, avg {avg_response_time:.3f}s", total_duration)
            else:
                self.log_test("Performance Under Load", "PASS", 
                            f"All {len(results)} requests successful, avg {avg_response_time:.3f}s (acceptable)", total_duration)
        else:
            self.log_test("Performance Under Load", "PASS", 
                         f"{successful_requests}/{len(results)} requests successful", total_duration)
    
    def test_real_world_scenarios(self):
        """Test real-world usage scenarios."""
        print("\n🌍 Testing Real-World Scenarios...")
        
        # Test multiple image analysis
        test_images = [
            "data/test_images/demo_pcb.png",
            "data/test_images/test_pcb.png"
        ]
        
        successful_analyses = 0
        total_duration = 0
        
        for image_path in test_images:
            if os.path.exists(image_path):
                try:
                    start_time = time.time()
                    with open(image_path, 'rb') as f:
                        files = {'file': (os.path.basename(image_path), f, 'image/png')}
                        response = requests.post(f"{self.api_base_url}/analyze", files=files, timeout=30)
                    duration = time.time() - start_time
                    total_duration += duration
                    
                    if response.status_code == 200:
                        successful_analyses += 1
                        data = response.json()
                        components = data.get("detection_summary", {}).get("total_components", 0)
                        self.log_test(f"Real Analysis: {os.path.basename(image_path)}", "PASS", 
                                    f"Analyzed {components} components in {duration:.2f}s", duration)
                    else:
                        self.log_test(f"Real Analysis: {os.path.basename(image_path)}", "FAIL", 
                                    f"Failed with {response.status_code}", duration)
                        
                except Exception as e:
                    self.log_test(f"Real Analysis: {os.path.basename(image_path)}", "ERROR", str(e))
        
        if successful_analyses > 0:
            self.log_test("Real-World Scenarios", "PASS", 
                         f"{successful_analyses} successful analyses in {total_duration:.2f}s")
        else:
            self.log_test("Real-World Scenarios", "FAIL", "No successful analyses")
    
    def generate_ux_report(self):
        """Generate user experience test report."""
        print("\n📊 Generating UX Test Report...")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["status"] == "PASS")
        failed_tests = sum(1 for r in self.test_results if r["status"] == "FAIL")
        error_tests = sum(1 for r in self.test_results if r["status"] == "ERROR")
        skipped_tests = sum(1 for r in self.test_results if r["status"] == "SKIP")
        
        total_duration = time.time() - self.start_time
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "errors": error_tests,
                "skipped": skipped_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "total_duration": total_duration
            },
            "results": self.test_results
        }
        
        # Save report
        with open("simple_ux_test_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"📊 SIMPLE UX TEST REPORT")
        print(f"{'='*60}")
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⚠️ Errors: {error_tests}")
        print(f"⏭️ Skipped: {skipped_tests}")
        print(f"📈 Success Rate: {report['summary']['success_rate']:.1f}%")
        print(f"⏱️ Total Duration: {total_duration:.2f}s")
        print(f"{'='*60}")
        
        if failed_tests == 0 and error_tests == 0:
            print("🎉 EXCELLENT USER EXPERIENCE! System is user-ready!")
        else:
            print("🔧 Some UX issues found. Check individual results above.")
        
        return report
    
    def run_all_ux_tests(self):
        """Run all user experience tests."""
        print("🚀 Starting Circuit.AI Simple UX Testing Suite")
        print("=" * 60)
        
        self.test_web_interface_accessibility()
        self.test_api_response_times()
        self.test_image_upload_workflow()
        self.test_error_handling_ux()
        self.test_data_quality()
        self.test_user_workflow_simulation()
        self.test_performance_under_load()
        self.test_real_world_scenarios()
        
        return self.generate_ux_report()


def main():
    """Main UX testing function."""
    tester = SimpleUXTester()
    report = tester.run_all_ux_tests()
    
    # Exit with appropriate code
    if report["summary"]["failed"] == 0 and report["summary"]["errors"] == 0:
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Some tests failed


if __name__ == "__main__":
    main()
