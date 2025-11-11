#!/usr/bin/env python3
"""
Queue FPIC Dataset Training

This script prepares the FPIC dataset for training and queues it as the next model version.
"""

import os
import argparse
import subprocess
import time
from pathlib import Path

def check_fpic_dataset_available() -> bool:
    """
    Check if FPIC dataset is available.
    
    Returns:
        True if dataset is available, False otherwise
    """
    possible_paths = [
        "datasets/fpic_raw",
        "datasets/FPIC",
        "datasets/fpic_dataset"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            # Check for typical FPIC structure
            if os.path.exists(os.path.join(path, "annotations")) and os.path.exists(os.path.join(path, "images")):
                print(f"✅ Found FPIC dataset at: {path}")
                return True
    
    return False

def convert_fpic_to_yolo(fpic_dir: str, output_dir: str) -> bool:
    """
    Convert FPIC dataset to YOLO format.
    
    Args:
        fpic_dir: Directory containing FPIC dataset
        output_dir: Output directory for YOLO format
        
    Returns:
        True if conversion successful, False otherwise
    """
    print(f"🔄 Converting FPIC dataset from {fpic_dir} to {output_dir}")
    
    # Run the conversion script
    cmd = [
        "python", "scripts/convert_fpic_to_yolo.py",
        "--ann-dir", os.path.join(fpic_dir, "annotations"),
        "--img-dir", os.path.join(fpic_dir, "images"),
        "--out-dir", output_dir,
        "--train-ratio", "0.8",
        "--val-ratio", "0.1"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("✅ FPIC conversion completed successfully")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ FPIC conversion failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def train_fpic_model(data_yaml: str, project: str = "pcb_runs", name: str = "fpic_v1") -> bool:
    """
    Train FPIC model.
    
    Args:
        data_yaml: Path to data.yaml file
        project: Project directory
        name: Run name
        
    Returns:
        True if training successful, False otherwise
    """
    print(f"🏋️ Starting FPIC model training...")
    
    cmd = [
        "yolo", "detect", "train",
        f"data={data_yaml}",
        "model=yolov8m.pt",
        "imgsz=768",
        "epochs=100",
        "batch=8",
        f"project={project}",
        f"name={name}"
    ]
    
    try:
        # Run training in background
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"✅ FPIC training started (PID: {process.pid})")
        print("Training will run in background. Check progress with:")
        print(f"  tail -f {project}/{name}/train.log")
        return True
    except Exception as e:
        print(f"❌ Failed to start FPIC training: {e}")
        return False

def create_fpic_training_script() -> str:
    """
    Create a script to run FPIC training.
    
    Returns:
        Path to the created script
    """
    script_content = """#!/bin/bash

# FPIC Model Training Script
# This script trains the FPIC model as v2 candidate

set -e

echo "🚀 Starting FPIC Model Training"
echo "================================"

# Check if FPIC dataset exists
if [ ! -f "datasets/fpic_yolo/data.yaml" ]; then
    echo "❌ FPIC dataset not found. Please run conversion first:"
    echo "   python scripts/queue_fpic_training.py --convert"
    exit 1
fi

# Start training
echo "🏋️ Training FPIC model..."
yolo detect train \\
    data=datasets/fpic_yolo/data.yaml \\
    model=yolov8m.pt \\
    imgsz=768 \\
    epochs=100 \\
    batch=8 \\
    project=pcb_runs \\
    name=fpic_v1

# Export model
echo "📦 Exporting model..."
yolo export model=pcb_runs/fpic_v1/weights/best.pt format=onnx

# Move to models directory
mkdir -p models/pcb
mv pcb_runs/fpic_v1/weights/best.onnx models/pcb/fpic_v1.onnx

echo "✅ FPIC training completed!"
echo "Model saved to: models/pcb/fpic_v1.onnx"
"""
    
    script_path = "scripts/train_fpic.sh"
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    os.chmod(script_path, 0o755)
    return script_path

def main():
    parser = argparse.ArgumentParser(description='Queue FPIC dataset training')
    parser.add_argument('--check', action='store_true', help='Check if FPIC dataset is available')
    parser.add_argument('--convert', action='store_true', help='Convert FPIC dataset to YOLO format')
    parser.add_argument('--train', action='store_true', help='Start FPIC model training')
    parser.add_argument('--fpic-dir', default='datasets/fpic_raw', help='FPIC dataset directory')
    parser.add_argument('--output-dir', default='datasets/fpic_yolo', help='Output directory for YOLO format')
    parser.add_argument('--create-script', action='store_true', help='Create training script')
    
    args = parser.parse_args()
    
    print("🔄 FPIC Dataset Training Queue")
    print("=" * 35)
    
    if args.check:
        if check_fpic_dataset_available():
            print("✅ FPIC dataset is available and ready for conversion")
        else:
            print("❌ FPIC dataset not found")
            print("Please download FPIC dataset and place it in one of these locations:")
            print("  - datasets/fpic_raw/")
            print("  - datasets/FPIC/")
            print("  - datasets/fpic_dataset/")
            print()
            print("Expected structure:")
            print("  fpic_dir/")
            print("  ├── annotations/")
            print("  │   ├── *.json")
            print("  └── images/")
            print("      ├── *.jpg")
    
    elif args.convert:
        if not check_fpic_dataset_available():
            print("❌ FPIC dataset not found. Please download it first.")
            return
        
        # Find the FPIC directory
        fpic_dir = None
        for path in ["datasets/fpic_raw", "datasets/FPIC", "datasets/fpic_dataset"]:
            if os.path.exists(path):
                fpic_dir = path
                break
        
        if convert_fpic_to_yolo(fpic_dir, args.output_dir):
            print("✅ FPIC dataset converted successfully!")
            print(f"YOLO format dataset: {args.output_dir}")
            print("Ready for training!")
        else:
            print("❌ FPIC conversion failed")
    
    elif args.train:
        data_yaml = os.path.join(args.output_dir, "data.yaml")
        if not os.path.exists(data_yaml):
            print(f"❌ YOLO dataset not found: {data_yaml}")
            print("Please run conversion first: --convert")
            return
        
        if train_fpic_model(data_yaml):
            print("✅ FPIC training queued successfully!")
        else:
            print("❌ Failed to queue FPIC training")
    
    elif args.create_script:
        script_path = create_fpic_training_script()
        print(f"✅ Created training script: {script_path}")
        print("Run with: ./scripts/train_fpic.sh")
    
    else:
        print("No action specified. Use --help for options.")
        print()
        print("Quick start:")
        print("1. Check dataset: --check")
        print("2. Convert dataset: --convert")
        print("3. Train model: --train")
        print("4. Or create script: --create-script")

if __name__ == "__main__":
    main()

