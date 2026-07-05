# Deployment — Splice Agent v1

See [`../docs/PACKAGING_AND_DEPLOYMENT.md`](../docs/PACKAGING_AND_DEPLOYMENT.md) for the full plan.

**Operator quickstart:** [`../docs/QUICKSTART_SPLICE_v1.md`](../docs/QUICKSTART_SPLICE_v1.md)  
**Runbook:** [`../docs/OPERATIONS_RUNBOOK_v1.md`](../docs/OPERATIONS_RUNBOOK_v1.md)

---

## Recommended v1: bare metal / VM (no Docker)

```bash
# Ubuntu 22.04+ example
sudo apt install -y python3.12-venv nodejs npm git
# Install KiCad 9 from kicad.org — kicad-cli must be on PATH

git clone https://github.com/Spectating101/hardware-splicer.git /opt/hardware-splicer
cd /opt/hardware-splicer && git checkout v1.0.1
bash scripts/install_splice_v1.sh
source .venv/bin/activate
hs-doctor
```

**Windows:** use WSL2 Ubuntu and the same steps inside WSL.

---

## Single-port demo (API + UI)

```bash
make splice-ui-serve
# open http://127.0.0.1:8787
```

Equivalent:

```bash
make splice-ui-build
export HARDWARE_SPLICER_SERVE_UI=1
export HARDWARE_SPLICER_TMP_ROOT=/var/lib/hardware-splicer/builds
mkdir -p "$HARDWARE_SPLICER_TMP_ROOT"
hs-serve --host 127.0.0.1 --port 8787
```

---

## HTTP API (headless)

```bash
export PYTHONPATH=src
export HARDWARE_SPLICER_TMP_ROOT=/var/lib/hardware-splicer/builds
mkdir -p "$HARDWARE_SPLICER_TMP_ROOT"
hs-serve --host 127.0.0.1 --port 8787
```

- OpenAPI: http://127.0.0.1:8787/docs  
- Health: http://127.0.0.1:8787/health  

**Do not** bind `0.0.0.0` on the public internet without nginx + TLS + API key.

---

## systemd

Copy [`systemd/hardware-splicer.service.example`](systemd/hardware-splicer.service.example), adjust paths and user, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hardware-splicer
sudo journalctl -u hardware-splicer -f
```

To serve UI from systemd, add to the unit:

```ini
Environment=HARDWARE_SPLICER_SERVE_UI=1
```

Ensure `apps/splice-ui/dist` exists (`make splice-ui-build` after each UI upgrade).

---

## nginx (LAN / VPN)

Example: [`nginx/splice-agent.conf.example`](nginx/splice-agent.conf.example)

- TLS termination  
- `X-API-Key` check  
- Proxy to `127.0.0.1:8787`  

---

## MCP (no HTTP)

Configure Cursor/Claude with `.venv/bin/python -m hardware_splicer.mcp_server` and `PYTHONPATH=src`. See [`../docs/MCP.md`](../docs/MCP.md).

---

## Docker

**Not recommended for v1** unless API and `kicad-cli` share a host mount. KiCad-in-container is fragile. Revisit for v2 worker queue.

---

## Upgrade

```bash
cd /opt/hardware-splicer
sudo systemctl stop hardware-splicer
git fetch && git checkout v1.0.1
bash scripts/install_splice_v1.sh
make splice-ui-build
sudo systemctl start hardware-splicer
```

See [`../CHANGELOG.md`](../CHANGELOG.md).

---

## External install proof

When testing on another machine, copy and fill [`../docs/INSTALL_REPORT_TEMPLATE.md`](../docs/INSTALL_REPORT_TEMPLATE.md).
