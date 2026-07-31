# Install report — DESKTOP-FGEDHGV (WSL2 Ubuntu 24.04)

**Purpose:** Tier III alien-machine proof — lab Windows cluster node, not the primary dev box (optiplex).

---

## Report metadata

| Field | Value |
|-------|-------|
| **Tester** | agent / optiplex controller |
| **Date** | 2026-07-07 |
| **Git tag / commit** | `main` @ `c1348ef` (deployed via `git archive` tarball from optiplex; public clone hung on node network) |
| **Machine name** | `DESKTOP-FGEDHGV` |
| **OS** | Windows 11 Pro + **WSL2 Ubuntu 24.04** |
| **KiCad version** | `9.0.9` |
| **Python** | `3.12.3` (WSL venv) |
| **Node** | `v20.20.2` (WSL) |
| **Tailscale IP** | `100.102.0.84` |

---

## Install steps followed

Public docs path with controller-assisted tarball (GitHub `git clone` stalled >40 min inside WSL on this node).

- [x] WSL2 Ubuntu 24.04 installed on Windows host (`wsl --install -d Ubuntu-24.04`)
- [x] KiCad 9 PPA + `kicad-cli`, `ngspice`, Node 20 in WSL
- [x] Repo deployed to `/root/hardware-splicer` (tarball from controller)
- [x] `bash scripts/install_splice_v1.sh`
- [x] `INSTALL_DEV=1 bash scripts/install_splice_v1.sh`
- [x] `make export-engine-pcb-data export-catalog-recipes` (required — gitignored generated data)
- [x] `hs-doctor`

**Install script modifications required?** **Yes** — after slim install, generated data files must exist:

```bash
make export-engine-pcb-data export-catalog-recipes
```

Fixed in `scripts/install_splice_v1.sh` on `main` after this run (install now runs both exports when npm is present).

---

## Doctor output

```
ok=True
demo_ready=True
fab_export_ready=True
dependencies=cadquery:missing, fastapi:ok, kicad_cli:ok, ngspice:ok, node:ok, npm:ok, pillow:ok, pytest:ok, uvicorn:ok
```

| Check | Pass / Fail |
|-------|-------------|
| Python venv | Pass |
| KiCad CLI | Pass |
| Node / npm | Pass |
| API import | Pass |

---

## Verification

- [x] `make verify-product-internal` — **exit code: 0** (~8 min wall on WSL)

Includes:

- `verify-splice-v1` — S2 4/4, S3 loop 3/3, real bench PASS
- `splice-ui-build` + `test_splice_product_v1.py`
- `verify-install-smoke`
- `verify-product-live-smoke` — async `splice-build` → `project_package` with gates

---

## API smoke

```json
{"ok": true, "version": "1.0.1", ...}
```

Live smoke job: `live-smoke-1783355401` → `splice_salvaged_robot_drive`, `gates_open=5`.

---

## Manual fixes required

1. **Git clone from GitHub inside WSL hung** — used `git archive` + `scp` from optiplex instead.
2. **Generated `engine_pcb_data.json` / `catalog_recipes.json`** — not in git; must run export targets (now in install script).

---

## Verdict

| | |
|--|--|
| **Install: PASS** | With tarball + export step |
| **Demo: PASS** | Live smoke + engine bar |
| **Ready for pilot on this OS?** | **With caveats** — WSL2 Ubuntu on lab Windows; not native Windows |

**Notes for repo maintainers:**

- Alien install from `git clone` alone will fail until install script exports PCB/catalog data (fixed post-run).
- Cluster nodes share `windows_lab` with GDELT jobs — coordinate CPU/disk before long verifies.

---

## Cluster context

| Item | Value |
|------|-------|
| Pool | YZU `windows_lab` |
| Node role | Data harvest + **Splice Tier III proof** |
| Other nodes | WSL not yet provisioned on all 5; this node is first alien pass |
