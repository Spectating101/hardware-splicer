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
cd /opt/hardware-splicer && git checkout <release-tag>   # the release you deploy
bash scripts/install_splice_v1.sh
source .venv/bin/activate
hs-doctor
```

**Windows:** use WSL2 Ubuntu and the same steps inside WSL.

---

## Single-port demo (API + UI)

```bash
make splice-ui-build
make serve
# open http://127.0.0.1:8787
```

`make serve` runs `hs-serve --ui`, which serves the canonical app
`hardware_splicer.product_api:app`: every API route plus the built UI on one port.
See [`../docs/SETUP.md`](../docs/SETUP.md#run-the-app) for UI lookup order and
`make ui-package` (stages the UI into the Python package for wheels).

Equivalent:

```bash
make splice-ui-build
export HARDWARE_SPLICER_TMP_ROOT=/var/lib/hardware-splicer/builds
export HARDWARE_SPLICER_STATE_DIR=/var/lib/hardware-splicer/state
mkdir -p "$HARDWARE_SPLICER_TMP_ROOT" "$HARDWARE_SPLICER_STATE_DIR"
hs-serve --ui --host 127.0.0.1 --port 8787
```

---

## Installed wheel (no editable checkout on the import path)

```bash
make ui-package                      # stages the built UI into the package
python -m build                      # dist/hardware_splicer-<version>-py3-none-any.whl + sdist
python3 -m venv /opt/hardware-splicer/.venv
/opt/hardware-splicer/.venv/bin/pip install 'dist/hardware_splicer-<version>-py3-none-any.whl[digital]'
hs-doctor --repo-root /opt/hardware-splicer      # check "ok" and the "install" block
hs-serve --ui --port 8787 --repo-root /opt/hardware-splicer
```

The wheel carries the API, the UI and package data. Registered digital cases,
project scenes and examples are read from the checkout named by `--repo-root` (or
`HARDWARE_SPLICER_REPO_ROOT`); without one the server still starts, `/v1/scenes`
is empty and creating a registered study answers `digital_runtime_unavailable`
with that hint. Without the `digital` extra, studies answer
`digital_runtime_unavailable` until `HARDWARE_SPLICER_DIGITAL_PYTHON` names a
Python with CadQuery. When `HARDWARE_SPLICER_TMP_ROOT` and
`HARDWARE_SPLICER_STATE_DIR` are unset, an installed package uses
`~/.cache/hardware-splicer` and `~/.local/state/hardware-splicer`.

The last install smoke test is in
[`../docs/status/generated/install-smoke-20261120.md`](../docs/status/generated/install-smoke-20261120.md).

---

## HTTP API (headless)

```bash
export HARDWARE_SPLICER_TMP_ROOT=/var/lib/hardware-splicer/builds
export HARDWARE_SPLICER_STATE_DIR=/var/lib/hardware-splicer/state
mkdir -p "$HARDWARE_SPLICER_TMP_ROOT" "$HARDWARE_SPLICER_STATE_DIR"
hs-serve --no-ui --host 127.0.0.1 --port 8787
```

- OpenAPI: http://127.0.0.1:8787/docs  
- Health: http://127.0.0.1:8787/health  

**Do not** bind `0.0.0.0` on the public internet without nginx + TLS + API key.
`hs-serve` refuses a non-loopback host unless `--allow-remote` is given.

---

## systemd

Copy [`systemd/hardware-splicer.service.example`](systemd/hardware-splicer.service.example), adjust paths and user, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hardware-splicer
sudo journalctl -u hardware-splicer -f
```

The example runs `hs-serve --ui`, which refuses to start without a UI build. Run
`make ui-package` (or `make splice-ui-build`) after each UI upgrade, or install a
wheel built after `make ui-package`. To use a separate build, set
`Environment=HARDWARE_SPLICER_UI_DIST=/path/to/dist`.

---

The example runs as a dedicated non-root account with `NoNewPrivileges`,
`ProtectSystem=strict`, `ProtectHome` and a private `/tmp`; the only writable path
is `/var/lib/hardware-splicer` (state and build scratch), created by
`StateDirectory=`. Check an edited copy with `systemd-analyze verify`.

---

## nginx (LAN / VPN)

Example: [`nginx/splice-agent.conf.example`](nginx/splice-agent.conf.example)

- TLS 1.2/1.3 termination, HTTP redirected to HTTPS
- Every path (UI, `/v1/*`, `/docs`, `/openapi.json`, `/health`, the project event
  stream) requires either HTTP basic auth (browsers) or a listed `X-API-Key`
  (scripts); a browser cannot add a header to page loads, so a key-only front
  would lock the UI out
- Credentials live in `/etc/nginx/splice-agent.htpasswd` and
  `/etc/nginx/splice-agent-api-keys.map`, created on the server and never
  committed; nginx refuses to load the site without them
- `/v1/projects/<id>/events` is proxied unbuffered for server-sent events
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
git fetch && git checkout <release-tag>
bash scripts/install_splice_v1.sh
make splice-ui-build
sudo systemctl start hardware-splicer
```

See [`../CHANGELOG.md`](../CHANGELOG.md).

---

## External install proof

When testing on another machine, copy and fill [`../docs/INSTALL_REPORT_TEMPLATE.md`](../docs/INSTALL_REPORT_TEMPLATE.md).
