# OSS integration status (v1.1 interface preview)

**Purpose:** Single matrix of open-source integrations — what is wired, what is documented, and what we may claim.

**API:** `GET /v1/integrations/catalog`  
**UI:** Interface lab → **OSS integration map**; Design tab → **Exports & interchange**

**Thesis:** Engine is **under-interfaced, not under-powered** — embed OSS layers; own gates and `PROJECT_PACKAGE` truth.

---

## Status legend

| Status | Meaning |
|--------|---------|
| **wired** | Callable in product UI or API today |
| **core** | Always-on engine dependency (KiCad CLI) |
| **opt_in** | Available only with explicit operator action |
| **partial** | Adapter exists; env-gated or subset |
| **documented** | Runbook/sidecar pattern; not a hard runtime dep |
| **reference** | Compared or patterned; not vendored |
| **planned** | Roadmap adapter only |

---

## Integration matrix

| ID | Project | Status | Hook | Claim (evidence-backed) |
|----|---------|--------|------|-------------------------|
| kicanvas | [KiCanvas](https://github.com/theacodes/kicanvas) | wired | Design tab + `POST /v1/build-files/content` | In-browser KiCad preview without KiCad GUI |
| circuit-json | [circuit-json](https://github.com/tscircuit/circuit-json) | wired | `circuit_json_import.py`, `/v1/netlist-compile`, artifact export | Web-native interchange into compile spine |
| compose-canvas | Canvas compose API | wired | `POST /v1/compose-canvas`, Interface lab | Module graph → same engine as Circuit.AI |
| kicad-cli | KiCad 9 CLI | core | `kicad_cli_drc.py`, ERC, Gerber in `build_compilation/` | Authoritative DRC/ERC/fab export |
| freerouting | [FreeRouting](https://github.com/freerouting/freerouting) | opt_in | `freerouting_bridge.py`, `POST /v1/build-files/autoroute` | Optional carrier autoroute — never default |
| tscircuit-autorouter | [tscircuit-autorouter](https://github.com/tscircuit/tscircuit-autorouter) | opt_in | `engine=tscircuit` on autoroute | MIT autoroute from circuit-json when Node package present |
| kicad-mcp | KiCad MCP servers | documented | [`KICAD_MCP_SIDECAR.md`](KICAD_MCP_SIDECAR.md) | Human KiCad session sidecar; re-compile on save |
| kibot | [KiBot](https://github.com/INTI-CMNB/KiBot) | reference | `kibot_reference.py` + `POST /v1/build-files/fab-manifest` | Fab artifact coverage comparison (not vendored) |
| ibom | [InteractiveHtmlBom](https://github.com/openscopeproject/InteractiveHtmlBom) | wired | `ibom_bridge` + `oss_export_bundle` / export-views | Best-effort HTML BOM — skips if CLI absent |
| pcbdraw | [PcbDraw](https://github.com/yaqwsx/PcbDraw) | wired | `pcbdraw_bridge` + package / export-views | Best-effort board SVG — skips if CLI absent |
| kikit | [KiKit](https://github.com/yaqwsx/KiKit) | opt_in | `POST /v1/build-files/kikit-fab` | Manufacturer fab preset — confirm required |
| jlc-api | JLCPCB / LCSC | partial | `jlcsearch_client.py`, `HARDWARE_SPLICER_JLC_ENRICH` | Opt-in BOM enrich + CPL-shaped fields |
| easyeda2kicad | [easyeda2kicad](https://github.com/uPesy/easyeda2kicad.py) | opt_in | `POST /v1/build-files/lcsc-lib` | LCSC → KiCad lib into `exports/lcsc_lib/` |
| esphome | [ESPHome](https://github.com/esphome/esphome) | wired | `esphome_export.py` → `firmware/esphome_stub.yaml` | Pin-true YAML stub — not flash authorization |
| nopscadlib | [NopSCADlib](https://github.com/nophead/NopSCADlib) | reference | `MECHANISM_PACK.oss_mech_refs` | Vitamins/manual pattern reference |
| build123d | [build123d](https://github.com/gumyr/build123d) | reference | `MECHANISM_PACK.oss_mech_refs` | Optional parametric CAD — no hard STL dep |
| skidl | [SKiDL](https://github.com/devbisme/skidl) | wired | KiCad netlist ingest via `kicad_netlist_text` | Python netlist → compile spine (import path) |
| atopile | [atopile](https://github.com/atopile/atopile) | partial | KiCad netlist paste + [`ATOPILE_IMPORT.md`](ATOPILE_IMPORT.md) | Code-defined boards via netlist export |
| schematic-ai | SINA / pcbGPT | planned | Intake → netlist-compile + gates | Research intake — not product UI |
| architon | [Architon](https://architon.io/) `rv` | documented | [`integrations/ARCHITON_GATE.md`](integrations/ARCHITON_GATE.md) | Optional pre-fab architecture contracts after HS compose — not bundled |

**Counts (catalog):** see `wired_count` / `total_count` in API response.

---

## Optional tool install (never required for money-path bar)

```bash
# InteractiveHtmlBom (CLI name varies by install)
pip install InteractiveHtmlBom

# PcbDraw board SVG
pip install pcbdraw

# KiKit fab presets
pip install kikit

# LCSC → KiCad libraries
pip install easyeda2kicad

# tscircuit MIT autorouter (Node)
npm i -g @tscircuit/capacity-autorouter
# or allow one-shot npx install:
# export HARDWARE_SPLICER_TSCIRCUIT_AUTOROUTE_INSTALL=1
```

When tools are missing, bridges return `{skipped: true}` and compile/package still succeed.

---

## Artifact export (Design tab)

After any compile, **Exports & interchange** lists files present under the build:

- KiCad `.kicad_pcb` / `.kicad_sch`
- `circuit_json.json`
- `KICAD_DRC.json`, `DESIGN_QUALITY.json`
- `BOM.csv`, `fab_package.zip` (when emitted)
- `PROJECT_PACKAGE.json`
- `build_compilation/exports/OSS_EXPORTS.json` (ibom/pcbdraw/esphome status)
- `firmware/esphome_stub.yaml` (when graph/firmware pins available)

Endpoints:

- `POST /v1/build-files/artifacts`, `circuit-json`, `download`
- `POST /v1/build-files/oss-exports` — re-run best-effort bundle
- `POST /v1/build-files/autoroute` — `confirm=true`, `engine=freerouting|tscircuit`
- `POST /v1/build-files/kikit-fab` — `confirm=true`
- `POST /v1/build-files/lcsc-lib` — `confirm=true`, `lcsc_id=C…`

---

## Verification

```bash
make verify-product-v1
pytest tests/test_build_files_api.py tests/test_oss_integrations_api.py tests/test_oss_export_bridges.py -q
```

Manual: `hs-serve` + `make splice-ui-dev` → Interface lab + Design tab on a compiled build.

---

*Update this doc when `oss_catalog.py` or UI hooks change.*
