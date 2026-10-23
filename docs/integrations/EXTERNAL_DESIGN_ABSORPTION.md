# External design absorption — first format spike

**Status:** Experimental adapter (stacked on draft PR #193); no live frontend import button, no proprietary platform account/API integration, no production deployment.

**Decision:** Prefer licensed interoperability to duplicating commercial hardware project generators. HS remains the canonical project and engineering authority layer. See [issue #195](https://github.com/Spectating101/hardware-splicer/issues/195) and [issue #194](https://github.com/Spectating101/hardware-splicer/issues/194).

## First candidate

OpenBlueprint at https://github.com/noobianlabs/openblueprint is **not** the 3E8 Robotics/Blueprint.io product. Its repository software is MIT licensed (retain copyright/license on copied source; no source is copied in this adapter). Its project ZIP contains plain `design.json`, `bom.csv`, `instructions.md`, and an **approximate massing** `assembly.stl`.

The `apps/splice-ui/src/projectSession/externalDesignImport.js` function parses that **design.json** into a distinctly source-labelled, read-only proposal with parts/quantities, connections, mechanical hierarchy, instructions, and estimated USD costs. It rejects broken references, duplicate part identities, undeclared pins, invalid quantities, and excessively large lists.

This is **not** an HS canonical session, engineering `PROJECT_PACKAGE`, or completed UI import. No unverified third-party proposal can advance build, power-on or fabrication. Raw source SHA, user author, content-license provenance and real HS reconciliation are explicitly missing rather than made up.

## Existing OSS already in HS

Before adding a replacement tool or deep dependency, prefer existing adapters/catalog:
- `docs/OSS_INTEGRATION_STATUS.md`: KiCanvas, circuit-json/tscircuit, KiCad CLI, FreeRouting, iBOM, PcbDraw, JLC, ESPHome, etc. Per-tool status varies from wired to partial/reference-only.
- `docs/INTEGRATION_STACK.md`: donor and evidence authority contract.
- `docs/OSS_INTERFACE_INTEGRATION_STRATEGY.md`: thin adapter and UI projection pattern.

## Other commercial products

| Product | Verified status | Policy |
| --- | --- | --- |
| Blueprint.io (formerly Blueprint.am) | Commercial generator; no confirmed public API | No scraping or guessed endpoint |
| Schemr | Advertises BOM, wiring, STL/STEP/Arduino exports; API unconfirmed | Evaluate a real user-authorized export, never reverse engineer |
| Cirkit Designer | Provides project sharing/exports and custom component simulation API; **no confirmed general SaaS API** | Respect https://www.cirkitdesigner.com/terms-of-use.html (no scraping/reverse engineering or unauthorized redistribution) |

## Next verification before UI exposure

1. Fix #194 (motor BOM count, source-bound power path, blocked unsafe wiring) first; importer may not bypass these gates.
2. Add actual user-selected `design.json` bytes input, compute the SHA-256 from bytes, bind license/author where evidenced.
3. Compare proposed counts and network references with the canonical HS graph/parts inventory; unresolved differences become explicit blockers.
4. Build one happy path with OpenBlueprint's real example ZIP and 2 invalid fixtures. Test greenfield environmental monitor and donor rover.
5. Only after schema/authority proof, add opt-in "Import reference design" in the existing project-first UI.
6. Offer deep links to commercial services where no official integration is available, not unlicensed embeds.

References: OpenBlueprint README, MIT LICENSE, `src/lib/design/schema.ts`, `src/lib/design/export.ts` (accessed 2026-10-23). Source-backed capability research applies only to public documented features, not verified official integration contracts.
