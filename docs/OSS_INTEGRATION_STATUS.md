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
| kicad-mcp | KiCad MCP servers | documented | [`KICAD_MCP_SIDECAR.md`](KICAD_MCP_SIDECAR.md) | Human KiCad session sidecar; re-compile on save |
| kibot | [KiBot](https://github.com/INTI-CMNB/KiBot) | reference | `kibot_reference.py` + `POST /v1/build-files/fab-manifest` | Fab artifact coverage comparison (not vendored) |
| jlc-api | JLCPCB / LCSC | partial | `jlcsearch_client.py`, `HARDWARE_SPLICER_JLC_ENRICH` | Opt-in BOM stock/price enrich |
| skidl | [SKiDL](https://github.com/devbisme/skidl) | wired | KiCad netlist ingest via `kicad_netlist_text` | Python netlist → compile spine (import path) |
| atopile | [atopile](https://github.com/atopile/atopile) | partial | KiCad netlist paste + [`ATOPILE_IMPORT.md`](ATOPILE_IMPORT.md) | Code-defined boards via netlist export |
| schematic-ai | SINA / pcbGPT | planned | Intake → netlist-compile + gates | Research intake — not product UI |

**Counts (catalog):** see `wired_count` / `total_count` in API response.

---

## Artifact export (Design tab)

After any compile, **Exports & interchange** lists files present under the build:

- KiCad `.kicad_pcb` / `.kicad_sch`
- `circuit_json.json`
- `KICAD_DRC.json`, `DESIGN_QUALITY.json`
- `BOM.csv`, `fab_package.zip` (when emitted)
- `PROJECT_PACKAGE.json`

Endpoints: `POST /v1/build-files/artifacts`, `circuit-json`, `download`, `autoroute` (confirm required).

---

## Verification

```bash
make verify-product-v1
pytest tests/test_build_files_api.py tests/test_oss_integrations_api.py -q
```

Manual: `hs-serve` + `make splice-ui-dev` → Interface lab + Design tab on a compiled build.

---

*Update this doc when `oss_catalog.py` or UI hooks change.*
