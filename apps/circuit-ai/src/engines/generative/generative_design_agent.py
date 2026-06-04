"""
Circuit-AI Generative Design Agent (Copilot / Cerebras Optimized)
================================================================
Uses High-Performance LLMs to translate Natural Language -> Circuit Actions.
Targeting: local GitHub Copilot CLI/OAuth first, with Cerebras as API fallback.
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


def _parse_json_text(text: str) -> Dict[str, Any]:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(cleaned[start:end])
        raise


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
        # Prefer the local Copilot CLI/OAuth path for engine testing, then Cerebras.
        self.provider = "unknown"
        self.model = None
        self.api_url = None
        self.api_key = None
        try:
            from src.intelligence.copilot_provider import DEFAULT_COPILOT_MODEL, copilot_provider_status

            copilot_model = os.getenv("COPILOT_MODEL") or DEFAULT_COPILOT_MODEL
            if copilot_provider_status(copilot_model).get("ready_for_live_model"):
                self.provider = "copilot"
                self.model = copilot_model
                return
        except Exception:
            pass

        self.cerebras_key = os.getenv("CEREBRAS_API_KEY")
        if self.cerebras_key:
            self.provider = "cerebras"
            self.model = "llama-3.3-70b"
            self.api_url = "https://api.cerebras.ai/v1/chat/completions"
            self.api_key = self.cerebras_key

    def _call_llm(self, user_prompt: str) -> Dict[str, Any]:
        """Makes a raw HTTP request."""
        if self.provider == "copilot":
            try:
                from src.intelligence.copilot_provider import call_copilot_prompt

                text, _model = call_copilot_prompt(
                    f"{SYSTEM_PROMPT}\n\nUser request:\n{user_prompt}",
                    model=self.model,
                )
                return _parse_json_text(text)
            except Exception as exc:
                return {
                    "type": "error",
                    "narrative": f"Copilot CLI call failed: {exc}",
                }

        if not self.api_key:
            return {
                "type": "error",
                "narrative": "Error: No local Copilot CLI/OAuth provider or CEREBRAS_API_KEY found."
            }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2,
        }
        # Cerebras supports response_format, which helps enforce JSON output.
        if self.provider == "cerebras":
            payload["response_format"] = {"type": "json_object"}

        try:
            url = self.api_url
            headers = {
                "Content-Type": "application/json",
            }

            headers["Authorization"] = f"Bearer {self.api_key}"

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers,
            )
            
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result['choices'][0]['message']['content']
                return _parse_json_text(content)

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
    if agent.provider != "unknown":
        try:
            res = agent.generate_solution("Design a USB-C power delivery circuit")
            print(json.dumps(res, indent=2))
        except Exception as e:
            print(f"Test failed: {e}")
    else:
        print("Skipping test: No local Copilot CLI/OAuth provider or API fallback found.")
