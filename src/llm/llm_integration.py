#!/usr/bin/env python3
"""
LLM Integration for Circuit.AI
==============================

Connects to your existing LLM engine for advanced component analysis.
No Redis dependency - direct integration with your LLM manager.
"""

import json
import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger
from src.config import settings
from src.llm.schemas import (
    ComponentAnalysis,
    ProjectSuggestionList,
    ConditionAssessment,
    EducationalContent,
    try_validate,
)

try:
    import litellm
    LITE_AVAILABLE = True
except Exception:
    LITE_AVAILABLE = False

# Import your existing LLM components
try:
    from src.services.llm_service.llm_manager import LLMManager
    from src.services.llm_service.model_dispatcher import ModelDispatcher
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    logger.warning("LLM service not available")


# Emergency fallback provider configuration
# These are tried in order when the primary LiteLLM provider fails
FALLBACK_PROVIDERS = [
    # Format: (provider_prefix, model_name, env_key_for_api_key)
    ("cohere", "command-r", "COHERE_API_KEY"),
    ("mistral", "mistral-small-latest", "MISTRAL_API_KEY"),
    ("anthropic", "claude-3-haiku-20240307", "ANTHROPIC_API_KEY"),
    ("openai", "gpt-3.5-turbo", "OPENAI_API_KEY"),
]


class CircuitLLMIntegration:
    """Advanced LLM integration for Circuit.AI."""
    
    def __init__(self, redis_url: str = None):
        """Initialize LLM integration."""
        self.llm_manager = None
        self.model_dispatcher = None
        self.redis_url = redis_url
        
        # Caching (disk-backed if enabled)
        self._cache: dict[str, str] = {}
        self._disk_cache = None
        try:
            if settings.llm_cache_enabled:
                from diskcache import Cache  # type: ignore
                import os as _os
                cache_path = settings.llm_cache_path
                # DiskCache expects a directory; if user provided a file-like path, use its directory
                if cache_path.endswith('.json'):
                    cache_path = _os.path.dirname(cache_path) or 'data/cache'
                _os.makedirs(cache_path, exist_ok=True)
                self._disk_cache = Cache(cache_path)
        except Exception as e:
            logger.debug(f"Disk cache unavailable: {e}")

        if LLM_AVAILABLE:
            try:
                # Initialize with optional Redis URL
                if redis_url:
                    self.llm_manager = LLMManager(redis_url=redis_url)
                else:
                    # Try without Redis for local development
                    self.llm_manager = LLMManager()
                
                self.model_dispatcher = ModelDispatcher()
                logger.info("LLM integration initialized successfully")
                
            except Exception as e:
                logger.warning(f"Could not initialize LLM engine: {e}")
                self.llm_manager = None
                self.model_dispatcher = None
        else:
            logger.warning("LLM service not available, checking LiteLLM provider config")
            # Provider-agnostic simple client via LiteLLM
            self.lite_provider = None
            if LITE_AVAILABLE and settings.llm_provider:
                self.lite_provider = settings.llm_provider
                logger.info(f"LiteLLM configured for provider: {self.lite_provider}")
    
    def analyze_component_advanced(self, component_data: Dict[str, Any]) -> Dict[str, Any]:
        """Advanced component analysis using LLM."""
        if not self.llm_manager:
            # Try LiteLLM unified call
            if self._lite_enabled():
                try:
                    prompt = self._create_component_analysis_prompt(component_data)
                    resp = self._lite_complete(prompt)
                    return self._parse_llm_response(resp)
                except Exception as e:
                    logger.warning(f"LiteLLM analysis failed: {e}")
                    return self._fallback_analysis(component_data)
            return self._fallback_analysis(component_data)
        
        try:
            prompt = self._create_component_analysis_prompt(component_data)
            response = self.llm_manager.generate_response(prompt)
            
            # Parse structured response
            analysis = self._parse_llm_response(response)
            # Validate
            valid = try_validate(ComponentAnalysis, analysis)
            return valid.model_dump() if valid else analysis
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return self._fallback_analysis(component_data)
    
    def generate_repair_guide(self, component_data: Dict[str, Any]) -> str:
        """Generate detailed repair guide using LLM."""
        if not self.llm_manager:
            if self._lite_enabled():
                try:
                    prompt = self._create_repair_guide_prompt(component_data)
                    return self._lite_complete(prompt)
                except Exception as e:
                    logger.warning(f"LiteLLM repair guide failed: {e}")
                    return self._fallback_repair_guide(component_data)
            return self._fallback_repair_guide(component_data)
        
        try:
            prompt = self._create_repair_guide_prompt(component_data)
            response = self.llm_manager.generate_response(prompt)
            return response
            
        except Exception as e:
            logger.error(f"LLM repair guide generation failed: {e}")
            return self._fallback_repair_guide(component_data)
    
    def suggest_projects(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Suggest projects based on available components using LLM."""
        if not self.llm_manager:
            if self._lite_enabled():
                try:
                    prompt = self._create_project_suggestion_prompt(components)
                    resp = self._lite_complete(prompt)
                    return self._parse_project_suggestions(resp)
                except Exception as e:
                    logger.warning(f"LiteLLM project suggestions failed: {e}")
                    return self._fallback_project_suggestions(components)
            return self._fallback_project_suggestions(components)
        
        try:
            prompt = self._create_project_suggestion_prompt(components)
            response = self.llm_manager.generate_response(prompt)
            
            suggestions = self._parse_project_suggestions(response)
            valid = try_validate(ProjectSuggestionList, {"projects": suggestions})
            return valid.model_dump()["projects"] if valid else suggestions
            
        except Exception as e:
            logger.error(f"LLM project suggestions failed: {e}")
            return self._fallback_project_suggestions(components)
    
    def assess_component_condition(self, component_data: Dict[str, Any], image_analysis: str = None) -> Dict[str, Any]:
        """Assess component condition using LLM."""
        if not self.llm_manager:
            if self._lite_enabled():
                try:
                    prompt = self._create_condition_assessment_prompt(component_data, image_analysis)
                    resp = self._lite_complete(prompt)
                    return self._parse_condition_assessment(resp)
                except Exception as e:
                    logger.warning(f"LiteLLM condition assessment failed: {e}")
                    return self._fallback_condition_assessment(component_data)
            return self._fallback_condition_assessment(component_data)
        
        try:
            prompt = self._create_condition_assessment_prompt(component_data, image_analysis)
            response = self.llm_manager.generate_response(prompt)
            
            assessment = self._parse_condition_assessment(response)
            valid = try_validate(ConditionAssessment, assessment)
            return valid.model_dump() if valid else assessment
            
        except Exception as e:
            logger.error(f"LLM condition assessment failed: {e}")
            return self._fallback_condition_assessment(component_data)
    
    def generate_educational_content(self, component_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate educational content using LLM."""
        if not self.llm_manager:
            if self._lite_enabled():
                try:
                    prompt = self._create_educational_content_prompt(component_data)
                    resp = self._lite_complete(prompt)
                    return self._parse_educational_content(resp)
                except Exception as e:
                    logger.warning(f"LiteLLM educational content failed: {e}")
                    return self._fallback_educational_content(component_data)
            return self._fallback_educational_content(component_data)

    def _lite_enabled(self) -> bool:
        return LITE_AVAILABLE and getattr(self, "lite_provider", None) is not None

    def _get_available_fallback_providers(self) -> list:
        """
        Get list of available fallback providers based on configured API keys.

        Returns:
            List of (model_string, provider_name) tuples for providers with valid API keys
        """
        import os
        available = []

        for provider, model, env_key in FALLBACK_PROVIDERS:
            api_key = os.environ.get(env_key)
            if api_key and len(api_key) > 5:  # Basic sanity check
                # LiteLLM format: provider/model or just model for openai
                if provider == "openai":
                    model_str = model
                else:
                    model_str = f"{provider}/{model}"
                available.append((model_str, provider))

        return available

    def _try_fallback_providers(self, prompt: str) -> Optional[str]:
        """
        Try fallback providers when primary LiteLLM call fails.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            Response text if successful, None if all fallbacks fail
        """
        if not LITE_AVAILABLE:
            return None

        available_providers = self._get_available_fallback_providers()
        if not available_providers:
            logger.warning("No fallback providers available (no API keys configured)")
            return None

        for model_str, provider_name in available_providers:
            try:
                logger.info(f"Trying fallback provider: {provider_name}")
                system_msg = {
                    "role": "system",
                    "content": (
                        "You are a strict JSON generator. Respond with ONLY valid, minified JSON. "
                        "Do not include explanations, prose, or code fences."
                    ),
                }
                response = litellm.completion(
                    model=model_str,
                    messages=[system_msg, {"role": "user", "content": prompt}],
                    timeout=30,
                )

                # Extract text from response
                choice = response["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    text = choice["message"]["content"] or ""
                    logger.info(f"Fallback provider {provider_name} succeeded")
                    return text
                if "text" in choice:
                    text = choice["text"] or ""
                    logger.info(f"Fallback provider {provider_name} succeeded")
                    return text

            except Exception as e:
                logger.warning(f"Fallback provider {provider_name} failed: {e}")
                continue

        logger.error("All fallback providers failed")
        return None

    def _lite_complete(self, prompt: str) -> str:
        """Make a completion call via LiteLLM with configured provider/model.

        If the primary provider fails after retries, attempts fallback providers
        before raising an exception.
        """
        if not self._lite_enabled():
            raise RuntimeError("LiteLLM not configured")
        model = settings.llm_model or "command-r"
        provider = settings.llm_provider
        # LiteLLM uses environment variables per provider; ensure keys are present
        # We rely on env already loaded via Settings
        kwargs = {}
        if settings.llm_api_base:
            kwargs["api_base"] = settings.llm_api_base

        # Cache key for this prompt
        cache_key = f"{model}:{hash(prompt)}" if settings.llm_cache_enabled else None

        # Check cache first
        if cache_key:
            # disk cache first
            if self._disk_cache is not None:
                cached = self._disk_cache.get(cache_key, default=None)
                if cached is not None:
                    return cached
            # memory cache
            if cache_key in self._cache:
                return self._cache[cache_key]

        # Helper to cache and return result
        def _cache_and_return(text: str) -> str:
            if cache_key and settings.llm_cache_enabled:
                self._cache[cache_key] = text
                if self._disk_cache is not None:
                    self._disk_cache.set(cache_key, text, expire=getattr(settings, "llm_cache_ttl_seconds", 3600))
            return text

        # Basic retry/backoff for primary provider
        last_exc = None
        for attempt in range(3):
            try:
                system_msg = {
                    "role": "system",
                    "content": (
                        "You are a strict JSON generator. Respond with ONLY valid, minified JSON. "
                        "Do not include explanations, prose, or code fences."
                    ),
                }
                response = litellm.completion(
                    model=model,
                    messages=[system_msg, {"role": "user", "content": prompt}],
                    **kwargs,
                )
                # Extract text depending on provider format
                choice = response["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    return _cache_and_return(choice["message"]["content"] or "")
                if "text" in choice:
                    return _cache_and_return(choice["text"] or "")
                return _cache_and_return(json.dumps(response))

            except Exception as e:
                last_exc = e
                logger.warning(f"Primary LLM attempt {attempt + 1} failed: {e}")
                import time as _t
                _t.sleep(0.5 * (attempt + 1))

        # Primary provider failed - try fallback providers
        logger.warning(f"Primary provider {provider}/{model} failed after 3 attempts, trying fallbacks")
        fallback_result = self._try_fallback_providers(prompt)
        if fallback_result is not None:
            return _cache_and_return(fallback_result)

        # All providers failed
        raise RuntimeError(f"LLM completion failed (primary and all fallbacks): {last_exc}")
    
    def _create_component_analysis_prompt(self, component_data: Dict[str, Any]) -> str:
        """Create prompt for component analysis."""
        return (
            "Analyze this electronic component for educational and reuse potential.\n"
            f"Component Type: {component_data.get('type', 'unknown')}\n"
            f"Detection Confidence: {component_data.get('detection_confidence', 0):.2f}\n"
            f"Capabilities: {', '.join(component_data.get('capabilities', []))}\n"
            f"Market Value: ${component_data.get('market_value', 0):.2f}\n\n"
            "Return ONLY valid JSON with these keys (no prose, no code fences):\n"
            "{\n"
            "  \"educational_value\": \"high|medium|low\",\n"
            "  \"reuse_potential\": \"high|medium|low\",\n"
            "  \"failure_modes\": [""],\n"
            "  \"testing_procedures\": [""],\n"
            "  \"safety_considerations\": [""],\n"
            "  \"repair_difficulty\": \"easy|medium|hard\",\n"
            "  \"estimated_lifespan\": \"years\",\n"
            "  \"environmental_impact\": \"low|medium|high\"\n"
            "}"
        )
    
    def _create_repair_guide_prompt(self, component_data: Dict[str, Any]) -> str:
        """Create prompt for repair guide generation."""
        return (
            "Generate a detailed repair guide for this electronic component.\n"
            f"Component: {component_data.get('type', 'unknown')}\n"
            f"Current repair guide: {component_data.get('repair_guide', 'No guide available')}\n\n"
            "Return ONLY plain text with ordered steps and safety notes."
        )
    
    def _create_project_suggestion_prompt(self, components: List[Dict[str, Any]]) -> str:
        """Create prompt for project suggestions."""
        component_list = []
        for comp in components:
            component_list.append(f"- {comp['type']}: {', '.join(comp.get('capabilities', []))}")
        
        return (
            "Suggest educational projects that can be built with these components.\n\n"
            "Available Components:\n" + "\n".join(component_list) + "\n\n"
            "Return ONLY valid JSON with a 'projects' array of objects containing: \n"
            "name, description, difficulty, time_estimate, components_used, skills_learned, educational_value, estimated_cost, safety_level."
        )
    
    def _create_condition_assessment_prompt(self, component_data: Dict[str, Any], image_analysis: str = None) -> str:
        """Create prompt for condition assessment."""
        return (
            "Assess the condition of this electronic component.\n"
            f"Component: {component_data.get('type', 'unknown')}\n"
            f"Detection Confidence: {component_data.get('detection_confidence', 0):.2f}\n"
            f"Image Analysis: {image_analysis or 'No image analysis available'}\n\n"
            "Return ONLY valid JSON with: condition, confidence (0..1), visible_damage[], estimated_functionality (0..100%), reuse_recommendation, safety_concerns[], testing_required[]."
        )
    
    def _create_educational_content_prompt(self, component_data: Dict[str, Any]) -> str:
        """Create prompt for educational content generation."""
        return (
            "Generate educational content for this electronic component.\n"
            f"Component: {component_data.get('type', 'unknown')}\n"
            f"Capabilities: {', '.join(component_data.get('capabilities', []))}\n\n"
            "Return ONLY valid JSON with: tutorial, key_concepts[], common_applications[], safety_notes[], troubleshooting[], quiz_questions[]."
        )
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured data."""
        try:
            # Try to extract JSON from response
            if '{' in response and '}' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
                data = json.loads(json_str)
                # Minimal schema normalization
                if not isinstance(data, dict):
                    return {"raw": data}
                return data
            else:
                # Fallback to basic parsing
                return {"raw_response": response}
        except json.JSONDecodeError:
            return {"raw_response": response, "parse_error": True}
    
    def _parse_project_suggestions(self, response: str) -> List[Dict[str, Any]]:
        """Parse project suggestions from LLM response."""
        try:
            parsed = self._parse_llm_response(response)
            return parsed.get("projects", [])
        except Exception:
            return []
    
    def _parse_condition_assessment(self, response: str) -> Dict[str, Any]:
        """Parse condition assessment from LLM response."""
        try:
            return self._parse_llm_response(response)
        except Exception:
            return {"condition": "unknown", "confidence": 0.0}
    
    def _parse_educational_content(self, response: str) -> Dict[str, Any]:
        """Parse educational content from LLM response."""
        try:
            return self._parse_llm_response(response)
        except Exception:
            return {"tutorial": "Content generation failed"}
    
    def _fallback_analysis(self, component_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback analysis when LLM is not available."""
        return {
            "educational_value": component_data.get("educational_value", "medium"),
            "reuse_potential": component_data.get("reuse_value", "unknown"),
            "failure_modes": ["overheating", "physical damage", "electrical stress"],
            "testing_procedures": ["visual inspection", "multimeter testing", "functional test"],
            "safety_considerations": ["discharge capacitors", "wear safety gear", "work in well-ventilated area"],
            "repair_difficulty": "medium",
            "estimated_lifespan": "5-10 years",
            "environmental_impact": "low"
        }
    
    def _fallback_repair_guide(self, component_data: Dict[str, Any]) -> str:
        """Fallback repair guide."""
        return f"""
        Repair Guide for {component_data.get('type', 'unknown')}:
        
        1. Safety First
           - Disconnect power
           - Wear safety gear
           - Work in well-ventilated area
        
        2. Visual Inspection
           - Check for physical damage
           - Look for burnt components
           - Inspect solder joints
        
        3. Testing
           - Use multimeter for basic tests
           - Check for shorts and opens
           - Verify component values
        
        4. Repair or Replace
           - Minor damage: repair possible
           - Major damage: replace component
           - When in doubt: replace
        
        5. Quality Control
           - Test after repair
           - Verify functionality
           - Document changes
        """
    
    def _fallback_project_suggestions(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback project suggestions."""
        return [
            {
                "name": "Basic Component Tester",
                "description": "Build a simple circuit to test components",
                "difficulty": "beginner",
                "time_estimate": "2-3 hours",
                "components_used": [comp["type"] for comp in components],
                "skills_learned": ["basic electronics", "testing", "soldering"],
                "educational_value": "high",
                "estimated_cost": "$5.00",
                "safety_level": "low"
            }
        ]
    
    def _fallback_condition_assessment(self, component_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback condition assessment."""
        return {
            "condition": "unknown",
            "confidence": 0.5,
            "visible_damage": ["unknown"],
            "estimated_functionality": "50%",
            "reuse_recommendation": "maybe",
            "safety_concerns": ["unknown condition"],
            "testing_required": ["full functional test"]
        }
    
    def _fallback_educational_content(self, component_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback educational content."""
        return {
            "tutorial": f"Learn about {component_data.get('type', 'electronic components')}",
            "key_concepts": ["basic electronics", "component function", "safety"],
            "common_applications": ["circuit building", "testing", "repair"],
            "safety_notes": ["always disconnect power", "wear safety gear"],
            "troubleshooting": ["check connections", "test with multimeter"],
            "quiz_questions": [
                {
                    "question": f"What is a {component_data.get('type', 'component')}?",
                    "options": ["A device", "A tool", "A material", "A process"],
                    "correct": "A",
                    "explanation": "It's an electronic device"
                }
            ]
        }


def main():
    """Test LLM integration."""
    print("🧠 Testing LLM Integration")
    print("=" * 40)
    
    # Test without Redis (for development)
    llm_integration = CircuitLLMIntegration()
    
    # Test component analysis
    test_component = {
        "type": "ic_chip",
        "detection_confidence": 0.95,
        "capabilities": ["arduino_projects", "iot_devices"],
        "market_value": 0.50,
        "educational_value": "high"
    }
    
    analysis = llm_integration.analyze_component_advanced(test_component)
    print(f"✅ Component analysis: {analysis.get('educational_value', 'unknown')}")
    
    repair_guide = llm_integration.generate_repair_guide(test_component)
    print(f"✅ Repair guide generated: {len(repair_guide)} characters")
    
    print("\n📋 LLM Integration Status:")
    print(f"   • LLM Available: {LLM_AVAILABLE}")
    print(f"   • Manager Initialized: {llm_integration.llm_manager is not None}")
    print(f"   • Fallback Mode: {llm_integration.llm_manager is None}")


if __name__ == "__main__":
    main() 