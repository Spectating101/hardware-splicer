# Splice UI — v1.0 product interface

**Location:** `apps/splice-ui/`  
**Purpose:** **Consumer-facing** Hardware-Splicer interface — plain-English project start, guided wizard, async builds, project package tabs.

---

## Consumer journey

```text
Home → Start a project
  → Describe goal (plain English)
  → Clarifier questions (power, controller, load, salvage)
  → Salvage vs new parts
  → Parts you have
  → Donor board picker (if salvage)
  → Power & runtime
  → Review → async build (jobs API)
  → Overview · Parts · Wiring · Steps · Gates · Bench
  → Download zip
```

**Examples** and **Recent builds** paths for demos and returning users.

---

## Architecture

```text
Browser (splice-ui :5178)
    │  /api/* proxied in dev
    ▼
FastAPI (hs-serve :8787)
    ├── GET  /v1/examples/splice-intakes
    ├── POST /v1/splice-and-build
    ├── POST /v1/splice-bench/status
    └── POST /v1/splice-bench/submit
```

CORS is enabled on the API for local dev ports 5177–5178.

---

## Run locally

```bash
# Terminal 1
pip install -e ".[mcp]"
hs-serve --host 127.0.0.1 --port 8787

# Terminal 2
make splice-ui-dev
```

Open http://127.0.0.1:5178

---

## Tabs (Blueprint-shaped package)

| Tab | Source |
|-----|--------|
| INFO | `project_package.info` |
| BOM | `project_package.bom` |
| WIRING | `project_package.wiring` |
| INSTRUCTIONS | `project_package.instructions` |
| GATES | `project_package.gates` + `SPLICE_BENCH_SESSION` |
| BENCH | live bench status + measurement submit |

---

## v1.0 scope

**In (consumer):**

- Plain-English goal + clarifier wizard
- Salvage / new mode, parts editor, donor fixture picker
- Async job builds with polling
- Consumer-friendly tab labels
- Recent builds + download zip
- Example gallery

**Still out (honest limits):**

- Donor **photo** upload in UI (API exists; not wired)
- Freeform NL without wizard steps
- KiCad / 3D preview embed
- Auth, billing, cloud hosting
- Full Circuit-AI canvas

---

## Related

- [`apps/splice-ui/README.md`](../apps/splice-ui/README.md)
- [`PACKAGING_AND_DEPLOYMENT.md`](PACKAGING_AND_DEPLOYMENT.md)
- [`RELEASE_V1.md`](RELEASE_V1.md)
