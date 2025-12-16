# Circuit-AI Quality & Safety Notes

## Detection Quality & Gating
- The agent now reports detection metadata with every run: count, average confidence, quality band (`none` | `low` | `medium` | `high`), model source, and whether a fallback model was used.
- Downstream modules (salvage, retro verification, inspection) only run when detection quality is `medium` or `high`. Otherwise they return “detection quality too low” or an `UNKNOWN` verdict to avoid false positives.
- Vision reports note when a fallback model is used or when no detections are found, so operators can judge reliability.

## Model Provenance
- Enhanced detector records which model was loaded (`trained:best.pt` vs `yolov8n-fallback`). This is surfaced in `detection_summary` and the vision report.
- If the trained weights are missing, the detector falls back to `yolov8n` and marks `fallback_used=True`.

## LLM Safety
- No hardcoded API keys. `CEREBRAS_API_KEY` must be provided via environment. If the key/client is unavailable or `LLM_ENABLED=0`, the agent returns a stubbed LLM response and avoids network calls.
- LLM calls are wrapped with a timeout (`LLM_TIMEOUT_SECONDS`, default 10s) to prevent hangs in restricted environments.

## API Metadata
- API responses include detection metadata in `metadata`: `detection_quality`, `detection_count`, `detection_avg_confidence`, `model_source`, `fallback_used`, and the full `detection_summary` for downstream consumers.

## Secret Hygiene
- Config files no longer contain embedded keys. A pre-commit hook with gitleaks is added to block new secret leaks (`.pre-commit-config.yaml`).

## Local Run Modes
- Offline mode: set `LLM_ENABLED=0` to run vision-only; a stub response is returned for the LLM portion.
- OCR: install `tesseract-ocr` and `pytesseract` to enable text enrichment. If not installed, OCR is skipped with a log notice.
