# Install report — DESKTOP-FGEDHGV (WSL2) — alpha.15 live vision

| Field | Value |
|-------|-------|
| **Tester** | maintainer via `HS_ALIEN_QWEN=1 deploy_alien_quickstart.sh` |
| **Date** | 2026-07-10 |
| **Git tag** | `v1.1.0-alpha.15` |
| **Machine** | `DESKTOP-FGEDHGV` / WSL2 Ubuntu 24.04 |
| **Wall** | 100 s |

## Command

```bash
HS_ALIEN_QWEN=1 bash scripts/deploy_alien_quickstart.sh v1.1.0-alpha.15
```

## Results

| Step | Result |
|------|--------|
| prior bar (1–5e) | PASS |
| Qwen phrase | PASS (`tokens=3065`) |
| live photo→salvage | PASS (`mode=live`, blocks=1) |
| live vision-assist | PASS (`live=True`, gates unchanged) |

```
deploy_alien_quickstart: PASS (v1.1.0-alpha.15 on desktop-fgedhgv)
```

## Notes

- Live VL used golden RC photo + unlocked vision budget env.
- Second public PCB (`arduino_leonardo_pcb.jpg`) committed for future smoke; not required in this bar.
- Physical DMM café session still the only leftover that needs real hardware.
