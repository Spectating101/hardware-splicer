"""
Test: DUMB Keyword Matching vs INTELLIGENT LLM Understanding

Shows why the user was right to call out hardcoded keywords.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import logging
logging.basicConfig(level=logging.WARNING)

from intelligence.intent_parser import IntentParser  # Dumb keyword parser
from intelligence.llm_intent_parser import LLMIntentParser  # Smart LLM parser


def test_edge_cases():
    """Test cases that BREAK keyword matching but LLM understands."""

    print("=" * 70)
    print("DUMB KEYWORDS vs INTELLIGENT LLM")
    print("=" * 70)

    # These are requests where keyword matching FAILS
    test_cases = [
        # Robot arm synonyms (no "robot" or "arm" keywords!)
        ("build me a manipulator for picking up circuit boards", "mechanical"),
        ("I need a 6-DOF articulated mechanism for assembly", "mechanical"),
        ("create a gripper system with servo actuation", "mechanical"),

        # Hydro generator synonyms (no "hydro" or "generator"!)
        ("make a water-powered electricity maker for storms", "power_generation"),
        ("build me something that harvests energy from rain", "power_generation"),
        ("I want to generate power using flowing water", "power_generation"),

        # Complex requests
        ("build a device that uses rain to charge my phone", "power_generation"),
        ("make an automated PCB component placement system", "mechanical"),

        # Ambiguous (needs intelligence to disambiguate)
        ("build me something with servos for automation", "mechanical"),  # Could be many things
    ]

    keyword_parser = IntentParser()  # Dumb
    llm_parser = LLMIntentParser(use_llm=True)  # Smart

    for i, (request, expected_type) in enumerate(test_cases, 1):
        print(f"\n{'=' * 70}")
        print(f"TEST CASE {i}")
        print(f"Request: \"{request}\"")
        print(f"Expected: {expected_type}")
        print(f"{'=' * 70}")

        # Dumb keyword parsing
        keyword_result = keyword_parser.parse(request)
        keyword_correct = keyword_result.project_type.value == expected_type

        print(f"\n❌ DUMB KEYWORDS:")
        print(f"  → Understood: {keyword_result.project_type.value}")
        print(f"  → Features: {keyword_result.features}")
        print(f"  → Result: {'✅ CORRECT' if keyword_correct else '❌ WRONG'}")

        # Smart LLM parsing
        try:
            llm_result = llm_parser.parse(request)
            llm_correct = llm_result.project_type.value == expected_type

            print(f"\n✅ INTELLIGENT LLM:")
            print(f"  → Understood: {llm_result.project_type.value}")
            print(f"  → Features: {llm_result.features}")
            print(f"  → Confidence: {llm_result.confidence:.2f}")
            print(f"  → Result: {'✅ CORRECT' if llm_correct else '❌ WRONG'}")

        except Exception as e:
            print(f"\n✅ INTELLIGENT LLM:")
            print(f"  → Error: {e}")
            print(f"  → (No API key? Set GROQ_API_KEY to enable)")


def show_keyword_limitation():
    """Show why hardcoding is stupid."""

    print("\n\n" + "=" * 70)
    print("WHY HARDCODED KEYWORDS ARE STUPID")
    print("=" * 70)

    print("""
Keyword approach:
  if "robot" in text and "arm" in text:
      return MECHANICAL

Problems:
  1. "manipulator" → MISSED (not in keyword list!)
  2. "articulated mechanism" → MISSED
  3. "gripper system" → MISSED
  4. "6-DOF assembly device" → MISSED

  You'd need to hardcode EVERY possible synonym!

  Keywords for robot arm:
    - robot, arm, manipulator, articulated, mechanism, gripper,
      actuator, servo system, pick-and-place, 6dof, 4dof,
      degrees of freedom, mechanical arm, robotic gripper,
      assembly system, precision placement, ...

  That's HUNDREDS of keywords for ONE project type!

  For 100 project types → TENS OF THOUSANDS of hardcoded keywords!

LLM approach:
  Ask LLM: "What is the user trying to build?"

  LLM understands:
    - "manipulator" = robot arm
    - "water-powered electricity" = hydro generator
    - "articulated mechanism" = mechanical system
    - "energy from rain" = power generation

  NO HARDCODING NEEDED - the LLM has common sense!
""")


def compare_scalability():
    """Show scalability difference."""

    print("\n" + "=" * 70)
    print("SCALABILITY COMPARISON")
    print("=" * 70)

    print("""
To support 100 different project types:

KEYWORD APPROACH:
  - Need to hardcode ~50 keywords per type
  - Total: 5,000 hardcoded keywords
  - Code size: ~500 lines of keyword lists
  - Maintenance: Add keywords every time users use new words
  - Fails on: Synonyms, creative phrasing, technical jargon

LLM APPROACH:
  - Need to describe project types once in prompt
  - Total: ~100 lines of project descriptions
  - Code size: ~50 lines of LLM calling code
  - Maintenance: Minimal - LLM adapts to new phrasing
  - Works on: Any natural language, understands intent

WINNER: LLM (10× less code, infinitely more flexible)
""")


def main():
    """Run intelligence comparison."""

    print("\n")
    print("█" * 70)
    print("USER WAS RIGHT: HARDCODED KEYWORDS ARE STUPID")
    print("█" * 70)

    test_edge_cases()
    show_keyword_limitation()
    compare_scalability()

    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print("""
User's Question: "Are you gonna hardcode every single case possible?"

Answer: NO! That's stupid!

PROPER SOLUTION:
  1. Use LLM to understand intent naturally
  2. Let AI do what AI is good at - understanding language
  3. Keep keyword matching as FALLBACK only (for when no API key)

The system is called "Circuit-AI Intelligence" - actually USE intelligence!
""")

    print("\nTo enable LLM mode:")
    print("  export GROQ_API_KEY=your_key_here")
    print("  python scripts/test_intelligent_parsing.py")


if __name__ == "__main__":
    main()
