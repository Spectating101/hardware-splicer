"""
LLM-Based Intent Parser

ACTUALLY uses AI to understand user requests instead of dumb keyword matching.

User was right: "Are you gonna hardcode every single case possible?"
Answer: NO - use LLM to understand intent naturally!
"""

import logging
import json
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path
import sys

# Add cite-agent to path for LLM providers
cite_agent_path = Path(__file__).parent.parent.parent.parent / "Cite-Agent"
if cite_agent_path.exists():
    sys.path.insert(0, str(cite_agent_path))

from groq import Groq

# Load .env.local if it exists
from pathlib import Path
env_file = Path(__file__).parent.parent.parent / ".env.local"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

logger = logging.getLogger(__name__)


# Reuse existing enums
from intelligence.intent_parser import ProjectType, DesignIntent


class LLMIntentParser:
    """
    INTELLIGENT intent parser using LLM.

    Instead of hardcoding keywords, let the LLM understand:
    - "build me a manipulator" → robot arm
    - "water-powered electricity maker" → hydro generator
    - "6-DOF articulated mechanism" → robot arm

    The LLM has common sense - use it!
    """

    def __init__(self, use_llm: bool = True):
        """
        Initialize LLM-based parser.

        Args:
            use_llm: If False, falls back to keyword matching (for testing)
        """
        self.use_llm = use_llm
        self.provider = None

        if use_llm:
            # Try Cerebras first (from .env.local)
            cerebras_key = (os.getenv('CEREBRAS_API_KEY') or
                          os.getenv('CEREBRAS_API_KEY_1') or
                          os.getenv('CEREBRAS_API_KEY_2'))
            if cerebras_key:
                try:
                    from openai import OpenAI
                    self.client = OpenAI(
                        api_key=cerebras_key,
                        base_url="https://api.cerebras.ai/v1"
                    )
                    self.provider = 'cerebras'
                    logger.info("LLM-based intent parser initialized with Cerebras")
                except Exception as e:
                    logger.warning(f"Cerebras initialization failed: {e}")

            # Try Groq as fallback
            if not self.provider:
                groq_key = os.getenv('GROQ_API_KEY') or os.getenv('GROQ_API_KEY_1')
                if groq_key:
                    try:
                        self.client = Groq(api_key=groq_key)
                        self.provider = 'groq'
                        logger.info("LLM-based intent parser initialized with Groq")
                    except Exception as e:
                        logger.warning(f"Groq initialization failed: {e}")

            # Try Gemini as last resort
            if not self.provider:
                gemini_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
                if gemini_key:
                    try:
                        import google.generativeai as genai
                        genai.configure(api_key=gemini_key)
                        self.client = genai.GenerativeModel('gemini-1.5-flash')
                        self.provider = 'gemini'
                        logger.info("LLM-based intent parser initialized with Gemini")
                    except Exception as e:
                        logger.warning(f"Gemini initialization failed: {e}")

            # No LLM available
            if not self.provider:
                logger.warning("No LLM API key found - falling back to keyword matching")
                self.use_llm = False

        # Always initialize fallback keyword parser
        from intelligence.intent_parser import IntentParser
        self.fallback_parser = IntentParser()

    def parse(self, user_request: str) -> DesignIntent:
        """
        Parse user request using LLM intelligence.

        Args:
            user_request: Natural language request

        Returns:
            DesignIntent with specifications
        """
        if not self.use_llm:
            logger.info("Using fallback keyword parser")
            return self.fallback_parser.parse(user_request)

        try:
            # Ask LLM to understand the request
            result = self._llm_parse(user_request)

            # Convert to DesignIntent
            intent = DesignIntent(
                project_type=ProjectType(result["project_type"]),
                features=result["features"],
                constraints=result["constraints"],
                required_components=result["required_components"],
                raw_request=user_request,
                confidence=result["confidence"]
            )

            logger.info(f"LLM parsed: {intent.project_type.value}, confidence: {intent.confidence:.2f}")

            return intent

        except Exception as e:
            logger.error(f"LLM parsing failed: {e}, falling back to keywords")
            return self.fallback_parser.parse(user_request)

    def _llm_parse(self, user_request: str) -> Dict:
        """Use LLM to parse intent."""

        prompt = f"""You are an intelligent hardware/electronics design assistant. Analyze this build request and extract structured information.

User Request: "{user_request}"

Available Project Types:
- sensor: Temperature, humidity, motion sensors, etc.
- actuator: Motors, servos, LEDs, relays
- controller: Motor controllers, system managers
- display: OLED, LCD screens
- communication: WiFi, Bluetooth modules
- power_supply: Voltage regulators, battery chargers
- mechanical: Robot arms, grippers, mechanisms, actuators
- power_generation: Hydro generators, solar panels, wind turbines

Analyze the request and respond with JSON:
{{
    "project_type": "<type>",
    "features": ["<feature1>", "<feature2>"],
    "constraints": {{"max_budget_usd": <number>, "battery_powered": <bool>}},
    "required_components": ["<component1>", "<component2>"],
    "reasoning": "<why you chose this classification>",
    "confidence": <0.0-1.0>
}}

Examples:
- "build me a manipulator for circuit boards" → project_type: "mechanical", features: ["pick_and_place", "gripper"], components: ["servo", "servo_driver", "microcontroller", "3d_printed_parts"]
- "make a water-powered electricity maker for storms" → project_type: "power_generation", features: ["hydro"], components: ["turbine", "dc_motor_as_generator", "rectifier", "voltage_regulator", "battery"]
- "6-DOF articulated mechanism" → project_type: "mechanical", features: ["degrees_of_freedom"], components: ["servo" (6x), "servo_driver", "microcontroller"]

Think about:
1. What is the user trying to build? (understand intent, not just keywords)
2. What components would it need?
3. Is it mechanical, electronic, or power-related?

Respond with ONLY valid JSON, no explanation outside the JSON.
"""

        # Call appropriate provider
        if self.provider == 'cerebras':
            response = self.client.chat.completions.create(
                model="llama-3.3-70b",
                messages=[
                    {"role": "system", "content": "You are an expert hardware design assistant. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            result_text = response.choices[0].message.content.strip()

        elif self.provider == 'groq':
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an expert hardware design assistant. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            result_text = response.choices[0].message.content.strip()

        elif self.provider == 'gemini':
            response = self.client.generate_content(prompt)
            result_text = response.text.strip()

        else:
            raise ValueError("No LLM provider available")

        # Parse JSON (LLM should return valid JSON)
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # Try to extract JSON if LLM added markdown
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
                result = json.loads(result_text)
            elif "```" in result_text:
                # Handle plain ``` without json tag
                result_text = result_text.split("```")[1].split("```")[0].strip()
                result = json.loads(result_text)
            else:
                raise ValueError(f"LLM didn't return valid JSON: {result_text}")

        # Validate required fields
        required_fields = ["project_type", "features", "constraints", "required_components", "confidence"]
        for field in required_fields:
            if field not in result:
                raise ValueError(f"LLM response missing field: {field}")

        return result

    def parse_with_examples(self, user_request: str, example_projects: List[Dict]) -> DesignIntent:
        """
        Parse with few-shot learning from example projects.

        This is even smarter - give the LLM examples of past successful builds
        so it can learn patterns.

        Args:
            user_request: User's build request
            example_projects: List of {request, type, components} examples

        Returns:
            DesignIntent
        """
        # TODO: Implement few-shot learning with examples
        # For now, just use standard parsing
        return self.parse(user_request)


def create_parser(use_llm: bool = None) -> LLMIntentParser:
    """
    Factory function to create parser.

    Args:
        use_llm: Force LLM mode (True) or keyword mode (False).
                 If None, auto-detects based on API key availability.

    Returns:
        LLMIntentParser instance
    """
    if use_llm is None:
        # Auto-detect: use LLM if API key available
        use_llm = bool(os.getenv('GROQ_API_KEY') or os.getenv('GROQ_API_KEY_1'))

    return LLMIntentParser(use_llm=use_llm)
