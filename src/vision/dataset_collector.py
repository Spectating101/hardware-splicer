#!/usr/bin/env python3
"""
PCB Dataset Collector for Circuit.AI
===================================

Collects and prepares real PCB images for YOLO training.
Replaces mock detection with real component detection.
"""

import os
import requests
import json
from pathlib import Path
from typing import List, Dict, Any
from PIL import Image
import numpy as np
from loguru import logger


class PCBDatasetCollector:
    """Collects and prepares PCB images for training."""
    
    def __init__(self, dataset_path: str = "data/pcb_dataset"):
        """Initialize dataset collector."""
        self.dataset_path = Path(dataset_path)
        self.dataset_path.mkdir(parents=True, exist_ok=True)
        
        # Component classes for YOLO training
        self.component_classes = [
            'ic_chip', 'capacitor', 'resistor', 'connector',
            'transformer', 'diode', 'led', 'transistor'
        ]
        
        # Create subdirectories
        self.images_path = self.dataset_path / "images"
        self.labels_path = self.dataset_path / "labels"
        self.images_path.mkdir(exist_ok=True)
        self.labels_path.mkdir(exist_ok=True)
        
        logger.info(f"Dataset collector initialized at {self.dataset_path}")
    
    def collect_from_urls(self, urls: List[str]) -> List[str]:
        """Collect PCB images from URLs."""
        collected_images = []
        
        for i, url in enumerate(urls):
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                # Save image
                image_path = self.images_path / f"pcb_{i:04d}.jpg"
                with open(image_path, 'wb') as f:
                    f.write(response.content)
                
                collected_images.append(str(image_path))
                logger.info(f"Collected image {i+1}/{len(urls)}: {image_path}")
                
            except Exception as e:
                logger.error(f"Failed to collect image {i+1}: {e}")
        
        return collected_images
    
    def collect_from_directory(self, source_dir: str) -> List[str]:
        """Collect PCB images from local directory."""
        source_path = Path(source_dir)
        if not source_path.exists():
            logger.error(f"Source directory not found: {source_dir}")
            return []
        
        # Supported image formats
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        
        collected_images = []
        for image_file in source_path.rglob("*"):
            if image_file.suffix.lower() in image_extensions:
                try:
                    # Copy image to dataset
                    dest_path = self.images_path / f"pcb_{len(collected_images):04d}{image_file.suffix}"
                    with open(image_file, 'rb') as src, open(dest_path, 'wb') as dst:
                        dst.write(src.read())
                    
                    collected_images.append(str(dest_path))
                    logger.info(f"Collected: {dest_path}")
                    
                except Exception as e:
                    logger.error(f"Failed to copy {image_file}: {e}")
        
        return collected_images
    
    def create_annotation_template(self, image_path: str) -> Dict[str, Any]:
        """Create annotation template for manual labeling."""
        image = Image.open(image_path)
        width, height = image.size
        
        return {
            "image_path": image_path,
            "image_size": {"width": width, "height": height},
            "components": [],
            "metadata": {
                "source": "manual_collection",
                "date_collected": str(Path(image_path).stat().st_mtime),
                "component_classes": self.component_classes
            }
        }
    
    def save_annotation(self, annotation: Dict[str, Any], filename: str = None):
        """Save annotation to JSON file."""
        if filename is None:
            image_name = Path(annotation["image_path"]).stem
            filename = f"{image_name}.json"
        
        annotation_path = self.labels_path / filename
        with open(annotation_path, 'w') as f:
            json.dump(annotation, f, indent=2)
        
        logger.info(f"Saved annotation: {annotation_path}")
    
    def convert_to_yolo_format(self, annotation: Dict[str, Any]) -> List[str]:
        """Convert annotation to YOLO format."""
        yolo_lines = []
        image_size = annotation["image_size"]
        width, height = image_size["width"], image_size["height"]
        
        for component in annotation["components"]:
            # Get component class index
            class_name = component["class"]
            if class_name not in self.component_classes:
                logger.warning(f"Unknown component class: {class_name}")
                continue
            
            class_index = self.component_classes.index(class_name)
            
            # Convert bounding box to YOLO format (normalized)
            bbox = component["bbox"]  # [x1, y1, x2, y2]
            x_center = (bbox[0] + bbox[2]) / 2 / width
            y_center = (bbox[1] + bbox[3]) / 2 / height
            box_width = (bbox[2] - bbox[0]) / width
            box_height = (bbox[3] - bbox[1]) / height
            
            # YOLO format: class x_center y_center width height
            yolo_line = f"{class_index} {x_center:.6f} {y_center:.6f} {box_width:.6f} {box_height:.6f}"
            yolo_lines.append(yolo_line)
        
        return yolo_lines
    
    def save_yolo_labels(self, annotation: Dict[str, Any]):
        """Save YOLO format labels."""
        image_name = Path(annotation["image_path"]).stem
        label_path = self.labels_path / f"{image_name}.txt"
        
        yolo_lines = self.convert_to_yolo_format(annotation)
        
        with open(label_path, 'w') as f:
            f.write('\n'.join(yolo_lines))
        
        logger.info(f"Saved YOLO labels: {label_path}")
    
    def create_dataset_config(self) -> Dict[str, Any]:
        """Create YOLO dataset configuration."""
        config = {
            "path": str(self.dataset_path),
            "train": "images/train",
            "val": "images/val",
            "test": "images/test",
            "nc": len(self.component_classes),
            "names": self.component_classes
        }
        
        config_path = self.dataset_path / "dataset.yaml"
        with open(config_path, 'w') as f:
            import yaml
            yaml.dump(config, f, default_flow_style=False)
        
        logger.info(f"Created dataset config: {config_path}")
        return config
    
    def split_dataset(self, train_ratio: float = 0.8, val_ratio: float = 0.1):
        """Split dataset into train/val/test sets."""
        image_files = list(self.images_path.glob("*.jpg")) + list(self.images_path.glob("*.png"))
        
        # Shuffle files
        import random
        random.shuffle(image_files)
        
        total_files = len(image_files)
        train_count = int(total_files * train_ratio)
        val_count = int(total_files * val_ratio)
        
        # Split files
        train_files = image_files[:train_count]
        val_files = image_files[train_count:train_count + val_count]
        test_files = image_files[train_count + val_count:]
        
        # Create directories
        train_path = self.dataset_path / "images" / "train"
        val_path = self.dataset_path / "images" / "val"
        test_path = self.dataset_path / "images" / "test"
        
        for path in [train_path, val_path, test_path]:
            path.mkdir(parents=True, exist_ok=True)
        
        # Move files
        for file_list, dest_path in [(train_files, train_path), (val_files, val_path), (test_files, test_path)]:
            for file_path in file_list:
                dest_file = dest_path / file_path.name
                file_path.rename(dest_file)
                
                # Move corresponding label file
                label_file = self.labels_path / f"{file_path.stem}.txt"
                if label_file.exists():
                    dest_label = dest_path.parent.parent / "labels" / dest_path.name / f"{file_path.stem}.txt"
                    dest_label.parent.mkdir(parents=True, exist_ok=True)
                    label_file.rename(dest_label)
        
        logger.info(f"Dataset split: {len(train_files)} train, {len(val_files)} val, {len(test_files)} test")
    
    def generate_sample_annotations(self):
        """Generate sample annotations for testing."""
        sample_annotations = [
            {
                "image_path": "data/pcb_dataset/images/pcb_0000.jpg",
                "image_size": {"width": 640, "height": 480},
                "components": [
                    {
                        "class": "ic_chip",
                        "bbox": [100, 100, 200, 150],
                        "confidence": 0.95
                    },
                    {
                        "class": "capacitor",
                        "bbox": [250, 100, 280, 130],
                        "confidence": 0.88
                    },
                    {
                        "class": "resistor",
                        "bbox": [100, 200, 130, 230],
                        "confidence": 0.92
                    }
                ]
            }
        ]
        
        for annotation in sample_annotations:
            self.save_annotation(annotation)
            self.save_yolo_labels(annotation)
        
        logger.info("Generated sample annotations")


def main():
    """Main function for dataset collection."""
    collector = PCBDatasetCollector()
    
    # Example usage
    print("🔍 PCB Dataset Collector")
    print("=" * 40)
    
    # Create sample annotations
    collector.generate_sample_annotations()
    
    # Create dataset config
    config = collector.create_dataset_config()
    
    print(f"✅ Dataset collector ready at: {collector.dataset_path}")
    print(f"✅ Component classes: {collector.component_classes}")
    print(f"✅ Dataset config created")
    
    print("\n📋 Next steps:")
    print("1. Add real PCB images to data/pcb_dataset/images/")
    print("2. Create annotations in data/pcb_dataset/labels/")
    print("3. Run split_dataset() to prepare for training")
    print("4. Train YOLO model with custom dataset")


if __name__ == "__main__":
    main() 