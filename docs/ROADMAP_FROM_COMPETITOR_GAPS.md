# Roadmap from competitor gaps — v1.0.2 (internal)

**Purpose:** Prevent panic-building after competitor comparison. **Only** items that strengthen layer 5 (bring-up proof).

**Inputs:** [`COMPETITOR_SCORECARD_v1.0.2.md`](COMPETITOR_SCORECARD_v1.0.2.md) · [`COMPARISON_DEMO_CASE_robot_repair_cafe.md`](COMPARISON_DEMO_CASE_robot_repair_cafe.md)

---

## Do now (≤1 week)

| Item | Why | Owner |
|------|-----|-------|
| **CI badge fix** | README badge red because legacy `verify` job fails; Splice v1 bar is green | Split workflow or badge to `splice-v1` job only |
| **Competitor pack** | Internal alignment before external talk | ✅ this doc set |
| **One trusted reviewer** | External proof = one conversation with release zip | Founder |
| **Claims discipline** | [`CLAIMS_BOUNDARY.md`](CLAIMS_BOUNDARY.md) on all outbound copy | Founder + agents |

**Do not** start outreach blast or grant apps until badge + one conversation.

---

## Do only if comparison exposes weakness

| Gap | Competitor pressure | Priority | Notes |
|-----|-------------------|----------|-------|
| UI job failure copy | Blueprint UX | P1 | User-visible errors — not Flux parity |
| BOM LCSC/JLC enrich | Flux/EasyEDA sourcing | P2 | Engine hooks exist |
| Wiring Mermaid in UI | Blueprint presentation | P2 | Data already in package |
| Cleaner `git clone` on lab WSL | Repro story | P2 | Tarball worked; network hung |
| 5-min demo video | Blueprint onboarding | P2 | Script exists: `DEMO_5_MIN_UI.md` |

---

## Do not (competitor traps)

| Trap | Why stop |
|------|----------|
| Browser ECAD editor | Flux bucket — **build from scratch**; prefer KiCanvas / KiCad MCP / circuit-json **embed** |
| Production autoroute default | Quilter bucket |
| Native Windows installer | Not wedge; WSL2 sufficient for v1 |
| Public multi-tenant SaaS | Different product + liability |
| “Beat Flux” repositioning | [`FLUX_TARGET.md`](FLUX_TARGET.md) is engine aspiration, not v1 SKU |
| Full fleet cluster Splice installs | Distraction from one good alien proof |
| More 40-page strategy docs | Comparison pack is enough |
| GDELT / data-lab mixed into Splice launch | Separate system |

---

## Integration (not competition) — later

| Partner class | Integration idea |
|---------------|------------------|
| **Quilter** | Export carrier constraints → route → re-import for DRC + gates |
| **JITX** | High-end path — different buyer |
| **Schematic AI (SINA, etc.)** | Intake adapter → existing splice spine |
| **KiCad** | Stay substrate; contribute upstream if useful |

---

## Success criteria for this sprint

```text
✓ Team can explain layer-5 wedge in one sentence
✓ Sample zip used in comparison, not hypothetical outputs
✓ No new roadmap items unless they strengthen gates/package/handoff
✓ One conversation scheduled or completed with release link
```

---

*Timebox: 1 day for docs; stop after one reviewer conversation.*
