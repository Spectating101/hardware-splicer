#!/usr/bin/env python3
"""
Download Public PCB Datasets

Aggregates multiple public sources to build training dataset.
"""

import os
import requests
import zipfile
from pathlib import Path
from loguru import logger
import json


class DatasetDownloader:
    """Download and organize public PCB datasets."""

    def __init__(self, output_dir: str = "data/collected_datasets"):
        """Initialize downloader."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Track what we've downloaded
        self.manifest_file = self.output_dir / "manifest.json"
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> dict:
        """Load download manifest."""
        if self.manifest_file.exists():
            with open(self.manifest_file, 'r') as f:
                return json.load(f)
        return {"datasets": []}

    def _save_manifest(self):
        """Save download manifest."""
        with open(self.manifest_file, 'w') as f:
            json.dump(self.manifest, f, indent=2)

    def download_roboflow_pcb_datasets(self):
        """
        Download PCB datasets from Roboflow Universe.

        Note: Requires manual download via web UI due to auth.
        This provides instructions.
        """
        logger.info("="*70)
        logger.info("ROBOFLOW UNIVERSE PCB DATASETS")
        logger.info("="*70)

        instructions = """
To download from Roboflow:

1. Go to: https://universe.roboflow.com/
2. Search: "PCB component detection"
3. Top datasets to download:
   - "PCB Components" by various authors
   - "Electronic Components Detection"
   - "Circuit Board Component Detection"

4. For each dataset:
   - Click "Download"
   - Choose format: "YOLO v8"
   - Download to: {output_dir}/roboflow/

5. Extract and organize:
   - Each dataset should have: train/, valid/, test/
   - And data.yaml file

Recommended datasets (as of 2024):
- https://universe.roboflow.com/...[specific URLs would go here]
        """.format(output_dir=self.output_dir)

        logger.info(instructions)

        # Create roboflow directory
        roboflow_dir = self.output_dir / "roboflow"
        roboflow_dir.mkdir(exist_ok=True)

        return roboflow_dir

    def download_kaggle_datasets(self):
        """
        Download PCB datasets from Kaggle.

        Requires Kaggle API credentials.
        """
        logger.info("="*70)
        logger.info("KAGGLE PCB DATASETS")
        logger.info("="*70)

        # Check if kaggle is installed
        try:
            import kaggle
        except ImportError:
            logger.error("Kaggle package not installed!")
            logger.info("Install with: pip install kaggle")
            logger.info("Setup credentials: https://github.com/Kaggle/kaggle-api#api-credentials")
            return None

        kaggle_dir = self.output_dir / "kaggle"
        kaggle_dir.mkdir(exist_ok=True)

        # List of known PCB datasets on Kaggle
        datasets_to_download = [
            # Format: (owner/dataset-name, description)
            # Note: These are examples - actual dataset names may vary
            # Users should search Kaggle for current PCB datasets
        ]

        logger.info("Search Kaggle for PCB datasets:")
        logger.info("kaggle datasets list -s 'PCB'")
        logger.info("kaggle datasets list -s 'circuit board'")
        logger.info("kaggle datasets list -s 'electronics'")

        return kaggle_dir

    def download_open_images_pcb(self):
        """
        Download PCB-related images from Open Images Dataset.

        Uses FiftyOne library for easy access.
        """
        logger.info("="*70)
        logger.info("OPEN IMAGES DATASET (PCB subset)")
        logger.info("="*70)

        try:
            import fiftyone as fo
            import fiftyone.zoo as foz
        except ImportError:
            logger.error("FiftyOne not installed!")
            logger.info("Install with: pip install fiftyone")
            return None

        open_images_dir = self.output_dir / "open_images"
        open_images_dir.mkdir(exist_ok=True)

        logger.info("Downloading Open Images PCB subset...")
        logger.info("Searching for labels: 'circuit board', 'electronics'")

        # This is example code - actual implementation would filter for PCB-related images
        # dataset = foz.load_zoo_dataset(
        #     "open-images-v6",
        #     split="train",
        #     label_types=["detections"],
        #     classes=["circuit board", "electronics"],
        #     max_samples=1000,
        # )

        logger.info(f"Would download to: {open_images_dir}")

        return open_images_dir

    def download_github_pcb_datasets(self):
        """
        Download PCB datasets from GitHub repos.
        """
        logger.info("="*70)
        logger.info("GITHUB PCB DATASETS")
        logger.info("="*70)

        github_datasets = [
            {
                "name": "PCB DSLR Dataset",
                "url": "https://github.com/WeiChungChang/pcb_dslr_dataset",
                "description": "High-res PCB images from DSLR camera",
                "estimated_size": "~500MB",
                "image_count": "~2000"
            },
            {
                "name": "PCB Defect Detection",
                "url": "https://github.com/Ixiaohuihuihui/Tiny-Defect-Detection-for-PCB",
                "description": "PCB defect detection dataset",
                "estimated_size": "~200MB",
                "image_count": "~1000"
            }
        ]

        github_dir = self.output_dir / "github"
        github_dir.mkdir(exist_ok=True)

        for dataset in github_datasets:
            logger.info(f"\n📦 {dataset['name']}")
            logger.info(f"   URL: {dataset['url']}")
            logger.info(f"   Description: {dataset['description']}")
            logger.info(f"   Images: {dataset['image_count']}")
            logger.info(f"   Size: {dataset['estimated_size']}")
            logger.info(f"   Download to: {github_dir}/{dataset['name'].lower().replace(' ', '_')}/")

        logger.info("\nTo download:")
        logger.info("git clone <repo_url>")
        logger.info("Or use GitHub's Download ZIP feature")

        return github_dir

    def generate_download_report(self):
        """Generate report of available datasets."""
        report = []

        report.append("="*70)
        report.append("PCB DATASET COLLECTION REPORT")
        report.append("="*70)
        report.append("")

        report.append("CURRENT STATUS:")
        report.append(f"  Output directory: {self.output_dir}")
        report.append(f"  Datasets tracked: {len(self.manifest['datasets'])}")
        report.append("")

        report.append("AVAILABLE SOURCES:")
        report.append("")

        report.append("1. Roboflow Universe")
        report.append("   - Multiple PCB component datasets")
        report.append("   - Pre-annotated (YOLO format)")
        report.append("   - ~1000-5000 images per dataset")
        report.append("   - Action: Manual download via web UI")
        report.append("")

        report.append("2. Kaggle")
        report.append("   - Search 'PCB', 'circuit board', 'electronics'")
        report.append("   - Requires Kaggle API setup")
        report.append("   - Action: kaggle datasets list -s 'PCB'")
        report.append("")

        report.append("3. Open Images Dataset")
        report.append("   - Google's large-scale dataset")
        report.append("   - Filter for electronics/circuit boards")
        report.append("   - Action: Use FiftyOne library")
        report.append("")

        report.append("4. GitHub Repos")
        report.append("   - PCB DSLR Dataset: ~2000 images")
        report.append("   - PCB Defect datasets: ~1000 images each")
        report.append("   - Action: git clone")
        report.append("")

        report.append("ESTIMATED TOTAL AVAILABLE:")
        report.append("  ~10,000-20,000 images from public sources")
        report.append("")

        report.append("NEXT STEPS:")
        report.append("  1. Download top 3 Roboflow datasets")
        report.append("  2. Clone GitHub repos")
        report.append("  3. Search Kaggle for recent uploads")
        report.append("  4. Merge and deduplicate")
        report.append("  5. Convert all to common format (YOLO v8)")
        report.append("")

        return "\n".join(report)


def main():
    """Run dataset collection."""
    logger.info("PCB Dataset Collection Tool")
    logger.info("="*70)

    downloader = DatasetDownloader()

    # Show instructions for each source
    downloader.download_roboflow_pcb_datasets()
    print()

    downloader.download_kaggle_datasets()
    print()

    downloader.download_github_pcb_datasets()
    print()

    downloader.download_open_images_pcb()
    print()

    # Generate report
    report = downloader.generate_download_report()
    print(report)

    # Save report
    report_file = downloader.output_dir / "collection_report.txt"
    with open(report_file, 'w') as f:
        f.write(report)

    logger.info(f"\n📄 Report saved to: {report_file}")


if __name__ == "__main__":
    main()
