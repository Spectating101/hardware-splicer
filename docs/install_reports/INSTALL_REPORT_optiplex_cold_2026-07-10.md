# Install report — cold-internal alpha.12

| Field | Value |
|-------|-------|
| **Tester** | maintainer (cold-internal proxy) |
| **Date** | 2026-07-10 |
| **Git tag / commit** | pre-tag `HEAD` with vision-assist + quickstart 5b (tagged `v1.1.0-alpha.12`) |
| **Machine name** | optiplex (fresh `git archive` extract under `_cold_runs/`) |
| **OS** | Debian 13 (linux 6.12) |
| **Mode** | Cold-internal dry-run — fresh archive, no dirty checkout |

## Automated bar

```bash
git archive HEAD | gzip > hs-cold-internal-alpha12.tar.gz
HS_TRACK_ROOT=... HS_QUICKSTART_PORT=8799 \
  bash scripts/agent_quickstart_verify.sh hs-cold-internal-alpha12.tar.gz
```

| Step | Result |
|------|--------|
| install + doctor | PASS |
| catalog ≥ 50 | PASS (50) |
| sync canvas agent-loop | PASS (0 DRC) |
| async compose job | PASS (0 DRC) |
| salvage donor_context | PASS (`salvage_catalog` / `robot_drive_base`) |
| compose+bench simulate | PASS (`power_on_authorized`) |
| vision-assist draft | PASS (`gates_unchanged`, not power-on) |
| **Wall time** | **126 s** |

## Notes

- No strangers required for this bar; alien FGEDHGV remains the second-machine proof path.
- Vision assist used golden `tests/data/golden/rc_toy_motor_board.jpg` offline (`live=false`).
- `/tmp` was full during first attempt — cold extracts should prefer home disk + `TMPDIR` on large trees.
