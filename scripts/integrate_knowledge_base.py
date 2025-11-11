#!/usr/bin/env python3
"""
Knowledge Base Integration

Integrates all collected data into the Circuit.AI knowledge base.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from loguru import logger
from typing import Dict, List


class KnowledgeBaseIntegrator:
    """Integrate collected data into knowledge base."""

    def __init__(self):
        """Initialize integrator."""
        self.fault_patterns_dir = Path("data/processed/fault_patterns")
        self.pinouts_dir = Path("data/extracted_pinouts")
        self.kb_dir = Path("data/knowledge_base")
        self.kb_dir.mkdir(parents=True, exist_ok=True)

    def load_fault_patterns(self) -> List[Dict]:
        """Load all fault patterns."""
        logger.info("Loading fault patterns...")

        fault_file = self.fault_patterns_dir / "all_fault_patterns.json"

        if not fault_file.exists():
            logger.error(f"Fault patterns not found: {fault_file}")
            return []

        with open(fault_file, 'r') as f:
            patterns = json.load(f)

        logger.info(f"  Loaded {len(patterns)} fault patterns")

        return patterns

    def load_pinouts(self) -> Dict:
        """Load all IC pinouts."""
        logger.info("Loading IC pinouts...")

        if not self.pinouts_dir.exists():
            logger.warning("No pinouts directory found")
            return {}

        pinouts = {}

        for pinout_file in self.pinouts_dir.glob("*_pinout.json"):
            with open(pinout_file, 'r') as f:
                pinout = json.load(f)

            ic_name = pinout.get('ic_name')
            if ic_name:
                pinouts[ic_name] = pinout

        logger.info(f"  Loaded {len(pinouts)} IC pinouts")

        return pinouts

    def categorize_fault_patterns(self, patterns: List[Dict]) -> Dict:
        """
        Categorize fault patterns by component type.

        Args:
            patterns: List of fault patterns

        Returns:
            Categorized patterns
        """
        logger.info("Categorizing fault patterns...")

        categories = {
            'power_supply': [],
            'microcontroller': [],
            'communication': [],
            'sensors': [],
            'general': []
        }

        # Keywords for categorization
        power_keywords = ['power', 'voltage', 'regulator', '5v', '3.3v', 'supply', 'battery']
        mcu_keywords = ['atmega', 'esp', 'stm32', 'pic', 'microcontroller', 'bootloader', 'programming']
        comm_keywords = ['usb', 'serial', 'uart', 'i2c', 'spi', 'communication', 'ch340', 'ft232']
        sensor_keywords = ['sensor', 'dht', 'bmp', 'temperature', 'humidity', 'pressure']

        for pattern in patterns:
            title = pattern.get('title', '').lower()
            symptoms = ' '.join(pattern.get('symptoms', [])).lower()
            components = ' '.join(pattern.get('affected_components', [])).lower()

            text = f"{title} {symptoms} {components}"

            categorized = False

            if any(keyword in text for keyword in power_keywords):
                categories['power_supply'].append(pattern)
                categorized = True

            if any(keyword in text for keyword in mcu_keywords):
                categories['microcontroller'].append(pattern)
                categorized = True

            if any(keyword in text for keyword in comm_keywords):
                categories['communication'].append(pattern)
                categorized = True

            if any(keyword in text for keyword in sensor_keywords):
                categories['sensors'].append(pattern)
                categorized = True

            if not categorized:
                categories['general'].append(pattern)

        for category, items in categories.items():
            logger.info(f"  {category}: {len(items)} patterns")

        return categories

    def create_search_index(self, patterns: List[Dict]) -> Dict:
        """
        Create search index for fault patterns.

        Args:
            patterns: List of fault patterns

        Returns:
            Search index mapping symptoms to patterns
        """
        logger.info("Creating search index...")

        index = {}

        for i, pattern in enumerate(patterns):
            # Index by symptoms
            for symptom in pattern.get('symptoms', []):
                # Extract keywords
                words = symptom.lower().split()

                for word in words:
                    if len(word) > 3:  # Skip short words
                        if word not in index:
                            index[word] = []

                        if i not in index[word]:
                            index[word].append(i)

        logger.info(f"  Created index with {len(index)} keywords")

        return index

    def generate_knowledge_base(self):
        """Generate complete knowledge base."""
        logger.info("="*70)
        logger.info("KNOWLEDGE BASE INTEGRATION")
        logger.info("="*70)

        # Load all data
        fault_patterns = self.load_fault_patterns()
        pinouts = self.load_pinouts()

        # Categorize
        categorized_patterns = self.categorize_fault_patterns(fault_patterns)

        # Create search index
        search_index = self.create_search_index(fault_patterns)

        # Build knowledge base
        knowledge_base = {
            'version': '1.0',
            'generated_at': '2025-10-19',
            'statistics': {
                'total_fault_patterns': len(fault_patterns),
                'total_ic_pinouts': len(pinouts),
                'categories': {k: len(v) for k, v in categorized_patterns.items()}
            },
            'fault_patterns': fault_patterns,
            'categorized_patterns': categorized_patterns,
            'ic_pinouts': pinouts,
            'search_index': search_index
        }

        # Save knowledge base
        kb_file = self.kb_dir / "complete_knowledge_base.json"

        with open(kb_file, 'w') as f:
            json.dump(knowledge_base, f, indent=2)

        logger.info(f"\n✅ Knowledge base saved to: {kb_file}")
        logger.info(f"📊 Size: {kb_file.stat().st_size / 1024 / 1024:.1f} MB")

        # Create compact version (without full text)
        compact_kb = {
            'version': knowledge_base['version'],
            'statistics': knowledge_base['statistics'],
            'search_index': search_index
        }

        compact_file = self.kb_dir / "knowledge_base_compact.json"

        with open(compact_file, 'w') as f:
            json.dump(compact_kb, f, indent=2)

        logger.info(f"✅ Compact KB saved to: {compact_file}")

        # Summary
        logger.info(f"\n{'='*70}")
        logger.info("KNOWLEDGE BASE SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"\n📚 Fault Patterns: {len(fault_patterns)}")
        logger.info(f"🔌 IC Pinouts: {len(pinouts)}")
        logger.info(f"\n📊 By Category:")

        for category, patterns in categorized_patterns.items():
            logger.info(f"   {category}: {len(patterns)}")

        logger.info(f"\n🔍 Search index: {len(search_index)} keywords")

        # Sample some ICs
        logger.info(f"\n💾 ICs with pinouts:")
        for i, ic_name in enumerate(list(pinouts.keys())[:10]):
            pin_count = pinouts[ic_name]['total_pins']
            logger.info(f"   {ic_name}: {pin_count} pins")

        if len(pinouts) > 10:
            logger.info(f"   ... and {len(pinouts) - 10} more")

        return knowledge_base


def main():
    """Integrate knowledge base."""
    integrator = KnowledgeBaseIntegrator()
    integrator.generate_knowledge_base()


if __name__ == "__main__":
    main()
