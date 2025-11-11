#!/usr/bin/env python3
"""
Set up LLM integration - either API or local model.
"""

import os
from pathlib import Path
from loguru import logger

def setup_llm_api():
    """Guide user to set up LLM API keys."""

    logger.info("🤖 LLM Integration Setup")
    logger.info("=" * 60)

    env_file = Path(".env")
    env_content = env_file.read_text() if env_file.exists() else ""

    logger.info("\n📋 Available LLM Options:")
    logger.info("1. OpenAI (GPT-4, GPT-3.5) - Best quality, paid")
    logger.info("2. Anthropic (Claude) - Great quality, paid")
    logger.info("3. Cohere - Good quality, free tier available")
    logger.info("4. Groq (Llama3) - Fast, free tier available")
    logger.info("5. Local (Ollama) - Free, runs locally")

    logger.info("\n💡 Recommendation: Groq or Cohere for free tier")

    logger.info("\n" + "=" * 60)
    logger.info("Option 1: API Key Setup")
    logger.info("=" * 60)

    logger.info("\n📝 To use API-based LLMs:")
    logger.info("1. Get API key from provider:")
    logger.info("   - Groq: https://console.groq.com")
    logger.info("   - Cohere: https://dashboard.cohere.com")
    logger.info("   - OpenAI: https://platform.openai.com")
    logger.info("   - Anthropic: https://console.anthropic.com")

    logger.info("\n2. Add to .env file:")
    logger.info("   LLM_ENABLED=true")
    logger.info("   COHERE_API_KEY=your_key_here")
    logger.info("   # or OPENAI_API_KEY=your_key_here")
    logger.info("   # or ANTHROPIC_API_KEY=your_key_here")

    logger.info("\n" + "=" * 60)
    logger.info("Option 2: Local LLM (Ollama)")
    logger.info("=" * 60)

    logger.info("\n📦 To use local LLM:")
    logger.info("1. Install Ollama: https://ollama.ai")
    logger.info("2. Pull a model: ollama pull llama3")
    logger.info("3. Update .env:")
    logger.info("   LLM_ENABLED=true")
    logger.info("   LLM_PROVIDER=ollama")
    logger.info("   LLM_MODEL=llama3")

    # Check current status
    logger.info("\n" + "=" * 60)
    logger.info("Current Configuration")
    logger.info("=" * 60)

    llm_enabled = "LLM_ENABLED=true" in env_content
    has_api_keys = any([
        "COHERE_API_KEY=" in env_content and "COHERE_API_KEY=\n" not in env_content,
        "OPENAI_API_KEY=" in env_content and "OPENAI_API_KEY=\n" not in env_content,
        "ANTHROPIC_API_KEY=" in env_content and "ANTHROPIC_API_KEY=\n" not in env_content,
    ])

    if llm_enabled and has_api_keys:
        logger.info("✅ LLM is configured and enabled")
    elif llm_enabled:
        logger.info("⚠️  LLM enabled but no API keys found")
    else:
        logger.info("❌ LLM is disabled")

    logger.info("\n" + "=" * 60)
    logger.info("Quick Start with Groq (Free)")
    logger.info("=" * 60)

    logger.info("""
1. Visit: https://console.groq.com
2. Sign up (free)
3. Create API key
4. Add to .env:
   LLM_ENABLED=true
   GROQ_API_KEY=gsk_...your_key_here

5. Restart the backend:
   python scripts/start_enhanced_system.py
""")

if __name__ == "__main__":
    setup_llm_api()
