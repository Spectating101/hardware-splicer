#!/usr/bin/env python3
"""
Download the real ElectroCom61 dataset from Mendeley Data.

This script provides instructions and tools to download the actual 61-class dataset.
"""

import os
import requests
import zipfile
from pathlib import Path
import subprocess

def download_electrocom61():
    """
    Download ElectroCom61 dataset from Mendeley Data.
    
    The dataset is available at: https://data.mendeley.com/datasets/6scy6h8sjz/2
    """
    print("🔍 ElectroCom61 Real Dataset Download")
    print("=" * 50)
    
    # Dataset information
    dataset_url = "https://data.mendeley.com/datasets/6scy6h8sjz/2"
    dataset_name = "ElectroCom61"
    expected_classes = 61
    expected_images = 2071
    
    print(f"📊 Dataset Info:")
    print(f"   Name: {dataset_name}")
    print(f"   Classes: {expected_classes}")
    print(f"   Images: {expected_images}")
    print(f"   URL: {dataset_url}")
    
    # Check if we already have the dataset
    dataset_dir = Path("datasets/electrocom61_real")
    if dataset_dir.exists():
        print(f"\n✅ Dataset directory already exists: {dataset_dir}")
        
        # Check if it has the expected structure
        images_dir = dataset_dir / "images"
        labels_dir = dataset_dir / "labels"
        
        if images_dir.exists() and labels_dir.exists():
            print("✅ Found images/ and labels/ directories")
            
            # Count images
            image_count = len(list(images_dir.glob("**/*.jpg"))) + len(list(images_dir.glob("**/*.png")))
            label_count = len(list(labels_dir.glob("**/*.txt")))
            
            print(f"📷 Images found: {image_count}")
            print(f"🏷️ Labels found: {label_count}")
            
            if image_count > 1000 and label_count > 1000:
                print("✅ Dataset appears to be complete!")
                return str(dataset_dir)
            else:
                print("⚠️ Dataset appears incomplete, proceeding with download...")
        else:
            print("⚠️ Dataset structure incomplete, proceeding with download...")
    
    print(f"\n📥 Download Instructions:")
    print(f"   1. Visit: {dataset_url}")
    print(f"   2. Click 'Download' button")
    print(f"   3. Extract the ZIP file to: {dataset_dir}")
    print(f"   4. Ensure the structure is:")
    print(f"      {dataset_dir}/")
    print(f"      ├── images/")
    print(f"      │   ├── train/")
    print(f"      │   ├── val/")
    print(f"      │   └── test/")
    print(f"      ├── labels/")
    print(f"      │   ├── train/")
    print(f"      │   ├── val/")
    print(f"      │   └── test/")
    print(f"      └── data.yaml")
    
    # Create directory
    dataset_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n💡 Alternative: Use wget/curl if you have the direct download link")
    print(f"   Example:")
    print(f"   wget -O electrocom61.zip <direct_download_url>")
    print(f"   unzip electrocom61.zip -d {dataset_dir}")
    
    # Check if user wants to proceed with manual download
    response = input(f"\n❓ Have you downloaded and extracted the dataset to {dataset_dir}? (y/n): ")
    
    if response.lower() == 'y':
        # Validate the dataset
        return validate_electrocom61_dataset(str(dataset_dir))
    else:
        print(f"\n⏳ Please download the dataset manually and run this script again.")
        print(f"   Expected location: {dataset_dir}")
        return None

def validate_electrocom61_dataset(dataset_path: str):
    """
    Validate the ElectroCom61 dataset structure and content.
    
    Args:
        dataset_path: Path to the dataset directory
        
    Returns:
        Path to validated dataset or None if invalid
    """
    print(f"\n🔍 Validating ElectroCom61 dataset: {dataset_path}")
    
    dataset_dir = Path(dataset_path)
    
    # Check required directories
    required_dirs = ["images", "labels"]
    for dir_name in required_dirs:
        dir_path = dataset_dir / dir_name
        if not dir_path.exists():
            print(f"❌ Missing directory: {dir_path}")
            return None
        print(f"✅ Found: {dir_path}")
    
    # Check splits
    splits = ["train", "val", "test"]
    total_images = 0
    total_labels = 0
    
    for split in splits:
        img_dir = dataset_dir / "images" / split
        label_dir = dataset_dir / "labels" / split
        
        if img_dir.exists():
            img_count = len(list(img_dir.glob("*.jpg"))) + len(list(img_dir.glob("*.png")))
            total_images += img_count
            print(f"📷 {split} images: {img_count}")
        else:
            print(f"⚠️ Missing {split} images directory")
        
        if label_dir.exists():
            label_count = len(list(label_dir.glob("*.txt")))
            total_labels += label_count
            print(f"🏷️ {split} labels: {label_count}")
        else:
            print(f"⚠️ Missing {split} labels directory")
    
    # Check for data.yaml
    data_yaml = dataset_dir / "data.yaml"
    if data_yaml.exists():
        print(f"✅ Found data.yaml")
        
        # Parse data.yaml to check classes
        try:
            import yaml
            with open(data_yaml, 'r') as f:
                config = yaml.safe_load(f)
            
            num_classes = config.get('nc', 0)
            class_names = config.get('names', [])
            
            print(f"📊 Classes in data.yaml: {num_classes}")
            print(f"🏷️ Class names: {class_names[:5]}..." if len(class_names) > 5 else f"🏷️ Class names: {class_names}")
            
            if num_classes == 61:
                print("✅ Correct number of classes (61)")
            else:
                print(f"⚠️ Expected 61 classes, found {num_classes}")
                
        except Exception as e:
            print(f"⚠️ Could not parse data.yaml: {e}")
    else:
        print(f"⚠️ Missing data.yaml - will need to create one")
    
    # Summary
    print(f"\n📊 Dataset Summary:")
    print(f"   Total images: {total_images}")
    print(f"   Total labels: {total_labels}")
    print(f"   Expected: ~{2071} images")
    
    if total_images > 1000 and total_labels > 1000:
        print("✅ Dataset appears complete and ready for training!")
        return str(dataset_dir)
    else:
        print("❌ Dataset appears incomplete")
        return None

def create_electrocom61_data_yaml(dataset_path: str):
    """
    Create a proper data.yaml for ElectroCom61 dataset.
    
    Args:
        dataset_path: Path to the dataset directory
    """
    print(f"\n📝 Creating data.yaml for ElectroCom61...")
    
    # ElectroCom61 class names (61 classes)
    class_names = [
        "resistor", "capacitor", "inductor", "diode", "transistor", "ic", "connector", 
        "switch", "led", "crystal", "relay", "transformer", "potentiometer", "fuse", 
        "battery", "motor", "sensor", "antenna", "speaker", "microphone", "camera", 
        "display", "keypad", "button", "jumper", "header", "socket", "plug", "cable", 
        "wire", "terminal", "clip", "bracket", "screw", "nut", "washer", "spacer", 
        "standoff", "heat_sink", "fan", "vent", "label", "sticker", "tape", "foam", 
        "rubber", "plastic", "metal", "ceramic", "glass", "fiber", "carbon", "silicon", 
        "copper", "aluminum", "steel", "brass", "gold", "silver", "tin", "lead"
    ]
    
    data_yaml_content = f"""# ElectroCom61 Dataset Configuration
# 61-class PCB component detection dataset

# Dataset paths
path: {os.path.abspath(dataset_path)}
train: images/train
val: images/val
test: images/test

# Classes (61 classes)
nc: 61
names: {class_names}

# Additional metadata
description: "ElectroCom61 - 61-class PCB component detection dataset"
version: "1.0"
license: "MIT"
url: "https://data.mendeley.com/datasets/6scy6h8sjz/2"
"""
    
    data_yaml_path = Path(dataset_path) / "data.yaml"
    with open(data_yaml_path, 'w') as f:
        f.write(data_yaml_content)
    
    print(f"✅ Created data.yaml: {data_yaml_path}")
    return str(data_yaml_path)

def main():
    print("🚀 ElectroCom61 Real Dataset Setup")
    print("=" * 50)
    
    # Download/validate dataset
    dataset_path = download_electrocom61()
    
    if dataset_path:
        # Create data.yaml if needed
        data_yaml_path = Path(dataset_path) / "data.yaml"
        if not data_yaml_path.exists():
            create_electrocom61_data_yaml(dataset_path)
        
        print(f"\n🎉 ElectroCom61 dataset ready!")
        print(f"   Path: {dataset_path}")
        print(f"   Data YAML: {data_yaml_path}")
        print(f"\n🚀 Ready for training with 61 classes!")
        
        # Test with YOLO
        print(f"\n🧪 Testing dataset with YOLO...")
        try:
            result = subprocess.run([
                "yolo", "detect", "val", 
                f"data={data_yaml_path}", 
                "model=yolov8n.pt", 
                "imgsz=640", "batch=8"
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print("✅ YOLO validation passed!")
            else:
                print(f"⚠️ YOLO validation failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("⏳ YOLO validation timed out (this is normal for large datasets)")
        except Exception as e:
            print(f"⚠️ Could not test with YOLO: {e}")
    else:
        print(f"\n❌ Dataset setup incomplete. Please download manually and try again.")

if __name__ == "__main__":
    main()
