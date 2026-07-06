# atopile import path (partial)

**Status:** **partial** — no atopile runtime bundled. Import via KiCad netlist export into the existing compile spine.

**Related:** [`OSS_INTEGRATION_STATUS.md`](OSS_INTEGRATION_STATUS.md) · Interface lab → **Paste KiCad netlist**

---

## Pattern

atopile designs compile to KiCad artifacts. Hardware-Splicer accepts the **KiCad netlist** (S-expression export) on the same path as SKiDL:

```text
atopile project  →  KiCad netlist (.net)  →  POST /v1/netlist-compile (kicad_netlist_text)
                                              →  build_compilation/*.kicad_pcb
                                              →  Design tab (KiCanvas) + gates
```

---

## Quick try (Interface lab)

1. `hs-serve` + `make splice-ui-dev`
2. Sidebar → **Interface lab**
3. Section **Paste KiCad netlist** — paste an atopile or SKiDL KiCad netlist export
4. **Compile pasted netlist** → **View board in KiCanvas**

Or use fixture `esp32_servo_kicad` as a reference netlist shape.

---

## API

```bash
curl -s -X POST http://127.0.0.1:8787/v1/netlist-compile \
  -H 'Content-Type: application/json' \
  -d '{"kicad_netlist_text":"<paste>", "build_id":"generic_low_voltage_build"}'
```

---

## Claims

| Allowed | Not allowed |
|---------|-------------|
| “atopile export → same compile spine as SKiDL” | “Native atopile editor in Splice UI” |
| “Code-defined boards via netlist interchange” | “atopile is a dependency” |

---

*Future: optional atopile CLI sidecar that exports netlist to a watched path — same as KiCad MCP pattern.*
