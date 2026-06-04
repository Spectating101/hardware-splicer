#!/usr/bin/env python3
"""
Production Model Evaluation Script

Evaluates trained models and outputs JSON metrics for dashboard integration.
"""

import os
import json
import argparse
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List

def evaluate_model(model_path: str, data_yaml: str) -> Dict[str, Any]:
    """
    Evaluate a trained model and return metrics.
    
    Args:
        model_path: Path to trained model
        data_yaml: Path to data.yaml file
        
    Returns:
        Dictionary with evaluation metrics
    """
    print(f"🔍 Evaluating model: {model_path}")
    
    # Run YOLO validation
    cmd = [
        "yolo", "detect", "val",
        f"model={model_path}",
        f"data={data_yaml}",
        "imgsz=640",
        "batch=8",
        "save_json=True"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("✅ Evaluation completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Evaluation failed: {e}")
        return {"error": str(e)}
    
    # Parse results from stdout
    metrics = parse_yolo_output(result.stdout)
    
    # Try to load JSON results if available
    json_results = load_json_results(model_path)
    if json_results:
        metrics.update(json_results)
    
    return metrics

def parse_yolo_output(output: str) -> Dict[str, Any]:
    """
    Parse YOLO validation output to extract metrics.
    
    Args:
        output: YOLO command output
        
    Returns:
        Dictionary with parsed metrics
    """
    metrics = {
        "mAP50": 0.0,
        "mAP50-95": 0.0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "per_class": {}
    }
    
    lines = output.split('\n')
    for line in lines:
        line = line.strip()
        
        # Look for metrics line
        if 'all' in line and 'Box(P' in line:
            parts = line.split()
            if len(parts) >= 6:
                try:
                    metrics["precision"] = float(parts[3])
                    metrics["recall"] = float(parts[4])
                    metrics["mAP50"] = float(parts[5])
                    if len(parts) > 6:
                        metrics["mAP50-95"] = float(parts[6])
                except (ValueError, IndexError):
                    pass
        
        # Look for per-class metrics
        elif len(line.split()) >= 6 and not line.startswith('all'):
            parts = line.split()
            try:
                class_name = parts[0]
                precision = float(parts[3])
                recall = float(parts[4])
                map50 = float(parts[5])
                map50_95 = float(parts[6]) if len(parts) > 6 else 0.0
                
                metrics["per_class"][class_name] = {
                    "precision": precision,
                    "recall": recall,
                    "mAP50": map50,
                    "mAP50-95": map50_95
                }
            except (ValueError, IndexError):
                pass
    
    # Calculate F1 score
    if metrics["precision"] > 0 and metrics["recall"] > 0:
        metrics["f1"] = 2 * (metrics["precision"] * metrics["recall"]) / (metrics["precision"] + metrics["recall"])
    
    return metrics

def load_json_results(model_path: str) -> Dict[str, Any]:
    """
    Load JSON results from YOLO validation if available.
    
    Args:
        model_path: Path to model
        
    Returns:
        Dictionary with JSON results or None
    """
    # Look for results.json in the runs directory
    runs_dir = Path("runs/detect")
    if not runs_dir.exists():
        return None
    
    # Find the most recent results.json
    json_files = list(runs_dir.glob("**/results.json"))
    if not json_files:
        return None
    
    latest_json = max(json_files, key=os.path.getmtime)
    
    try:
        with open(latest_json, 'r') as f:
            results = json.load(f)
        return {"json_results": results}
    except Exception as e:
        print(f"Warning: Could not load JSON results: {e}")
        return None

def create_model_card(model_name: str, metrics: Dict[str, Any], dataset_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a comprehensive model card.
    
    Args:
        model_name: Name of the model
        metrics: Evaluation metrics
        dataset_info: Dataset information
        
    Returns:
        Model card dictionary
    """
    model_card = {
        "model_name": model_name,
        "version": "2.0",
        "evaluation_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": dataset_info,
        "performance": {
            "mAP50": metrics.get("mAP50", 0.0),
            "mAP50-95": metrics.get("mAP50-95", 0.0),
            "precision": metrics.get("precision", 0.0),
            "recall": metrics.get("recall", 0.0),
            "f1": metrics.get("f1", 0.0),
            "production_ready": metrics.get("mAP50", 0.0) >= 0.6
        },
        "per_class_metrics": metrics.get("per_class", {}),
        "recommendations": []
    }
    
    # Add recommendations based on performance
    mAP50 = metrics.get("mAP50", 0.0)
    if mAP50 < 0.3:
        model_card["recommendations"].append("Very low mAP50 - consider more training data or different architecture")
    elif mAP50 < 0.5:
        model_card["recommendations"].append("Low mAP50 - consider longer training or data augmentation")
    elif mAP50 < 0.6:
        model_card["recommendations"].append("Moderate mAP50 - acceptable for development, consider fine-tuning for production")
    else:
        model_card["recommendations"].append("Good mAP50 - ready for production deployment")
    
    precision = metrics.get("precision", 0.0)
    recall = metrics.get("recall", 0.0)
    
    if precision < 0.3:
        model_card["recommendations"].append("Low precision - many false positives, consider higher confidence thresholds")
    if recall < 0.3:
        model_card["recommendations"].append("Low recall - many false negatives, consider lower confidence thresholds")
    
    return model_card

def main():
    parser = argparse.ArgumentParser(description='Evaluate Circuit.AI models')
    parser.add_argument('--model', required=True, help='Path to model file')
    parser.add_argument('--data-yaml', required=True, help='Path to data.yaml file')
    parser.add_argument('--output', help='Output file for results (JSON)')
    parser.add_argument('--model-name', help='Model name for model card')
    
    args = parser.parse_args()
    
    print("🔍 Circuit.AI Model Evaluation")
    print("=" * 40)
    
    # Check if model exists
    if not os.path.exists(args.model):
        print(f"❌ Model not found: {args.model}")
        exit(1)
    
    # Check if data.yaml exists
    if not os.path.exists(args.data_yaml):
        print(f"❌ Data YAML not found: {args.data_yaml}")
        exit(1)
    
    # Evaluate model
    metrics = evaluate_model(args.model, args.data_yaml)
    
    if "error" in metrics:
        print(f"❌ Evaluation failed: {metrics['error']}")
        exit(1)
    
    # Create model card
    model_name = args.model_name or Path(args.model).stem
    dataset_info = {
        "path": args.data_yaml,
        "classes": 10,  # Will be updated from data.yaml
        "description": "ElectroCom61 synthetic dataset"
    }
    
    model_card = create_model_card(model_name, metrics, dataset_info)
    
    # Print results
    print(f"\n📊 Evaluation Results for {model_name}")
    print("=" * 50)
    print(f"mAP50: {metrics.get('mAP50', 0.0):.3f}")
    print(f"mAP50-95: {metrics.get('mAP50-95', 0.0):.3f}")
    print(f"Precision: {metrics.get('precision', 0.0):.3f}")
    print(f"Recall: {metrics.get('recall', 0.0):.3f}")
    print(f"F1: {metrics.get('f1', 0.0):.3f}")
    
    if metrics.get('per_class'):
        print(f"\n📋 Per-Class Metrics:")
        for class_name, class_metrics in metrics['per_class'].items():
            print(f"  {class_name}: mAP50={class_metrics.get('mAP50', 0.0):.3f}, P={class_metrics.get('precision', 0.0):.3f}, R={class_metrics.get('recall', 0.0):.3f}")
    
    print(f"\n🎯 Production Ready: {'✅ Yes' if model_card['performance']['production_ready'] else '❌ No'}")
    
    if model_card['recommendations']:
        print(f"\n💡 Recommendations:")
        for rec in model_card['recommendations']:
            print(f"  - {rec}")
    
    # Save results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(model_card, f, indent=2)
        print(f"\n📄 Results saved to: {args.output}")
    
    # Save model card
    card_path = f"models/pcb/{model_name}_card.json"
    os.makedirs("models/pcb", exist_ok=True)
    with open(card_path, 'w') as f:
        json.dump(model_card, f, indent=2)
    print(f"📋 Model card saved to: {card_path}")
    
    # Exit with appropriate code
    exit(0 if model_card['performance']['production_ready'] else 1)

if __name__ == "__main__":
    main()
