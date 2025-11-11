#!/usr/bin/env python3
"""
Convert FPIC dataset to YOLO format

This script converts FPIC (FPCB Image Classification) dataset annotations
from JSON format to YOLO format for training.
"""

import json
import cv2
import os
import glob
from pathlib import Path
import argparse
from typing import Dict, List, Tuple

def to_yolo_bbox(xmin: float, ymin: float, xmax: float, ymax: float, img_width: int, img_height: int) -> Tuple[float, float, float, float]:
    """
    Convert bounding box from absolute coordinates to YOLO format.
    
    Args:
        xmin, ymin, xmax, ymax: Bounding box coordinates
        img_width, img_height: Image dimensions
        
    Returns:
        Tuple of (center_x, center_y, width, height) normalized to [0,1]
    """
    center_x = (xmin + xmax) / 2.0 / img_width
    center_y = (ymin + ymax) / 2.0 / img_height
    width = (xmax - xmin) / img_width
    height = (ymax - ymin) / img_height
    
    return center_x, center_y, width, height

def get_class_mapping() -> Dict[str, int]:
    """
    Get mapping from FPIC class names to YOLO class IDs.
    
    Returns:
        Dictionary mapping class names to integer IDs
    """
    # Common PCB component classes
    class_mapping = {
        'resistor': 0,
        'capacitor': 1,
        'inductor': 2,
        'diode': 3,
        'transistor': 4,
        'ic': 5,
        'connector': 6,
        'switch': 7,
        'led': 8,
        'crystal': 9,
        'relay': 10,
        'transformer': 11,
        'fuse': 12,
        'potentiometer': 13,
        'thermistor': 14,
        'varistor': 15,
        'photodiode': 16,
        'phototransistor': 17,
        'optoisolator': 18,
        'voltage_regulator': 19,
        'oscillator': 20,
        'filter': 21,
        'amplifier': 22,
        'comparator': 23,
        'multiplexer': 24,
        'demultiplexer': 25,
        'encoder': 26,
        'decoder': 27,
        'counter': 28,
        'flip_flop': 29,
        'memory': 30,
        'microcontroller': 31,
        'microprocessor': 32,
        'dsp': 33,
        'fpga': 34,
        'cpld': 35,
        'adc': 36,
        'dac': 37,
        'timer': 38,
        'watchdog': 39,
        'uart': 40,
        'spi': 41,
        'i2c': 42,
        'can': 43,
        'usb': 44,
        'ethernet': 45,
        'wifi': 46,
        'bluetooth': 47,
        'gps': 48,
        'sensor': 49,
        'actuator': 50,
        'motor': 51,
        'servo': 52,
        'stepper': 53,
        'dc_motor': 54,
        'ac_motor': 55,
        'generator': 56,
        'battery': 57,
        'charger': 58,
        'power_supply': 59,
        'inverter': 60,
        'converter': 61,
        'rectifier': 62
    }
    
    return class_mapping

def convert_annotation(ann_path: str, img_dir: str, out_img_dir: str, out_lbl_dir: str, class_mapping: Dict[str, int]) -> bool:
    """
    Convert a single annotation file from FPIC to YOLO format.
    
    Args:
        ann_path: Path to the annotation JSON file
        img_dir: Directory containing source images
        out_img_dir: Directory to copy images to
        out_lbl_dir: Directory to write YOLO labels to
        class_mapping: Mapping from class names to IDs
        
    Returns:
        True if conversion was successful, False otherwise
    """
    try:
        # Load annotation
        with open(ann_path, 'r') as f:
            ann = json.load(f)
        
        # Get image file path
        img_file = ann.get("imagePath", "")
        if not img_file:
            print(f"Warning: No imagePath in {ann_path}")
            return False
        
        # Get image dimensions
        img_width = ann.get("imageWidth", 0)
        img_height = ann.get("imageHeight", 0)
        
        if img_width == 0 or img_height == 0:
            print(f"Warning: Invalid image dimensions in {ann_path}")
            return False
        
        # Copy image file
        src_img_path = os.path.join(img_dir, img_file)
        dst_img_path = os.path.join(out_img_dir, img_file)
        
        if not os.path.exists(src_img_path):
            print(f"Warning: Image file not found: {src_img_path}")
            return False
        
        # Copy image
        Path(dst_img_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dst_img_path).write_bytes(Path(src_img_path).read_bytes())
        
        # Convert annotations
        yolo_lines = []
        shapes = ann.get("shapes", [])
        
        for shape in shapes:
            label = shape.get("label", "").lower().strip()
            points = shape.get("points", [])
            
            if not label or not points:
                continue
            
            # Map label to class ID
            if label not in class_mapping:
                print(f"Warning: Unknown class '{label}' in {ann_path}")
                continue
            
            class_id = class_mapping[label]
            
            # Convert points to bounding box
            if len(points) >= 2:
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                
                xmin = min(xs)
                ymin = min(ys)
                xmax = max(xs)
                ymax = max(ys)
                
                # Convert to YOLO format
                center_x, center_y, width, height = to_yolo_bbox(xmin, ymin, xmax, ymax, img_width, img_height)
                
                # Validate coordinates
                if 0 <= center_x <= 1 and 0 <= center_y <= 1 and 0 < width <= 1 and 0 < height <= 1:
                    yolo_lines.append(f"{class_id} {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}")
                else:
                    print(f"Warning: Invalid bbox coordinates in {ann_path}")
        
        # Write YOLO label file
        if yolo_lines:
            label_file = os.path.splitext(img_file)[0] + '.txt'
            label_path = os.path.join(out_lbl_dir, label_file)
            
            Path(label_path).parent.mkdir(parents=True, exist_ok=True)
            with open(label_path, 'w') as f:
                f.write('\n'.join(yolo_lines))
        
        return True
        
    except Exception as e:
        print(f"Error converting {ann_path}: {e}")
        return False

def create_data_yaml(out_dir: str, class_mapping: Dict[str, int], train_ratio: float = 0.8, val_ratio: float = 0.1):
    """
    Create data.yaml file for YOLO training.
    
    Args:
        out_dir: Output directory for YOLO dataset
        class_mapping: Mapping from class names to IDs
        train_ratio: Ratio of data for training
        val_ratio: Ratio of data for validation
    """
    # Get all image files
    img_dir = os.path.join(out_dir, "images")
    img_files = []
    
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp']:
        img_files.extend(glob.glob(os.path.join(img_dir, ext)))
        img_files.extend(glob.glob(os.path.join(img_dir, "**", ext), recursive=True))
    
    # Shuffle and split
    import random
    random.shuffle(img_files)
    
    n_total = len(img_files)
    n_train = int(n_total * train_ratio)
    n_val = int(n_total * val_ratio)
    
    train_files = img_files[:n_train]
    val_files = img_files[n_train:n_train + n_val]
    test_files = img_files[n_train + n_val:]
    
    # Create directories
    for split in ['train', 'val', 'test']:
        os.makedirs(os.path.join(out_dir, 'images', split), exist_ok=True)
        os.makedirs(os.path.join(out_dir, 'labels', split), exist_ok=True)
    
    # Move files to appropriate splits
    for i, img_file in enumerate(img_files):
        rel_path = os.path.relpath(img_file, img_dir)
        
        if img_file in train_files:
            split = 'train'
        elif img_file in val_files:
            split = 'val'
        else:
            split = 'test'
        
        # Move image
        dst_img = os.path.join(out_dir, 'images', split, rel_path)
        Path(dst_img).parent.mkdir(parents=True, exist_ok=True)
        Path(dst_img).write_bytes(Path(img_file).read_bytes())
        
        # Move corresponding label
        label_file = os.path.splitext(rel_path)[0] + '.txt'
        src_label = os.path.join(out_dir, 'labels', label_file)
        dst_label = os.path.join(out_dir, 'labels', split, label_file)
        
        if os.path.exists(src_label):
            Path(dst_label).parent.mkdir(parents=True, exist_ok=True)
            Path(dst_label).write_bytes(Path(src_label).read_bytes())
    
    # Create data.yaml
    class_names = [name for name, _ in sorted(class_mapping.items(), key=lambda x: x[1])]
    
    data_yaml = f"""# FPIC Dataset converted to YOLO format
path: {out_dir}
train: images/train
val: images/val
test: images/test

# Classes
nc: {len(class_names)}
names: {class_names}

# Dataset info
description: "FPIC dataset converted to YOLO format"
version: "1.0"
license: "MIT"
"""
    
    yaml_path = os.path.join(out_dir, 'data.yaml')
    with open(yaml_path, 'w') as f:
        f.write(data_yaml)
    
    print(f"Created data.yaml with {len(class_names)} classes")
    print(f"Train: {len(train_files)}, Val: {len(val_files)}, Test: {len(test_files)}")

def main():
    parser = argparse.ArgumentParser(description='Convert FPIC dataset to YOLO format')
    parser.add_argument('--ann-dir', required=True, help='Directory containing FPIC annotation JSON files')
    parser.add_argument('--img-dir', required=True, help='Directory containing source images')
    parser.add_argument('--out-dir', required=True, help='Output directory for YOLO dataset')
    parser.add_argument('--train-ratio', type=float, default=0.8, help='Ratio of data for training')
    parser.add_argument('--val-ratio', type=float, default=0.1, help='Ratio of data for validation')
    
    args = parser.parse_args()
    
    # Create output directories
    os.makedirs(args.out_dir, exist_ok=True)
    os.makedirs(os.path.join(args.out_dir, 'images'), exist_ok=True)
    os.makedirs(os.path.join(args.out_dir, 'labels'), exist_ok=True)
    
    # Get class mapping
    class_mapping = get_class_mapping()
    
    # Find all annotation files
    ann_files = glob.glob(os.path.join(args.ann_dir, '*.json'))
    print(f"Found {len(ann_files)} annotation files")
    
    # Convert annotations
    successful = 0
    failed = 0
    
    for ann_file in ann_files:
        if convert_annotation(ann_file, args.img_dir, 
                            os.path.join(args.out_dir, 'images'), 
                            os.path.join(args.out_dir, 'labels'), 
                            class_mapping):
            successful += 1
        else:
            failed += 1
    
    print(f"Conversion complete: {successful} successful, {failed} failed")
    
    # Create data.yaml
    create_data_yaml(args.out_dir, class_mapping, args.train_ratio, args.val_ratio)
    
    print(f"YOLO dataset created in: {args.out_dir}")

if __name__ == "__main__":
    main()

