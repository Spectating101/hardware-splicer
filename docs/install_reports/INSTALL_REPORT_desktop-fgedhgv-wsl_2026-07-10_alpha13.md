# Install report — DESKTOP-FGEDHGV (WSL2) — cold-internal alpha.13

| Field | Value |
|-------|-------|
| **Tester** | maintainer via optiplex → `deploy_alien_quickstart.sh` |
| **Date** | 2026-07-10 |
| **Git tag** | `v1.1.0-alpha.13` |
| **Machine** | `DESKTOP-FGEDHGV` / WSL2 Ubuntu 24.04 |
| **Mode** | Cold-internal second-machine (fresh `git archive`) |

## Command

```bash
bash scripts/deploy_alien_quickstart.sh v1.1.0-alpha.13
```

## Results

| Step | Result |
|------|--------|
| install + doctor | PASS |
| catalog ≥ 50 | PASS (50) |
| sync canvas agent-loop | PASS (0 DRC) |
| async compose job | PASS (0 DRC) |
| salvage donor_context | PASS |
| compose+bench simulate | PASS (`power_on_authorized`) |
| vision-assist draft | PASS (`gates_unchanged`) |
| golden-real (non-sim) | PASS (`simulated=False`, matched=5, power_on) |
| **Wall time** | **53 s** |

```
deploy_alien_quickstart: PASS (v1.1.0-alpha.13 on desktop-fgedhgv)
```

## Notes

- Closes the previous “simulated-only” honesty gap for the automated cold bar.
- Golden-real uses committed manual capture JSON + photo provenance — still not a live café DMM session.
- Qwen optional path not re-run this session (`qwen_vision_key=missing` on slim alien install).
