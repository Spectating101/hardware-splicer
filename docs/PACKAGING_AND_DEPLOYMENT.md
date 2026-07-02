# Packaging & deployment — Splice Agent v1.0

**Purpose:** Concrete plan for **packaging** (installable product) and **deployment** (how it runs in production-ish settings).

**Scope:** `Hardware-Splicer Splice Agent v1.0` only — not full monorepo (Circuit-AI UI, mecha-splicer, CadQuery).

**Related:** [`RELEASE_V1.md`](RELEASE_V1.md) · [`SETUP.md`](SETUP.md) · [`MCP.md`](MCP.md) · [`MONETIZATION_AND_PRODUCT_ASSESSMENT.md`](MONETIZATION_AND_PRODUCT_ASSESSMENT.md)

---

## 1. Recommendation (gun to head)

| Layer | Do this | Skip for v1 |
|-------|---------|-------------|
| **Package** | `pyproject.toml` + `pip install -e ".[mcp]"` | PyPI publish |
| **Install profile** | **Splice v1 slim** (`scripts/install_splice_v1.sh`) | Full `make setup` for customers |
| **Deploy** | Self-host: CLI + MCP + optional HTTP | Kubernetes, multi-tenant SaaS |
| **Container** | Optional API image; **KiCad on host** | All-in-one KiCad Docker (fragile) |
| **Release** | Git tag `v1.0.0` + GitHub Release + notes | Fancy installer |
| **UI** | **`apps/splice-ui`** — live splice workbench (v1.0) | circuit-ai full editor, static demo-only UI |

**Default deployment story for v1.0:**

```text
Linux/macOS host with KiCad 9 + Node 18
  → install_splice_v1.sh
  → hs-doctor (or python scripts/hardware_splicer.py doctor)
  → hs-serve on :8787 + make splice-ui-dev (http://127.0.0.1:5178)
  → OR MCP in Cursor for agent workflows
```

---

## 2. Deployment personas

### Persona 1 — **Solo / lab (you)**

- `pip install -e ".[mcp]"`  
- MCP in Cursor via `mcp/hardware-splicer.mcp.json`  
- Builds write to `HARDWARE_SPLICER_TMP_ROOT`  

**Cost:** $0 infra. **KiCad required on same machine.**

### Persona 2 — **Pilot customer (repair café / EMS)**

- Same install on **their** Linux PC or your laptop on-site  
- You run `splice_build`; deliver `PROJECT_PACKAGE` folder  
- Optional: `systemd` unit for HTTP API on LAN only  

**Cost:** $0–5/mo. **No public cloud required.**

### Persona 3 — **Agent integrator**

- HTTP API on private VPS (`hs-serve`)  
- API key at reverse proxy (nginx) — **not built into app yet**  
- KiCad **on same VPS** or remote worker (v2)  

**Cost:** ~$5–20/mo VPS + your time. **v1.0: co-locate API + KiCad on one VM.**

### Persona 4 — **Public SaaS**

- Auth, billing, queue, sandboxes  
- **v2+** — do not block v1.0 on this  

---

## 3. Install profiles

### Full dev (current)

```bash
make setup   # venv + npm (circuit-ai frontend + demo) + 3d-splicer venv
```

**Use when:** developing engine, running full `make verify`, geometry, tier-C.

### Splice v1 slim (ship this)

```bash
bash scripts/install_splice_v1.sh
```

**Installs:**

- Python venv  
- `requirements-splice-v1.txt` (pinned core)  
- `pip install -e ".[mcp]"`  
- **npm install** only in `apps/circuit-ai/circuit-ai-frontend` (KiCad graph compiler — **required for compile**)  

**Skips:**

- `apps/hardware-splicer-demo` npm  
- CadQuery / 3d-splicer full stack  
- `requirements-apps-test.txt`  

**Prerequisites (document, don’t bundle):**

- Python 3.12+  
- Node 18+  
- `kicad-cli` 9+ on PATH  

---

## 4. Python packaging (`pyproject.toml`)

**Why:** One command install, version string, console entrypoints.

**Console scripts (v1):**

| Command | Maps to |
|---------|---------|
| `hs-doctor` | `hardware_splicer.sdk:engine_doctor` wrapper or CLI doctor |
| `hs-serve` | uvicorn `hardware_splicer.api:app` |
| `hs-mcp` | `python -m hardware_splicer.mcp_server` |

**Extras:**

- `pip install -e .` — engine + API  
- `pip install -e ".[mcp]"` — + MCP server  
- `pip install -e ".[dev]"` — + pytest  

**Not doing yet:** PyPI upload (trademark, KiCad dep, support burden).

---

## 5. Requirements split

| File | Audience |
|------|----------|
| `requirements-splice-v1.txt` | **Production / pilot** — pinned runtime |
| `requirements.txt` | Minimal legacy (superseded by splice-v1 for ship) |
| `requirements-mcp.txt` | MCP extra |
| `requirements-dev.txt` (optional) | pytest, httpx |

**Pin policy for v1.0.0:** freeze from working `.venv` at tag time; document Python 3.12–3.13 tested.

---

## 6. Container strategy (honest)

### Problem

KiCad + headless display + large footprint = **painful** in Docker.

### v1.0 pattern: **API container + host KiCad** OR **single fat VM, no Docker**

**Option A — No Docker (recommended v1)**  
Install on Ubuntu 22.04+ VM with KiCad from packages. Run `hs-serve` under `systemd`.

**Option B — Docker API only**  
Image runs FastAPI; **mount**:

- `/usr/bin/kicad-cli` from host (brittle)  
- `/opt/kicad` or use host network compile worker  

Document in `deploy/DEPLOY.md` — **not** “docker run and forget.”

**Option C — CI image**  
GitHub Actions already runs verify; optional `deploy/Dockerfile.ci` for reproducible CI only.

### What the API container needs

```text
Python 3.12
FastAPI/uvicorn
Repo src/ + examples/ + apps/circuit-ai/circuit-ai-frontend/node_modules (for compile)
Writable volume: HARDWARE_SPLICER_TMP_ROOT
Host: kicad-cli, node
```

---

## 7. `systemd` example (LAN API)

```ini
# /etc/systemd/system/hardware-splicer.service
[Unit]
Description=Hardware-Splicer Splice Agent API
After=network.target

[Service]
Type=simple
User=hsplicer
WorkingDirectory=/opt/hardware-splicer
Environment=PYTHONPATH=src
Environment=HARDWARE_SPLICER_AUTOROUTE=0
Environment=HARDWARE_SPLICER_TMP_ROOT=/var/lib/hardware-splicer/builds
ExecStart=/opt/hardware-splicer/.venv/bin/uvicorn hardware_splicer.api:app --host 127.0.0.1 --port 8787
Restart=on-failure

[Install]
WantedBy=multi-user.host
```

Put **nginx** with TLS + API key in front if exposed beyond localhost.

---

## 8. MCP deployment (zero server)

**Best v1 “deployment” for agents:**

1. Customer clones repo at tag `v1.0.0`  
2. `bash scripts/install_splice_v1.sh`  
3. Cursor / Claude Desktop config:

```json
{
  "mcpServers": {
    "hardware-splicer": {
      "command": "/opt/hardware-splicer/.venv/bin/python",
      "args": ["-m", "hardware_splicer.mcp_server"],
      "env": { "PYTHONPATH": "/opt/hardware-splicer/src" }
    }
  }
}
```

**No HTTP, no systemd, no cloud.** This **is** a complete deployment for B2B integrators.

---

## 9. Release artifacts (GitHub Release)

| Asset | Contents |
|-------|----------|
| **Source** | Tag `v1.0.0` on `main` |
| `RELEASE_NOTES_v1.0.md` | In repo + pasted in release |
| `requirements-splice-v1.txt` | Pinned |
| Optional **`golden-splice-bundle.zip`** | Pre-built output from `verify-splice-loop` (demo without KiCad) |
| Optional **3 min demo video** | Link in release notes |

**Do not** ship `.venv` or `node_modules` in tarball — install script rebuilds.

---

## 10. Environment contract (production)

| Variable | Default | Production |
|----------|---------|------------|
| `HARDWARE_SPLICER_AUTOROUTE` | `0` | **Keep 0** unless documented |
| `HARDWARE_SPLICER_DRC_FIX_LOOP` | `1` | `1` |
| `HARDWARE_SPLICER_TMP_ROOT` | repo cache | `/var/lib/hardware-splicer/builds` |
| `HARDWARE_SPLICER_SKIP_VISION_LIVE` | — | `1` if no API keys |
| `HARDWARE_SPLICER_OFFLINE_SALVAGE` | — | `1` for deterministic demos |
| `PYTHONPATH` | — | `src` if not pip installed |

**Health checks:**

```bash
hs-doctor                    # or scripts/hardware_splicer.py doctor
curl -s localhost:8787/...   # add GET /health if missing (v1.0.1)
```

---

## 11. Packaging checklist (before tag)

### P0 — must ship

- [ ] `pyproject.toml` + `pip install -e ".[mcp]"` works on clean machine  
- [ ] `scripts/install_splice_v1.sh` documented in README  
- [ ] `src/hardware_splicer/__version__ = "1.0.0"`  
- [ ] `requirements-splice-v1.txt` pinned  
- [ ] `RELEASE_NOTES_v1.0.md`  
- [ ] `make verify-splice && make verify-splice-loop` green  
- [ ] `docs/SETUP.md` points to slim vs full install  

### P1 — should ship

- [ ] `deploy/DEPLOY.md` — systemd + nginx sketch  
- [ ] `GET /health` on API  
- [ ] Golden bundle zip on GitHub Release  
- [ ] `mcp/hardware-splicer.mcp.json` uses absolute paths template  

### P2 — later

- [ ] Dockerfile.ci  
- [ ] PyPI  
- [ ] Hosted SaaS  

---

## 12. What NOT to package in v1.0 SKU

| Exclude | Why |
|---------|-----|
| Full `apps/circuit-ai` API server | Separate product surface |
| `apps/mecha-splicer` | S4 |
| `apps/3d-splicer` + CadQuery | Heavy, optional |
| `apps/hardware-splicer-demo` | v2 UI |
| Competition PDFs | Archive only |
| `.cursor/`, `.mcp.json` personal configs | |

**Monorepo stays on GitHub** — **product SKU** is splice engine slice.

---

## 13. Execution order (2–3 weeks)

| Week | Task |
|------|------|
| **1** | `pyproject.toml`, `__version__`, `install_splice_v1.sh`, pin requirements |
| **1** | README: v1.0 quick path (5 commands) |
| **2** | `deploy/DEPLOY.md`, optional `/health`, systemd sample |
| **2** | Fresh VM smoke test (Ubuntu + KiCad) |
| **3** | `RELEASE_NOTES`, tag `v1.0.0`, GitHub Release, demo video |

---

## 14. Success criteria

**Packaging done when:** stranger on Ubuntu with KiCad runs:

```bash
git clone … && cd Hardware-Splicer && git checkout v1.0.0
bash scripts/install_splice_v1.sh
hs-doctor   # ok: true, kicad_cli: ok
make verify-splice-loop
```

**Deployment done when:** at least one of:

- MCP works from install doc alone  
- `hs-serve` runs under systemd on LAN  
- You deliver a pilot `PROJECT_PACKAGE` from that install  

---

## 15. Changelog

| Date | Note |
|------|------|
| 2026-07 | Initial packaging & deployment plan |
