# Engine vs interface — internal framing

**Purpose:** Reconcile two truths that look contradictory:

1. **GTM wedge (v1):** Sell layer 5 — bring-up, gates, `PROJECT_PACKAGE` — not “we beat Flux on greenfield UX.”
2. **Engine thesis:** The compile/splice spine is **strong and can be better than Flux on truth**; the gap is **interface wiring**, not missing engine depth.

**Related:** [`FLUX_TARGET.md`](FLUX_TARGET.md) · [`INTEGRATIONS_RESEARCH.md`](INTEGRATIONS_RESEARCH.md) · [`COMPETITOR_SCORECARD_v1.0.2.md`](COMPETITOR_SCORECARD_v1.0.2.md)

---

## The distinction

| Layer | What we have | What’s missing |
|-------|--------------|----------------|
| **Engine** | Netlist IR, compose spine, KiCad export, DRC/ERC, splice plan, salvage, gates, casefiles, headless CI | Autoroute default-on, TS compile retirement, broader library ingest |
| **Interface** | `splice-ui` wizard + package tabs; **Design verify** (KiCanvas, BOM, fab); Interface lab; HTTP/MCP | Donor photo in wizard; full Circuit.AI canvas in main path |

**Wrong internal story:** “We’re weak on layers 1–4.”  
**Right internal story:** “We’re **under-interfaced** on layers 1–4; we **don’t build Flux from scratch** — we **plug** OSS editors onto our engine.”

---

## Why the engine can be “better” (honest)

From [`FLUX_TARGET.md`](FLUX_TARGET.md) — compete on **compile truth**, not browser polish:

| Capability | Flux-class SaaS | Hardware-Splicer engine |
|------------|-----------------|-------------------------|
| Ground truth | Their stack | **KiCad CLI DRC/ERC** in CI |
| Salvage / donor | Weak | **Splice plan + carrier compile** |
| Failure mode | Opaque UX errors | **`COMPILE_CASEFILE.json`** |
| Headless / agent | SaaS-bound | **HTTP + MCP** same spine |
| Evidence gates | Not productized | **Bench session + power-on verdict** |

Flux wins **editor UX and collaboration today**. We can win **inspectable compile + splice + gates** — *if* users can **see and touch** the design through a proper interface.

---

## Plug-in strategy (don’t reinvent)

Already catalogued in [`INTEGRATIONS_RESEARCH.md`](INTEGRATIONS_RESEARCH.md). Pattern:

```text
OSS editor/viewer → thin adapter in integrations/ → pytest → optional MCP/UI embed
```

| Interface need | Borrow (examples) | Repo status |
|----------------|-------------------|-------------|
| Schematic/PCB **view** in browser | [KiCanvas](https://github.com/theacodes/kicanvas) / KiCad web viewers | **Wired** — Design verify tab + `/v1/build-files/*` |
| Live edit when human has KiCad open | `kicad-mcp-pro`, kipilot-mcp | Documented **sidecar** + recheck API |
| Web-native circuit graph | `tscircuit` / circuit-json | **Wired** — Interface lab + `netlist-compile` |
| Canvas compose | Our `/v1/compose-canvas` | **Wired** — Interface lab (not main wizard path) |
| Autoroute | FreeRouting bridge | `freerouting_bridge.py`; `AUTOROUTE=1` opt-in |
| Fab/JLC shape | Fabrication-Toolkit, jlcpcb API | Partial; JLC enrich hooks |
| Schematic capture AI | SchGen / SINA-style | **Intake adapter** — not core engine |

**We do not need** a from-scratch browser ECAD. We need **adapter + embed** work.

---

## What splice-ui still defers ([`UI_V1.md`](UI_V1.md))

- Full Circuit-AI canvas in main product wizard path  
- Donor photo upload in wizard (API exists)  
- Mermaid offline / CDN-free wiring diagram  

KiCad preview embed is **shipped** on the Design verify tab (v1.1 preview).

---

## Competitor comparison — corrected axis

| Compare on | Not |
|------------|-----|
| “Can we attach a real editor to our compile spine?” | “Did we ship Flux’s gallery?” |
| Artifact truth (DRC, gates, casefile) | Pixel-perfect collaborative canvas |
| Time to **first integrated preview** | Time to **build** a new ECAD SaaS |

**External sentence (v1 pilots):**  
Donor/splice → gates → package (layer 5 wedge).

**Internal sentence (engine):**  
Headless compile truth + splice; **hang any UI on it** via OSS plugs — see FLUX_TARGET.

---

## Suggested interface sprint (post v1.1.0-alpha.1)

Ordered by leverage — see [`OSS_INTERFACE_INTEGRATION_STRATEGY.md`](OSS_INTERFACE_INTEGRATION_STRATEGY.md) for full map.

1. ~~KiCanvas embed in Design verify tab~~ — ✅ v1.1 preview
2. ~~Interface lab — compose-canvas + circuit-json + netlist~~ — ✅ v1.1 preview
3. ~~KiCad MCP sidecar doc + dev profile~~ — ✅ documented
4. **Tag `v1.1.0-alpha.1`** after manual UI pass
5. **Donor photo** — wire existing vision API to wizard step
6. **JLC enrich toggle** in Design verify UI
7. **Autoroute CI slice** — promote `AUTOROUTE=1` on 2–3 fixtures before UX promises routing  

---

*Last updated: 2026-07-07*
