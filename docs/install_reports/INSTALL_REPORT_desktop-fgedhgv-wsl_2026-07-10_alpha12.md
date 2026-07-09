# Install report — DESKTOP-FGEDHGV (WSL2) — cold-internal alpha.12

| Field | Value |
|-------|-------|
| **Tester** | maintainer via optiplex → `deploy_alien_quickstart.sh` |
| **Date** | 2026-07-10 |
| **Git tag** | `v1.1.0-alpha.12` |
| **Machine** | `DESKTOP-FGEDHGV` / WSL2 Ubuntu 24.04 |
| **Mode** | Cold-internal second-machine (fresh `git archive`) |

## Command

```bash
bash scripts/deploy_alien_quickstart.sh v1.1.0-alpha.12
```

## Results

| Step | Result |
|------|--------|
| install + doctor | PASS (`ok=True`) |
| catalog ≥ 50 | PASS (50) |
| sync canvas agent-loop | PASS (0 DRC) |
| async compose job | PASS (0 DRC) |
| salvage donor_context | PASS (`salvage_catalog` / `robot_drive_base`) |
| compose+bench simulate | PASS (`power_on_authorized`) |
| vision-assist draft | PASS (`gates_unchanged`) |
| **Wall time** | **44 s** |

```
deploy_alien_quickstart: PASS (v1.1.0-alpha.12 on desktop-fgedhgv)
```

## Notes

- Qwen optional path not re-run this session (offline bar only).
- Same automated bar as optiplex cold extract; second machine confirms packaging/path independence.
