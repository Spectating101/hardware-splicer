# Install report — DESKTOP-FGEDHGV (WSL2) — alpha.14 leftovers bar

| Field | Value |
|-------|-------|
| **Tester** | maintainer via `HS_ALIEN_QWEN=1 deploy_alien_quickstart.sh` |
| **Date** | 2026-07-10 |
| **Git tag** | `v1.1.0-alpha.14` |
| **Machine** | `DESKTOP-FGEDHGV` / WSL2 Ubuntu 24.04 |
| **Wall** | 79 s |

## Command

```bash
HS_ALIEN_QWEN=1 bash scripts/deploy_alien_quickstart.sh v1.1.0-alpha.14
```

## Results

| Step | Result |
|------|--------|
| install + doctor | PASS |
| catalog / canvas / async / salvage | PASS |
| sim bench + vision-assist + golden-real | PASS |
| donor-board-vision offline | PASS (`applied=1`, 6 blocks) |
| copper honesty | PASS (`cosmetic_preview`, not fab-ready) |
| Qwen phrase (step 6) | PASS (`tokens=3065`) |

```
deploy_alien_quickstart: PASS (v1.1.0-alpha.14 on desktop-fgedhgv)
```

## Notes

- `.env.local` scp'd via `HS_ALIEN_QWEN=1` (not in git archive).
- Live café DMM still requires physical instruments — see `docs/REAL_BENCH_OPERATOR.md`.
