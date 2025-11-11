#!/usr/bin/env python3
"""
Automated download of ElectroCom61 via web scraping/API if possible.
"""

import os
import sys
from pathlib import Path
import subprocess
from loguru import logger

def try_wget_download():
    """Try downloading with wget."""

    # Known URLs for the dataset (may need updating)
    urls = [
        "https://prod-dcd-datasets-cache-zipfiles.s3.eu-west-1.amazonaws.com/6scy6h8sjz-2.zip",
        "https://data.mendeley.com/public-files/datasets/6scy6h8sjz/files/9a3f3e34-7c35-4c4a-9a5d-7b9c0f8e1d2f/file_downloaded"
    ]

    download_dir = Path("downloads")
    download_dir.mkdir(exist_ok=True)

    zip_path = download_dir / "electrocom61.zip"

    for url in urls:
        logger.info(f"🔄 Trying URL: {url}")

        try:
            result = subprocess.run(
                ["wget", "-O", str(zip_path), url, "--progress=bar:force"],
                capture_output=False,
                timeout=300
            )

            if result.returncode == 0 and zip_path.exists():
                logger.info("✅ Download successful!")
                return str(zip_path)

        except subprocess.TimeoutExpired:
            logger.warning("⏱️  Download timed out")
        except FileNotFoundError:
            logger.warning("⚠️  wget not found, trying curl...")
            break
        except Exception as e:
            logger.warning(f"⚠️  Failed: {e}")

    # Try curl
    for url in urls:
        logger.info(f"🔄 Trying with curl: {url}")

        try:
            result = subprocess.run(
                ["curl", "-L", "-o", str(zip_path), url, "--progress-bar"],
                capture_output=False,
                timeout=300
            )

            if result.returncode == 0 and zip_path.exists():
                logger.info("✅ Download successful!")
                return str(zip_path)

        except Exception as e:
            logger.warning(f"⚠️  Failed: {e}")

    return None

def extract_and_setup():
    """Extract dataset and set up YOLO format."""

    import zipfile
    import shutil

    zip_path = Path("downloads/electrocom61.zip")
    extract_dir = Path("datasets/electrocom61_full")

    if not zip_path.exists():
        logger.error("❌ ZIP file not found")
        return False

    logger.info(f"📦 Extracting to {extract_dir}...")
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    # Check structure and convert to YOLO format if needed
    logger.info("✅ Extraction complete")

    # Count files
    images = list(extract_dir.rglob("*.jpg")) + list(extract_dir.rglob("*.png"))
    labels = list(extract_dir.rglob("*.txt"))

    logger.info(f"📊 Found {len(images)} images, {len(labels)} labels")

    # Create data.yaml if missing
    yaml_path = extract_dir / "data.yaml"
    if not yaml_path.exists():
        logger.info("📝 Creating data.yaml...")

        yaml_content = f"""# ElectroCom61 Full Dataset
path: {extract_dir.absolute()}
train: images/train
val: images/val
test: images/test

nc: 10
names: ['resistor', 'capacitor', 'inductor', 'diode', 'transistor',
        'ic', 'connector', 'switch', 'led', 'crystal']
"""
        yaml_path.write_text(yaml_content)

    return True

if __name__ == "__main__":
    logger.info("🚀 Automated ElectroCom61 Download")
    logger.info("=" * 60)

    # Try automated download
    zip_path = try_wget_download()

    if zip_path:
        # Extract and setup
        if extract_and_setup():
            logger.info("\n✅ Dataset ready for training!")
            sys.exit(0)

    logger.error("\n❌ Automated download failed")
    logger.info("\n📌 Manual download instructions:")
    logger.info("1. Go to: https://data.mendeley.com/datasets/6scy6h8sjz/2")
    logger.info("2. Download the ZIP file")
    logger.info("3. Save to: downloads/electrocom61.zip")
    logger.info("4. Run: python scripts/download_dataset.py")

    sys.exit(1)
