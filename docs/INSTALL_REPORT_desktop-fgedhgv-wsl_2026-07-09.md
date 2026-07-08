# Install report — DESKTOP-FGEDHGV (WSL2 Ubuntu 24.04) — alpha.5 Track B

**Purpose:** Phase 0 alien-machine proof — **AGENT_QUICKSTART** path at `v1.1.0-alpha.5` (not just `verify-product-internal`).

**Controller:** optiplex → `ssh desktop-fgedhgv` → WSL `Ubuntu-24.04`

---

## Report metadata

| Field | Value |
|-------|-------|
| **Tester** | agent / optiplex controller |
| **Date** | 2026-07-09 |
| **Git tag / commit** | `v1.1.0-alpha.5` @ `6c63d10` |
| **Machine name** | `DESKTOP-FGEDHGV` |
| **OS** | Windows 11 + **WSL2 Ubuntu 24.04** |
| **KiCad version** | `9.0.9` |
| **Python** | `3.12.3` (WSL venv) |
| **Node** | `v20.20.2` (WSL) |
| **Tailscale** | `100.102.0.84` (`ssh desktop-fgedhgv`) |

---

## Install steps followed

Public path equivalent — tarball deploy (GitHub clone not attempted; prior July run hung).

- [x] `git archive v1.1.0-alpha.5` on optiplex → `hs-alpha5.tar.gz`
- [x] `scp` tarball to `C:\Users\user\` on FGEDHGV
- [x] WSL extract to `/root/hardware-splicer-alpha5` (clean dir)
- [x] `bash scripts/install_splice_v1.sh`
- [x] `hs-doctor` — `ok=True`
- [x] Agent quickstart curls 1–2 per [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md)

**Install script modifications required?** **No**

**Qwen / AI phrase curl (curl 3)?** **PASS** on 2026-07-09 — `qwen_configured=true`, 3072 tokens, 0 DRC errors, package emitted (see log `/root/hs-alpha5-qwen-quickstart.log` on node).

---

## Doctor output

```
ok=True
demo_ready=True
fab_export_ready=True
dependencies: kicad_cli:ok, ngspice:ok, node:ok, npm:ok, fastapi:ok, uvicorn:ok
cadquery:missing, pytest:missing (slim install — expected)
qwen_vision_key=missing
llm_policy.offline_compose=true, qwen_configured=false
```

| Check | Pass / Fail |
|-------|-------------|
| Python venv | Pass |
| KiCad CLI | Pass |
| Node / npm | Pass |
| API import | Pass |
| PCB/catalog export (install script) | Pass (159 modules, 27 footprints, 18 recipes) |

---

## Agent quickstart (Phase 0 bar)

**Wall time:** **36 seconds** (install + doctor + API + 2 curls)

### Curl 1 — `GET /v1/modules/catalog`

| Field | Result |
|-------|--------|
| HTTP | 200 |
| `count` | **27** |
| `ok` | true |

### Curl 2 — `POST /v1/compose/agent-loop` (canvas, offline)

| Field | Result |
|-------|--------|
| `agent_loop.resolved` | **true** |
| `final_kicad_drc_errors` | **0** |
| `copper_tier` | `cosmetic_preview` |
| `project_package` | **present** |
| `project_name` | `fgedhgv_track_b_canvas` |
| `out_dir` | `/tmp/hardware_splicer_api/compose/c3d994ae...` |

### Curl 3 — `POST /v1/compose/agent-loop` (Qwen phrase)

| Field | Result |
|-------|--------|
| `qwen_configured` | **true** |
| `mode` | `llm_first` |
| `module_ids` | esp32-devkit, soil_moisture, ssd1306, lcd_16x2_i2c, usb-power-5v |
| `agent_loop.resolved` | **true** |
| `final_kicad_drc_errors` | **0** |
| `project_package` | **present** |
| `qwen_usage.total_tokens` | **3072** |
| Wall time | ~26s (API already warm from prior install) |

---

## Verification (hard bar)

- [ ] `make verify-product-internal` — **not run** (Track B scope = agent quickstart only)
- [x] **Agent quickstart Track B** — **PASS** (36s)

---

## Manual fixes required

1. **Deploy path:** use `git archive` + `scp` from optiplex (same as July 2026 report).
2. **WSL invoke:** use `wsl --distribution Ubuntu-24.04 -- bash ...` (not `-e bash -lc` when distro stopped).
3. **SSH user:** `desktop-fgedhgv` in `~/.ssh/config` → `User user`, not `phyrexian`.

Repeat script on controller:

```bash
git archive v1.1.0-alpha.5 | gzip > /tmp/hs-alpha5.tar.gz
scp /tmp/hs-alpha5.tar.gz scripts/agent_quickstart_verify.sh desktop-fgedhgv:
ssh desktop-fgedhgv "wsl --distribution Ubuntu-24.04 -- bash /mnt/c/Users/user/hs_fgedhgv_track_b.sh"
```

Or use [`scripts/agent_quickstart_verify.sh`](../scripts/agent_quickstart_verify.sh) after copying tarball.

---

## Verdict

| | |
|--|--|
| **Install: PASS** | Tarball + `install_splice_v1.sh`, no manual exports |
| **Agent quickstart: PASS** | Catalog + canvas agent-loop → DRC 0 + package in 36s |
| **Phase 0 exit (Track B): PASS** | Alien machine, no Qwen, no author hand-holding during run |
| **Ready for pilot on this OS?** | **With caveats** — WSL2; full `verify-product-internal` still optional |

**Notes for repo maintainers:**

- Alpha.5 agent spine is **reproducible on alien WSL** without LLM keys.
- Phase 0 criterion “&lt;15 min without hand-holding” — **met** (36s automated wall time after tarball on disk).
- Next: optional curl 3 with `.env.local` on alien node; async job wrapper (Phase 1).

---

## Cluster context

| Item | Value |
|------|-------|
| Pool | YZU `windows_lab` |
| Node | `DESKTOP-FGEDHGV` — first **alpha.5 agent quickstart** pass |
| Coexistence | GDELT harvest workers on sibling nodes — coordinate long verifies |
