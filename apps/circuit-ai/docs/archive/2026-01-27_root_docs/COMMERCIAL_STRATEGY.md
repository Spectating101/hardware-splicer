# Circuit-AI Commercial Strategy & Spin-off Guide

**Current Status:** The core `CircuitAgent` is now a multi-modal platform capable of powering 4 distinct commercial products. This document maps the code to the business use cases.

---

## 💎 Product 1: "Circuit-Scout" (B2B E-Waste Appraiser)

**Value Prop:** "The metal detector for finding high-value chips in e-waste piles."
**Target Audience:** E-waste recyclers, eBay flippers, Estate sale pickers.
**Monetization:** SaaS Subscription ($29-$99/mo).

### Tech Stack Map
| Feature | Code Module | Logic |
| :--- | :--- | :--- |
| **Jackpot Alert** | `src/intelligence/salvage_consultant.py` | Scans OCR for `Xilinx`, `STM32`, `Intel`, `Gold`. Triggers $$$ alert. |
| **Part Identification** | `src/vision/enhanced_detector.py` | Identifies `IC_Chip`, `Connectors` (High resell value). |
| **Upcycle Tips** | `src/intelligence/salvage_consultant.py` | Suggests "Saw off the Power Supply" to increase scrap value. |

### Launch Strategy
1.  **Wrapper:** Build a simple mobile-first web app (Camera -> API -> Result).
2.  **Marketing:** Cold DM eBay sellers with "I found a $50 chip in your junk pile photo."

---

## 🎮 Product 2: "Retro-Check" (Consumer Authenticator)

**Value Prop:** "Instant verification for Pokemon and Retro Game cartridges."
**Target Audience:** Gamers, Collectors, Parents.
**Monetization:** Micro-transaction ($0.99/scan) or Ad-supported.

### Tech Stack Map
| Feature | Code Module | Logic |
| :--- | :--- | :--- |
| **Fake Spotter** | `src/intelligence/retro_authenticator.py` | Checks for "Black Blob" chips (Fake) vs Square ICs (Real). |
| **Typos Check** | `src/intelligence/retro_authenticator.py` | Scans text for "Nintondo", "Gameoy" errors. |
| **Battery Check** | `src/intelligence/retro_authenticator.py` | Verifies presence of battery for Real Time Clock (RTC) games. |

### Launch Strategy
1.  **Wrapper:** Simple landing page "Upload Cartridge Photo".
2.  **Marketing:** Post on `r/gameverifying` and Retro Gaming Discords.

---

## 🏭 Product 3: "Pocket-AOI" (Manufacturing Inspection)

**Value Prop:** "Automated Optical Inspection (AOI) for small batch assembly."
**Target Audience:** Hardware Startups, Tindie Sellers, Small EMS.
**Monetization:** Per-seat License ($50/mo).

### Tech Stack Map
| Feature | Code Module | Logic |
| :--- | :--- | :--- |
| **Golden Sample Diff** | `src/intelligence/inspection_diff.py` | Compares current board count vs "Perfect" board. |
| **Solder Bridge Detection** | `src/intelligence/advanced_trace_follower.py` | Detects short circuits between nets (Beta). |
| **Missing Part** | `src/vision/enhanced_detector.py` | Flags if `Capacitor` count < Expected. |

### Launch Strategy
1.  **Wrapper:** Desktop/Tablet App (Needs "Set Reference" UI).
2.  **Marketing:** Content marketing on Hackaday, Tindie forums.

---

## 🎓 Product 4: "Circuit-AI" (The Original Vision)

**Value Prop:** "Your AI Lab Partner for Electronics Repair."
**Target Audience:** Students, Hobbyists, Right-to-Repair.
**Monetization:** Freemium / Brand Builder.

### Tech Stack Map
| Feature | Code Module | Logic |
| :--- | :--- | :--- |
| **Fault Diagnosis** | `src/intelligence/fault_detector.py` | Detects burns, corrosion, broken traces. |
| **Board ID** | `src/intelligence/board_analysis_engine.py` | Identifies "Power Supply" vs "Motherboard". |
| **Repair Guide** | `src/circuit_agent.py` | LLM generates step-by-step fix instructions. |

---

## 🚀 Execution Roadmap

**Phase 1: The "Cash Flow" Pivot (Weeks 1-4)**
1.  Focus 100% on **Product 1 (Circuit-Scout)** or **Product 2 (Retro-Check)**.
2.  Do NOT build a complex UI. Use a Telegram Bot or simple Next.js form.
3.  Validate with 10 paying customers.

**Phase 2: The "Platform" Play (Months 2-6)**
1.  Refine the API (`src/circuit_agent.py`) to expose distinct endpoints:
    *   `POST /api/v1/analyze/reseller`
    *   `POST /api/v1/analyze/retro`
    *   `POST /api/v1/analyze/repair`
2.  Sell access to the API itself to other developers.

**Phase 3: Deep Tech (Year 1)**
1.  Train custom YOLO models for specific "Fake Chips" (Retro product).
2.  Expand "Jackpot Database" with scraping (Reseller product).
