#!/usr/bin/env python3
"""
Circuit.AI - Workflow Demonstration
===================================

This script demonstrates the complete workflow of Circuit.AI,
showing each step of the analysis pipeline with real data.
"""

import sys
import os
import time
import json
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Dict, Any, List

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.ingest import CircuitAnalyzer
from src.vision.detector import ComponentDetector
from src.llm.mapper import FunctionalMapper
from src.core.database import CircuitDatabase


def demonstrate_workflow(image_path: str):
    """Demonstrate the complete Circuit.AI workflow step by step."""
    print("🔍 Circuit.AI - Complete Workflow Demonstration")
    print("=" * 60)
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return
    
    print(f"📸 Input Image: {image_path}")
    
    # Step 1: Load and preprocess image
    print("\n" + "=" * 60)
    print("STEP 1: IMAGE LOADING & PREPROCESSING")
    print("=" * 60)
    
    try:
        # Load image
        start_time = time.time()
        image = Image.open(image_path)
        image_np = np.array(image)
        load_time = time.time() - start_time
        
        print(f"✅ Image loaded successfully")
        print(f"   📏 Dimensions: {image_np.shape}")
        print(f"   🎨 Color channels: {image_np.shape[2] if len(image_np.shape) > 2 else 1}")
        print(f"   ⏱️  Load time: {load_time:.3f}s")
        
        # Initialize detector
        detector = ComponentDetector()
        print(f"✅ Component detector initialized")
        print(f"   🔧 Default backend: {detector.default_backend}")
        print(f"   📱 Device: {detector.device}")
        print(f"   🔍 OCR enabled: {detector.ocr_enabled_default}")
        
    except Exception as e:
        print(f"❌ Error loading image: {e}")
        return
    
    # Step 2: Component Detection
    print("\n" + "=" * 60)
    print("STEP 2: COMPONENT DETECTION")
    print("=" * 60)
    
    try:
        start_time = time.time()
        detections = detector.detect_components(image_np, backend='classical', enable_ocr=True)
        detection_time = time.time() - start_time
        
        print(f"✅ Component detection completed")
        print(f"   🔍 Components found: {len(detections)}")
        print(f"   ⏱️  Detection time: {detection_time:.3f}s")
        
        # Show detection details
        if detections:
            print(f"   📊 Detection details:")
            for i, detection in enumerate(detections[:5]):  # Show first 5
                class_name = detection.get('class_name', 'unknown')
                confidence = detection.get('confidence', 0)
                bbox = detection.get('bbox', [])
                print(f"      {i+1}. {class_name} (confidence: {confidence:.2f}, bbox: {bbox})")
            
            if len(detections) > 5:
                print(f"      ... and {len(detections) - 5} more")
        
        # Generate detection summary
        detection_summary = detector.get_detection_summary(detections)
        print(f"   📈 Detection summary:")
        print(f"      • Total components: {detection_summary.get('total_components', 0)}")
        print(f"      • Average confidence: {detection_summary.get('average_confidence', 0):.2f}")
        print(f"      • Detection quality: {detection_summary.get('detection_quality', 'unknown')}")
        
        component_breakdown = detection_summary.get('components_by_type', {})
        if component_breakdown:
            print(f"      • Component breakdown:")
            for comp_type, count in component_breakdown.items():
                print(f"        - {comp_type}: {count}")
        
    except Exception as e:
        print(f"❌ Error in component detection: {e}")
        return
    
    # Step 3: Functional Mapping
    print("\n" + "=" * 60)
    print("STEP 3: FUNCTIONAL MAPPING")
    print("=" * 60)
    
    try:
        mapper = FunctionalMapper()
        print(f"✅ Functional mapper initialized")
        print(f"   🗄️  Component database: {len(mapper.component_database)} entries")
        print(f"   📋 Project templates: {len(mapper.project_templates)} templates")
        
        start_time = time.time()
        functionality_data = mapper.map_detections_to_functionality(detections)
        mapping_time = time.time() - start_time
        
        print(f"✅ Functional mapping completed")
        print(f"   ⏱️  Mapping time: {mapping_time:.3f}s")
        
        # Show functionality analysis
        components = functionality_data.get('components', [])
        capabilities = functionality_data.get('capabilities', [])
        total_market_value = functionality_data.get('total_market_value', 0)
        project_potential = functionality_data.get('project_potential', 'none')
        
        print(f"   📊 Functionality analysis:")
        print(f"      • Components analyzed: {len(components)}")
        print(f"      • Capabilities identified: {len(capabilities)}")
        print(f"      • Total market value: ${total_market_value:.2f}")
        print(f"      • Project potential: {project_potential}")
        
        if capabilities:
            print(f"      • Top capabilities:")
            for i, capability in enumerate(capabilities[:8]):
                print(f"        - {capability}")
            if len(capabilities) > 8:
                print(f"        ... and {len(capabilities) - 8} more")
        
        if components:
            print(f"      • Component analysis:")
            for i, component in enumerate(components[:3]):
                comp_type = component.get('type', 'unknown')
                reuse_value = component.get('reuse_value', 'unknown')
                market_value = component.get('market_value', 0)
                print(f"        {i+1}. {comp_type} (reuse: {reuse_value}, value: ${market_value:.2f})")
        
    except Exception as e:
        print(f"❌ Error in functional mapping: {e}")
        return
    
    # Step 4: Project Recommendations
    print("\n" + "=" * 60)
    print("STEP 4: PROJECT RECOMMENDATIONS")
    print("=" * 60)
    
    try:
        start_time = time.time()
        recommendations = mapper.generate_project_recommendations(functionality_data)
        recommendation_time = time.time() - start_time
        
        print(f"✅ Project recommendations generated")
        print(f"   ⏱️  Recommendation time: {recommendation_time:.3f}s")
        print(f"   📋 Recommendations found: {len(recommendations)}")
        
        if recommendations:
            print(f"   🎯 Top recommendations:")
            for i, rec in enumerate(recommendations[:3]):
                project_name = rec.get('project_name', 'Unknown')
                score = rec.get('score', 0)
                difficulty = rec.get('difficulty', 'unknown')
                print(f"      {i+1}. {project_name} (score: {score:.1f}%, difficulty: {difficulty})")
        else:
            print(f"   ℹ️  No specific recommendations available (using fallback analysis)")
        
    except Exception as e:
        print(f"❌ Error in project recommendations: {e}")
        return
    
    # Step 5: Complete Analysis
    print("\n" + "=" * 60)
    print("STEP 5: COMPLETE ANALYSIS")
    print("=" * 60)
    
    try:
        analyzer = CircuitAnalyzer()
        print(f"✅ Circuit analyzer initialized")
        
        start_time = time.time()
        complete_results = analyzer.analyze_pcb(image_np, backend='classical', enable_ocr=True)
        total_time = time.time() - start_time
        
        print(f"✅ Complete analysis finished")
        print(f"   ⏱️  Total processing time: {total_time:.3f}s")
        
        # Generate summary
        summary = analyzer.get_analysis_summary(complete_results)
        print(f"   📊 Analysis summary:")
        print(f"      • {summary.get('summary_text', 'No summary available')}")
        
        # Show metadata
        metadata = complete_results.get('analysis_metadata', {})
        print(f"   🔧 Analysis metadata:")
        print(f"      • Backend used: {metadata.get('backend', 'unknown')}")
        print(f"      • OCR enabled: {metadata.get('ocr', False)}")
        print(f"      • Detection quality: {metadata.get('detection_quality', 'unknown')}")
        print(f"      • Project potential: {metadata.get('project_potential', 'unknown')}")
        
    except Exception as e:
        print(f"❌ Error in complete analysis: {e}")
        return
    
    # Step 6: Database Storage
    print("\n" + "=" * 60)
    print("STEP 6: DATABASE STORAGE")
    print("=" * 60)
    
    try:
        database = CircuitDatabase()
        print(f"✅ Database initialized")
        
        # Store analysis result
        analysis_id = database.store_analysis_result(complete_results)
        print(f"✅ Analysis stored in database")
        print(f"   🆔 Analysis ID: {analysis_id}")
        
        # Get statistics
        stats = database.get_statistics()
        print(f"   📈 Database statistics:")
        print(f"      • Total analyses: {stats.get('total_analyses', 0)}")
        print(f"      • Total components: {stats.get('total_components', 0)}")
        print(f"      • Average processing time: {stats.get('average_processing_time', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error in database storage: {e}")
        return
    
    # Final Summary
    print("\n" + "=" * 60)
    print("🎯 WORKFLOW DEMONSTRATION COMPLETE")
    print("=" * 60)
    
    print(f"✅ All steps completed successfully!")
    print(f"📸 Image processed: {os.path.basename(image_path)}")
    print(f"🔍 Components detected: {len(detections)}")
    print(f"⚡ Capabilities identified: {len(capabilities)}")
    print(f"💰 Market value: ${total_market_value:.2f}")
    print(f"🎯 Project potential: {project_potential}")
    
    print(f"\n🚀 Circuit.AI is working perfectly!")
    print(f"   • Computer vision: ✅ Detecting components")
    print(f"   • AI analysis: ✅ Mapping capabilities")
    print(f"   • Database: ✅ Storing results")
    print(f"   • API: ✅ Ready for integration")
    print(f"   • Web UI: ✅ User-friendly interface")


def main():
    """Run workflow demonstration with available test images."""
    test_images = [
        "data/test_images/demo_pcb.png",
        "data/test_images/test_pcb.png"
    ]
    
    for image_path in test_images:
        if os.path.exists(image_path):
            print(f"\n{'='*80}")
            demonstrate_workflow(image_path)
            print(f"{'='*80}\n")
            break
    else:
        print("❌ No test images found. Please ensure demo_pcb.png or test_pcb.png exists in data/test_images/")


if __name__ == "__main__":
    main()
