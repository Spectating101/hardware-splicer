# Operations runbook — Splice Agent v1

**Purpose:** Run, monitor, upgrade, and recover Splice Agent on a lab or LAN server.

**Audience:** Lab admins, EMS NPI desk, integrators.

**Related:** [`../deploy/DEPLOY.md`](../deploy/DEPLOY.md) · [`PACKAGING_AND_DEPLOYMENT.md`](PACKAGING_AND_DEPLOYMENT.md)

---

## 1. Architecture (v1)

```text
[Operator browser] ──► [hs-serve :8787] ──► [SQLite job store]
                              │
                              ├──► KiCad CLI (same host)
                              ├──► Node build compiler (circuit-ai-frontend)
                              └──► Build artifacts → HARDWARE_SPLICER_TMP_ROOT
```

KiCad **must** run on the same machine as compile. There is no remote KiCad worker in v1.

---

## 2. Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PYTHONPATH` | — | Set to `src` if not using pip install |
| `HARDWARE_SPLICER_TMP_ROOT` | system temp | Build output directory |
| `HARDWARE_SPLICER_STATE_DIR` | `/tmp/hardware_splicer_state` | Job DB parent |
| `HARDWARE_SPLICER_JOB_DB` | under state dir | SQLite path override |
| `HARDWARE_SPLICER_JOB_WORKERS` | `1` | In-process job workers |
| `HARDWARE_SPLICER_SERVE_UI` | off | `1` = serve `apps/splice-ui/dist` at `/` |
| `HARDWARE_SPLICER_AUTOROUTE` | `0` | Keep `0` for honest v1 demos |
| `HARDWARE_SPLICER_DRC_FIX_LOOP` | `1` | DRC retry loop in CI/prod |

Full list: [`INTEGRATION.md`](INTEGRATION.md).

---

## 3. Start / stop

**Foreground (demo):**

```bash
source .venv/bin/activate
make splice-ui-serve
# or
HARDWARE_SPLICER_SERVE_UI=1 hs-serve --host 127.0.0.1 --port 8787
```

**systemd:** copy [`../deploy/systemd/hardware-splicer.service.example`](../deploy/systemd/hardware-splicer.service.example), adjust paths, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hardware-splicer
sudo systemctl status hardware-splicer
```

**Stop:**

```bash
sudo systemctl stop hardware-splicer
```

---

## 4. Health checks

```bash
curl -sf http://127.0.0.1:8787/health | jq .
hs-doctor
```

Expected: `"ok": true`, KiCad and Node reported in doctor.

**Periodic:** disk space on `HARDWARE_SPLICER_TMP_ROOT` (builds can be large).

---

## 5. Logs

| Source | Location |
|--------|----------|
| systemd | `journalctl -u hardware-splicer -f` |
| Foreground uvicorn | stdout/stderr |
| Job failures | `GET /v1/jobs/{id}` → `error` field |

Enable persistent journal on production hosts.

---

## 6. Backup

Back up:

1. **Job database** — `$HARDWARE_SPLICER_STATE_DIR` (or `HARDWARE_SPLICER_JOB_DB`)
2. **Active build dirs** — under `HARDWARE_SPLICER_TMP_ROOT` if customers need re-download

v1 does not auto-prune old builds. Schedule cron cleanup for dirs older than N days if disk is tight.

---

## 7. Upgrade procedure

```bash
cd /opt/hardware-splicer
sudo systemctl stop hardware-splicer
git fetch
git checkout v1.0.1   # or new tag
bash scripts/install_splice_v1.sh
make splice-ui-build    # if serving UI
hs-doctor
sudo systemctl start hardware-splicer
```

Read `CHANGELOG.md` and release notes for breaking API changes (rare in v1.0.x).

---

## 8. Recovery

| Failure | Action |
|---------|--------|
| KiCad missing after OS update | Reinstall KiCad; verify `kicad-cli` on PATH |
| Stuck job `running` | Restart service; check job store; cancel via API if needed |
| Disk full | Clean `HARDWARE_SPLICER_TMP_ROOT`; expand volume |
| UI 404 on `/` | Run `make splice-ui-build`; set `HARDWARE_SPLICER_SERVE_UI=1` |
| DRC failures | Expected for bad intake — inspect `COMPILE_CASEFILE.json` |

---

## 9. LAN exposure

Do **not** bind `0.0.0.0` without a reverse proxy.

Use [`../deploy/nginx/splice-agent.conf.example`](../deploy/nginx/splice-agent.conf.example):

- TLS termination
- API key header check
- Rate limit (optional)

---

## 10. Windows / WSL

v1 install script is bash. For Windows hosts, run the stack inside **WSL2 Ubuntu** and follow this runbook as Linux.

Native Windows support is not documented for v1.
