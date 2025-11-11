#!/usr/bin/env python3
"""
NASA Technical Reports Server (NTRS) Downloader

Downloads technical reports relevant to electronics and manufacturing.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
from loguru import logger
from typing import List, Dict
import time


class NASANTRSDownloader:
    """Download NASA technical reports."""

    def __init__(self, output_dir: str = "data/research_papers/nasa"):
        """Initialize downloader."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # NASA NTRS API endpoint
        self.api_base = "https://ntrs.nasa.gov/api/citations"

    def search_reports(self, query: str, max_results: int = 50) -> List[Dict]:
        """
        Search NASA NTRS.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            List of report metadata
        """
        logger.info(f"Searching NASA NTRS: '{query}'")

        params = {
            'q': query,
            'page[size]': min(max_results, 100),
            'sort': '-publicationDate'
        }

        try:
            response = requests.get(f"{self.api_base}/search", params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            results = data.get('results', [])

            logger.info(f"  Found {len(results)} reports")
            return results

        except Exception as e:
            logger.error(f"  Search failed: {e}")
            return []

    def download_report(self, report: Dict) -> bool:
        """
        Download a report PDF.

        Args:
            report: Report metadata

        Returns:
            True if successful
        """
        report_id = report.get('id', 'unknown')
        title = report.get('title', 'Unknown')[:50]  # Truncate for filename

        # Clean title for filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        output_file = self.output_dir / f"{report_id}_{safe_title}.pdf"

        if output_file.exists():
            logger.info(f"  ✅ Already have: {safe_title}")
            return True

        logger.info(f"  ⬇️  Downloading: {title}")

        # Get download URLs from report metadata
        downloads = report.get('downloads', [])

        pdf_url = None
        for download in downloads:
            if download.get('type') == 'application/pdf':
                pdf_url = download.get('links', {}).get('pdf')
                break

        if not pdf_url:
            logger.warning(f"  ⚠️  No PDF available")
            return False

        try:
            response = requests.get(pdf_url, timeout=60, allow_redirects=True)
            response.raise_for_status()

            with open(output_file, 'wb') as f:
                f.write(response.content)

            file_size = output_file.stat().st_size / 1024 / 1024  # MB
            logger.info(f"  ✅ Downloaded: {safe_title} ({file_size:.1f} MB)")

            return True

        except Exception as e:
            logger.error(f"  ❌ Failed: {e}")
            if output_file.exists():
                output_file.unlink()
            return False

    def download_by_topics(self, topics: List[str], max_per_topic: int = 20):
        """
        Download reports for multiple topics.

        Args:
            topics: List of search topics
            max_per_topic: Max reports per topic
        """
        logger.info("="*70)
        logger.info("NASA NTRS DOWNLOADER")
        logger.info("="*70)

        total_downloaded = 0

        for topic in topics:
            logger.info(f"\n{'='*70}")
            logger.info(f"TOPIC: {topic}")
            logger.info(f"{'='*70}")

            reports = self.search_reports(topic, max_results=max_per_topic)

            topic_downloaded = 0

            for i, report in enumerate(reports[:max_per_topic], 1):
                logger.info(f"\n[{i}/{len(reports)}]")

                if self.download_report(report):
                    topic_downloaded += 1
                    total_downloaded += 1

                # Rate limit
                time.sleep(2)

            logger.info(f"\n✅ Downloaded {topic_downloaded} reports for '{topic}'")

        logger.info(f"\n{'='*70}")
        logger.info("DOWNLOAD COMPLETE")
        logger.info(f"{'='*70}")
        logger.info(f"\n✅ Total reports downloaded: {total_downloaded}")
        logger.info(f"📁 Saved to: {self.output_dir}")

        return total_downloaded


def main():
    """Download NASA technical reports."""
    downloader = NASANTRSDownloader()

    # Topics relevant to electronics/manufacturing
    topics = [
        "circuit board failure analysis",
        "electronics reliability",
        "fault detection systems",
        "predictive maintenance",
        "manufacturing quality control",
        "electronic component testing",
        "printed circuit board",
        "soldering defects",
        "power supply design",
        "sensor calibration"
    ]

    downloader.download_by_topics(topics, max_per_topic=10)


if __name__ == "__main__":
    main()
