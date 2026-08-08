"""Bounded phrase normalization for legacy/offline compatibility.

Lexical typo repair is different from semantic interpretation. Correcting
``tempurature`` to ``temperature`` preserves the user's stated objective; rewriting
``where do I start`` into a plant-watering project does not. The historical semantic
rewrite table therefore requires a separate explicit opt-in and is never implied merely
because the model is unavailable.
"""

from __future__ import annotations

import re
from typing import Any, Dict

TYPO_FIXES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\btempurature\b", re.I), "temperature"),
    (re.compile(r"\bhumdity\b", re.I), "humidity"),
    (re.compile(r"\bultrasonnic\b", re.I), "ultrasonic"),
    (re.compile(r"\besp ?32\b", re.I), "esp32"),
    (re.compile(r"\bpumb\b", re.I), "pump"),
    (re.compile(r"\brelayy\b", re.I), "relay"),
]

# Historical semantic compatibility rewrites. These are SCRIPT_BRAIN and may only run
# behind HARDWARE_SPLICER_OFFLINE_SEMANTIC_REWRITE=1. Keep the table isolated so old
# regression fixtures can still be replayed without contaminating normal product paths.
REWRITES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"make my plants happy|keep the herbs alive|plants? (?:are )?thirsty", re.I), "water my plants when soil is dry"),
    (re.compile(r"room (?:is )?too (?:hot|cold|humid)|how (?:hot|cold|humid) is (?:it|the room)", re.I), "track temperature and humidity in my room"),
    (re.compile(r"(?:is it|will it) (?:safe|okay|ok) to plug in|can i plug (?:it|this) in", re.I), "will this blow up if I plug it in"),
    (re.compile(r"(?:write|get|make|give me) (?:the )?(?:code|software|firmware|sketch|program)", re.I), "generate firmware for this board"),
    (re.compile(r"upload (?:to|code to) (?:the )?(?:board|arduino|esp32)", re.I), "generate firmware for this board"),
    (re.compile(r"shopping list|what parts do i need", re.I), "download the bill of materials"),
    (re.compile(r"(?:order|get) (?:the )?boards? made|send (?:it )?to fab", re.I), "manufacture the circuit board"),
    (re.compile(r"show (?:me )?(?:the )?(?:layout|pcb|board)", re.I), "show me the circuit board"),
    (re.compile(r"how far (?:away|is)|something (?:in front|nearby)", re.I), "need something that senses distance"),
    (re.compile(r"smell(?:s|y)? (?:bad|gas)|kitchen air|stale air", re.I), "read air quality in the kitchen"),
    (re.compile(r"screen (?:that|to) show|display (?:the )?(?:temp|numbers|readings)", re.I), "small screen to show sensor readings"),
    (re.compile(r"weather on (?:a )?(?:touch)?screen|touchscreen.*(?:temp|weather)", re.I), "show room temperature on a color display"),
    (re.compile(r"science fair.*(?:plant|water|garden)", re.I), "water my plants when soil is dry"),
    (re.compile(r"esp32.*wifi.*temp", re.I), "help me track temperature and humidity in my room"),
    (re.compile(r"water the garden|drip irrigation|auto water", re.I), "control a 5v pump for drip irrigation"),
    (re.compile(r"spin (?:a )?motor|make (?:a )?wheel turn", re.I), "test a motor on my bench"),
    (re.compile(r"little car|rc car|toy car that drives", re.I), "little robot that drives around"),
    (re.compile(r"smoke (?:when|from) solder|stinks when i solder", re.I), "desk fan so solder smoke doesn't stink"),
    (re.compile(r"wifi (?:strength|signal)|see (?:nearby )?wifi networks", re.I), "wifi analyzer on a small display"),
    (re.compile(r"turn (?:on|off) (?:the )?light|switch (?:the )?lamp", re.I), "I want a relay to switch a lamp"),
    (re.compile(r"connect (?:everything|them)|finish (?:the )?circuit", re.I), "make it work"),
    (re.compile(r"start (?:over|fresh)|blank (?:slate|canvas)", re.I), "clear the canvas and start over"),
    (re.compile(r"grandma|beginner|simple|easy|no experience|never done this", re.I), "help me "),
    (re.compile(r"don't know (?:anything )?about (?:electronics|wiring|circuits)|not an engineer", re.I), "help me build something simple"),
    (re.compile(r"what (?:do i|should i) (?:need to )?buy|parts list for me", re.I), "download the bill of materials"),
    (re.compile(r"kid'?s? project|school project|science fair", re.I), "help me "),
    (re.compile(r"numbers? on (?:a |the )?screen|see (?:the )?readings?|show (?:me )?(?:the )?temp", re.I), "small screen to show sensor readings"),
    (re.compile(r"hook (?:this|it|everything) up|wire (?:this|it) for me|connect (?:these|them) for me", re.I), "make it work"),
    (re.compile(r"where do i start|no idea where to begin|overwhelmed", re.I), "help me water my plants when soil is dry"),
    (re.compile(r"too complicated|confusing|lost", re.I), "explain "),
    (re.compile(r"download (?:the )?code|starter code|sketch for (?:this|my) board", re.I), "generate firmware for this board"),
    (re.compile(r"am i going to (?:burn|fry|kill) something|burn (?:my|the) house", re.I), "will this blow up if I plug it in"),
]


def expand_user_phrase_with_provenance(text: str) -> Dict[str, Any]:
    """Normalize a phrase while making every compatibility transformation explicit."""
    try:
        from .integrations.llm_policy import (
            offline_phrase_expand_enabled,
            offline_semantic_rewrite_enabled,
        )
    except ImportError:
        from hardware_splicer.integrations.llm_policy import (
            offline_phrase_expand_enabled,
            offline_semantic_rewrite_enabled,
        )

    original = text.strip()
    if not offline_phrase_expand_enabled():
        return {
            "text": original,
            "original_text": original,
            "lexical_normalization_applied": False,
            "semantic_rewrite_applied": False,
            "semantic_rewrite_source": None,
            "authority_effect": "none",
        }

    normalized = original
    lexical_applied = False
    for pattern, replacement in TYPO_FIXES:
        updated = pattern.sub(replacement, normalized)
        if updated != normalized:
            lexical_applied = True
            normalized = updated

    semantic_applied = False
    semantic_source: str | None = None
    if offline_semantic_rewrite_enabled():
        for pattern, replacement in REWRITES:
            if pattern.search(normalized):
                normalized = f"{normalized} {replacement}".strip()
                semantic_applied = True
                semantic_source = pattern.pattern
                break

    return {
        "text": normalized,
        "original_text": original,
        "lexical_normalization_applied": lexical_applied,
        "semantic_rewrite_applied": semantic_applied,
        "semantic_rewrite_source": semantic_source,
        "authority_effect": "none",
    }


def expand_user_phrase(text: str) -> str:
    """Compatibility projection returning only normalized text."""
    return str(expand_user_phrase_with_provenance(text)["text"])
