# Install report — optiplex cold alpha.15 (live vision)

| Field | Value |
|-------|-------|
| **Tester** | maintainer cold-internal |
| **Date** | 2026-07-10 |
| **Tag** | `v1.1.0-alpha.15` |
| **Machine** | optiplex (fresh archive + `.env.local`) |
| **Wall** | 117 s |

| Step | Result |
|------|--------|
| 1–5e prior bar | PASS |
| 6 Qwen phrase | PASS (`tokens=3065`) |
| 6b live photo→salvage | PASS (`mode=live`, blocks≥1) |
| 6c live vision-assist | PASS (`live=True`, gates unchanged) |

## Notes

- Unlocked vision budget via `VISION_MONTHLY_USD_LIMIT` (defaults were $0 → `blocked_disabled`).
- Procured second public PCB: `tests/data/golden/arduino_leonardo_pcb.jpg` (CC BY-SA 2.0).
- FreeRouting jar present locally; default compose path still `cosmetic_preview` (honesty preserved).
