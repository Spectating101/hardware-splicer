"""
Circuit-AI Generative Design Agent (Cerebras / Gemini Optimized)
================================================================
Uses High-Performance LLMs to translate Natural Language -> Circuit Actions.
Targeting: Llama-3.3-70b (Cerebras) or Gemini 1.5 Pro (Google)
"""

import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Any

# Load env vars manually for the standalone script context
def load_env_if_needed():
    # Only simple parsing for the demo script
    try:
        # Search upwards from this file (and also CWD) for a `.env.local`.
        candidates = []
        try:
            candidates.append(Path.cwd())
        except Exception:
            pass
        try:
            candidates.append(Path(__file__).resolve().parent)
        except Exception:
            pass
        env_path = None
        for base in candidates:
            for parent in [base, *base.parents]:
                p = parent / ".env.local"
                if p.exists():
                    env_path = p
                    break
            if env_path:
                break

        if env_path:
            with env_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        key, val = line.strip().split("=", 1)
                        if key not in os.environ or not os.environ.get(key):
                            os.environ[key] = val
    except (OSError, ValueError):
        pass

load_env_if_needed()

# Standard Schema for Circuit Actions
SYSTEM_PROMPT = """
You are an expert PCB Design Engineer AI. 
Translate the user's natural language request into a structured JSON circuit modification plan.

RULES:
1. You must ONLY use real, commercially available electronic components (DigiKey/Mouser).
2. If the user asks for fictional parts (e.g., "Flux Capacitor", "Warp Drive", "Magic Smoke"), you must REFUSE. Set "type" to "error" and explain why in "narrative".
3. Do not hallucinate part numbers. Use generic equivalents if specific parts are unknown.

Your Output JSON format must be exactly:
{
  "type": "modification" | "routing" | "optimization" | "unknown" | "error",
  "narrative": "A brief engineer-to-engineer explanation.",
  "components_to_add": [
    { "ref": "string", "type": "string", "package": "string", "value": "string" }
  ],
  "nets_to_route": [
    { "from": "string", "to": "string" }
  ],
  "constraints": ["string"]
}

Example Request: "Add a blinking LED"
Example Output:
{
  "type": "modification",
  "narrative": "Adding a 555-timer astable multivibrator to drive an LED.",
  "components_to_add": [
    { "ref": "U1", "type": "NE555", "package": "SOIC-8", "value": "Timer" },
    { "ref": "D1", "type": "LED", "package": "0805", "value": "Red" }
  ],
  "nets_to_route": [],
  "constraints": []
}

Return raw JSON only.
"""

class GenerativeAgent:
    def __init__(self):
        # Prefer Cerebras for speed, then Gemini, then fallback
        self.cerebras_key = os.getenv("CEREBRAS_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        
        if self.cerebras_key:
            self.provider = "cerebras"
            self.model = "llama-3.3-70b"
            self.api_url = "https://api.cerebras.ai/v1/chat/completions"
            self.api_key = self.cerebras_key
        elif self.gemini_key:
            self.provider = "gemini"
            self.model = "gemini-1.5-pro" # Mapped internally if using OpenAI Compat
            self.api_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            self.api_key = self.gemini_key
        else:
            self.provider = "unknown"
            self.api_key = None

    def _call_llm(self, user_prompt: str) -> Dict[str, Any]:
        """Makes a raw HTTP request."""
        if not self.api_key:
            return {
                "type": "error",
                "narrative": "Error: No API Keys (CEREBRAS_API_KEY or GEMINI_API_KEY) found."
            }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2,
        }
        # Google’s OpenAI-compat endpoint does not reliably support `response_format`.
        # Cerebras does; keep it there to enforce JSON output.
        if self.provider == "cerebras":
            payload["response_format"] = {"type": "json_object"}

        try:
            url = self.api_url
            headers = {
                "Content-Type": "application/json",
            }

            headers["Authorization"] = f"Bearer {self.api_key}"
            # Some Google endpoints also accept/expect this header for API keys.
            if self.provider == "gemini" and (self.api_key or "").startswith("AIza"):
                headers["x-goog-api-key"] = self.api_key

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers,
            )
            
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result['choices'][0]['message']['content']
                return json.loads(content)

        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                body = ""
            return {
                "type": "error",
                "narrative": f"LLM API Call Failed ({self.provider}): {e.code} {e.reason} {body}".strip()
            }
        except Exception as e:
            return {
                "type": "error",
                "narrative": f"LLM API Call Failed ({self.provider}): {str(e)}"
            }

    def generate_solution(self, user_prompt: str, mode: str = "standard") -> Dict[str, Any]:
        print(f"[GenAI] Using {self.provider.upper()} ({self.model})...")
        print(f"[GenAI] Analyzing: '{user_prompt}' (Mode: {mode})")
        
        # Adjust System Prompt for Detail
        if mode == "detailed":
            detail_instruction = " You are a Senior Failure Analysis Engineer. Provide a detailed, step-by-step reasoning in the 'narrative' field. Explain WHY you chose specific components or actions. addressing potential pitfalls (e.g. carbonization, voltage rating)."
            # We inject this into the user prompt or system prompt context
            # For simplicity in this structure, we append to user prompt to force the behavior
            user_prompt += f"\n\n[SYSTEM: {detail_instruction}]"

        plan = self._call_llm(user_prompt)
        
        return {
            "status": "success" if plan.get("type") != "error" else "error",
            "plan": plan,
            "narrative": plan.get("narrative", "No narrative provided.")
        }

if __name__ == "__main__":
    agent = GenerativeAgent()
    
    # Test
    if agent.api_key:
        try:
            res = agent.generate_solution("Design a USB-C power delivery circuit")
            print(json.dumps(res, indent=2))
        except Exception as e:
            print(f"Test failed: {e}")
    else:
        print("Skipping test: No API keys found in environment.")
