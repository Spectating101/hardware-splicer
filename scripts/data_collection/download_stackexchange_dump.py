#!/usr/bin/env python3
"""
Download Stack Exchange Data Dump

Legally downloads Stack Exchange Q&A (CC-BY-SA licensed)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
from loguru import logger
import xml.etree.ElementTree as ET
from typing import List, Dict
import json


class StackExchangeDownloader:
    """Download Stack Exchange data dumps."""

    def __init__(self, output_dir: str = "data/stackexchange"):
        """Initialize downloader."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Archive.org base URL for Stack Exchange dumps
        self.archive_base = "https://archive.org/download/stackexchange"

    def list_available_sites(self) -> List[str]:
        """List relevant Stack Exchange sites for electronics/engineering."""
        relevant_sites = [
            "electronics.stackexchange.com",  # Electronics & Electrical Engineering
            "diy.stackexchange.com",  # DIY & Home Improvement
            "engineering.stackexchange.com",  # Engineering
            "arduino.stackexchange.com",  # Arduino
            "raspberrypi.stackexchange.com",  # Raspberry Pi
            "robotics.stackexchange.com",  # Robotics
        ]

        return relevant_sites

    def download_site_dump(self, site: str):
        """
        Download Stack Exchange site dump.

        Args:
            site: Site domain (e.g., "electronics.stackexchange.com")
        """
        logger.info(f"Downloading {site} dump...")

        # Stack Exchange dumps are named like: electronics.stackexchange.com.7z
        archive_name = f"{site}.7z"
        url = f"{self.archive_base}/{archive_name}"

        output_file = self.output_dir / archive_name

        if output_file.exists():
            logger.info(f"  Already downloaded: {output_file}")
            return output_file

        logger.info(f"  URL: {url}")
        logger.info(f"  Size: ~500MB-2GB (varies by site)")
        logger.info(f"  This will take a while...")

        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            block_size = 8192
            downloaded = 0

            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total_size:
                        percent = downloaded / total_size * 100
                        logger.info(f"  Downloaded: {percent:.1f}%")

            logger.info(f"  ✅ Downloaded to: {output_file}")
            return output_file

        except Exception as e:
            logger.error(f"  ❌ Error downloading: {e}")
            return None

    def extract_7z(self, archive_file: Path):
        """
        Extract .7z archive.

        Requires 7z command-line tool.
        """
        try:
            import py7zr
        except ImportError:
            logger.error("py7zr not installed!")
            logger.info("Install with: pip install py7zr")
            logger.info("Or use 7z command: 7z x " + str(archive_file))
            return None

        extract_dir = archive_file.parent / archive_file.stem

        if extract_dir.exists():
            logger.info(f"  Already extracted: {extract_dir}")
            return extract_dir

        logger.info(f"Extracting {archive_file.name}...")

        with py7zr.SevenZipFile(archive_file, mode='r') as archive:
            archive.extractall(path=extract_dir)

        logger.info(f"  ✅ Extracted to: {extract_dir}")
        return extract_dir

    def parse_posts_xml(self, posts_xml: Path, max_posts: int = 1000) -> List[Dict]:
        """
        Parse Posts.xml to extract Q&A.

        Args:
            posts_xml: Path to Posts.xml
            max_posts: Maximum posts to parse

        Returns:
            List of questions with answers
        """
        logger.info(f"Parsing {posts_xml.name}...")

        questions = {}
        answers = []

        # Parse XML
        tree = ET.parse(posts_xml)
        root = tree.getroot()

        count = 0
        for row in root.findall('row'):
            if count >= max_posts:
                break

            post_type = row.get('PostTypeId')

            # 1 = Question, 2 = Answer
            if post_type == '1':
                # Question
                questions[row.get('Id')] = {
                    'id': row.get('Id'),
                    'title': row.get('Title', ''),
                    'body': row.get('Body', ''),
                    'tags': row.get('Tags', ''),
                    'score': int(row.get('Score', 0)),
                    'answers': []
                }

            elif post_type == '2':
                # Answer
                parent_id = row.get('ParentId')
                answers.append({
                    'parent_id': parent_id,
                    'body': row.get('Body', ''),
                    'score': int(row.get('Score', 0)),
                    'accepted': row.get('Id') == row.get('AcceptedAnswerId', '')
                })

            count += 1

        # Link answers to questions
        for answer in answers:
            parent_id = answer['parent_id']
            if parent_id in questions:
                questions[parent_id]['answers'].append(answer)

        # Convert to list
        qa_pairs = list(questions.values())

        logger.info(f"  Parsed {len(qa_pairs)} questions with {len(answers)} answers")

        return qa_pairs

    def save_qa_json(self, qa_pairs: List[Dict], output_file: Path):
        """Save Q&A to JSON."""
        with open(output_file, 'w') as f:
            json.dump(qa_pairs, f, indent=2)

        logger.info(f"  Saved to: {output_file}")


def main():
    """Download Stack Exchange dumps."""
    logger.info("Stack Exchange Data Dump Downloader")
    logger.info("="*70)
    logger.info("License: CC-BY-SA (legal to use)")
    logger.info("="*70)

    downloader = StackExchangeDownloader()

    # List sites
    sites = downloader.list_available_sites()

    logger.info("\nRelevant Stack Exchange sites:")
    for i, site in enumerate(sites, 1):
        logger.info(f"  {i}. {site}")

    logger.info("\nTo download:")
    logger.info("1. Choose a site (e.g., electronics.stackexchange.com)")
    logger.info("2. Run: downloader.download_site_dump('electronics.stackexchange.com')")
    logger.info("3. Extract: downloader.extract_7z(archive_file)")
    logger.info("4. Parse: downloader.parse_posts_xml(posts_xml_path)")

    # Example workflow
    logger.info("\n" + "="*70)
    logger.info("EXAMPLE: Download Electronics Stack Exchange")
    logger.info("="*70)

    example = """
from scripts.data_collection.download_stackexchange_dump import StackExchangeDownloader

downloader = StackExchangeDownloader()

# Download
archive = downloader.download_site_dump('electronics.stackexchange.com')

# Extract
extracted_dir = downloader.extract_7z(archive)

# Parse Q&A
posts_xml = extracted_dir / 'Posts.xml'
qa_pairs = downloader.parse_posts_xml(posts_xml, max_posts=10000)

# Save
downloader.save_qa_json(qa_pairs, Path('data/electronics_qa.json'))

print(f"Extracted {len(qa_pairs)} Q&A pairs")
"""

    print(example)


if __name__ == "__main__":
    main()
