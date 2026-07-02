# Deployment — Splice Agent v1.0

See [`../docs/PACKAGING_AND_DEPLOYMENT.md`](../docs/PACKAGING_AND_DEPLOYMENT.md) for full plan.

## Recommended v1: bare metal / VM (no Docker)

```bash
# Ubuntu 22.04+ example
sudo apt install -y python3.12-venv nodejs npm
# Install KiCad 9 from kicad.org — kicad-cli must be on PATH

git clone <repo> /opt/hardware-splicer
cd /opt/hardware-splicer && git checkout v1.0.0
bash scripts/install_splice_v1.sh
source .venv/bin/activate
hs-doctor
```

## HTTP API (LAN)

```bash
export PYTHONPATH=src
export HARDWARE_SPLICER_TMP_ROOT=/var/lib/hardware-splicer/builds
mkdir -p "$HARDWARE_SPLICER_TMP_ROOT"
hs-serve --host 127.0.0.1 --port 8787
```

Use **nginx** + TLS + API key for anything beyond localhost.

## systemd

Copy [`systemd/hardware-splicer.service.example`](systemd/hardware-splicer.service.example), adjust paths, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hardware-splicer
```

## MCP (no HTTP)

Configure Cursor/Claude with `.venv/bin/python -m hardware_splicer.mcp_server` and `PYTHONPATH=src`. See [`../docs/MCP.md`](../docs/MCP.md).

## Docker

**Not recommended for v1** unless API and `kicad-cli` share a host mount. KiCad-in-container is fragile. Revisit for v2 worker queue.
