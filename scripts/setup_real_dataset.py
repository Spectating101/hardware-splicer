#!/usr/bin/env python3
"""
Setup Real Dataset for Circuit.AI Training

This script helps set up a real dataset for training. It provides multiple options:
1. Download ElectroCom61 from Mendeley Data
2. Use an alternative dataset
3. Create a synthetic dataset for testing
"""

import os
import requests
import zipfile
import shutil
import json
import numpy as np
from PIL import Image, ImageDraw
from pathlib import Path
import argparse
import subprocess

def create_synthetic_dataset(output_dir: str, num_images: int = 100):
    """
    Create a synthetic dataset for testing purposes.
    
    Args:
        output_dir: Output directory for the dataset
        num_images: Number of images to generate
    """
    print(f"🎨 Creating synthetic dataset with {num_images} images...")
    
    # Create directories
    for split in ["train", "val", "test"]:
        os.makedirs(os.path.join(output_dir, "images", split), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "labels", split), exist_ok=True)
    
    # Component classes (simplified)
    classes = [
        "resistor", "capacitor", "inductor", "diode", "transistor", 
        "ic", "connector", "switch", "led", "crystal"
    ]
    
    # Generate images
    for i in range(num_images):
        # Create a random PCB-like image
        img = Image.new('RGB', (640, 640), color=(50, 50, 50))  # Dark background
        draw = ImageDraw.Draw(img)
        
        # Add some random components
        num_components = np.random.randint(3, 8)
        labels = []
        
        for j in range(num_components):
            # Random component
            class_id = np.random.randint(0, len(classes))
            class_name = classes[class_id]
            
            # Random position and size
            x = np.random.randint(50, 590)
            y = np.random.randint(50, 590)
            w = np.random.randint(20, 80)
            h = np.random.randint(20, 80)
            
            # Draw component (simple rectangle)
            color = tuple(np.random.randint(100, 255, 3))
            draw.rectangle([x, y, x + w, y + h], fill=color, outline=(255, 255, 255))
            
            # Add label
            draw.text((x, y - 20), class_name, fill=(255, 255, 255))
            
            # Convert to YOLO format
            center_x = (x + w/2) / 640
            center_y = (y + h/2) / 640
            width = w / 640
            height = h / 640
            
            labels.append(f"{class_id} {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}")
        
        # Save image
        split = "train" if i < num_images * 0.7 else "val" if i < num_images * 0.9 else "test"
        img_path = os.path.join(output_dir, "images", split, f"image_{i:04d}.jpg")
        img.save(img_path)
        
        # Save labels
        label_path = os.path.join(output_dir, "labels", split, f"image_{i:04d}.txt")
        with open(label_path, 'w') as f:
            f.write('\n'.join(labels))
    
    # Create data.yaml
    data_yaml_content = f"""# Synthetic Dataset Configuration
path: {output_dir}
train: images/train
val: images/val
test: images/test

# Classes
nc: {len(classes)}
names: {classes}

# Dataset info
description: "Synthetic PCB component dataset for testing"
version: "1.0"
license: "MIT"
"""
    
    yaml_path = os.path.join(output_dir, "data.yaml")
    with open(yaml_path, 'w') as f:
        f.write(data_yaml_content)
    
    print(f"✅ Synthetic dataset created in {output_dir}")
    print(f"   Images: {num_images}")
    print(f"   Classes: {len(classes)}")
    print(f"   Splits: train/val/test")

def download_alternative_dataset():
    """
    Download an alternative dataset that's publicly available.
    """
    print("🔍 Looking for alternative datasets...")
    
    # List of alternative datasets
    alternatives = [
        {
            "name": "PCB Component Detection Dataset",
            "url": "https://github.com/PCB-Detection/PCB-Component-Detection",
            "description": "GitHub repository with PCB component detection data"
        },
        {
            "name": "Electronic Component Detection",
            "url": "https://www.kaggle.com/datasets/electronic-component-detection",
            "description": "Kaggle dataset for electronic component detection"
        }
    ]
    
    print("Available alternatives:")
    for i, alt in enumerate(alternatives, 1):
        print(f"{i}. {alt['name']}")
        print(f"   {alt['description']}")
        print(f"   URL: {alt['url']}")
        print()
    
    return alternatives

def setup_electrocom61_manual():
    """
    Provide instructions for manual ElectroCom61 setup.
    """
    print("📋 Manual ElectroCom61 Setup Instructions")
    print("=" * 50)
    print()
    print("1. Go to: https://data.mendeley.com/datasets/6scy6h8sjz/2")
    print("2. Click 'Download' and save the zip file")
    print("3. Extract the zip file")
    print("4. Run the following command:")
    print("   python scripts/download_electrocom61.py --zip-file path/to/extracted/zip")
    print()
    print("Expected structure after extraction:")
    print("datasets/electrocom61/")
    print("├── data.yaml")
    print("├── images/")
    print("│   ├── train/")
    print("│   ├── val/")
    print("│   └── test/")
    print("└── labels/")
    print("    ├── train/")
    print("    ├── val/")
    print("    └── test/")
    print()

def check_dataset_ready(dataset_path: str) -> bool:
    """
    Check if a dataset is ready for training.
    
    Args:
        dataset_path: Path to dataset
        
    Returns:
        True if ready, False otherwise
    """
    required_files = [
        "data.yaml",
        "images/train",
        "images/val", 
        "labels/train",
        "labels/val"
    ]
    
    for file_path in required_files:
        full_path = os.path.join(dataset_path, file_path)
        if not os.path.exists(full_path):
            print(f"❌ Missing: {file_path}")
            return False
    
    # Check if directories have files
    for split in ["train", "val"]:
        img_dir = os.path.join(dataset_path, "images", split)
        label_dir = os.path.join(dataset_path, "labels", split)
        
        if not os.listdir(img_dir):
            print(f"❌ No images in images/{split}/")
            return False
        
        if not os.listdir(label_dir):
            print(f"❌ No labels in labels/{split}/")
            return False
    
    print("✅ Dataset is ready for training!")
    return True

def main():
    parser = argparse.ArgumentParser(description='Setup real dataset for Circuit.AI training')
    parser.add_argument('--mode', choices=['check', 'synthetic', 'manual', 'alternatives'], 
                       default='check', help='Setup mode')
    parser.add_argument('--dataset-path', default='datasets/electrocom61', 
                       help='Path to dataset')
    parser.add_argument('--num-images', type=int, default=100, 
                       help='Number of images for synthetic dataset')
    
    args = parser.parse_args()
    
    print("🔧 Circuit.AI Dataset Setup")
    print("=" * 30)
    
    if args.mode == 'check':
        print(f"Checking dataset at: {args.dataset_path}")
        if check_dataset_ready(args.dataset_path):
            print("\n🚀 Ready to train!")
            print("Run: yolo detect train data=datasets/electrocom61/data.yaml model=yolov8m.pt")
        else:
            print("\n❌ Dataset not ready. Choose an option:")
            print("1. Create synthetic dataset: --mode synthetic")
            print("2. Manual setup instructions: --mode manual")
            print("3. Alternative datasets: --mode alternatives")
    
    elif args.mode == 'synthetic':
        create_synthetic_dataset(args.dataset_path, args.num_images)
        print("\n🚀 Synthetic dataset ready for training!")
        print("Run: yolo detect train data=datasets/electrocom61/data.yaml model=yolov8m.pt")
    
    elif args.mode == 'manual':
        setup_electrocom61_manual()
    
    elif args.mode == 'alternatives':
        download_alternative_dataset()

if __name__ == "__main__":
    main()

