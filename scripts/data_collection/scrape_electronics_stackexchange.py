#!/usr/bin/env python3
"""
Electronics Stack Exchange Scraper

Extracts repair/troubleshooting Q&A to build fault pattern database.
"""

import requests
import time
import json
from pathlib import Path
from typing import List, Dict
from loguru import logger


class StackExchangeScraper:
    """Scrape repair knowledge from Electronics Stack Exchange."""

    def __init__(self):
        """Initialize scraper."""
        self.api_base = "https://api.stackexchange.com/2.3"
        self.site = "electronics"
        self.output_dir = Path("data/stackexchange_repairs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_repair_questions(self, max_questions: int = 100) -> List[Dict]:
        """
        Get repair/troubleshooting questions.

        Args:
            max_questions: Maximum questions to fetch

        Returns:
            List of questions with answers
        """
        logger.info(f"Fetching repair questions from Stack Exchange...")

        questions = []

        tags = ["repair", "troubleshooting", "debugging", "circuit-analysis"]

        for tag in tags:
            logger.info(f"Fetching questions tagged: {tag}")

            url = f"{self.api_base}/questions"
            params = {
                "order": "desc",
                "sort": "votes",
                "tagged": tag,
                "site": self.site,
                "filter": "withbody",  # Include question body
                "pagesize": min(100, max_questions // len(tags))
            }

            try:
                response = requests.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                if 'items' in data:
                    questions.extend(data['items'])
                    logger.info(f"  Found {len(data['items'])} questions")

                # Respect rate limiting
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Error fetching questions: {e}")

        logger.info(f"Total questions fetched: {len(questions)}")

        return questions[:max_questions]

    def get_answers_for_question(self, question_id: int) -> List[Dict]:
        """Get answers for a specific question."""
        url = f"{self.api_base}/questions/{question_id}/answers"
        params = {
            "order": "desc",
            "sort": "votes",
            "site": self.site,
            "filter": "withbody"
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if 'items' in data:
                return data['items']

        except Exception as e:
            logger.error(f"Error fetching answers: {e}")

        return []

    def extract_fault_pattern(self, question: Dict, answers: List[Dict]) -> Optional[Dict]:
        """
        Extract fault pattern from Q&A.

        Format:
        - Symptoms: From question title/body
        - Diagnosis: From top answer
        - Root cause: Extracted from answer
        - Fix: Step-by-step from answer
        """
        # Extract symptoms from question
        symptoms = self._extract_symptoms(question)

        if not symptoms:
            return None

        # Get top answer (highest voted)
        if not answers:
            return None

        top_answer = max(answers, key=lambda a: a.get('score', 0))

        # Extract diagnosis and fix
        diagnosis = self._extract_diagnosis(top_answer)
        fix_steps = self._extract_fix_steps(top_answer)

        if not diagnosis:
            return None

        return {
            "fault_id": f"se_{question['question_id']}",
            "source": "stack_exchange",
            "question_url": question.get('link', ''),
            "symptoms": symptoms,
            "diagnosis": diagnosis,
            "fix_steps": fix_steps,
            "votes": question.get('score', 0),
            "answer_votes": top_answer.get('score', 0)
        }

    def _extract_symptoms(self, question: Dict) -> List[str]:
        """Extract symptoms from question."""
        title = question.get('title', '')
        body = question.get('body', '')

        symptoms = []

        # Common symptom phrases
        symptom_patterns = [
            "won't", "doesn't", "not working", "broken", "failed",
            "no output", "no response", "dead", "burnt", "hot",
            "short circuit", "voltage drop", "current spike"
        ]

        text = (title + " " + body).lower()

        for pattern in symptom_patterns:
            if pattern in text:
                # Extract sentence containing symptom
                sentences = text.split('.')
                for sentence in sentences:
                    if pattern in sentence:
                        symptoms.append(sentence.strip())
                        break

        return symptoms[:3]  # Top 3 symptoms

    def _extract_diagnosis(self, answer: Dict) -> Optional[str]:
        """Extract diagnosis from answer."""
        body = answer.get('body', '')

        # Look for diagnostic statements
        diagnostic_keywords = [
            "the problem is", "likely cause", "most common",
            "this indicates", "probably", "typically caused by"
        ]

        body_lower = body.lower()

        for keyword in diagnostic_keywords:
            if keyword in body_lower:
                # Extract sentence
                idx = body_lower.find(keyword)
                # Get ~100 chars after keyword
                diagnosis = body[idx:idx+150]
                return diagnosis.split('.')[0] + '.'

        return None

    def _extract_fix_steps(self, answer: Dict) -> List[str]:
        """Extract repair steps from answer."""
        body = answer.get('body', '')

        steps = []

        # Look for numbered lists or bullet points
        lines = body.split('\n')

        for line in lines:
            line = line.strip()

            # Numbered list
            if line and line[0].isdigit() and ('.' in line or ')' in line):
                steps.append(line)

            # Bullet point
            elif line.startswith(('-', '*', '•')):
                steps.append(line[1:].strip())

        return steps[:5]  # Max 5 steps

    def save_fault_patterns(self, patterns: List[Dict]):
        """Save fault patterns to JSON."""
        output_file = self.output_dir / "fault_patterns.json"

        with open(output_file, 'w') as f:
            json.dump(patterns, f, indent=2)

        logger.info(f"Saved {len(patterns)} fault patterns to: {output_file}")


def main():
    """Run Stack Exchange scraping."""
    logger.info("Electronics Stack Exchange Scraper")
    logger.info("="*70)

    scraper = StackExchangeScraper()

    # Fetch questions
    questions = scraper.get_repair_questions(max_questions=50)

    # Extract fault patterns
    fault_patterns = []

    for i, question in enumerate(questions[:20], 1):  # Process first 20
        logger.info(f"\nProcessing question {i}/20: {question.get('title', '')[:60]}...")

        # Get answers
        answers = scraper.get_answers_for_question(question['question_id'])

        if answers:
            pattern = scraper.extract_fault_pattern(question, answers)

            if pattern:
                fault_patterns.append(pattern)
                logger.info(f"  ✅ Extracted fault pattern")
            else:
                logger.info(f"  ⏭️  Skipped (no clear diagnosis)")

        time.sleep(0.5)  # Rate limiting

    # Save
    scraper.save_fault_patterns(fault_patterns)

    # Summary
    logger.info("\n" + "="*70)
    logger.info("SUMMARY")
    logger.info("="*70)
    logger.info(f"Questions fetched: {len(questions)}")
    logger.info(f"Fault patterns extracted: {len(fault_patterns)}")
    logger.info(f"Success rate: {len(fault_patterns)/min(20, len(questions))*100:.1f}%")


if __name__ == "__main__":
    main()
