#!/usr/bin/env python3
"""Extract Stack Exchange .7z files."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import py7zr
from loguru import logger


def main():
    """Extract all .7z files in data/stackexchange."""
    se_dir = Path("data/stackexchange")

    logger.info("Extracting Stack Exchange dumps...")

    archives = list(se_dir.glob("*.7z"))

    if not archives:
        logger.error("No .7z files found!")
        return

    for archive in archives:
        extract_dir = se_dir / archive.stem

        if extract_dir.exists():
            logger.info(f"✅ Already extracted: {archive.name}")
            continue

        logger.info(f"⬇️  Extracting: {archive.name}")
        logger.info(f"   Size: {archive.stat().st_size / 1024 / 1024:.1f} MB")
        logger.info(f"   Target: {extract_dir}")

        try:
            with py7zr.SevenZipFile(archive, mode='r') as z:
                z.extractall(path=extract_dir)

            logger.info(f"   ✅ Extracted successfully")

        except Exception as e:
            logger.error(f"   ❌ Failed: {e}")

    logger.info("\n✅ Extraction complete!")


if __name__ == "__main__":
    main()
