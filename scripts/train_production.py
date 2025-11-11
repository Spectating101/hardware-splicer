#!/usr/bin/env python3
"""
Train YOLOv8 on full ElectroCom61 dataset for production.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ultralytics import YOLO
from loguru import logger
import torch

def train_model():
    """Train model on full dataset."""

    logger.info("🚀 Production Training - ElectroCom61 Full Dataset")
    logger.info("=" * 70)

    # Check GPU
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    logger.info(f"🖥️  Device: {device}")

    # Dataset path
    data_yaml = "datasets/electrocom61_full/data.yaml"

    if not Path(data_yaml).exists():
        logger.error(f"❌ Dataset not found: {data_yaml}")
        return

    # Load model
    logger.info("📦 Loading YOLOv8m model...")
    model = YOLO("models/yolo/yolov8m.pt")

    # Training configuration
    logger.info("⚙️  Training configuration:")
    config = {
        'data': data_yaml,
        'epochs': 100,  # Reduced from 150 for faster training
        'batch': 16,
        'imgsz': 640,
        'patience': 50,
        'save': True,
        'device': device,
        'workers': 8,
        'project': 'pcb_runs',
        'name': 'electrocom61_full_production',
        'exist_ok': True,
        'pretrained': True,
        'optimizer': 'auto',
        'verbose': True,
        'val': True,
        'plots': True,
        # Data augmentation
        'hsv_h': 0.015,
        'hsv_s': 0.7,
        'hsv_v': 0.4,
        'degrees': 0.0,
        'translate': 0.1,
        'scale': 0.5,
        'fliplr': 0.5,
        'mosaic': 1.0,
        'mixup': 0.0,
    }

    for key, value in config.items():
        if key != 'data':
            logger.info(f"   {key}: {value}")

    # Train
    logger.info("\n🏋️  Starting training...")
    logger.info("This will take a while (30min - 2hrs depending on hardware)")

    results = model.train(**config)

    logger.info("\n✅ Training complete!")
    logger.info(f"📊 Results saved to: pcb_runs/electrocom61_full_production/")

    # Validate
    logger.info("\n🧪 Running validation...")
    metrics = model.val()

    logger.info(f"\n📈 Final metrics:")
    logger.info(f"   mAP50: {metrics.box.map50:.3f}")
    logger.info(f"   mAP50-95: {metrics.box.map:.3f}")
    logger.info(f"   Precision: {metrics.box.mp:.3f}")
    logger.info(f"   Recall: {metrics.box.mr:.3f}")

    best_model_path = Path(f"pcb_runs/electrocom61_full_production/weights/best.pt")
    logger.info(f"\n💾 Best model saved to: {best_model_path}")

    return str(best_model_path)

if __name__ == "__main__":
    try:
        model_path = train_model()
        logger.info(f"\n✅ Model ready: {model_path}")
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Training interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
