#!/usr/bin/env python3
"""
Model Training Script for Circuit.AI

This script provides a unified interface for training YOLO models
on different datasets (ElectroCom61, FPIC, DeepPCB).
"""

import argparse
import os
import sys
from pathlib import Path
import yaml
from typing import Dict, Any

try:
    from ultralytics import YOLO
except ImportError:
    print("Error: ultralytics not installed. Run: pip install ultralytics")
    sys.exit(1)

def get_model_config(dataset: str) -> Dict[str, Any]:
    """
    Get model configuration for different datasets.
    
    Args:
        dataset: Dataset name (electrocom61, fpic, deeppcb)
        
    Returns:
        Configuration dictionary
    """
    configs = {
        'electrocom61': {
            'model': 'yolov8m.pt',
            'imgsz': 640,
            'epochs': 100,
            'batch': 16,
            'patience': 20,
            'lr0': 0.01,
            'lrf': 0.1,
            'momentum': 0.937,
            'weight_decay': 0.0005,
            'warmup_epochs': 3,
            'warmup_momentum': 0.8,
            'warmup_bias_lr': 0.1,
            'box': 7.5,
            'cls': 0.5,
            'dfl': 1.5,
            'pose': 12.0,
            'kobj': 2.0,
            'label_smoothing': 0.0,
            'nbs': 64,
            'overlap_mask': True,
            'mask_ratio': 4,
            'dropout': 0.0,
            'val': True,
            'split': 'val',
            'save_json': False,
            'save_hybrid': False,
            'conf': None,
            'iou': 0.7,
            'max_det': 300,
            'half': False,
            'dnn': False,
            'plots': True,
            'source': None,
            'show': False,
            'save_txt': False,
            'save_conf': False,
            'save_crop': False,
            'show_labels': True,
            'show_conf': True,
            'vid_stride': 1,
            'line_width': None,
            'visualize': False,
            'augment': False,
            'agnostic_nms': False,
            'classes': None,
            'retina_masks': False,
            'boxes': True,
            'format': 'torchscript',
            'keras': False,
            'optimize': False,
            'int8': False,
            'dynamic': False,
            'simplify': False,
            'opset': None,
            'workspace': 4,
            'nms': False,
            'lr_scheduler': 'auto',
            'cos_lr': False,
            'close_mosaic': 10,
            'resume': False,
            'amp': True,
            'fraction': 1.0,
            'profile': False,
            'freeze': None,
            'multi_scale': False,
            'overlap_mask': True,
            'mask_ratio': 4,
            'dropout': 0.0,
            'val': True,
            'split': 'val',
            'save_json': False,
            'save_hybrid': False,
            'conf': None,
            'iou': 0.7,
            'max_det': 300,
            'half': False,
            'dnn': False,
            'plots': True,
            'source': None,
            'show': False,
            'save_txt': False,
            'save_conf': False,
            'save_crop': False,
            'show_labels': True,
            'show_conf': True,
            'vid_stride': 1,
            'line_width': None,
            'visualize': False,
            'augment': False,
            'agnostic_nms': False,
            'classes': None,
            'retina_masks': False,
            'boxes': True
        },
        'fpic': {
            'model': 'yolov8m.pt',
            'imgsz': 768,
            'epochs': 100,
            'batch': 8,
            'patience': 25,
            'lr0': 0.01,
            'lrf': 0.1,
            'momentum': 0.937,
            'weight_decay': 0.0005,
            'warmup_epochs': 3,
            'warmup_momentum': 0.8,
            'warmup_bias_lr': 0.1,
            'box': 7.5,
            'cls': 0.5,
            'dfl': 1.5,
            'pose': 12.0,
            'kobj': 2.0,
            'label_smoothing': 0.0,
            'nbs': 64,
            'overlap_mask': True,
            'mask_ratio': 4,
            'dropout': 0.0,
            'val': True,
            'split': 'val',
            'save_json': False,
            'save_hybrid': False,
            'conf': None,
            'iou': 0.7,
            'max_det': 300,
            'half': False,
            'dnn': False,
            'plots': True,
            'source': None,
            'show': False,
            'save_txt': False,
            'save_conf': False,
            'save_crop': False,
            'show_labels': True,
            'show_conf': True,
            'vid_stride': 1,
            'line_width': None,
            'visualize': False,
            'augment': False,
            'agnostic_nms': False,
            'classes': None,
            'retina_masks': False,
            'boxes': True
        },
        'deeppcb': {
            'model': 'yolov8m.pt',
            'imgsz': 640,
            'epochs': 80,
            'batch': 16,
            'patience': 15,
            'lr0': 0.01,
            'lrf': 0.1,
            'momentum': 0.937,
            'weight_decay': 0.0005,
            'warmup_epochs': 3,
            'warmup_momentum': 0.8,
            'warmup_bias_lr': 0.1,
            'box': 7.5,
            'cls': 0.5,
            'dfl': 1.5,
            'pose': 12.0,
            'kobj': 2.0,
            'label_smoothing': 0.0,
            'nbs': 64,
            'overlap_mask': True,
            'mask_ratio': 4,
            'dropout': 0.0,
            'val': True,
            'split': 'val',
            'save_json': False,
            'save_hybrid': False,
            'conf': None,
            'iou': 0.7,
            'max_det': 300,
            'half': False,
            'dnn': False,
            'plots': True,
            'source': None,
            'show': False,
            'save_txt': False,
            'save_conf': False,
            'save_crop': False,
            'show_labels': True,
            'show_conf': True,
            'vid_stride': 1,
            'line_width': None,
            'visualize': False,
            'augment': False,
            'agnostic_nms': False,
            'classes': None,
            'retina_masks': False,
            'boxes': True
        }
    }
    
    return configs.get(dataset, configs['electrocom61'])

def train_model(dataset: str, data_yaml: str, project: str = "pcb_runs", name: str = None, **kwargs):
    """
    Train a YOLO model on the specified dataset.
    
    Args:
        dataset: Dataset name
        data_yaml: Path to data.yaml file
        project: Project directory for runs
        name: Run name (defaults to dataset_v1)
        **kwargs: Additional training parameters
    """
    if not os.path.exists(data_yaml):
        raise FileNotFoundError(f"Data YAML file not found: {data_yaml}")
    
    # Get model configuration
    config = get_model_config(dataset)
    
    # Override with provided kwargs
    config.update(kwargs)
    
    # Set default name if not provided
    if name is None:
        name = f"{dataset}_v1"
    
    # Load model
    model = YOLO(config['model'])
    
    # Start training
    print(f"Starting training for {dataset} dataset...")
    print(f"Data YAML: {data_yaml}")
    print(f"Project: {project}")
    print(f"Name: {name}")
    print(f"Model: {config['model']}")
    print(f"Image size: {config['imgsz']}")
    print(f"Epochs: {config['epochs']}")
    print(f"Batch size: {config['batch']}")
    
    results = model.train(
        data=data_yaml,
        project=project,
        name=name,
        **config
    )
    
    print(f"Training completed!")
    print(f"Results saved to: {project}/{name}")
    
    return results

def export_model(model_path: str, format: str = "onnx", output_dir: str = "models/pcb"):
    """
    Export trained model to different formats.
    
    Args:
        model_path: Path to trained model weights
        format: Export format (onnx, torchscript, etc.)
        output_dir: Output directory for exported model
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    # Load model
    model = YOLO(model_path)
    
    # Export model
    print(f"Exporting model to {format} format...")
    exported_path = model.export(format=format)
    
    # Move to output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Get model name from path
    model_name = Path(model_path).stem
    output_path = os.path.join(output_dir, f"{model_name}.{format}")
    
    # Copy exported model
    import shutil
    shutil.copy2(exported_path, output_path)
    
    print(f"Model exported to: {output_path}")
    
    return output_path

def main():
    parser = argparse.ArgumentParser(description='Train YOLO models for Circuit.AI')
    parser.add_argument('--dataset', required=True, choices=['electrocom61', 'fpic', 'deeppcb'],
                       help='Dataset to train on')
    parser.add_argument('--data-yaml', required=True, help='Path to data.yaml file')
    parser.add_argument('--project', default='pcb_runs', help='Project directory for runs')
    parser.add_argument('--name', help='Run name (defaults to dataset_v1)')
    parser.add_argument('--epochs', type=int, help='Number of training epochs')
    parser.add_argument('--batch', type=int, help='Batch size')
    parser.add_argument('--imgsz', type=int, help='Image size')
    parser.add_argument('--export', action='store_true', help='Export model after training')
    parser.add_argument('--export-format', default='onnx', help='Export format')
    parser.add_argument('--export-dir', default='models/pcb', help='Export directory')
    
    args = parser.parse_args()
    
    # Prepare training arguments
    train_kwargs = {}
    if args.epochs:
        train_kwargs['epochs'] = args.epochs
    if args.batch:
        train_kwargs['batch'] = args.batch
    if args.imgsz:
        train_kwargs['imgsz'] = args.imgsz
    
    try:
        # Train model
        results = train_model(
            dataset=args.dataset,
            data_yaml=args.data_yaml,
            project=args.project,
            name=args.name,
            **train_kwargs
        )
        
        # Export model if requested
        if args.export:
            model_path = os.path.join(args.project, args.name or f"{args.dataset}_v1", "weights", "best.pt")
            export_model(model_path, args.export_format, args.export_dir)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

