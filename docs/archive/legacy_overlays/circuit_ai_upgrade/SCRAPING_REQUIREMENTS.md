# Knowledge Engine: Content Scraping Requirements

**Objective:** Upgrade the "Knowledge Bridge" from using Headlines (Low Fidelity) to Full Article Content (High Fidelity) to prevent context errors.

## 1. The Pipeline
```
[NEWS_SOURCES.json] -> [URL Scraper] -> [Content Cleaner] -> [Summarizer] -> [Knowledge Bridge]
```

## 2. Requirements for the Scraper

### A. Input Handling
*   Must consume the `url` field from `NEWS_SOURCES.json` (RSS feeds).
*   Must handle pagination if the feed is truncated.

### B. Content Extraction (The Critical Part)
*   **Target:** Extract the *technical body text*.
*   **Exclude:** Comments, Sidebars, "Recommended for you," and Ads.
*   **Why:** If the AI reads "Recommended: Buy this unrelated Shoes," it might hallucinate shoe components in the circuit.

### C. Output Format (JSON)
The scraping system must output a JSON stream consumable by `knowledge_bridge.py`:

```json
{
  "source": "Hackaday",
  "title": "Don't use 5V logic with ESP32",
  "url": "https://hackaday.com/...",
  "full_text_summary": "The ESP32 is not 5V tolerant. Connecting 5V sensors directly will burn the GPIO...",
  "key_technical_terms": ["level shifter", "voltage divider", "logic level"]
}
```

## 3. Integration Logic
*   **Current State:** `knowledge_bridge.py` uses a hardcoded list of strings.
*   **Future State:** It should load `scraped_insights.json`.

```python
# Pseudo-code for integration
signals = load_json("scraped_insights.json")
result = bridge.critique_design_with_context(user_design, signals)
```

## 4. Failure Modes to Avoid
1.  **Paywalls:** If the scraper hits a paywall (EE Times), skip it. Do not feed "Subscribe to read more" to the AI.
2.  **Clickbait:** If the article body contradicts the title, the `full_text_summary` must reflect the *body*.
