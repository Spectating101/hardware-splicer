"""
LLM-Powered PCB Design Analysis

Adds AI insights to validation results when LLM is available.
Falls back gracefully if LLM is not configured.
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def get_llm_design_insights(pcb_geometry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Get LLM-powered design insights from PCB geometry.

    Returns None if LLM is not available, otherwise returns insights dict.
    """
    try:
        from src.config import settings

        # Check if LLM is enabled and configured
        if not settings.llm_enabled:
            return None

        if not settings.cerebras_api_key and not settings.openai_api_key and not settings.cohere_api_key:
            return None

        # Try to use LLM integration
        try:
            import litellm
        except ImportError:
            logger.debug("litellm not installed, skipping LLM insights")
            return None

        # Extract key information from PCB
        board = pcb_geometry.get('board', {})
        footprints = pcb_geometry.get('footprints', [])
        nets = pcb_geometry.get('nets', [])
        segments = pcb_geometry.get('segments', [])

        # Build analysis context
        component_types = {}
        for fp in footprints:
            value = fp.get('value', 'unknown')
            component_types[value] = component_types.get(value, 0) + 1

        # Create prompt
        prompt = f"""Analyze this PCB design and provide brief insights (2-3 sentences max):

Board: {board.get('bbox_mm', {}).get('width', 0)}mm x {board.get('bbox_mm', {}).get('height', 0)}mm
Components ({len(footprints)} total): {', '.join(f'{count}x {comp}' for comp, count in list(component_types.items())[:10])}
Nets: {len(nets)} connections
Traces: {len(segments)} segments

Provide JSON with:
{{"insights": "Brief design analysis", "recommendations": ["suggestion1", "suggestion2"], "complexity": "beginner|intermediate|advanced"}}"""

        # Configure model based on available API keys
        # Set environment variables for litellm to use
        model = "llama-3.3-70b"  # Cerebras Llama
        if settings.cerebras_api_key:
            model = "cerebras/llama-3.3-70b"
            os.environ["CEREBRAS_API_KEY"] = settings.cerebras_api_key
        elif settings.openai_api_key:
            model = "gpt-4o-mini"
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        elif settings.cohere_api_key:
            model = "command-r"
            os.environ["COHERE_API_KEY"] = settings.cohere_api_key

        # Make LLM call with short timeout
        try:
            response = litellm.completion(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a PCB design expert. Respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                timeout=5.0,  # 5 second timeout
                max_tokens=200  # Keep response brief
            )

            content = response.choices[0].message.content

            # Strip markdown code blocks if present
            if content.startswith("```"):
                # Remove opening ```json or ```
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                # Remove closing ```
                if content.endswith("```"):
                    content = content.rsplit("```", 1)[0]
                content = content.strip()

            # Try to parse JSON
            try:
                result = json.loads(content)
                return {
                    "insights": result.get("insights", "Design analysis complete"),
                    "recommendations": result.get("recommendations", [])[:3],  # Max 3
                    "complexity": result.get("complexity", "intermediate"),
                    "llm_model": model
                }
            except json.JSONDecodeError:
                # If JSON parsing fails, return raw insights
                return {
                    "insights": content[:200],  # Truncate to 200 chars
                    "recommendations": [],
                    "complexity": "unknown",
                    "llm_model": model
                }

        except Exception as e:
            logger.debug(f"LLM call failed: {e}")
            return None

    except Exception as e:
        logger.debug(f"LLM insights unavailable: {e}")
        return None


def get_fallback_insights(pcb_geometry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Provide rule-based insights when LLM is not available.
    """
    footprints = pcb_geometry.get('footprints', [])
    board = pcb_geometry.get('board', {})
    bbox = board.get('bbox_mm', {})

    width = bbox.get('width', 0)
    height = bbox.get('height', 0)
    area = width * height if width and height else 0

    insights = []
    recommendations = []

    # Determine complexity
    if len(footprints) > 50:
        complexity = "advanced"
        insights.append(f"Complex design with {len(footprints)} components")
    elif len(footprints) > 20:
        complexity = "intermediate"
        insights.append(f"Moderate complexity with {len(footprints)} components")
    else:
        complexity = "beginner"
        insights.append(f"Simple design with {len(footprints)} components")

    # Check board size
    if area > 20000:  # > 200cm²
        recommendations.append("Consider splitting into smaller boards for easier manufacturing")
    elif area < 500:  # < 50cm²
        recommendations.append("Small board - ensure minimum fab capabilities are met")

    # Check for power components
    power_components = [fp for fp in footprints
                       if any(keyword in fp.get('value', '').upper()
                             for keyword in ['LDO', 'BUCK', 'BOOST', 'REGULATOR'])]

    if power_components:
        recommendations.append("Add thermal management for power components")

    # Check for high-speed components
    has_usb = any('USB' in fp.get('value', '').upper() for fp in footprints)
    has_oscillator = any(keyword in fp.get('value', '').upper()
                        for fp in footprints
                        for keyword in ['OSC', 'XTAL', 'CRYSTAL'])

    if has_usb or has_oscillator:
        recommendations.append("Review trace impedance for high-speed signals")

    return {
        "insights": '. '.join(insights) + '.',
        "recommendations": recommendations[:3],
        "complexity": complexity,
        "llm_model": "rule-based"
    }
