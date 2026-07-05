# Support & liability — Splice Agent v1

**Purpose:** Professional boundaries for pilots, site licenses, and grant reviewers.

**Version:** 1.0.1 · **Product:** Hardware-Splicer Splice Agent

**Related:** [`PACKAGING_AND_DEPLOYMENT.md`](PACKAGING_AND_DEPLOYMENT.md) · [`OFFER_SPLICE_BENCH_KIT_v1.md`](OFFER_SPLICE_BENCH_KIT_v1.md)

---

## 1. Product definition

**Splice Agent** is self-hosted software that:

- Accepts structured donor/splice intake
- Compiles a KiCad carrier and runs DRC checks where configured
- Emits a **PROJECT_PACKAGE** with BOM, wiring, instructions, and **bench gates**
- Tracks bench measurements and gate verdict before power-on authorization

It is **bring-up and documentation infrastructure**, not a safety-certified ECAD tool or a substitute for qualified electrical engineering judgment.

---

## 2. What we stand behind (v1)

| Area | Commitment |
|------|------------|
| **Reproducibility** | Documented install + `make verify-splice-v1` bar; CI `splice-v1` job on product paths |
| **Compile honesty** | KiCad/DRC outcomes and `COMPILE_CASEFILE.json` on failure — not hidden |
| **Gate workflow** | Bench session JSON, gate IDs, measurement records, verdict fields |
| **API/MCP parity** | Same splice spine via HTTP and MCP for integrators |
| **Versioning** | Semver tags, `CHANGELOG.md`, release notes per tag |

---

## 3. What we do not guarantee

| Exclusion | Reason |
|-----------|--------|
| Donor harness safety | Physical wiring, insulation, and fire risk are operator/site responsibility |
| “Any prompt → any PCB” | Intake is bounded; synthesis is planner-limited |
| Production copper quality | Default path is not full production autoroute |
| Regulatory certification | No UL/CE/EMC certification from this software |
| Uptime SLA (community/OSS) | Self-host; operator runs KiCad and disk |
| Vision/LLM outputs as measurements | Vision assists; bench gates require recorded measurements |

---

## 4. Power-on and liability

**Critical rule:**

> The engine **assists** compile and gate tracking. The **operator** (or site qualified person) **authorizes energization** after reviewing gate verdict, measurements, and physical inspection.

`power_on_authorized` in bench session JSON means **software gate state** — not legal clearance or certified safety.

Paid pilots should include explicit language:

- Customer owns final power-on decision
- Customer owns donor hardware condition and enclosure
- Vendor provides software, compile artifacts, and gate workflow — not on-site electrical certification

---

## 5. Software license

| Distribution | Terms |
|--------------|-------|
| **Source checkout** | Proprietary — see `pyproject.toml` (`license = { text = "Proprietary" }`) |
| **Commercial site license** | Separate written agreement (not implied by git clone) |
| **Contributions** | By arrangement with rights holder |

Contact the repository owner for commercial licensing. Do not assume MIT/OSS terms unless a separate `LICENSE` file is published.

---

## 6. Support tiers (intended)

| Tier | Scope | Response |
|------|-------|----------|
| **Community** | Public repo issues, best effort | No SLA |
| **Pilot / project** | One splice delivery + handoff call | By statement of work |
| **Site license** | Install on customer LAN, email support, quarterly updates | Agreed in contract (e.g. 2–5 business days) |

**In scope for paid support:** engine bugs, install regressions on documented platforms, job API behavior.

**Out of scope:** KiCad installation on exotic OS, customer schematic edits, fab yield, donor damage.

---

## 7. Security posture (v1)

- Default bind: `127.0.0.1` — not internet-facing
- LAN exposure: use nginx + TLS + API key (see `deploy/nginx/`)
- No built-in multi-tenant auth in v1 — do not expose raw `hs-serve` to the public internet
- Secrets via environment variables — never commit `.env`

---

## 8. Data handling

- Builds and job state default to local disk (`HARDWARE_SPLICER_TMP_ROOT`, `HARDWARE_SPLICER_STATE_DIR`)
- Operator controls retention and backup
- No telemetry shipped to vendor in v1 self-host

---

## 9. Reporting issues

1. `hs-doctor --json` output
2. `COMPILE_CASEFILE.json` or job error payload if compile failed
3. `SPLICE_BENCH_SESSION.json` if gate workflow issue
4. OS, KiCad version, git tag

File GitHub issues for community tier; email for paid license holders per contract.

---

## 10. Changelog

| Date | Change |
|------|--------|
| 2026-07 | Initial v1 support & liability boundary |
