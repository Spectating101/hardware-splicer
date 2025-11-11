#!/usr/bin/env python3
"""
Quick YOLO Dataset Validator

Validates dataset structure, class mappings, and label files.
"""

import glob
import os
import yaml
from pathlib import Path

def validate_yolo_dataset(dataset_path: str):
    """
    Validate YOLO dataset structure and content.
    
    Args:
        dataset_path: Path to dataset directory
    """
    print(f"🔍 Validating YOLO dataset: {dataset_path}")
    print("=" * 50)
    
    # Check if dataset exists
    if not os.path.exists(dataset_path):
        print(f"❌ Dataset directory not found: {dataset_path}")
        return False
    
    # Check data.yaml
    yaml_path = os.path.join(dataset_path, "data.yaml")
    if not os.path.exists(yaml_path):
        print(f"❌ data.yaml not found: {yaml_path}")
        return False
    
    print(f"✅ Found data.yaml: {yaml_path}")
    
    # Parse data.yaml
    try:
        with open(yaml_path, 'r') as f:
            data_config = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Failed to parse data.yaml: {e}")
        return False
    
    # Extract configuration
    dataset_root = data_config.get('path', '')
    train_path = data_config.get('train', '')
    val_path = data_config.get('val', '')
    test_path = data_config.get('test', '')
    num_classes = data_config.get('nc', 0)
    class_names = data_config.get('names', [])
    
    print(f"📁 Dataset root: {dataset_root}")
    print(f"📊 Number of classes: {num_classes}")
    print(f"🏷️ Class names: {class_names}")
    
    # Check if paths are absolute or relative
    if not os.path.isabs(dataset_root):
        dataset_root = os.path.join(dataset_path, dataset_root)
    
    print(f"📁 Resolved dataset root: {dataset_root}")
    
    # Check dataset structure
    required_dirs = ['images', 'labels']
    for dir_name in required_dirs:
        dir_path = os.path.join(dataset_root, dir_name)
        if not os.path.exists(dir_path):
            print(f"❌ Missing directory: {dir_path}")
            return False
        print(f"✅ Found directory: {dir_path}")
    
    # Check splits
    splits = ['train', 'val', 'test']
    total_images = 0
    total_labels = 0
    found_classes = set()
    bad_lines = []
    
    for split in splits:
        img_dir = os.path.join(dataset_root, 'images', split)
        label_dir = os.path.join(dataset_root, 'labels', split)
        
        if os.path.exists(img_dir):
            img_count = len([f for f in os.listdir(img_dir) 
                           if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
            total_images += img_count
            print(f"📷 {split} images: {img_count}")
        else:
            print(f"⚠️ Missing {split} images directory: {img_dir}")
        
        if os.path.exists(label_dir):
            label_count = len([f for f in os.listdir(label_dir) if f.endswith('.txt')])
            total_labels += label_count
            print(f"🏷️ {split} labels: {label_count}")
            
            # Validate label files
            for label_file in glob.glob(os.path.join(label_dir, "*.txt")):
                try:
                    with open(label_file, 'r') as f:
                        for line_num, line in enumerate(f, 1):
                            line = line.strip()
                            if not line:
                                continue
                            
                            tokens = line.split()
                            if len(tokens) < 5:
                                bad_lines.append((label_file, line_num, line, "Insufficient tokens"))
                                continue
                            
                            try:
                                class_id = int(float(tokens[0]))
                                if class_id < 0 or class_id >= num_classes:
                                    bad_lines.append((label_file, line_num, line, f"Class ID {class_id} out of range [0, {num_classes-1}]"))
                                else:
                                    found_classes.add(class_id)
                            except ValueError:
                                bad_lines.append((label_file, line_num, line, "Invalid class ID"))
                                
                except Exception as e:
                    bad_lines.append((label_file, 0, "", f"File read error: {e}"))
        else:
            print(f"⚠️ Missing {split} labels directory: {label_dir}")
    
    print(f"\n📊 Dataset Summary:")
    print(f"   Total images: {total_images}")
    print(f"   Total labels: {total_labels}")
    print(f"   Found classes: {sorted(found_classes)}")
    print(f"   Expected classes: {list(range(num_classes))}")
    print(f"   Bad lines: {len(bad_lines)}")
    
    # Check for mismatches
    issues = []
    
    if total_images == 0:
        issues.append("No images found")
    
    if total_labels == 0:
        issues.append("No label files found")
    
    if len(found_classes) == 0:
        issues.append("No valid class IDs found in labels")
    
    if found_classes and max(found_classes) >= num_classes:
        issues.append(f"Class IDs exceed expected range (max: {max(found_classes)}, expected: {num_classes-1})")
    
    if len(found_classes) != num_classes:
        missing_classes = set(range(num_classes)) - found_classes
        if missing_classes:
            issues.append(f"Missing classes: {sorted(missing_classes)}")
    
    # Show bad lines (first 5)
    if bad_lines:
        print(f"\n❌ Bad label lines (showing first 5):")
        for i, (file_path, line_num, line, error) in enumerate(bad_lines[:5]):
            print(f"   {os.path.basename(file_path)}:{line_num}: {line} ({error})")
        if len(bad_lines) > 5:
            print(f"   ... and {len(bad_lines) - 5} more")
    
    # Final assessment
    if issues:
        print(f"\n❌ Dataset validation failed:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print(f"\n✅ Dataset validation passed!")
        return True

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate YOLO dataset')
    parser.add_argument('--dataset', default='datasets/electrocom61', help='Dataset path')
    
    args = parser.parse_args()
    
    success = validate_yolo_dataset(args.dataset)
    
    if not success:
        print(f"\n💡 Suggestions:")
        print(f"   1. Check that data.yaml paths are correct")
        print(f"   2. Ensure images/ and labels/ directories exist")
        print(f"   3. Verify label files are in YOLO format (class_id cx cy w h)")
        print(f"   4. Check that class IDs match the number of classes in data.yaml")
        exit(1)
    else:
        print(f"\n🚀 Dataset is ready for training!")
        exit(0)

if __name__ == "__main__":
    main()
