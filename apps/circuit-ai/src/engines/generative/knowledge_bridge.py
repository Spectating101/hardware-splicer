from typing import List, Dict, Any
import json
import re
from pathlib import Path
try:
    from .generative_design_agent import GenerativeAgent
except ImportError:
    from generative_design_agent import GenerativeAgent

def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\\-]{2,}", text or "")}


def _truncate_words(text: str, max_words: int) -> str:
    words = (text or "").split()
    if len(words) <= max_words:
        return (text or "").strip()
    return " ".join(words[:max_words]).strip() + "…"


def _rank_signals(original_plan: Dict[str, Any], signals: List[Dict[str, Any]], *, max_signals: int = 5) -> List[Dict[str, Any]]:
    """
    Keep the prompt small and relevant by ranking signals against the plan.
    This avoids diluting the critique with unrelated headlines.
    """
    plan_blob = json.dumps(original_plan, ensure_ascii=False)
    plan_tokens = _tokenize(plan_blob)
    if not plan_tokens:
        return signals[:max_signals]

    scored: list[tuple[int, Dict[str, Any]]] = []
    for s in signals:
        title = str(s.get("title") or "")
        summary = str(s.get("full_text_summary") or "")
        terms = s.get("key_technical_terms") or []
        term_blob = " ".join(str(t) for t in terms)

        text_tokens = _tokenize(title + " " + term_blob + " " + summary)
        overlap = len(plan_tokens.intersection(text_tokens))

        # Small bias toward voltage/level-shifting topics for embedded plans
        low = (title + " " + summary).lower()
        bias = 0
        if any(k in low for k in ("voltage", "level shifter", "logic level", "adc", "i2c", "gpio")):
            bias += 1
        scored.append((overlap + bias, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [s for score, s in scored if score > 0][:max_signals]
    return top if top else [s for _, s in scored][:max_signals]


class KnowledgeBridge:
    def __init__(self):
        self.ai = GenerativeAgent()

    def critique_design_with_context(self, original_plan: Dict, signals: List[Dict]):
        """
        Takes an established design plan and uses recent news signals 
        to provide a 'Safety & Modernity' critique.
        """
        ranked = _rank_signals(original_plan, signals, max_signals=5)
        compact_signals: List[Dict[str, Any]] = []
        for s in ranked:
            compact_signals.append(
                {
                    "source": s.get("source"),
                    "title": s.get("title"),
                    "url": s.get("url"),
                    "full_text_summary": _truncate_words(str(s.get("full_text_summary") or ""), 220),
                    "key_technical_terms": s.get("key_technical_terms") or [],
                }
            )
        
        prompt = f"""
        Original Engineering Plan: {original_plan}        
        Recent External Signals (Unverified News): 
        {compact_signals}
        
        CRITIQUE TASK:
        1. Review the original plan using standard engineering principles.
        2. Evaluate if any 'External Signals' provide a valid warning or a modern optimization.
        3. If a signal contradicts standard practice, ignore it.
        4. If a signal mentions a known component issue or a significantly better alternative, highlight it as a 'Recommendation'.
        5. Do not assume protocols or voltages not stated; if uncertain, phrase it as a verification step.
        
        Return a 'Critique Report' in the narrative.
        """
        
        return self.ai.generate_solution(prompt, mode="detailed")


def load_scraped_insights(path: Path) -> List[Dict[str, Any]]:
    """
    Loads a JSONL file emitted by the content scraper.
    Each line must be a JSON object containing (at minimum):
      - source, title, url, full_text_summary, key_technical_terms
    """
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


if __name__ == "__main__":
    # SCENARIO: Smart Plant Monitor (Common Beginner Project)
    plant_monitor_plan = {
        "mcu": "ESP32-DevKitC",
        "sensor": "Generic Resistive Soil Moisture Sensor",
        "power": "USB 5V",
        "notes": "Direct analog connection to GPIO 34."
    }
    
    # Prefer real scraped insights if present (JSONL), fallback to the demo strings.
    scraped_path = Path(__file__).resolve().parent / "scraped_insights.jsonl"
    blueprint_signals: List[Dict[str, Any]] = load_scraped_insights(scraped_path)
    if not blueprint_signals:
        blueprint_signals = [
            {
                "source": "Electromaker",
                "title": "Resistive soil sensors corrode within weeks",
                "url": "https://example.com",
                "full_text_summary": "Resistive soil sensors corrode within weeks. Capacitive sensors are a better standard for longevity.",
                "key_technical_terms": ["capacitive", "resistive", "corrosion", "soil sensor"],
            },
            {
                "source": "Maker.io",
                "title": "ESP32 ADC2 limitations with WiFi",
                "url": "https://example.com",
                "full_text_summary": "ESP32 ADC2 pins cannot be used when WiFi is active. Prefer ADC1 (GPIO 32-39) or an external ADC.",
                "key_technical_terms": ["esp32", "adc1", "adc2", "wifi", "gpio"],
            },
            {
                "source": "Hackaday",
                "title": "5V logic mismatch with ESP32",
                "url": "https://example.com",
                "full_text_summary": "Common issue: 5V sensors logic level mismatch with 3.3V ESP32 inputs; use a level shifter/voltage divider.",
                "key_technical_terms": ["level shifter", "voltage divider", "logic level", "3.3v", "5v"],
            },
        ]
    
    bridge = KnowledgeBridge()
    print(">>> RUNNING PROJECT BLUEPRINT CRITIQUE <<<")
    result = bridge.critique_design_with_context(plant_monitor_plan, blueprint_signals)
    
    print("-" * 50)
    print(f"ENGINEER'S VERDICT:\n{result['narrative']}")
    print("-" * 50)
