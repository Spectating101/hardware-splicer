#!/usr/bin/env python3
"""
IMMEDIATE DOWNLOAD - Start collecting data NOW

Downloads legal sources in parallel.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from loguru import logger
import time
from concurrent.futures import ThreadPoolExecutor


def download_file(url: str, output_path: Path, description: str):
    """Download a file with progress."""
    if output_path.exists():
        logger.info(f"✅ Already have: {output_path.name}")
        return output_path

    logger.info(f"⬇️  Downloading: {description}")
    logger.info(f"   URL: {url}")
    logger.info(f"   Target: {output_path}")

    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        block_size = 1024 * 1024  # 1MB chunks

        with open(output_path, 'wb') as f:
            start_time = time.time()
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total_size > 0:
                        percent = downloaded / total_size * 100
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed / 1024 / 1024  # MB/s

                        if downloaded % (10 * block_size) == 0:  # Log every 10MB
                            logger.info(f"   Progress: {percent:.1f}% ({downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB) - {speed:.1f} MB/s")

        logger.info(f"   ✅ Downloaded: {output_path.name} ({total_size/1024/1024:.1f}MB)")
        return output_path

    except Exception as e:
        logger.error(f"   ❌ Failed: {e}")
        if output_path.exists():
            output_path.unlink()  # Delete partial download
        return None


def download_stackexchange_site(site_name: str, output_dir: Path):
    """Download a Stack Exchange site dump."""
    # Note: Archive.org URLs for SE dumps
    # Format: https://archive.org/download/stackexchange/{site}.7z

    url = f"https://archive.org/download/stackexchange/{site_name}.7z"
    output_file = output_dir / f"{site_name}.7z"

    return download_file(url, output_file, f"Stack Exchange: {site_name}")


def main():
    """Start downloading everything legal."""
    logger.info("="*70)
    logger.info("IMMEDIATE DATA COLLECTION - STARTING NOW")
    logger.info("="*70)

    base_dir = Path("data")

    # Create directories
    se_dir = base_dir / "stackexchange"
    manuals_dir = base_dir / "manuals"
    papers_dir = base_dir / "research_papers"

    se_dir.mkdir(parents=True, exist_ok=True)
    manuals_dir.mkdir(parents=True, exist_ok=True)
    papers_dir.mkdir(parents=True, exist_ok=True)

    # Priority 1: Stack Exchange sites (LEGAL - CC-BY-SA)
    logger.info("\n📚 PRIORITY 1: Stack Exchange Dumps (Legal)")
    logger.info("   License: CC-BY-SA")
    logger.info("   Size: ~500MB-2GB per site")

    se_sites = [
        "electronics.stackexchange.com",
        "arduino.stackexchange.com",
        "raspberrypi.stackexchange.com",
        "diy.stackexchange.com",
    ]

    logger.info(f"   Downloading {len(se_sites)} sites...")

    # Download Stack Exchange sites in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(download_stackexchange_site, site, se_dir)
            for site in se_sites
        ]

        results = [f.result() for f in futures]

    successful = [r for r in results if r is not None]
    logger.info(f"\n✅ Downloaded {len(successful)}/{len(se_sites)} Stack Exchange sites")

    # Next: Download some sample manuals from Archive.org
    logger.info("\n📖 PRIORITY 2: Sample Manuals from Archive.org")

    # Some known Archive.org manual collections
    sample_manuals = [
        ("https://archive.org/download/bitsavers_attdatashe_23M/1989_ATT_Data_Communications_Products.pdf",
         manuals_dir / "ATT_DataComm_1989.pdf",
         "AT&T Data Communications Manual"),
    ]

    for url, output, desc in sample_manuals:
        download_file(url, output, desc)

    # Summary
    logger.info("\n" + "="*70)
    logger.info("DOWNLOAD SESSION COMPLETE")
    logger.info("="*70)
    logger.info(f"\n📊 Results:")
    logger.info(f"   Stack Exchange sites: {len(successful)}")
    logger.info(f"   Location: {se_dir}")

    logger.info(f"\n📝 Next Steps:")
    logger.info(f"   1. Extract .7z files: py7zr x <file>.7z")
    logger.info(f"   2. Parse Posts.xml from each site")
    logger.info(f"   3. Extract Q&A pairs into JSON")

    logger.info(f"\n💡 Quick Extract Command:")
    logger.info(f"   cd {se_dir}")
    logger.info(f"   for f in *.7z; do py7zr x \"$f\"; done")


if __name__ == "__main__":
    main()
