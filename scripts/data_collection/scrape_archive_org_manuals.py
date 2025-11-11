#!/usr/bin/env python3
"""
Archive.org Manual Scraper

Downloads technical manuals from Archive.org public domain collections.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
from loguru import logger
from typing import List, Dict
import time
import json


class ArchiveOrgScraper:
    """Scrape technical manuals from Archive.org."""

    def __init__(self, output_dir: str = "data/manuals"):
        """Initialize scraper."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.api_base = "https://archive.org"

    def search_manuals(self, query: str, max_results: int = 100) -> List[Dict]:
        """
        Search Archive.org for manuals.

        Args:
            query: Search query (e.g., "electronics manual")
            max_results: Maximum results to return

        Returns:
            List of items with metadata
        """
        logger.info(f"Searching Archive.org: '{query}'")

        # Archive.org Advanced Search API
        search_url = f"{self.api_base}/advancedsearch.php"

        params = {
            'q': query,
            'fl[]': ['identifier', 'title', 'creator', 'date', 'format'],
            'sort[]': 'downloads desc',  # Most popular first
            'rows': max_results,
            'page': 1,
            'output': 'json'
        }

        try:
            response = requests.get(search_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            docs = data.get('response', {}).get('docs', [])

            logger.info(f"  Found {len(docs)} items")
            return docs

        except Exception as e:
            logger.error(f"  Search failed: {e}")
            return []

    def get_item_files(self, identifier: str) -> List[Dict]:
        """
        Get downloadable files for an item.

        Args:
            identifier: Archive.org item identifier

        Returns:
            List of files with download URLs
        """
        metadata_url = f"{self.api_base}/metadata/{identifier}"

        try:
            response = requests.get(metadata_url, timeout=30)
            response.raise_for_status()

            data = response.json()
            files = data.get('files', [])

            # Filter for PDFs
            pdf_files = [
                f for f in files
                if f.get('format') == 'Text PDF' or f.get('name', '').endswith('.pdf')
            ]

            return pdf_files

        except Exception as e:
            logger.error(f"  Failed to get files for {identifier}: {e}")
            return []

    def download_file(self, identifier: str, filename: str, output_path: Path) -> bool:
        """
        Download a file from Archive.org.

        Args:
            identifier: Item identifier
            filename: File name
            output_path: Where to save

        Returns:
            True if successful
        """
        if output_path.exists():
            logger.info(f"  ✅ Already have: {output_path.name}")
            return True

        download_url = f"{self.api_base}/download/{identifier}/{filename}"

        logger.info(f"  ⬇️  Downloading: {filename}")

        try:
            response = requests.get(download_url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            block_size = 1024 * 1024  # 1MB

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_size > 0:
                            percent = downloaded / total_size * 100

                            # Log every 10%
                            if downloaded % (10 * block_size) == 0:
                                logger.info(f"     {percent:.1f}% ({downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB)")

            logger.info(f"  ✅ Downloaded: {output_path.name}")
            return True

        except Exception as e:
            logger.error(f"  ❌ Download failed: {e}")
            if output_path.exists():
                output_path.unlink()
            return False

    def download_collection(self, collection_name: str, max_items: int = 50):
        """
        Download items from a specific collection.

        Args:
            collection_name: Collection identifier (e.g., "bitsavers")
            max_items: Maximum items to download
        """
        logger.info(f"Downloading from collection: {collection_name}")

        # Search within collection
        query = f"collection:{collection_name} AND format:pdf"
        items = self.search_manuals(query, max_results=max_items)

        collection_dir = self.output_dir / collection_name
        collection_dir.mkdir(parents=True, exist_ok=True)

        successful = 0

        for item in items[:max_items]:
            identifier = item.get('identifier')
            title = item.get('title', identifier)

            logger.info(f"\nProcessing: {title}")
            logger.info(f"  ID: {identifier}")

            # Get files
            files = self.get_item_files(identifier)

            if not files:
                logger.warning(f"  No PDF files found")
                continue

            # Download first PDF only (usually the main document)
            pdf_file = files[0]
            filename = pdf_file.get('name')

            output_path = collection_dir / filename

            if self.download_file(identifier, filename, output_path):
                successful += 1

            # Rate limit
            time.sleep(2)

        logger.info(f"\n✅ Downloaded {successful}/{len(items)} manuals from {collection_name}")
        return successful


def main():
    """Download manuals from Archive.org."""
    logger.info("="*70)
    logger.info("ARCHIVE.ORG MANUAL DOWNLOADER")
    logger.info("="*70)

    scraper = ArchiveOrgScraper()

    # Priority collections for electronics/industrial
    collections = [
        {
            'name': 'bitsavers_attdatashe',  # AT&T datasheets and manuals
            'max_items': 20,
            'description': 'AT&T technical documentation'
        },
        {
            'name': 'manuals',  # General manuals collection
            'max_items': 30,
            'description': 'General electronics manuals'
        }
    ]

    total_downloaded = 0

    for collection in collections:
        logger.info(f"\n{'='*70}")
        logger.info(f"COLLECTION: {collection['description']}")
        logger.info(f"{'='*70}")

        count = scraper.download_collection(
            collection['name'],
            max_items=collection['max_items']
        )

        total_downloaded += count

    # Also search for specific topics
    logger.info(f"\n{'='*70}")
    logger.info("TOPICAL SEARCHES")
    logger.info(f"{'='*70}")

    topics = [
        "electronics repair manual",
        "oscilloscope manual",
        "multimeter manual",
        "PLC programming manual",
        "circuit board repair"
    ]

    topic_dir = scraper.output_dir / "topical"
    topic_dir.mkdir(parents=True, exist_ok=True)

    for topic in topics:
        logger.info(f"\n🔍 Searching: {topic}")

        items = scraper.search_manuals(topic, max_results=5)

        for item in items[:5]:
            identifier = item.get('identifier')
            title = item.get('title', identifier)

            logger.info(f"\n  Processing: {title}")

            files = scraper.get_item_files(identifier)

            if files:
                pdf_file = files[0]
                filename = f"{identifier}_{pdf_file.get('name')}"
                output_path = topic_dir / filename

                if scraper.download_file(identifier, pdf_file.get('name'), output_path):
                    total_downloaded += 1

            time.sleep(2)

    # Summary
    logger.info(f"\n{'='*70}")
    logger.info("DOWNLOAD COMPLETE")
    logger.info(f"{'='*70}")
    logger.info(f"\n📊 Total manuals downloaded: {total_downloaded}")
    logger.info(f"📁 Saved to: {scraper.output_dir}")

    logger.info(f"\n💡 Next Steps:")
    logger.info(f"   1. Extract text from PDFs")
    logger.info(f"   2. Parse for technical content")
    logger.info(f"   3. Add to knowledge base")


if __name__ == "__main__":
    main()
