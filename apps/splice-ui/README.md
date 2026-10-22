# Splice UI (v1.0)

Real **consumer-facing** web interface for Hardware-Splicer — plain-English project start, guided wizard, async builds, and project package tabs.

## Quick start

### Single port (auditor / demo)

```bash
make splice-ui-serve
```

Open http://127.0.0.1:8787 — API and built UI on one origin.

### Dev (hot reload)

Terminal 1 — API:

```bash
pip install -e ".[mcp]"
hs-serve --host 127.0.0.1 --port 8787
```

Terminal 2 — UI:

```bash
cd apps/splice-ui
npm install
npm run dev
```

Open http://127.0.0.1:5178

## OpenBlueprint compatibility (experimental)

The home screen accepts a plain-English goal and carries it into the existing
HS clarification wizard. It can also import the **MIT OpenBlueprint**
`DesignPackage` JSON file (`design.json` inside an OpenBlueprint export ZIP)
for a local, read-only inspection — **no backend required**. Imported proposals
can start a new HS intake, but do not become verified circuits, real CAD or
authorized hardware. Compiled native HS projects get the same Overview / Parts /
Architecture / Wiring / Mechanical / Code / Build / Verify explorer, backed by
actual HS package and evidence state.

See [OpenBlueprint bridge and nonclaims](../../docs/OPENBLUEPRINT_BRIDGE.md).
This is not a Blueprint.io integration or an OpenBlueprint generator fork.

## Consumer flow

1. **Home** — value prop + “Start a project” / “Try an example”
2. **Wizard** — goal in plain English → clarifier questions → salvage vs new → parts list → donor fixture → power → review
3. **Async build** — `POST /v1/jobs/splice-build` with progress polling (30–90s KiCad compile)
4. **Results** — Overview · Parts list · Wiring · Build steps · Safety gates · Bench
5. **Recent builds** — sidebar history + download zip

## API surface (UI)

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/examples/splice-intakes` | Demo projects |
| `GET /v1/examples/donor-fixtures` | Donor board picker |
| `POST /v1/intent/clarify` | Follow-up questions |
| `POST /v1/jobs/splice-build` | Start build |
| `GET /v1/jobs/{id}/result` | Load package |
| `GET /v1/jobs/{id}/bundle` | Download artifacts |
| `POST /v1/splice-bench/*` | Gate workflow |

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_BASE` | `/api` (dev) · `""` (prod build) | API prefix; empty = same origin |
| `HARDWARE_SPLICER_SERVE_UI` | off | When `1`, `hs-serve` / uvicorn serves `apps/splice-ui/dist` at `/` |

Production: `make splice-ui-build` then `HARDWARE_SPLICER_SERVE_UI=1 hs-serve`, or serve `dist/` behind the same origin as the API.

## Related

- `docs/UI_V1.md` — product UI scope for v1.0
- `docs/PACKAGING_AND_DEPLOYMENT.md` — install and deploy
- `hs-mcp` — optional agent/MCP path alongside this UI
