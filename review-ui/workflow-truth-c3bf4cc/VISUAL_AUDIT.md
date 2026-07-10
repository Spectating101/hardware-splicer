# Visual audit — workflow truth + Design-canonical greenfield

**Baseline:** `c3bf4cc`  
**Viewport:** 1440×900  
**Server:** `http://127.0.0.1:8787` (SERVE_UI + live KiCad agent-loop)

## Live DRC evidence (required this pass)

| Shot | File | Notes |
|------|------|-------|
| Populated Design canvas | `live-drc/05-design-canvas-populated.png` | ESP32 + DHT22 modules on canvas after Intake → Design |
| DRC agent loop result | `live-drc/06-design-drc-agent.png` | Live compile: DRC clean, 11 warnings, cosmetic preview copper, Continue to Verify |
| Verify after transition | `live-drc/07-verify-after-transition.png` | Status header + ProjectReadinessPanel share DRC/copper/bench truth |

## Supporting journey shots

| Shot | File |
|------|------|
| Home | `01-home.png` |
| Intake (Design tab disabled) | `02-intake.png` |
| Intake review → Continue to Design | `03-intake-review.png` |
| Design empty-state after COMMIT_INTAKE | `04-design-empty.png` |

## Product claims verified visually

1. Greenfield Intake CTA is **Continue to Design** (no compose from Intake).
2. Design unlocks only after Intake completion.
3. Empty Design explains goal carry-over + AI vs manual + DRC/copper honesty.
4. Live Studio compile shows agent rounds and DRC-clean ≠ fab-ready copper.
5. Verify shows one readiness panel (not duplicated ReadinessHero + SummaryBar chips).
