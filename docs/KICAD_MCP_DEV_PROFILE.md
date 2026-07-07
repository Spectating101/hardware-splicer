# KiCad MCP dev profile

**Purpose:** Repeatable workflow for **human edits in KiCad** while Hardware-Splicer keeps DRC truth, package, and gates authority.

**Status:** **partial** — script + API wired; MCP server choice remains operator-configured.

**Related:** [`KICAD_MCP_SIDECAR.md`](KICAD_MCP_SIDECAR.md) · [`BUILD_FILES_API_SECURITY.md`](BUILD_FILES_API_SECURITY.md)

---

## Thesis

> Edit in real KiCad; Hardware-Splicer re-compiles checks, gates, and packages.

This is the bridge between “we are not Flux” and “we still have a serious design interface story.”

---

## Quick start

```bash
# After any splice/compile produced build_compilation/*.kicad_pcb
export HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1   # if build_dir is outside API output root

scripts/kicad_mcp_dev_profile.sh /path/to/build session   # print full workflow
scripts/kicad_mcp_dev_profile.sh /path/to/build open      # launch KiCad
# … edit and save in KiCad …
scripts/kicad_mcp_dev_profile.sh /path/to/build recheck   # DRC/ERC + package + PDF/SVG
```

**splice-ui:** Design tab → **Recheck after KiCad edit** (calls `POST /v1/build-files/recheck`).

---

## What `recheck` does

1. `kicad-cli pcb drc` on primary `.kicad_pcb` → `KICAD_DRC.json`
2. `kicad-cli sch erc` on matching `.kicad_sch` → `KICAD_ERC.json`
3. Merge into `DESIGN_QUALITY.json` (timestamp + source)
4. Optional: `export-views` (PDF/SVG/PNG)
5. Optional: `render_project_package` → `PROJECT_PACKAGE.json` + zip

Implementation: `src/hardware_splicer/kicad_sidecar_recheck.py`

---

## MCP (optional)

Configure a KiCad MCP server in Cursor/Claude with working directory:

```text
<build_dir>/build_compilation
```

Candidate servers: see [`KICAD_MCP_SIDECAR.md`](KICAD_MCP_SIDECAR.md). **Not bundled** — no hard dependency.

---

## API

```bash
curl -s -X POST http://127.0.0.1:8787/v1/build-files/recheck \
  -H 'Content-Type: application/json' \
  -d '{"build_dir":"/path/to/build","refresh_package":true,"export_views":true}'
```

---

## Claims

| Allowed | Not allowed |
|---------|-------------|
| KiCad remains the edit surface; HS rechecks truth | Built-in collaborative ECAD |
| Dev profile + optional MCP sidecar | MCP required to use Splice Agent |
| Same `build_dir` after human save | Replaces KiCad |

---

*Next: pin one MCP server in lab docs after a version-matched pass.*
