# Install report — optiplex cold leftovers bar (pre-alpha.14)

| Field | Value |
|-------|-------|
| **Tester** | maintainer cold-internal |
| **Date** | 2026-07-10 |
| **Tag** | `v1.1.0-alpha.14` (this release) |
| **Machine** | optiplex (reused cold tree + `.env.local`) |
| **Wall** | 46 s |

| Step | Result |
|------|--------|
| 1–5c prior bar | PASS |
| 5d donor-board-vision | PASS (`applied=1`, 6 blocks) |
| 5e copper honesty | PASS (`cosmetic_preview`, not fab-ready) |
| 6 Qwen phrase | PASS (`tokens=3065`) |

## Notes

- Donor vision payload must resolve `@` refs via `load_project_intake` before HTTP POST.
- Qwen auto-enabled when `.env.local` present (`HS_QUICKSTART_QWEN=0` disables).
