# Cold-internal exit — alpha.16

**Declared:** 2026-07-10  
**Tag:** `v1.1.0-alpha.16`  
**Meaning:** Software-only readiness is finished for Phase 0 and Phase 1 under the **cold-internal** proxy (fresh archive + second machine). Strangers are optional. Autoroute is **out of scope** for this exit (maintainer-owned).

---

## Proof machines

| Machine | Report |
|---------|--------|
| optiplex (fresh archive) | [`install_reports/INSTALL_REPORT_optiplex_cold_2026-07-10_alpha16.md`](install_reports/INSTALL_REPORT_optiplex_cold_2026-07-10_alpha16.md) |
| DESKTOP-FGEDHGV (WSL) | [`install_reports/INSTALL_REPORT_desktop-fgedhgv-wsl_2026-07-10_alpha16.md`](install_reports/INSTALL_REPORT_desktop-fgedhgv-wsl_2026-07-10_alpha16.md) |

**Command:** `bash scripts/deploy_alien_quickstart.sh v1.1.0-alpha.16`  
**Keyed live VL:** `HS_ALIEN_QWEN=1 …`

---

## Bar that must stay green

Automated: `scripts/agent_quickstart_verify.sh`

1. Catalog ≥ 50  
2. Canvas agent-loop → 0 DRC + package  
3. Async compose job  
4. Salvage `donor_context`  
5. Compose + simulated bench → `power_on_authorized`  
5b. Vision-assist draft → gates unchanged  
5c. Golden-real (non-sim) capture  
5f. Public-web DMM photos → power-on + `public_web_is_not_this_board`  
5d. Offline donor-board-vision  
5e. Copper honesty (preview ≠ fab-ready)  
6 / 6b / 6c. Qwen phrase + live photo salvage + live vision-assist **when keyed**

---

## Explicitly not claimed by this exit

| Claim | Why not |
|-------|---------|
| On-board café measurement of *this* donor | Needs physical DMM/PSU — [`REAL_BENCH_OPERATOR.md`](REAL_BENCH_OPERATOR.md) |
| `copper_tier: autorouted` / default fab-ready | Autoroute opt-in; maintainer track; default stays preview |
| Stranger zero-help dry-run filed | Process ready; not required for cold exit |
| Design Studio ECAD parity | Agent-loop wired; deeper UX is Phase 2 |

---

## Honesty rules that remain

- DRC 0 ≠ fab-ready  
- `simulate_bench` ≠ field evidence  
- Vision drafts ≠ gate closure  
- Public-web DMM LCDs ≠ this-board café  
- Default `HARDWARE_SPLICER_AUTOROUTE=0`

---

## After exit — what “finish” means next

1. **Physics:** one on-board capture when a board is on the bench  
2. **Copper (optional):** headless FreeRouting experiments by maintainer — do not block releases  
3. **Studio:** pin wire edit / live DRC hints  
4. **Distribution:** self-hosted kit when café case exists  

Product spine for agents is **done**. Remaining work is depth and claims, not missing glue.
