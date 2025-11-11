#!/usr/bin/env python3
"""
Production Training Script v2 - Circuit.AI

Handles both synthetic and real ElectroCom61 datasets with proper validation.
"""

import argparse
import os
import yaml
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List

def validate_dataset(dataset_path: str) -> Dict[str, Any]:
    """
    Validate dataset structure and return metadata.
    
    Args:
        dataset_path: Path to dataset directory
        
    Returns:
        Dictionary with dataset metadata
    """
    print(f"🔍 Validating dataset: {dataset_path}")
    
    dataset_dir = Path(dataset_path)
    data_yaml = dataset_dir / "data.yaml"
    
    if not data_yaml.exists():
        print(f"❌ data.yaml not found: {data_yaml}")
        return {"valid": False, "error": "Missing data.yaml"}
    
    # Parse data.yaml
    try:
        with open(data_yaml, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Failed to parse data.yaml: {e}")
        return {"valid": False, "error": f"Invalid data.yaml: {e}"}
    
    # Extract metadata
    num_classes = config.get('nc', 0)
    class_names = config.get('names', [])
    dataset_root = config.get('path', '')
    
    print(f"📊 Dataset metadata:")
    print(f"   Classes: {num_classes}")
    print(f"   Class names: {class_names[:5]}..." if len(class_names) > 5 else f"   Class names: {class_names}")
    
    # Count images and labels
    total_images = 0
    total_labels = 0
    splits_info = {}
    
    splits = ['train', 'val', 'test']
    for split in splits:
        img_dir = dataset_dir / "images" / split
        label_dir = dataset_dir / "labels" / split
        
        img_count = 0
        label_count = 0
        
        if img_dir.exists():
            img_count = len(list(img_dir.glob("*.jpg"))) + len(list(img_dir.glob("*.png")))
            total_images += img_count
        
        if label_dir.exists():
            label_count = len(list(label_dir.glob("*.txt")))
            total_labels += label_count
        
        splits_info[split] = {"images": img_count, "labels": label_count}
        print(f"   {split}: {img_count} images, {label_count} labels")
    
    # Validate class IDs in labels
    max_class_id = -1
    for split in splits:
        label_dir = dataset_dir / "labels" / split
        if label_dir.exists():
            for label_file in label_dir.glob("*.txt"):
                try:
                    with open(label_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                class_id = int(float(line.split()[0]))
                                max_class_id = max(max_class_id, class_id)
                except Exception:
                    continue
    
    print(f"   Max class ID found: {max_class_id}")
    print(f"   Total images: {total_images}")
    print(f"   Total labels: {total_labels}")
    
    # Validation checks
    issues = []
    
    if total_images == 0:
        issues.append("No images found")
    
    if total_labels == 0:
        issues.append("No label files found")
    
    if num_classes == 0:
        issues.append("No classes defined")
    
    if max_class_id >= num_classes:
        issues.append(f"Class IDs exceed defined classes (max: {max_class_id}, defined: {num_classes})")
    
    if num_classes == 10 and total_images < 500:
        issues.append("Small synthetic dataset detected - consider using real ElectroCom61")
    
    # Determine dataset type
    dataset_type = "unknown"
    if num_classes == 61:
        dataset_type = "real_electrocom61"
    elif num_classes == 10:
        dataset_type = "synthetic"
    else:
        dataset_type = "custom"
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "metadata": {
            "num_classes": num_classes,
            "class_names": class_names,
            "total_images": total_images,
            "total_labels": total_labels,
            "splits": splits_info,
            "max_class_id": max_class_id,
            "dataset_type": dataset_type
        }
    }

def get_training_config(dataset_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get training configuration based on dataset metadata.
    
    Args:
        dataset_metadata: Dataset metadata from validation
        
    Returns:
        Training configuration dictionary
    """
    num_classes = dataset_metadata["num_classes"]
    total_images = dataset_metadata["total_images"]
    dataset_type = dataset_metadata["dataset_type"]
    
    # Base configuration
    config = {
        "model": "yolov8m.pt",
        "imgsz": 640,
        "epochs": 150,
        "batch": 16,
        "lr0": 0.01,
        "lrf": 0.1,
        "weight_decay": 0.0005,
        "mosaic": 0.5,
        "hsv_h": 0.015,
        "hsv_s": 0.7,
        "hsv_v": 0.4
    }
    
    # Adjust based on dataset characteristics
    if dataset_type == "real_electrocom61":
        print("🎯 Real ElectroCom61 detected - using optimized settings")
        config.update({
            "epochs": 200,  # More epochs for real data
            "batch": 16,    # Standard batch size
            "imgsz": 640,   # Standard image size
            "mosaic": 1.0,  # Full mosaic for real data
        })
    elif dataset_type == "synthetic":
        print("⚠️ Synthetic dataset detected - using conservative settings")
        config.update({
            "epochs": 100,  # Fewer epochs for synthetic data
            "batch": 8,     # Smaller batch size
            "imgsz": 640,   # Standard image size
            "mosaic": 0.3,  # Reduced mosaic for synthetic data
        })
    
    # Adjust based on dataset size
    if total_images < 500:
        print("⚠️ Small dataset detected - using conservative settings")
        config.update({
            "epochs": min(config["epochs"], 100),
            "batch": min(config["batch"], 8),
            "mosaic": min(config["mosaic"], 0.3),
        })
    elif total_images > 2000:
        print("✅ Large dataset detected - using aggressive settings")
        config.update({
            "epochs": max(config["epochs"], 200),
            "batch": max(config["batch"], 16),
            "mosaic": max(config["mosaic"], 0.8),
        })
    
    return config

def train_model(dataset_path: str, model_name: str, config: Dict[str, Any]) -> bool:
    """
    Train YOLO model with given configuration.
    
    Args:
        dataset_path: Path to dataset
        model_name: Name for the model
        config: Training configuration
        
    Returns:
        True if training successful, False otherwise
    """
    print(f"🏋️ Starting training: {model_name}")
    print(f"📊 Configuration:")
    for key, value in config.items():
        print(f"   {key}: {value}")
    
    # Build YOLO command
    cmd = [
        "yolo", "detect", "train",
        f"data={dataset_path}/data.yaml",
        f"model={config['model']}",
        f"imgsz={config['imgsz']}",
        f"epochs={config['epochs']}",
        f"batch={config['batch']}",
        f"lr0={config['lr0']}",
        f"lrf={config['lrf']}",
        f"weight_decay={config['weight_decay']}",
        f"mosaic={config['mosaic']}",
        f"hsv_h={config['hsv_h']}",
        f"hsv_s={config['hsv_s']}",
        f"hsv_v={config['hsv_v']}",
        "project=pcb_runs",
        f"name={model_name}",
        "exist_ok=True"
    ]
    
    print(f"\n🚀 Running command:")
    print(f"   {' '.join(cmd)}")
    
    try:
        # Start training
        result = subprocess.run(cmd, check=True)
        print(f"✅ Training completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Training failed: {e}")
        return False
    except KeyboardInterrupt:
        print(f"\n⏹️ Training interrupted by user")
        return False

def export_model(model_name: str, format: str = "torchscript") -> bool:
    """
    Export trained model to specified format.
    
    Args:
        model_name: Name of the trained model
        format: Export format (torchscript, onnx)
        
    Returns:
        True if export successful, False otherwise
    """
    print(f"📦 Exporting model: {model_name} to {format}")
    
    model_path = f"pcb_runs/{model_name}/weights/best.pt"
    if not os.path.exists(model_path):
        print(f"❌ Model not found: {model_path}")
        return False
    
    # Create output directory
    output_dir = Path("models/pcb")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build export command
    cmd = [
        "yolo", "export",
        f"model={model_path}",
        f"format={format}",
        "imgsz=640"
    ]
    
    if format == "onnx":
        cmd.extend(["opset=13", "simplify=True"])
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # Move exported model to output directory
        exported_file = f"pcb_runs/{model_name}/weights/best.{format}"
        if os.path.exists(exported_file):
            import shutil
            shutil.move(exported_file, output_dir / f"{model_name}.{format}")
            print(f"✅ Model exported to: {output_dir / f'{model_name}.{format}'}")
            return True
        else:
            print(f"❌ Exported file not found: {exported_file}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Export failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Circuit.AI Production Training v2")
    parser.add_argument("--dataset", default="datasets/electrocom61", help="Dataset path")
    parser.add_argument("--model-name", default="electrocom61_v2", help="Model name")
    parser.add_argument("--export-format", default="torchscript", choices=["torchscript", "onnx"], help="Export format")
    parser.add_argument("--skip-training", action="store_true", help="Skip training, only validate dataset")
    
    args = parser.parse_args()
    
    print("🚀 Circuit.AI Production Training v2")
    print("=" * 50)
    
    # Validate dataset
    validation_result = validate_dataset(args.dataset)
    
    if not validation_result["valid"]:
        print(f"\n❌ Dataset validation failed:")
        for issue in validation_result["issues"]:
            print(f"   - {issue}")
        
        if validation_result["issues"] and "synthetic" in str(validation_result["issues"]):
            print(f"\n💡 Recommendation:")
            print(f"   Download the real ElectroCom61 dataset (61 classes, 2071 images)")
            print(f"   URL: https://data.mendeley.com/datasets/6scy6h8sjz/2")
            print(f"   Extract to: datasets/electrocom61_real")
        
        return 1
    
    print(f"\n✅ Dataset validation passed!")
    
    # Get training configuration
    config = get_training_config(validation_result["metadata"])
    
    if args.skip_training:
        print(f"\n⏭️ Skipping training as requested")
        return 0
    
    # Train model
    success = train_model(args.dataset, args.model_name, config)
    
    if not success:
        return 1
    
    # Export model
    export_success = export_model(args.model_name, args.export_format)
    
    if export_success:
        print(f"\n🎉 Training pipeline completed successfully!")
        print(f"   Model: {args.model_name}")
        print(f"   Format: {args.export_format}")
        return 0
    else:
        print(f"\n⚠️ Training completed but export failed")
        return 1

if __name__ == "__main__":
    exit(main())
