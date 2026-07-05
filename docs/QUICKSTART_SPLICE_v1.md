# Quick start — Splice Agent v1

**Purpose:** Install, verify, and run the product on one machine in under 30 minutes.

**Audience:** Engineers, lab operators, pilot customers, reviewers.

**Related:** [`PACKAGING_AND_DEPLOYMENT.md`](PACKAGING_AND_DEPLOYMENT.md) · [`DEMO_5_MIN_UI.md`](DEMO_5_MIN_UI.md) · [`SETUP.md`](SETUP.md)

---

## 1. Prerequisites

| Requirement | Check |
|-------------|-------|
| Python 3.12+ | `python3 --version` |
| KiCad 9+ | `kicad-cli --version` |
| Node.js 18+ | `node --version` |
| Git | `git --version` |

**Linux:** Ubuntu 22.04+ recommended. **Windows:** use WSL2 Ubuntu for v1 (bash install script). Native Windows is not a supported v1 install path.

Install KiCad from [kicad.org](https://www.kicad.org/download/) and ensure `kicad-cli` is on `PATH`.

---

## 2. Install (customer profile)

```bash
git clone https://github.com/Spectating101/hardware-splicer.git
cd hardware-splicer
git checkout v1.0.1    # or main for latest
bash scripts/install_splice_v1.sh
source .venv/bin/activate
hs-doctor
```

`hs-doctor` must show critical checks OK. Fix KiCad or Node first if not.

**Developers** (tests + verify bar):

```bash
INSTALL_DEV=1 bash scripts/install_splice_v1.sh
make verify-splice-v1
```

---

## 3. Run the product (single port)

Best for demos, pilots, and visual review:

```bash
make splice-ui-serve
```

Open **http://127.0.0.1:8787**

- **Quick demo** — one-click example build (~30–90 s)
- **Gates** — safety verdict and open measurements
- **Bench** — submit a measurement to close a gate
- **Download zip** — job bundle with KiCad + package artifacts

---

## 4. Run headless (API / agents)

**HTTP only:**

```bash
hs-serve --host 127.0.0.1 --port 8787
curl -s http://127.0.0.1:8787/health | jq .
```

**MCP** (Cursor / Claude Desktop): see [`MCP.md`](MCP.md) and `mcp/hardware-splicer.mcp.json`.

**OpenAPI:** http://127.0.0.1:8787/docs

---

## 5. Key API flows

| Action | Endpoint |
|--------|----------|
| Health | `GET /health` |
| Example intakes | `GET /v1/examples/splice-intakes` |
| Start async build | `POST /v1/jobs/splice-build` |
| Poll job | `GET /v1/jobs/{id}` |
| Result + package | `GET /v1/jobs/{id}/result` |
| Download artifacts | `GET /v1/jobs/{id}/bundle` |
| Bench status | `POST /v1/splice-bench/status` |
| Close gate | `POST /v1/splice-bench/submit` |

Full operator flow: [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md).

---

## 6. Dev mode (hot reload UI)

Terminal 1:

```bash
hs-serve --port 8787
```

Terminal 2:

```bash
make splice-ui-dev
```

Open **http://127.0.0.1:5178** (Vite proxies `/api` → backend).

---

## 7. Common issues

| Symptom | Fix |
|---------|-----|
| `kicad-cli` not found | Install KiCad 9+; add to PATH |
| npm missing | Install Node 18+; re-run install script |
| UI shows Offline | Start `hs-serve` or use `make splice-ui-serve` |
| Build `ok: false` with gates open | Expected — review **Gates** tab; not always compile failure |
| Permission errors on builds | Set `HARDWARE_SPLICER_TMP_ROOT` to writable path |

---

## 8. Next steps

| Goal | Doc |
|------|-----|
| LAN / lab deploy | [`../deploy/DEPLOY.md`](../deploy/DEPLOY.md) |
| Operations | [`OPERATIONS_RUNBOOK_v1.md`](OPERATIONS_RUNBOOK_v1.md) |
| External install proof | [`INSTALL_REPORT_TEMPLATE.md`](INSTALL_REPORT_TEMPLATE.md) |
| Commercial pilot | [`OFFER_SPLICE_BENCH_KIT_v1.md`](OFFER_SPLICE_BENCH_KIT_v1.md) |
