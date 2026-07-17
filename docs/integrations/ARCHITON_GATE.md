# Architon gate — optional compose path

**Status:** Documented compose spike (2026-07-18). **Not** a default install dependency.  
**Why:** Architon (`rv`) is deterministic pre-fab electrical/architecture verification from KiCad netlist/BOM. Hardware-Splicer already owns splice compile + DRC + bench gates; Architon adds a **system-contract** check before fab spend.

**Upstream:** [architon.io](https://architon.io/) · CLI commonly invoked as `rv scan` / `rv check`

---

## Where HS emits inputs

After a successful compose / project package, look under the build / package tree for:

| Artifact | Typical use for Architon |
|----------|--------------------------|
| `.kicad_pcb` / project dir | `rv scan <project-dir>` |
| KiCad `.net` netlist (if emitted) | Netlist import |
| `BOM.csv` | BOM merge into DesignIR |

Exact paths vary by job; use Design tab **Exports & interchange** or `POST /v1/build-files/artifacts` ([`OSS_INTEGRATION_STATUS.md`](../OSS_INTEGRATION_STATUS.md)).

HS authoritative DRC remains **`kicad-cli`**. Architon does **not** replace KiCad DRC or bench `power_on_authorized`.

---

## Suggested operator flow

1. Run HS splice / compose until `kicad_drc_errors == 0` and `PROJECT_PACKAGE` exists.  
2. Install Architon CLI per upstream docs (keep it outside the HS venv).  
3. From the emitted KiCad project directory:

```bash
rv scan .
# or: rv check contracts.yaml   # if you maintain architecture contracts
```

4. Treat Architon exit ≠ 0 as **pre-fab hold** — fix contracts/design, re-compose in HS, re-scan.  
5. Record both: HS package hash + Architon report JSON/HTML in the pilot handoff zip.

---

## Product claims (honesty)

| Allowed | Not allowed |
|---------|-------------|
| “Optional Architon contract scan on the carrier” | “HS includes Architon” as a bundled dependency |
| “DRC clean + architecture contracts checked” when both ran | Claiming Architon ran when it did not |

---

## Integration roadmap (later)

- [ ] `scripts/optional_architon_gate.sh` — locate latest package out_dir, invoke `rv scan`, copy report beside `PROJECT_PACKAGE`  
- [ ] Catalog row in `/v1/integrations/catalog` with status `documented` → `opt_in` when script ships  
- [ ] Do **not** vendor Architon source into this repo  

---

## Verification

```bash
command -v rv || command -v architon || echo "Architon CLI not installed — doc-only path OK"
```
