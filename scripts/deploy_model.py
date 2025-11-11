#!/usr/bin/env python3
"""
Automated model deployment - copies trained model to production location.
"""

import sys
import shutil
from pathlib import Path
from loguru import logger

def deploy_trained_model(run_name: str = "electrocom61_full_production"):
    """Deploy trained model to production."""

    logger.info("🚀 Model Deployment Script")
    logger.info("=" * 60)

    # Paths
    project_root = Path(__file__).parent.parent
    training_weights = project_root / f"pcb_runs/{run_name}/weights/best.pt"
    production_model = project_root / "models/pcb/production_model.pt"
    backup_model = project_root / "models/pcb/production_model_backup.pt"

    # Verify trained model exists
    if not training_weights.exists():
        logger.error(f"❌ Trained model not found at: {training_weights}")
        logger.info(f"   Available runs:")
        runs_dir = project_root / "pcb_runs"
        if runs_dir.exists():
            for run_dir in runs_dir.iterdir():
                if run_dir.is_dir():
                    weights = run_dir / "weights/best.pt"
                    status = "✅" if weights.exists() else "❌"
                    logger.info(f"   {status} {run_dir.name}")
        return False

    logger.info(f"📦 Found trained model: {training_weights}")
    logger.info(f"   Size: {training_weights.stat().st_size / 1024 / 1024:.1f} MB")

    # Create production model directory
    production_model.parent.mkdir(parents=True, exist_ok=True)

    # Backup existing production model
    if production_model.exists():
        logger.info(f"💾 Backing up existing model...")
        shutil.copy2(production_model, backup_model)
        logger.info(f"   Backup saved to: {backup_model}")

    # Copy trained model to production
    logger.info(f"📋 Deploying model to production...")
    shutil.copy2(training_weights, production_model)

    # Verify deployment
    if production_model.exists():
        logger.info(f"✅ Model deployed successfully!")
        logger.info(f"   Production model: {production_model}")
        logger.info(f"   Size: {production_model.stat().st_size / 1024 / 1024:.1f} MB")

        # Update config to use production model
        logger.info(f"\n📝 Update your code to load the model:")
        logger.info(f"   from pathlib import Path")
        logger.info(f"   model_path = Path('models/pcb/production_model.pt')")
        logger.info(f"   model = YOLO(str(model_path))")

        return True
    else:
        logger.error(f"❌ Deployment failed!")
        return False

def validate_model(model_path: Path):
    """Quick validation test on deployed model."""

    logger.info("\n🧪 Validating deployed model...")

    try:
        from ultralytics import YOLO

        # Load model
        logger.info(f"   Loading model...")
        model = YOLO(str(model_path))

        # Check model info
        logger.info(f"   ✅ Model loaded successfully")
        logger.info(f"   Classes: {len(model.names)}")
        logger.info(f"   Names: {list(model.names.values())[:5]}...")

        # Test on sample image if available
        test_images = list(Path("datasets/electrocom61_full/test/images").glob("*.jpg"))
        if test_images:
            logger.info(f"\n   Testing on sample image...")
            results = model(str(test_images[0]), verbose=False)
            logger.info(f"   ✅ Inference successful")
            logger.info(f"   Detections: {len(results[0].boxes)}")

        return True

    except Exception as e:
        logger.error(f"   ❌ Validation failed: {e}")
        return False

if __name__ == "__main__":
    # Check for custom run name
    run_name = sys.argv[1] if len(sys.argv) > 1 else "electrocom61_full_production"

    # Deploy model
    success = deploy_trained_model(run_name)

    if success:
        # Validate
        production_model = Path("models/pcb/production_model.pt")
        validate_model(production_model)

        logger.info("\n✅ Deployment complete!")
        logger.info("\nNext steps:")
        logger.info("1. Restart your backend server")
        logger.info("2. Test with real PCB images")
        logger.info("3. Check detection quality")

    else:
        logger.error("\n❌ Deployment failed")
        sys.exit(1)
