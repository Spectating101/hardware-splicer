#!/usr/bin/env python3
"""
Stack Exchange Q&A Parser

Extracts and structures Q&A pairs from Stack Exchange XML dumps.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import xml.etree.ElementTree as ET
from loguru import logger
from typing import List, Dict
import json
import re
from html import unescape


class StackExchangeParser:
    """Parse Stack Exchange dumps."""

    def __init__(self, dump_dir: str = "data/stackexchange"):
        """Initialize parser."""
        self.dump_dir = Path(dump_dir)
        self.output_dir = Path("data/processed/stackexchange_qa")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_text_from_html(self, html: str) -> str:
        """
        Extract text from HTML content.

        Args:
            html: HTML string

        Returns:
            Plain text
        """
        if not html:
            return ""

        # Remove HTML tags
        text = re.sub(r'<code>.*?</code>', '[CODE]', html, flags=re.DOTALL)
        text = re.sub(r'<pre>.*?</pre>', '[CODE_BLOCK]', text, flags=re.DOTALL)
        text = re.sub(r'<.*?>', '', text)

        # Unescape HTML entities
        text = unescape(text)

        # Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def is_electronics_related(self, question: Dict) -> bool:
        """
        Filter for electronics/repair related questions.

        Args:
            question: Question dict

        Returns:
            True if relevant
        """
        # Keywords indicating repair/troubleshooting
        repair_keywords = [
            'repair', 'fix', 'broken', 'fault', 'troubleshoot', 'debug',
            'not working', 'damaged', 'failed', 'malfunction', 'dead',
            'short circuit', 'overheat', 'burn', 'smoke', 'voltage',
            'measure', 'test', 'diagnose', 'component', 'replace'
        ]

        text = (question.get('title', '') + ' ' + question.get('body', '')).lower()

        return any(keyword in text for keyword in repair_keywords)

    def parse_posts_xml(self, posts_xml: Path, site_name: str, max_questions: int = 10000):
        """
        Parse Posts.xml to extract Q&A.

        Args:
            posts_xml: Path to Posts.xml
            site_name: Site name for metadata
            max_questions: Maximum questions to parse

        Returns:
            List of Q&A pairs
        """
        logger.info(f"Parsing {posts_xml.name} from {site_name}...")

        if not posts_xml.exists():
            logger.error(f"  File not found: {posts_xml}")
            return []

        questions = {}
        answers = []

        try:
            # Parse XML incrementally to handle large files
            context = ET.iterparse(posts_xml, events=('end',))

            count = 0

            for event, elem in context:
                if elem.tag != 'row':
                    continue

                post_type = elem.get('PostTypeId')

                if post_type == '1':
                    # Question
                    question_id = elem.get('Id')
                    title = elem.get('Title', '')
                    body = elem.get('Body', '')
                    tags = elem.get('Tags', '')
                    score = int(elem.get('Score', 0))
                    accepted_answer_id = elem.get('AcceptedAnswerId')

                    questions[question_id] = {
                        'id': question_id,
                        'title': title,
                        'body': self.extract_text_from_html(body),
                        'tags': tags,
                        'score': score,
                        'accepted_answer_id': accepted_answer_id,
                        'answers': [],
                        'site': site_name
                    }

                    count += 1

                    if count >= max_questions:
                        break

                elif post_type == '2':
                    # Answer
                    answer_id = elem.get('Id')
                    parent_id = elem.get('ParentId')
                    body = elem.get('Body', '')
                    score = int(elem.get('Score', 0))

                    answers.append({
                        'id': answer_id,
                        'parent_id': parent_id,
                        'body': self.extract_text_from_html(body),
                        'score': score
                    })

                # Clear element to save memory
                elem.clear()

            logger.info(f"  Parsed {len(questions)} questions, {len(answers)} answers")

            # Link answers to questions
            for answer in answers:
                parent_id = answer['parent_id']
                if parent_id in questions:
                    questions[parent_id]['answers'].append({
                        'id': answer['id'],
                        'body': answer['body'],
                        'score': answer['score'],
                        'is_accepted': answer['id'] == questions[parent_id].get('accepted_answer_id')
                    })

            # Convert to list and filter
            qa_pairs = []

            for question in questions.values():
                # Only include questions with at least one answer
                if len(question['answers']) > 0:
                    # Sort answers by score (accepted first, then by score)
                    question['answers'].sort(
                        key=lambda a: (not a.get('is_accepted', False), -a['score'])
                    )

                    qa_pairs.append(question)

            logger.info(f"  {len(qa_pairs)} questions with answers")

            # Filter for electronics/repair related
            relevant_qa = [q for q in qa_pairs if self.is_electronics_related(q)]

            logger.info(f"  {len(relevant_qa)} relevant to electronics/repair")

            return relevant_qa

        except Exception as e:
            logger.error(f"  Failed to parse: {e}")
            return []

    def parse_all_sites(self):
        """Parse all downloaded Stack Exchange sites."""
        logger.info("="*70)
        logger.info("STACK EXCHANGE Q&A PARSER")
        logger.info("="*70)

        all_qa = []

        # Look for extracted directories
        site_dirs = [d for d in self.dump_dir.iterdir() if d.is_dir()]

        if not site_dirs:
            logger.warning("No extracted Stack Exchange sites found!")
            logger.info("Please extract .7z files first:")
            logger.info("  cd data/stackexchange")
            logger.info("  for f in *.7z; do py7zr x \"$f\"; done")
            return

        for site_dir in site_dirs:
            site_name = site_dir.name

            logger.info(f"\n{'='*70}")
            logger.info(f"SITE: {site_name}")
            logger.info(f"{'='*70}")

            posts_xml = site_dir / "Posts.xml"

            if not posts_xml.exists():
                logger.warning(f"  Posts.xml not found in {site_dir}")
                continue

            qa_pairs = self.parse_posts_xml(posts_xml, site_name, max_questions=50000)

            all_qa.extend(qa_pairs)

            # Save site-specific output
            output_file = self.output_dir / f"{site_name}_qa.json"

            with open(output_file, 'w') as f:
                json.dump(qa_pairs, f, indent=2)

            logger.info(f"  ✅ Saved to: {output_file}")

        # Save combined output
        combined_file = self.output_dir / "all_sites_qa.json"

        with open(combined_file, 'w') as f:
            json.dump(all_qa, f, indent=2)

        logger.info(f"\n{'='*70}")
        logger.info("PARSING COMPLETE")
        logger.info(f"{'='*70}")
        logger.info(f"\n✅ Total Q&A pairs: {len(all_qa)}")
        logger.info(f"📁 Saved to: {self.output_dir}")

        # Statistics
        total_answers = sum(len(q['answers']) for q in all_qa)
        avg_answers = total_answers / len(all_qa) if all_qa else 0

        logger.info(f"\n📊 Statistics:")
        logger.info(f"   Questions: {len(all_qa)}")
        logger.info(f"   Total answers: {total_answers}")
        logger.info(f"   Avg answers per question: {avg_answers:.1f}")

        return all_qa


def main():
    """Parse Stack Exchange dumps."""
    parser = StackExchangeParser()
    parser.parse_all_sites()


if __name__ == "__main__":
    main()
