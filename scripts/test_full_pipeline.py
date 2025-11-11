#!/usr/bin/env python3
"""
End-to-end pipeline test - validates entire system workflow.
"""

import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from PIL import Image
from loguru import logger

async def test_detection_only():
    """Test just the detection component."""

    logger.info("🔍 Testing Detection Component")
    logger.info("-" * 60)

    try:
        from src.vision.enhanced_detector import EnhancedComponentDetector

        detector = EnhancedComponentDetector()
        logger.info("✅ Detector initialized")

        # Load test image
        test_images = list(Path("datasets/electrocom61_full/test/images").glob("*.jpg"))
        if not test_images:
            logger.warning("⚠️  No test images found")
            return False

        test_img_path = test_images[0]
        logger.info(f"📷 Loading test image: {test_img_path.name}")

        img = Image.open(test_img_path)
        img_array = np.array(img)

        # Run detection
        logger.info("🔎 Running detection...")
        detections = detector.detect_components(
            img_array,
            methods=['yolo'],
            enable_ocr=False
        )

        logger.info(f"✅ Detected {len(detections)} components")
        for i, det in enumerate(detections[:5], 1):
            logger.info(f"   {i}. {det.class_name} (conf: {det.confidence:.2f})")

        return len(detections) > 0

    except Exception as e:
        logger.error(f"❌ Detection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_full_pipeline():
    """Test complete analysis pipeline."""

    logger.info("\n🔄 Testing Full Analysis Pipeline")
    logger.info("-" * 60)

    try:
        from src.core.enhanced_analyzer import EnhancedCircuitAnalyzer

        analyzer = EnhancedCircuitAnalyzer()
        logger.info("✅ Analyzer initialized")

        # Load test image
        test_images = list(Path("datasets/electrocom61_full/test/images").glob("*.jpg"))
        test_img_path = test_images[0]

        img = Image.open(test_img_path)
        img_array = np.array(img)

        # Run full analysis
        logger.info("🔬 Running full PCB analysis...")
        result = await analyzer.analyze_pcb(
            img_array,
            backend='yolo',
            enable_ocr=False,
            enable_caching=False
        )

        logger.info("✅ Analysis complete!")
        logger.info(f"\n📊 Results:")
        logger.info(f"   Status: {result.get('status', 'unknown')}")
        logger.info(f"   Components detected: {result.get('num_components', 0)}")

        if 'components' in result:
            logger.info(f"\n   Top components:")
            for comp in result['components'][:5]:
                logger.info(f"      - {comp.get('name', 'unknown')}")

        if 'functionality' in result:
            logger.info(f"\n   Functionality analysis: ✅")

        if 'projects' in result:
            logger.info(f"   Project recommendations: {len(result['projects'])}")

        return True

    except Exception as e:
        logger.error(f"❌ Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_database():
    """Test database connectivity."""

    logger.info("\n💾 Testing Database")
    logger.info("-" * 60)

    try:
        import sqlite3
        conn = sqlite3.connect("data/circuit_ai.db")
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM components")
        count = cursor.fetchone()[0]

        logger.info(f"✅ Database connected")
        logger.info(f"   Components in database: {count}")

        cursor.execute("SELECT name FROM components LIMIT 5")
        samples = cursor.fetchall()
        logger.info(f"   Sample components:")
        for name, in samples:
            logger.info(f"      - {name}")

        conn.close()
        return count > 0

    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        return False

async def test_model_deployment():
    """Test if production model exists and works."""

    logger.info("\n🤖 Testing Model Deployment")
    logger.info("-" * 60)

    production_model = Path("models/pcb/production_model.pt")

    if not production_model.exists():
        logger.warning("⚠️  Production model not deployed yet")
        logger.info(f"   Expected at: {production_model}")
        logger.info(f"   Run: python scripts/deploy_model.py")
        return False

    try:
        from ultralytics import YOLO

        logger.info(f"📦 Loading production model...")
        model = YOLO(str(production_model))

        logger.info(f"✅ Production model loaded")
        logger.info(f"   Classes: {len(model.names)}")
        logger.info(f"   Size: {production_model.stat().st_size / 1024 / 1024:.1f} MB")

        # Quick test
        test_images = list(Path("datasets/electrocom61_full/test/images").glob("*.jpg"))
        if test_images:
            results = model(str(test_images[0]), verbose=False)
            logger.info(f"   Test inference: ✅ ({len(results[0].boxes)} detections)")

        return True

    except Exception as e:
        logger.error(f"❌ Model test failed: {e}")
        return False

async def main():
    """Run all tests."""

    logger.info("="  * 60)
    logger.info("🧪 Circuit.AI - Full System Test Suite")
    logger.info("=" * 60)

    results = {}

    # Test 1: Database
    results['database'] = await test_database()

    # Test 2: Model deployment
    results['model'] = await test_model_deployment()

    # Test 3: Detection only
    results['detection'] = await test_detection_only()

    # Test 4: Full pipeline (requires LLM)
    try:
        results['pipeline'] = await test_full_pipeline()
    except Exception as e:
        logger.warning(f"⚠️  Full pipeline test skipped (LLM may not be configured)")
        results['pipeline'] = None

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 Test Results Summary")
    logger.info("=" * 60)

    for test_name, passed in results.items():
        if passed is True:
            status = "✅ PASS"
        elif passed is False:
            status = "❌ FAIL"
        else:
            status = "⏭️  SKIP"

        logger.info(f"{test_name.title():20} {status}")

    passed_count = sum(1 for r in results.values() if r is True)
    total_count = sum(1 for r in results.values() if r is not None)

    logger.info(f"\nPassed: {passed_count}/{total_count}")

    if passed_count == total_count:
        logger.info("\n✅ All tests passed! System is ready.")
        return 0
    else:
        logger.warning("\n⚠️  Some tests failed. Check logs above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
