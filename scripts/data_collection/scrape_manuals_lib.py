#!/usr/bin/env python3
"""
ManualsLib Scraper

Scrapes electronics manuals from ManualsLib.com (1.6M+ manuals).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
from loguru import logger
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import time
import re


class ManualsLibScraper:
    """Scrape manuals from ManualsLib."""

    def __init__(self, output_dir: str = "data/manuals/manualslib"):
        """Initialize scraper."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.base_url = "https://www.manualslib.com"

        # Headers to avoid being blocked
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def search_manuals(self, query: str, max_results: int = 50) -> List[Dict]:
        """
        Search for manuals.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of manual metadata
        """
        logger.info(f"Searching ManualsLib: '{query}'")

        search_url = f"{self.base_url}/search.php"
        params = {
            'q': query,
            'search_type': 'manuals'
        }

        try:
            response = requests.get(search_url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Parse search results
            results = []
            manual_items = soup.find_all('div', class_='item-manual')

            for item in manual_items[:max_results]:
                try:
                    # Extract manual link
                    link_elem = item.find('a', href=True)
                    if not link_elem:
                        continue

                    manual_url = self.base_url + link_elem['href']
                    title = link_elem.get_text(strip=True)

                    # Extract brand
                    brand_elem = item.find('span', class_='brand')
                    brand = brand_elem.get_text(strip=True) if brand_elem else "Unknown"

                    results.append({
                        'title': title,
                        'brand': brand,
                        'url': manual_url
                    })

                except Exception as e:
                    logger.warning(f"  Failed to parse item: {e}")
                    continue

            logger.info(f"  Found {len(results)} manuals")
            return results

        except Exception as e:
            logger.error(f"  Search failed: {e}")
            return []

    def get_download_link(self, manual_url: str) -> Optional[str]:
        """
        Get PDF download link from manual page.

        Args:
            manual_url: Manual page URL

        Returns:
            Download URL or None
        """
        try:
            response = requests.get(manual_url, headers=self.headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for download button
            download_btn = soup.find('a', class_='btn-download')
            if download_btn and download_btn.get('href'):
                download_url = download_btn['href']

                # Make absolute URL
                if download_url.startswith('/'):
                    download_url = self.base_url + download_url

                return download_url

            # Alternative: look for PDF link
            pdf_link = soup.find('a', href=re.compile(r'\.pdf$', re.I))
            if pdf_link:
                pdf_url = pdf_link['href']
                if pdf_url.startswith('/'):
                    pdf_url = self.base_url + pdf_url
                return pdf_url

            return None

        except Exception as e:
            logger.warning(f"  Failed to get download link: {e}")
            return None

    def download_manual(self, manual: Dict) -> bool:
        """
        Download a manual.

        Args:
            manual: Manual metadata

        Returns:
            True if successful
        """
        title = manual['title']
        brand = manual['brand']
        url = manual['url']

        # Create safe filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_brand = "".join(c for c in brand if c.isalnum() or c in (' ', '-', '_')).rstrip()

        output_file = self.output_dir / f"{safe_brand}_{safe_title}.pdf"

        if output_file.exists():
            logger.info(f"  ✅ Already have: {title}")
            return True

        logger.info(f"  ⬇️  Downloading: {brand} - {title}")

        # Get download link
        download_url = self.get_download_link(url)

        if not download_url:
            logger.warning(f"  ⚠️  No download link found")
            return False

        try:
            response = requests.get(download_url, headers=self.headers, timeout=60, allow_redirects=True)
            response.raise_for_status()

            # Check if it's actually a PDF
            content_type = response.headers.get('content-type', '')
            if 'pdf' not in content_type.lower() and not response.content.startswith(b'%PDF'):
                logger.warning(f"  ⚠️  Not a PDF")
                return False

            with open(output_file, 'wb') as f:
                f.write(response.content)

            file_size = output_file.stat().st_size / 1024 / 1024  # MB
            logger.info(f"  ✅ Downloaded: {title} ({file_size:.1f} MB)")

            return True

        except Exception as e:
            logger.error(f"  ❌ Failed: {e}")
            if output_file.exists():
                output_file.unlink()
            return False

    def scrape_category(self, category: str, max_manuals: int = 30):
        """
        Scrape manuals from a category.

        Args:
            category: Search category/query
            max_manuals: Maximum manuals to download
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"CATEGORY: {category}")
        logger.info(f"{'='*70}")

        manuals = self.search_manuals(category, max_results=max_manuals)

        successful = 0

        for i, manual in enumerate(manuals[:max_manuals], 1):
            logger.info(f"\n[{i}/{len(manuals)}]")

            if self.download_manual(manual):
                successful += 1

            # Rate limit - be very respectful
            time.sleep(3)

        logger.info(f"\n✅ Downloaded {successful}/{len(manuals)} manuals from '{category}'")
        return successful


def main():
    """Scrape ManualsLib."""
    logger.info("="*70)
    logger.info("MANUALSLIB SCRAPER")
    logger.info("="*70)
    logger.info("\n⚠️  Rate limiting: 3 seconds between downloads")
    logger.info("⚠️  Being respectful to avoid blocking")

    scraper = ManualsLibScraper()

    # Categories relevant to electronics
    categories = [
        "oscilloscope",
        "multimeter",
        "power supply",
        "circuit board",
        "soldering station",
        "function generator",
        "spectrum analyzer",
        "logic analyzer",
        "benchtop equipment",
        "test equipment"
    ]

    total_downloaded = 0

    for category in categories:
        count = scraper.scrape_category(category, max_manuals=10)
        total_downloaded += count

    logger.info(f"\n{'='*70}")
    logger.info("SCRAPING COMPLETE")
    logger.info(f"{'='*70}")
    logger.info(f"\n✅ Total manuals downloaded: {total_downloaded}")
    logger.info(f"📁 Saved to: {scraper.output_dir}")


if __name__ == "__main__":
    main()
