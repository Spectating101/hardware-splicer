#!/usr/bin/env python3
"""
Download ElectroCom61 PCB Component Dataset.
Dataset: https://data.mendeley.com/datasets/6scy6h8sjz/2
"""

import os
import sys
import zipfile
from pathlib import Path
import requests
from loguru import logger
from tqdm import tqdm

# Mendeley dataset direct download link
# Note: This link expires, you may need to get a fresh one from the website
DATASET_URL = "https://data.mendeley.com/public-files/datasets/6scy6h8sjz/files/9a3f3e34-7c35-4c4a-9a5d-7b9c0f8e1d2f/file_downloaded"

def download_file(url: str, destination: Path):
    """Download file with progress bar."""
    response = requests.get(url, stream=True)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))

    with open(destination, 'wb') as f:
        with tqdm(total=total_size, unit='B', unit_scale=True) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                pbar.update(len(chunk))

def download_electrocom61():
    """Download and extract ElectroCom61 dataset."""

    logger.info("🔍 ElectroCom61 Dataset Downloader")
    logger.info("=" * 60)

    # Setup paths
    project_root = Path(__file__).parent.parent
    dataset_dir = project_root / "datasets" / "electrocom61_full"
    download_dir = project_root / "downloads"

    download_dir.mkdir(exist_ok=True)
    dataset_dir.mkdir(parents=True, exist_ok=True)

    zip_path = download_dir / "electrocom61.zip"

    # Check if already downloaded
    if dataset_dir.exists() and (dataset_dir / "images").exists():
        image_count = len(list((dataset_dir / "images").rglob("*.jpg")))
        if image_count > 1500:
            logger.info(f"✅ Dataset already exists with {image_count} images")
            return str(dataset_dir)

    logger.info("📥 Downloading dataset...")
    logger.warning("⚠️  Manual download required!")
    logger.info("")
    logger.info("Steps:")
    logger.info("1. Visit: https://data.mendeley.com/datasets/6scy6h8sjz/2")
    logger.info("2. Click 'Download all files' button (may require free account)")
    logger.info(f"3. Save ZIP file to: {zip_path}")
    logger.info("4. Run this script again")
    logger.info("")

    if not zip_path.exists():
        logger.error(f"❌ ZIP file not found at {zip_path}")
        logger.info("Please download manually and try again")
        return None

    # Extract
    logger.info(f"📦 Extracting to {dataset_dir}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(dataset_dir)

    logger.info("✅ Dataset extracted successfully!")

    # Verify structure
    required_dirs = ['images', 'labels']
    for dir_name in required_dirs:
        dir_path = dataset_dir / dir_name
        if not dir_path.exists():
            logger.warning(f"⚠️  Missing directory: {dir_name}")

    # Count files
    image_count = len(list((dataset_dir / "images").rglob("*.jpg")))
    label_count = len(list((dataset_dir / "labels").rglob("*.txt")))

    logger.info(f"📊 Dataset stats:")
    logger.info(f"   Images: {image_count}")
    logger.info(f"   Labels: {label_count}")

    return str(dataset_dir)

if __name__ == "__main__":
    try:
        dataset_path = download_electrocom61()
        if dataset_path:
            logger.info(f"\n✅ Dataset ready at: {dataset_path}")
        else:
            logger.error("\n❌ Dataset download failed")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)
