#!/usr/bin/env python3
"""
Test the trained PCB component detection model.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ultralytics import YOLO
import cv2
from loguru import logger

def test_model():
    """Test the trained model on sample images."""

    # Load trained model
    model_path = "pcb_runs/electrocom61_v2/weights/best.pt"
    logger.info(f"Loading model from {model_path}")

    model = YOLO(model_path)

    # Get model info
    logger.info(f"Model loaded successfully")
    logger.info(f"Classes: {model.names}")

    # Test on validation images
    val_dir = Path("datasets/electrocom61/images/val")
    test_images = list(val_dir.glob("*.jpg"))[:5]

    if not test_images:
        logger.warning("No validation images found")
        return

    logger.info(f"Testing on {len(test_images)} images...")

    for img_path in test_images:
        logger.info(f"\nTesting: {img_path.name}")

        # Run inference
        results = model(str(img_path), conf=0.25)

        # Print detections
        for result in results:
            boxes = result.boxes
            logger.info(f"  Found {len(boxes)} components:")
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                logger.info(f"    - {model.names[cls]}: {conf:.2f}")

    logger.info("\n✅ Model test complete!")

if __name__ == "__main__":
    test_model()
