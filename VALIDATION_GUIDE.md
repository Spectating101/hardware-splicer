# Circuit-AI Validation & Calibration Guide

**Current Status:** Safe Prototype (Beta).
**Verified Baseline:** None established yet. Run the steps below with your own labeled images to create one.

This guide outlines the steps required to establish and maintain production readiness.

---

## 1. Establish a Baseline
Create your own small labeled set (at least 5–10 images per target use case) and record results. Keep a simple JSON/CSV of expected outcomes for reproducibility.

---

## 2. Golden Image Smoke Test
To prevent regressions (updates breaking the vision system), you must establish a "Golden Image".

1.  **Select a Board:** Pick one high-quality image of an Arduino Uno (or your target board).
2.  **Define Truth:** Create a JSON file listing expected detections.
    ```json
    {
      "filename": "golden_arduino.jpg",
      "expected_counts": {
        "ATMEGA328P": 1,
        "USB_Port": 1,
        "Capacitor": 4
      },
      "min_confidence": 0.85
    }
    ```
3.  **Run Test:** Create a CI script that fails if the system finds *fewer* items than expected.

---

## 3. Retro-Check Calibration (Precision/Recall)
The `RetroAuthenticator` uses heuristics. You must tune them.

**Data Requirements:**
*   Folder `tests/data/real_carts/` (10 images of genuine games).
*   Folder `tests/data/fake_carts/` (10 images of known fakes).

**Calibration Loop:**
1.  Run `circuit_ai_cli.py --mode retro` on all 20 images.
2.  Calculate **False Positives** (Real called Fake) and **False Negatives** (Fake called Real).
3.  **Tune Thresholds:**
    *   Adjust `RetroAuthenticator` logic (e.g., "Black Blob" detection sensitivity).
    *   Adjust OCR fuzzy matching (e.g., "Nintondo" vs "Ninlendo").

---

## 4. Spectral Topology Verification
The `SpectralCircuitAnalyzer` identifies functional blocks (filters, dividers).

**Verification:**
1.  **Input:** 5 images of simple "Textbook Circuits" (e.g., a clear breadboard photo of a Voltage Divider).
2.  **Expected Output:** `{"topology": "Voltage Divider", "confidence": >0.8}`.
3.  **Action:** If it fails, adjust the `tolerance` in `spectral_circuit_analyzer.py` (currently 0.1).

---

## 5. Salvage Pricing Update
The prices in `salvage_consultant.py` are static estimates.

**Action:**
*   Connect to eBay API (Future Feature) OR
*   Quarterly manual update of `HIGH_VALUE_KEYWORDS` based on market trends (e.g., if STM32 prices drop, update the file).
