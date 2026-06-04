#!/usr/bin/env python3
"""
Circuit.AI - Practical Demonstration
====================================

This script demonstrates the real-world functionality of Circuit.AI
by testing with actual PCB images and showing the complete workflow.
"""

import sys
import os
import time
import requests
import json
from pathlib import Path
from typing import Dict, Any, List

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.ingest import CircuitAnalyzer
from src.core.database import CircuitDatabase


def test_api_endpoints():
    """Test all API endpoints to ensure they're working."""
    print("🔌 Testing API Endpoints...")
    
    base_url = "http://localhost:8000"
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✅ Health endpoint: OK")
        else:
            print("❌ Health endpoint: FAILED")
            return False
    except Exception as e:
        print(f"❌ Health endpoint: ERROR - {e}")
        return False
    
    # Test statistics endpoint
    try:
        response = requests.get(f"{base_url}/statistics")
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Statistics endpoint: OK (Total analyses: {stats.get('total_analyses', 0)})")
        else:
            print("❌ Statistics endpoint: FAILED")
    except Exception as e:
        print(f"❌ Statistics endpoint: ERROR - {e}")
    
    # Test components endpoint
    try:
        response = requests.get(f"{base_url}/components")
        if response.status_code == 200:
            components = response.json()
            print(f"✅ Components endpoint: OK ({len(components)} components available)")
        else:
            print("❌ Components endpoint: FAILED")
    except Exception as e:
        print(f"❌ Components endpoint: ERROR - {e}")
    
    return True


def test_image_analysis(image_path: str):
    """Test image analysis with a real PCB image."""
    print(f"\n🔍 Testing Image Analysis: {image_path}")
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return None
    
    # Test with API
    base_url = "http://localhost:8000"
    
    try:
        with open(image_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(f"{base_url}/analyze", files=files)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ API Analysis: SUCCESS")
            
            # Extract key information
            summary = result.get('summary', {})
            total_components = summary.get('total_components', 0)
            project_potential = summary.get('project_potential', 'unknown')
            
            print(f"   📊 Components detected: {total_components}")
            print(f"   🎯 Project potential: {project_potential}")
            
            # Show component breakdown
            breakdown = summary.get('component_breakdown', {})
            if breakdown:
                print("   🔧 Component breakdown:")
                for comp_type, count in breakdown.items():
                    print(f"      • {comp_type}: {count}")
            
            # Show detection details
            detections = result.get('results', {}).get('detections', [])
            if detections:
                print("   🔍 Top detections:")
                for i, detection in enumerate(detections[:3]):
                    class_name = detection.get('class_name', 'unknown')
                    confidence = detection.get('confidence', 0)
                    print(f"      {i+1}. {class_name} (confidence: {confidence:.2f})")
            
            return result
        else:
            print(f"❌ API Analysis: FAILED - Status {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ API Analysis: ERROR - {e}")
        return None


def test_direct_analysis(image_path: str):
    """Test direct analysis using the CircuitAnalyzer."""
    print(f"\n🔬 Testing Direct Analysis: {image_path}")
    
    try:
        analyzer = CircuitAnalyzer()
        
        start_time = time.time()
        result = analyzer.analyze_pcb(image_path)
        processing_time = time.time() - start_time
        
        print(f"✅ Direct Analysis: SUCCESS ({processing_time:.2f}s)")
        
        # Extract key information
        detections = result.get('detections', [])
        total_components = len(detections)
        
        print(f"   📊 Components detected: {total_components}")
        
        # Show detection details
        if detections:
            print("   🔍 Detection details:")
            for i, detection in enumerate(detections[:3]):  # Show first 3
                class_name = detection.get('class_name', 'unknown')
                confidence = detection.get('confidence', 0)
                print(f"      {i+1}. {class_name} (confidence: {confidence:.2f})")
            
            if len(detections) > 3:
                print(f"      ... and {len(detections) - 3} more")
        
        return result
        
    except Exception as e:
        print(f"❌ Direct Analysis: ERROR - {e}")
        return None


def test_web_interface():
    """Test web interface accessibility."""
    print("\n🌐 Testing Web Interface...")
    
    try:
        response = requests.get("http://localhost:7860")
        if response.status_code == 200:
            print("✅ Gradio UI: ACCESSIBLE")
            print("   📱 Open http://localhost:7860 in your browser")
            return True
        else:
            print(f"❌ Gradio UI: FAILED - Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Gradio UI: ERROR - {e}")
        return False


def show_system_status():
    """Show current system status."""
    print("\n📈 System Status")
    print("=" * 50)
    
    # Check if servers are running
    try:
        api_response = requests.get("http://localhost:8000/health", timeout=2)
        api_status = "✅ RUNNING" if api_response.status_code == 200 else "❌ ERROR"
    except Exception:
        api_status = "❌ NOT RUNNING"
    
    try:
        ui_response = requests.get("http://localhost:7860", timeout=2)
        ui_status = "✅ RUNNING" if ui_response.status_code == 200 else "❌ ERROR"
    except Exception:
        ui_status = "❌ NOT RUNNING"
    
    print(f"API Server (port 8000): {api_status}")
    print(f"Web UI (port 7860): {ui_status}")
    
    # Show statistics if API is running
    if api_status == "✅ RUNNING":
        try:
            stats_response = requests.get("http://localhost:8000/statistics")
            if stats_response.status_code == 200:
                stats = stats_response.json()
                print(f"Total analyses: {stats.get('total_analyses', 0)}")
                print(f"Average processing time: {stats.get('average_processing_time', 'N/A')}")
        except Exception: pass


def main():
    """Run comprehensive practical demonstration."""
    print("🚀 Circuit.AI - Practical Demonstration")
    print("=" * 60)
    
    # Show system status
    show_system_status()
    
    # Test API endpoints
    if not test_api_endpoints():
        print("\n❌ API endpoints not working. Please start the API server first.")
        print("   Run: source venv/bin/activate && uvicorn src.api.main:app --host 0.0.0.0 --port 8000")
        return
    
    # Test web interface
    test_web_interface()
    
    # Test with available images
    test_images = [
        "data/test_images/demo_pcb.png",
        "data/test_images/test_pcb.png"
    ]
    
    print("\n" + "=" * 60)
    print("🔬 PRACTICAL ANALYSIS TESTS")
    print("=" * 60)
    
    for image_path in test_images:
        if os.path.exists(image_path):
            print(f"\n📸 Testing with: {os.path.basename(image_path)}")
            print("-" * 40)
            
            # Test API analysis
            api_result = test_image_analysis(image_path)
            
            # Test direct analysis
            direct_result = test_direct_analysis(image_path)
            
            if api_result and direct_result:
                print("✅ Both API and direct analysis working correctly!")
            elif api_result:
                print("⚠️  API working, but direct analysis failed")
            elif direct_result:
                print("⚠️  Direct analysis working, but API failed")
            else:
                print("❌ Both analysis methods failed")
    
    print("\n" + "=" * 60)
    print("🎯 PRACTICAL DEMONSTRATION COMPLETE")
    print("=" * 60)
    
    print("\n📋 Next Steps:")
    print("1. Open http://localhost:7860 in your browser")
    print("2. Upload a PCB image and click 'Analyze PCB'")
    print("3. Try the 'Run Demo' button to see sample results")
    print("4. Explore component information and project recommendations")
    
    print("\n🔧 Available Features:")
    print("• Component detection (IC chips, capacitors, resistors, etc.)")
    print("• Confidence scoring and bounding box detection")
    print("• Educational value assessment")
    print("• Project recommendations based on salvaged components")
    print("• Export capabilities (CSV, PDF)")
    print("• Historical analysis tracking")
    
    print("\n🚀 Ready for deployment to Railway, Render, or other platforms!")


if __name__ == "__main__":
    main()
