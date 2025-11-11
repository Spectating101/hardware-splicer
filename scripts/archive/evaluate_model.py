#!/usr/bin/env python3
"""
Model Evaluation Script for Circuit.AI

This script evaluates trained models and generates performance reports.
"""

import os
import json
import time
import argparse
import numpy as np
from pathlib import Path
from typing import Dict, List, Any
import cv2
from PIL import Image

try:
    from ultralytics import YOLO
    from ultralytics.utils.metrics import ConfusionMatrix
    from ultralytics.utils.plotting import Annotator
except ImportError:
    print("Error: ultralytics not installed. Run: pip install ultralytics")
    exit(1)

def load_model(model_path: str) -> YOLO:
    """
    Load a YOLO model.
    
    Args:
        model_path: Path to model file
        
    Returns:
        Loaded YOLO model
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")
    
    print(f"Loading model: {model_path}")
    model = YOLO(model_path)
    print(f"✅ Model loaded successfully")
    
    return model

def evaluate_on_dataset(model: YOLO, data_yaml: str, split: str = "val") -> Dict[str, Any]:
    """
    Evaluate model on a dataset split.
    
    Args:
        model: YOLO model
        data_yaml: Path to data.yaml file
        split: Dataset split to evaluate on (val, test)
        
    Returns:
        Evaluation metrics
    """
    print(f"Evaluating on {split} split...")
    
    # Run validation
    results = model.val(data=data_yaml, split=split, verbose=True)
    
    # Extract metrics
    metrics = {
        "mAP50": float(results.box.map50) if hasattr(results.box, 'map50') else 0.0,
        "mAP50-95": float(results.box.map) if hasattr(results.box, 'map') else 0.0,
        "precision": float(results.box.mp) if hasattr(results.box, 'mp') else 0.0,
        "recall": float(results.box.mr) if hasattr(results.box, 'mr') else 0.0,
        "f1": 0.0
    }
    
    # Calculate F1 score
    if metrics["precision"] > 0 and metrics["recall"] > 0:
        metrics["f1"] = 2 * (metrics["precision"] * metrics["recall"]) / (metrics["precision"] + metrics["recall"])
    
    return metrics

def benchmark_inference_speed(model: YOLO, test_images: List[str], num_runs: int = 20) -> Dict[str, float]:
    """
    Benchmark model inference speed.
    
    Args:
        model: YOLO model
        test_images: List of test image paths
        num_runs: Number of runs for benchmarking
        
    Returns:
        Speed metrics
    """
    print(f"Benchmarking inference speed on {len(test_images)} images...")
    
    # Warm up
    for img_path in test_images[:3]:
        try:
            model(img_path, verbose=False)
        except:
            continue
    
    # Benchmark
    times = []
    successful_runs = 0
    
    for run in range(num_runs):
        for img_path in test_images:
            try:
                start_time = time.time()
                model(img_path, verbose=False)
                inference_time = time.time() - start_time
                times.append(inference_time)
                successful_runs += 1
            except Exception as e:
                print(f"Warning: Failed to process {img_path}: {e}")
                continue
    
    if not times:
        return {"error": "No successful inference runs"}
    
    times = np.array(times)
    
    return {
        "mean_time": float(np.mean(times)),
        "median_time": float(np.median(times)),
        "std_time": float(np.std(times)),
        "min_time": float(np.min(times)),
        "max_time": float(np.max(times)),
        "p95_time": float(np.percentile(times, 95)),
        "p99_time": float(np.percentile(times, 99)),
        "successful_runs": successful_runs,
        "total_runs": num_runs * len(test_images)
    }

def test_on_real_images(model: YOLO, test_dir: str) -> Dict[str, Any]:
    """
    Test model on real PCB images.
    
    Args:
        model: YOLO model
        test_dir: Directory containing test images
        
    Returns:
        Test results
    """
    if not os.path.exists(test_dir):
        print(f"Warning: Test directory not found: {test_dir}")
        return {"error": "Test directory not found"}
    
    # Find test images
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
    test_images = []
    
    for ext in image_extensions:
        test_images.extend(Path(test_dir).glob(f"*{ext}"))
        test_images.extend(Path(test_dir).glob(f"*{ext.upper()}"))
    
    if not test_images:
        print(f"Warning: No test images found in {test_dir}")
        return {"error": "No test images found"}
    
    print(f"Testing on {len(test_images)} real images...")
    
    results = {
        "total_images": len(test_images),
        "successful_detections": 0,
        "total_detections": 0,
        "images_with_ic": 0,
        "images_with_resistor": 0,
        "images_with_capacitor": 0,
        "class_counts": {},
        "confidence_stats": []
    }
    
    for img_path in test_images:
        try:
            # Run inference
            result = model(str(img_path), verbose=False)[0]
            
            if result.boxes is not None and len(result.boxes) > 0:
                results["successful_detections"] += 1
                results["total_detections"] += len(result.boxes)
                
                # Count detections by class
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    class_name = result.names[class_id]
                    confidence = float(box.conf[0])
                    
                    if class_name not in results["class_counts"]:
                        results["class_counts"][class_name] = 0
                    results["class_counts"][class_name] += 1
                    
                    results["confidence_stats"].append(confidence)
                    
                    # Track specific components
                    if class_name == "ic":
                        results["images_with_ic"] += 1
                    elif class_name == "resistor":
                        results["images_with_resistor"] += 1
                    elif class_name == "capacitor":
                        results["images_with_capacitor"] += 1
                        
        except Exception as e:
            print(f"Warning: Failed to process {img_path}: {e}")
            continue
    
    # Calculate statistics
    if results["confidence_stats"]:
        results["avg_confidence"] = float(np.mean(results["confidence_stats"]))
        results["min_confidence"] = float(np.min(results["confidence_stats"]))
        results["max_confidence"] = float(np.max(results["confidence_stats"]))
    else:
        results["avg_confidence"] = 0.0
        results["min_confidence"] = 0.0
        results["max_confidence"] = 0.0
    
    return results

def generate_report(model_path: str, data_yaml: str, test_dir: str = None, output_file: str = None) -> Dict[str, Any]:
    """
    Generate a comprehensive evaluation report.
    
    Args:
        model_path: Path to model file
        data_yaml: Path to data.yaml file
        test_dir: Directory with test images
        output_file: Output file for report
        
    Returns:
        Evaluation report
    """
    print("🔍 Circuit.AI Model Evaluation")
    print("=" * 40)
    
    # Load model
    model = load_model(model_path)
    
    # Get model info
    model_info = {
        "model_path": model_path,
        "model_size": os.path.getsize(model_path) / (1024 * 1024),  # MB
        "num_classes": len(model.names),
        "class_names": list(model.names.values())
    }
    
    # Evaluate on validation set
    try:
        val_metrics = evaluate_on_dataset(model, data_yaml, "val")
        print(f"✅ Validation metrics: mAP50={val_metrics['mAP50']:.3f}")
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        val_metrics = {"error": str(e)}
    
    # Benchmark speed
    try:
        # Get some test images for speed benchmark
        test_images = []
        if os.path.exists(os.path.join(os.path.dirname(data_yaml), "images", "val")):
            val_dir = os.path.join(os.path.dirname(data_yaml), "images", "val")
            for img_file in os.listdir(val_dir)[:5]:  # Use first 5 images
                if img_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    test_images.append(os.path.join(val_dir, img_file))
        
        if test_images:
            speed_metrics = benchmark_inference_speed(model, test_images)
            print(f"✅ Speed benchmark: {speed_metrics.get('mean_time', 0):.3f}s avg")
        else:
            speed_metrics = {"error": "No test images for speed benchmark"}
    except Exception as e:
        print(f"❌ Speed benchmark failed: {e}")
        speed_metrics = {"error": str(e)}
    
    # Test on real images
    real_test_results = {}
    if test_dir:
        try:
            real_test_results = test_on_real_images(model, test_dir)
            print(f"✅ Real image test: {real_test_results.get('successful_detections', 0)}/{real_test_results.get('total_images', 0)} images with detections")
        except Exception as e:
            print(f"❌ Real image test failed: {e}")
            real_test_results = {"error": str(e)}
    
    # Compile report
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model_info": model_info,
        "validation_metrics": val_metrics,
        "speed_metrics": speed_metrics,
        "real_image_test": real_test_results,
        "recommendations": []
    }
    
    # Generate recommendations
    if "mAP50" in val_metrics and val_metrics["mAP50"] < 0.7:
        report["recommendations"].append("mAP50 below 0.7 - consider more training or data augmentation")
    
    if "mean_time" in speed_metrics and speed_metrics["mean_time"] > 0.5:
        report["recommendations"].append("Inference time > 0.5s - consider model optimization or quantization")
    
    if "successful_detections" in real_test_results and real_test_results["successful_detections"] < real_test_results["total_images"] * 0.8:
        report["recommendations"].append("Low detection rate on real images - model may need more diverse training data")
    
    # Save report
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"📊 Report saved to: {output_file}")
    
    return report

def main():
    parser = argparse.ArgumentParser(description='Evaluate Circuit.AI models')
    parser.add_argument('--model', required=True, help='Path to model file')
    parser.add_argument('--data-yaml', required=True, help='Path to data.yaml file')
    parser.add_argument('--test-dir', help='Directory with test images')
    parser.add_argument('--output', help='Output file for report')
    parser.add_argument('--format', choices=['json', 'txt'], default='json', help='Output format')
    
    args = parser.parse_args()
    
    # Generate report
    report = generate_report(args.model, args.data_yaml, args.test_dir, args.output)
    
    # Print summary
    print("\n📋 Evaluation Summary")
    print("=" * 30)
    print(f"Model: {report['model_info']['model_path']}")
    print(f"Size: {report['model_info']['model_size']:.1f} MB")
    print(f"Classes: {report['model_info']['num_classes']}")
    
    if "mAP50" in report["validation_metrics"]:
        print(f"mAP50: {report['validation_metrics']['mAP50']:.3f}")
    
    if "mean_time" in report["speed_metrics"]:
        print(f"Avg inference: {report['speed_metrics']['mean_time']:.3f}s")
    
    if report["recommendations"]:
        print("\n💡 Recommendations:")
        for rec in report["recommendations"]:
            print(f"  - {rec}")

if __name__ == "__main__":
    main()

