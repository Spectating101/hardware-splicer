# OSS interface integration strategy (internal)

**Purpose:** Map open-source EDA **viewers, editors, and interchange** layers onto the Hardware-Splicer engine — **embed, don’t reinvent**.

**Thesis:** The engine is **under-interfaced, not under-powered**. Win bring-up (layer 5) in market; reveal engine strength through borrowed UIs next.

**Related:** [`ENGINE_VS_INTERFACE.md`](ENGINE_VS_INTERFACE.md) · [`INTEGRATIONS_RESEARCH.md`](INTEGRATIONS_RESEARCH.md) · [`FLUX_TARGET.md`](FLUX_TARGET.md)

**v1.1 preview (on `main`):** splice-ui **Design verify** tab (KiCanvas, BOM, fab) + **Interface lab** + OSS catalog. Verify: `make verify-ui-interface-smoke`.

**Release boundary:** [`V1.1_INTERFACE_PREVIEW.md`](V1.1_INTERFACE_PREVIEW.md) · draft notes: [`RELEASE_NOTES_v1.1.0-alpha.1.md`](../RELEASE_NOTES_v1.1.0-alpha.1.md)

---

## 1. Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│  OSS viewers / editors / interchange (borrowed)               │
│  KiCanvas · tscircuit/circuit-json · KiCad MCP · atopile …   │
└───────────────────────────┬─────────────────────────────────┘
                            │ thin adapters
┌───────────────────────────▼─────────────────────────────────┐
│  Hardware-Splicer engine (own)                                │
│  compose · netlist IR · KiCad export · DRC/ERC · splice       │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  Authority layer (own — moat)                                 │
│  bench gates · PROJECT_PACKAGE · casefiles · power-on boundary│
└─────────────────────────────────────────────────────────────┘
```

**Do not build:** Flux-class browser ECAD from scratch, native Windows installer, public SaaS, production autorouter as default promise.

**Do build:** Adapters in `src/hardware_splicer/integrations/` + UI embed in `apps/splice-ui/`.

---

## 2. OSS map by layer

| Layer | OSS candidates | HS hook | Priority |
|-------|----------------|---------|----------|
| **KiCad preview** | [KiCanvas](https://github.com/theacodes/kicanvas) | `POST /v1/build-files/*` + inline embed | **P0** ✅ spike |
| **Web-native graph** | [tscircuit](https://github.com/tscircuit/tscircuit), [circuit-json](https://github.com/tscircuit/circuit-json) | `circuit_json_import.py`, `/v1/netlist-compile` | **P0** ✅ spike |
| **Canvas compose** | Our API + Circuit.AI pattern | `/v1/compose-canvas` | **P0** ✅ spike |
| **Live KiCad edit** | kicad-mcp-pro, Seeed kicad-mcp | Sidecar MCP; re-compile on save | **P1** |
| **Artifact CI** | [KiBot](https://github.com/INTI-CMNB/KiBot) | Normalize BOM/Gerber/PDF outputs | **P1** |
| **Autoroute** | [FreeRouting](https://github.com/freerouting/freerouting) | `freerouting_bridge.py`, `AUTOROUTE=1` | **P1** (opt-in) |
| **Code capture** | [atopile](https://github.com/atopile/atopile), [SKiDL](https://github.com/devbisme/skidl) | Import → netlist → compile | **P2** |
| **Schematic AI intake** | SINA, pcbGPT | Intake adapter only | **P2/P3** |
| **Ground truth** | KiCad 9 CLI | Already core — never replace | **core** |

---

## 3. Candidate table (license / maturity)

| Project | License | Maturity | Role | Caution |
|---------|---------|----------|------|---------|
| KiCanvas | MIT | Alpha | Read-only sch/pcb in browser | KiCad 6+; vendored `public/kicanvas/kicanvas.js` |
| circuit-json | MIT | Active | Interchange for agents/editors | Subset mapping in our adapter |
| tscircuit | MIT | Active | React editor ecosystem | Heavier dep; use interchange first |
| KiCad MCP (various) | varies | Early | Human-in-loop KiCad session | Don’t hard-dep one repo |
| KiBot | GPL-3.0 | Mature | Fab/doc automation | GPL boundary for bundled output |
| FreeRouting | GPL-3.0 | Mature | Opt-in autoroute | Never default-on in product copy |
| atopile | MIT | Growing | Code-defined boards | Import path, not main UI |
| SKiDL | MIT | Mature | Python netlists | Import path |

---

## 4. P0 / P1 / P2 order

### P0 — interface proof (one week)

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | KiCanvas read-only preview in splice-ui **Design** tab | ✅ |
| 2 | `POST /v1/build-files/list` + `content` for KiCad files | ✅ |
| 3 | Interface lab: `/v1/compose-canvas` | ✅ |
| 4 | Interface lab: circuit-json → `/v1/netlist-compile` | ✅ |
| 5 | `GET /v1/examples/netlist-fixtures/{id}` | ✅ |
| 6 | `GET /v1/integrations/catalog` + OSS map UI | ✅ |
| 7 | Artifact list / download / circuit-json export | ✅ |
| 8 | KiCad netlist fixture path (`kicad_netlist_text`) | ✅ |

**Try it:**

```bash
hs-serve --host 127.0.0.1 --port 8787
make splice-ui-dev
# Build any example → Design tab
# Sidebar → Interface lab
```

### P1 — sidecar + artifacts

| Item | Status |
|------|--------|
| KiCad MCP dev profile | documented — [`KICAD_MCP_SIDECAR.md`](KICAD_MCP_SIDECAR.md) |
| KiCad MCP recheck script + API | ✅ [`KICAD_MCP_DEV_PROFILE.md`](KICAD_MCP_DEV_PROFILE.md) |
| Artifact export API + Design tab | ✅ wired |
| FreeRouting opt-in (`POST /v1/build-files/autoroute`) | ✅ wired |
| KiBot comparison for `build_compilation/` outputs | ✅ `POST /v1/build-files/fab-manifest` |
| Donor photo wizard step (vision API exists) | partial |

**Master matrix:** [`OSS_INTEGRATION_STATUS.md`](OSS_INTEGRATION_STATUS.md)

### P2 — intake ecosystem

- atopile / SKiDL import smoke tests
- SINA / pcbGPT as optional intake adapters
- Deeper tscircuit editor embed (if circuit-json roundtrip stable)

---

## 5. Integration pattern

```text
OSS tool → src/hardware_splicer/integrations/<name>.py
        → pytest (+ verify-* if engine-critical)
        → optional MCP tool (mcp_server.py)
        → optional splice-ui panel
```

---

## 6. Claims alignment

| Say | Don’t say |
|-----|-----------|
| Engine emits KiCad artifacts you can **preview and verify** | “We beat Flux on editor UX today” |
| Borrowing KiCanvas / circuit-json / KiCad MCP | “We built a browser ECAD suite” |
| Layer-5 wedge for pilots | “We’re weak on design” |

---

*Last updated: 2026-07-07 · P0 spike in splice-ui*
