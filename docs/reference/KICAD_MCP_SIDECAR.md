# KiCad MCP sidecar (P1 — documented, not bundled)

**Purpose:** Let a human edit KiCad schematics/PCBs in the desktop app while Hardware-Splicer keeps compile truth, DRC, and `PROJECT_PACKAGE` authority.

**Status:** **documented** — not a hard runtime dependency. Multiple community MCP servers exist; we do not pin one repo in the product.

---

## Pattern

```text
Operator                    Sidecar (optional)              Hardware-Splicer
────────                    ──────────────────              ────────────────
Opens KiCad GUI    ←──→     KiCad MCP server                hs-serve API
Edits .kicad_*              (stdio/SSE to agent)            build_compilation/
Saves files                 Agent assists in KiCad          DRC / gates / zip
                            ───────────────────────────────► Re-run compile + design-quality
```

1. Compile a build normally (CLI, UI, or agent).
2. Open `build_compilation/*.kicad_pcb` in KiCad (or via MCP-assisted session).
3. After human save, point HS at the same `build_dir` and refresh:
   - `scripts/kicad_mcp_dev_profile.sh <build_dir> recheck`
   - `POST /v1/build-files/recheck`
   - splice-ui Design tab → **Recheck after KiCad edit**

---

## Candidate servers (evaluate per lab)

| Project | Notes |
|---------|--------|
| [mixelpixx/KiCAD-MCP-Server](https://github.com/mixelpixx/KiCAD-MCP-Server) | Early MCP bridge |
| Seeed / community `kicad-mcp` forks | Vary by KiCad version |

**Caution:** License and KiCad version differ per fork. Treat as **dev profile** only until one server is pinned for a release train.

---

## What we claim

| Allowed | Not allowed |
|---------|-------------|
| “KiCad remains the edit surface; HS re-compiles and gates” | “Built-in collaborative ECAD” |
| “MCP sidecar for human-in-loop edits” | “MCP required to use Splice Agent” |
| “Same `build_dir` truth after save” | “Replaces KiCad” |

---

## Env / ops (sketch)

```bash
# Terminal A — API
hs-serve --host 127.0.0.1 --port 8787

# Terminal B — KiCad + MCP (example; exact command depends on chosen server)
# Configure MCP in Cursor/Claude with chosen KiCad MCP server
# Working directory: path to build_compilation/
```

After edits, in splice-ui **Design** tab: reload preview (KiCanvas reads `POST /v1/build-files/content`).

---

## Related

- [`OSS_INTEGRATION_STATUS.md`](OSS_INTEGRATION_STATUS.md)
- [`OSS_INTERFACE_INTEGRATION_STRATEGY.md`](OSS_INTERFACE_INTEGRATION_STRATEGY.md)
- [`KICAD_MCP_DEV_PROFILE.md`](KICAD_MCP_DEV_PROFILE.md)
- [`ENGINE_VS_INTERFACE.md`](ENGINE_VS_INTERFACE.md)
