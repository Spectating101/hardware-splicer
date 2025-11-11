#!/usr/bin/env python3
"""
Download ElectroCom61 dataset from Mendeley Data

This script downloads the ElectroCom61 dataset and sets it up in the correct format.
"""

import os
import requests
import zipfile
import shutil
from pathlib import Path
import argparse

def download_file(url: str, filename: str) -> bool:
    """
    Download a file from URL.
    
    Args:
        url: URL to download from
        filename: Local filename to save to
        
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"Downloading {filename}...")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"✅ Downloaded {filename}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to download {filename}: {e}")
        return False

def extract_zip(zip_path: str, extract_to: str) -> bool:
    """
    Extract a zip file.
    
    Args:
        zip_path: Path to zip file
        extract_to: Directory to extract to
        
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"Extracting {zip_path} to {extract_to}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        
        print(f"✅ Extracted to {extract_to}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to extract {zip_path}: {e}")
        return False

def setup_electrocom61_dataset(dataset_dir: str) -> bool:
    """
    Set up ElectroCom61 dataset in the correct format.
    
    Args:
        dataset_dir: Directory containing the extracted dataset
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Look for the dataset files
        possible_paths = [
            os.path.join(dataset_dir, "ElectroCom61"),
            os.path.join(dataset_dir, "electrocom61"),
            os.path.join(dataset_dir, "Dataset"),
            dataset_dir
        ]
        
        dataset_path = None
        for path in possible_paths:
            if os.path.exists(path):
                # Check if it has images and labels directories
                if os.path.exists(os.path.join(path, "images")) and os.path.exists(os.path.join(path, "labels")):
                    dataset_path = path
                    break
        
        if dataset_path is None:
            print("❌ Could not find dataset structure with images/ and labels/ directories")
            return False
        
        print(f"✅ Found dataset at: {dataset_path}")
        
        # Create target directory
        target_dir = "datasets/electrocom61"
        os.makedirs(target_dir, exist_ok=True)
        
        # Copy images and labels
        for split in ["train", "val", "test"]:
            src_images = os.path.join(dataset_path, "images", split)
            src_labels = os.path.join(dataset_path, "labels", split)
            
            dst_images = os.path.join(target_dir, "images", split)
            dst_labels = os.path.join(target_dir, "labels", split)
            
            if os.path.exists(src_images):
                shutil.copytree(src_images, dst_images, dirs_exist_ok=True)
                print(f"✅ Copied {split} images")
            
            if os.path.exists(src_labels):
                shutil.copytree(src_labels, dst_labels, dirs_exist_ok=True)
                print(f"✅ Copied {split} labels")
        
        # Create or copy data.yaml
        src_yaml = os.path.join(dataset_path, "data.yaml")
        dst_yaml = os.path.join(target_dir, "data.yaml")
        
        if os.path.exists(src_yaml):
            shutil.copy2(src_yaml, dst_yaml)
            print(f"✅ Copied data.yaml")
        else:
            # Create a basic data.yaml
            create_data_yaml(target_dir)
            print(f"✅ Created data.yaml")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to setup dataset: {e}")
        return False

def create_data_yaml(dataset_dir: str):
    """
    Create a data.yaml file for ElectroCom61 dataset.
    
    Args:
        dataset_dir: Dataset directory
    """
    data_yaml_content = """# ElectroCom61 Dataset Configuration
# YOLO format dataset for PCB component detection

# Dataset paths
path: datasets/electrocom61  # dataset root dir
train: images/train  # train images (relative to 'path')
val: images/val      # val images (relative to 'path')
test: images/test    # test images (relative to 'path')

# Classes (61 classes)
nc: 61  # number of classes
names: [
  'resistor', 'capacitor', 'inductor', 'diode', 'transistor', 'ic', 'connector',
  'switch', 'led', 'crystal', 'relay', 'transformer', 'fuse', 'potentiometer',
  'thermistor', 'varistor', 'photodiode', 'phototransistor', 'optoisolator',
  'voltage_regulator', 'oscillator', 'filter', 'amplifier', 'comparator',
  'multiplexer', 'demultiplexer', 'encoder', 'decoder', 'counter', 'flip_flop',
  'memory', 'microcontroller', 'microprocessor', 'dsp', 'fpga', 'cpld',
  'adc', 'dac', 'timer', 'watchdog', 'uart', 'spi', 'i2c', 'can', 'usb',
  'ethernet', 'wifi', 'bluetooth', 'gps', 'sensor', 'actuator', 'motor',
  'servo', 'stepper', 'dc_motor', 'ac_motor', 'generator', 'battery',
  'charger', 'power_supply', 'inverter', 'converter', 'rectifier'
]

# Additional metadata
description: "ElectroCom61 - 61-class PCB component detection dataset"
version: "1.0"
license: "MIT"
url: "https://data.mendeley.com/datasets/6scy6h8sjz/2"
"""
    
    yaml_path = os.path.join(dataset_dir, "data.yaml")
    with open(yaml_path, 'w') as f:
        f.write(data_yaml_content)

def main():
    parser = argparse.ArgumentParser(description='Download ElectroCom61 dataset')
    parser.add_argument('--url', help='Direct download URL (if available)')
    parser.add_argument('--zip-file', help='Local zip file path')
    parser.add_argument('--extract-dir', default='datasets/electrocom61_raw', help='Directory to extract to')
    
    args = parser.parse_args()
    
    print("🔽 ElectroCom61 Dataset Downloader")
    print("=" * 40)
    
    # Check if dataset already exists
    if os.path.exists("datasets/electrocom61/data.yaml"):
        print("✅ ElectroCom61 dataset already exists!")
        return
    
    # Download or use provided zip file
    zip_path = None
    
    if args.zip_file and os.path.exists(args.zip_file):
        zip_path = args.zip_file
        print(f"✅ Using provided zip file: {zip_path}")
    elif args.url:
        zip_path = "electrocom61.zip"
        if not download_file(args.url, zip_path):
            return
    else:
        print("❌ No download URL or zip file provided")
        print("Please download the dataset manually from:")
        print("https://data.mendeley.com/datasets/6scy6h8sjz/2")
        print("Then run: python scripts/download_electrocom61.py --zip-file path/to/electrocom61.zip")
        return
    
    # Extract dataset
    if not extract_zip(zip_path, args.extract_dir):
        return
    
    # Setup dataset
    if not setup_electrocom61_dataset(args.extract_dir):
        return
    
    # Clean up
    if zip_path and zip_path != args.zip_file:
        os.remove(zip_path)
        print(f"✅ Cleaned up {zip_path}")
    
    print("\n🎉 ElectroCom61 dataset setup complete!")
    print("Dataset location: datasets/electrocom61/")
    print("Ready for training!")

if __name__ == "__main__":
    main()

