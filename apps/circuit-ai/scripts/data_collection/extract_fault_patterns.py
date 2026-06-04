#!/usr/bin/env python3
"""
Fault Pattern Extractor

Extracts structured fault patterns from Stack Exchange Q&A.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
from loguru import logger
from typing import List, Dict
import re


class FaultPatternExtractor:
    """Extract fault patterns from Q&A."""

    def __init__(self, qa_dir: str = "data/processed/stackexchange_qa"):
        """Initialize extractor."""
        self.qa_dir = Path(qa_dir)
        self.output_dir = Path("data/processed/fault_patterns")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_symptoms(self, question: Dict) -> List[str]:
        """
        Extract symptoms from question.

        Args:
            question: Question dict

        Returns:
            List of symptoms
        """
        text = question.get('title', '') + ' ' + question.get('body', '')

        symptoms = []

        # Common symptom patterns
        symptom_patterns = [
            r"(?:not|doesn't|won't|isn't|cannot|can't)\s+(\w+(?:\s+\w+){0,3})",
            r"(\w+(?:\s+\w+){0,2})\s+(?:not working|doesn't work|won't work|failed|broken|dead)",
            r"getting\s+(\w+(?:\s+\w+){0,3})",
            r"(\w+(?:\s+\w+){0,2})\s+(?:is|are)\s+(?:too hot|overheating|burning|smoking)",
            r"no\s+(\w+(?:\s+\w+){0,2})",
            r"(\w+(?:\s+\w+){0,2})\s+(?:keeps|always)\s+(\w+(?:\s+\w+){0,2})"
        ]

        for pattern in symptom_patterns:
            matches = re.findall(pattern, text.lower())
            for match in matches:
                if isinstance(match, tuple):
                    symptom = ' '.join(match).strip()
                else:
                    symptom = match.strip()

                if len(symptom) > 5 and symptom not in symptoms:
                    symptoms.append(symptom)

        return symptoms[:5]  # Top 5 symptoms

    def extract_components(self, text: str) -> List[str]:
        """
        Extract component mentions.

        Args:
            text: Text to search

        Returns:
            List of components
        """
        # Common component patterns
        component_patterns = [
            r'\b(ATmega\d+[A-Z]*)',
            r'\b(ESP\d+)',
            r'\b(STM32[A-Z]\d+)',
            r'\b(LM\d+)',
            r'\b(TL\d+)',
            r'\b(74HC\d+)',
            r'\b(CH340[A-Z]?)',
            r'\b(FT232[A-Z]+)',
            r'\b(capacitor|resistor|transistor|diode|LED|IC|chip|regulator|USB)',
        ]

        components = []

        for pattern in component_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            components.extend(matches)

        # Deduplicate
        components = list(set([c.upper() if c.isupper() or len(c) < 4 else c.lower() for c in components]))

        return components[:10]  # Top 10

    def extract_diagnostic_steps(self, answer: Dict) -> List[str]:
        """
        Extract diagnostic/repair steps from answer.

        Args:
            answer: Answer dict

        Returns:
            List of steps
        """
        body = answer.get('body', '')

        steps = []

        # Look for step-by-step instructions
        step_patterns = [
            r'\d+\.\s+([^\.]+)',
            r'first,?\s+([^\.]+)',
            r'then,?\s+([^\.]+)',
            r'next,?\s+([^\.]+)',
            r'(?:check|test|measure|verify)\s+([^\.]+)',
            r'(?:replace|remove|solder|desolder)\s+([^\.]+)',
        ]

        for pattern in step_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            for match in matches:
                step = match.strip()
                if len(step) > 10 and step not in steps:
                    steps.append(step)

        return steps[:10]  # Top 10 steps

    def classify_difficulty(self, question: Dict, answer: Dict) -> str:
        """
        Classify repair difficulty.

        Args:
            question: Question dict
            answer: Answer dict

        Returns:
            Difficulty level
        """
        text = (question.get('body', '') + ' ' + answer.get('body', '')).lower()

        # Easy indicators
        easy_keywords = ['just', 'simply', 'easy', 'quick', 'basic', 'straightforward']

        # Hard indicators
        hard_keywords = ['complex', 'difficult', 'advanced', 'experienced', 'professional',
                         'solder', 'desolder', 'smd', 'reflow', 'bga', 'microscope']

        easy_count = sum(1 for keyword in easy_keywords if keyword in text)
        hard_count = sum(1 for keyword in hard_keywords if keyword in text)

        if hard_count > easy_count + 2:
            return 'hard'
        elif easy_count > hard_count + 2:
            return 'easy'
        else:
            return 'medium'

    def extract_fault_pattern(self, qa: Dict) -> Dict:
        """
        Extract structured fault pattern from Q&A.

        Args:
            qa: Q&A pair

        Returns:
            Fault pattern dict
        """
        # Get best answer (highest score or accepted)
        answers = qa.get('answers', [])

        if not answers:
            return None

        best_answer = answers[0]  # Already sorted by score/accepted

        # Extract components
        all_text = qa.get('title', '') + ' ' + qa.get('body', '') + ' ' + best_answer.get('body', '')
        components = self.extract_components(all_text)

        # Extract symptoms
        symptoms = self.extract_symptoms(qa)

        # Extract diagnostic steps
        diagnostic_steps = self.extract_diagnostic_steps(best_answer)

        if not symptoms or not diagnostic_steps:
            return None

        # Build fault pattern
        fault_pattern = {
            'fault_id': f"se_{qa.get('site', 'unknown')}_{qa.get('id')}",
            'title': qa.get('title', ''),
            'symptoms': symptoms,
            'affected_components': components,
            'diagnostic_steps': diagnostic_steps,
            'repair_difficulty': self.classify_difficulty(qa, best_answer),
            'source': {
                'site': qa.get('site', ''),
                'question_id': qa.get('id', ''),
                'score': qa.get('score', 0),
                'answer_score': best_answer.get('score', 0)
            },
            'full_question': qa.get('body', '')[:500],  # First 500 chars
            'full_answer': best_answer.get('body', '')[:1000]  # First 1000 chars
        }

        return fault_pattern

    def extract_from_qa_file(self, qa_file: Path) -> List[Dict]:
        """
        Extract fault patterns from Q&A file.

        Args:
            qa_file: Path to Q&A JSON

        Returns:
            List of fault patterns
        """
        logger.info(f"Processing {qa_file.name}...")

        with open(qa_file, 'r') as f:
            qa_pairs = json.load(f)

        fault_patterns = []

        for qa in qa_pairs:
            pattern = self.extract_fault_pattern(qa)

            if pattern:
                fault_patterns.append(pattern)

        logger.info(f"  Extracted {len(fault_patterns)} fault patterns")

        return fault_patterns

    def process_all_qa(self):
        """Process all Q&A files to extract fault patterns."""
        logger.info("="*70)
        logger.info("FAULT PATTERN EXTRACTOR")
        logger.info("="*70)

        if not self.qa_dir.exists():
            logger.error(f"Q&A directory not found: {self.qa_dir}")
            logger.info("Please parse Stack Exchange dumps first:")
            logger.info("  python scripts/data_collection/parse_stackexchange_qa.py")
            return

        all_patterns = []

        qa_files = list(self.qa_dir.glob("*_qa.json"))

        if not qa_files:
            logger.warning("No Q&A files found!")
            return

        for qa_file in qa_files:
            patterns = self.extract_from_qa_file(qa_file)
            all_patterns.extend(patterns)

            # Save site-specific patterns
            output_file = self.output_dir / f"{qa_file.stem}_patterns.json"

            with open(output_file, 'w') as f:
                json.dump(patterns, f, indent=2)

            logger.info(f"  ✅ Saved to: {output_file}")

        # Save combined patterns
        combined_file = self.output_dir / "all_fault_patterns.json"

        with open(combined_file, 'w') as f:
            json.dump(all_patterns, f, indent=2)

        logger.info(f"\n{'='*70}")
        logger.info("EXTRACTION COMPLETE")
        logger.info(f"{'='*70}")
        logger.info(f"\n✅ Total fault patterns: {len(all_patterns)}")
        logger.info(f"📁 Saved to: {self.output_dir}")

        # Statistics
        difficulty_counts = {}
        for pattern in all_patterns:
            diff = pattern.get('repair_difficulty', 'unknown')
            difficulty_counts[diff] = difficulty_counts.get(diff, 0) + 1

        logger.info(f"\n📊 By difficulty:")
        for diff, count in sorted(difficulty_counts.items()):
            logger.info(f"   {diff}: {count}")

        return all_patterns


def main():
    """Extract fault patterns."""
    extractor = FaultPatternExtractor()
    extractor.process_all_qa()


if __name__ == "__main__":
    main()
