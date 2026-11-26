# Hardware-Splicer scale plan: how far it can go, and everything needed to get there (2026-11-26)

Companion to `COMMERCE_CONVERSION_RESEARCH_20261126.md`. That report chose the route (services first, products as
proof). This one asks how far the route goes and lists every feature and function, engineering and business, needed to
scale it, with what exists today. Assumptions are marked as such; nothing here has been sold or built.

## 1. The ladder: where each stage tops out

| Stage | What is sold | Evidence and limit | Monthly revenue range (assumption-based) |
|---|---|---|---|
| 0. Today | Nothing | No physical proof, PRO360 account unverified, lead system aimed at software only | 0 |
| 1. First jobs (from Feb 2027) | Small hardware design jobs in Taiwan: PCB layout, enclosures and mechanisms, 3D models and prints, small prototypes | Demand measured: about 19 PCB, 14 mechanism, 14 product-design and 49 3D-printing requests a month on PRO360, about 22 budgeted hardware posts a month on Tasker; posted medians NT$10,000 (3D) to NT$20,000-30,000 (PCB, firmware, prototypes) | 2-4 jobs at NT$10,000-30,000 = **NT$20,000-120,000**. Assumes a 10-20% win rate (not measured) and about 20-30 quotes a month, so NT$5,000-8,000 of PRO360 quote fees |
| 2. Productized solo studio | Fixed-price packages, repeat clients, international clients via Upwork | Upwork hardware rates about US$40-85/h (Fiverr 2026 guide); limit is one person's hours | **NT$100,000-200,000**: the solo ceiling, since each job still needs client talk and review |
| 3. Studio with a bench | You sell and review; engineers deliver with HS as the quality gate. Your notes aim at a business in Indonesia: Indonesian PCB designers list about US$12-25/h on Upwork against Taiwan budgets of NT$20,000-30,000 per job | Limit: finding reliable engineers, and HS checks good enough that review stays fast | Margin on rate gap; scales with clients, not your hours |
| 4. Products from repeated requests | One niche product per repeated request type (a board, a kit, an inspection rover) | Certification only when volume pays for it: NCC about NT$70,000-170,000 per radio product (lab estimate); BSMI for power supplies | Unbounded, but capital and certification come first |

Two later options that research weakened:
- **A "non-red" drone parts-origin checker.** ITRI already runs Taiwan's verification platform and is authorized for US
  "Green UAS" evaluation, with 267+ companies in the supply chain. What remains is a service: helping small component
  makers prepare traceability files before ITRI review. Only worth pursuing after customer interviews.
- **Selling HS as software.** Flux has US$37M in funding and charges about US$20-142 a month; competing head-on is not
  realistic. HS's edge is checked deliverables, which is worth more inside a studio than as a subscription.

## 2. Engineering features: what HS has, what each paid job type needs

Rated against what Taiwan clients actually asked for in the scraped requests: board sizes, MCU pin maps, Allegro files,
enclosures, mechanisms, assembly drawings, wiring harnesses, samples.

| Deliverable a client pays for | HS today | Gap to close | Priority |
|---|---|---|---|
| PCB from a block diagram or pin map | Component schematic generator from real KiCad libraries, read-back parity, ERC, routed PCB, DRC with parity, Gerbers, drill, pick-and-place, BOM (`kicad_component_board`, HS-BUS-A) | Intake that turns a client's pin map or block diagram into the design file; a retry-and-keep loop for FreeRouting's run-to-run misses | **P1** |
| PCB priced and orderable | JLCPCB/LCSC parts, stock and price via `jlcparts_lookup`; keyword matches flagged | Board and assembly quote (JLCPCB setup about US$8 economic tier, per-joint and extended-part fees: confirm live); a "basic parts first" substitution pass | **P1** |
| PCB in the client's tool | KiCad only | Altium imports KiCad files (its guide lists up to KiCad 6 or 8, versions disagree); no KiCad-to-Allegro route found. Offer KiCad plus Gerbers, and test an Altium import on a copy | P2 |
| Enclosure for a board | `device_case` (STL/OpenSCAD two-part box from a device plan); CadQuery parts (HS-ARM-A) | Board-to-case fit from the KiCad STEP export (`kicad-cli pcb export step`), screw bosses, port cut-outs from real connector positions | **P1** |
| Mechanism and structural design | CadQuery CAD, motion sweep, URDF, static torque, FEM screening (`mechanical_cad_fem`, gmsh now installed) | FEM on real parts with cited material data (PLA figures not yet sourced); joint and fastener detail | P2 |
| 2D dimensioned drawings | **None** | Drawings from the CAD (views, dimensions, title block) as PDF and DXF; clients asked for 組立圖 (assembly drawings) | **P1** |
| 3D model fixes and prints | STEP/STL export; mesh tools (trimesh) | Mesh repair (watertight check and fix), print-orientation and wall checks; local print-shop pricing | P2 |
| Firmware starter | `firmware_scaffold`, `device_firmware` (compile-only packages) | Build and flash for ESP32/STM32 through PlatformIO with a minimal on-bench test | P2 |
| Wiring harness | `wiring_harness` (DC and signal checks) | Harness drawing and cut list (one client needed a 48 V vehicle harness) | P3 |
| Client hand-off | `engineering_package` (reproducible ZIP), `verification.json` per project | A client-facing report: renders, checks passed, open items, BOM cost, in Chinese and English | **P1** |
| Physical proof | Bench-evidence modules (`bench_loop`, physical evidence ledger) | Actually building and testing: none of the designs has been made | **P1** |

## 3. Proof pieces: one each, built and tested

| Piece | Remaining work | Why it sells services |
|---|---|---|
| HS-BUS-A board | Order a small batch (quote first), test with real servos | Shows a full PCB job: schematic to working board |
| Arm, cost-down | Redesign on Feetech STS3215 servos to reach the SO-ARM101 class (US$299 assembled), print, assemble | Shows mechanism plus electronics at a market price point |
| CCTV/inspection rover | Chassis CAD, camera and streaming, controller board, drive test | Matches requests like "AI inspection robot" (Tasker NT$200,000) and the robot posts |
| FPV drone | Airframe CAD, flight-controller choice and configuration, flight test | Matches drone ground-control and drone posts; also the non-red conversation |
| Compact FieldDeck (CM5) | Redesign around CM5 with a proper power path | Shows a consumer-electronics enclosure job |

## 4. Business functions: what exists in your other project, what is missing

The lead system lives in `Molina-Optiplex` (scrapers, scoring, apply queue, rate card). Its May 2026 audit already said
the missing layer was "engagement/conversion", and that is still true.

| Function | Today | Needed |
|---|---|---|
| Lead collection | PRO360, Tasker, Kolabtree scrapers every 2 h; 461,575 posts stored | **Tasker stored nothing since 27 Oct 2026** while logging "done" (parser silently broken). Searches only software keywords. Add hardware keywords (PCB, 電路, 韌體, 機構, 3D列印, 樣機, 無人機) |
| Lead scoring | Rate card and scoring built for software and data work; it explicitly excludes PLC/MCU/firmware | A hardware lane: fit scoring for PCB, enclosure, mechanism, prototype, firmware |
| Approval and drafts | Apply queue with draft messages; stalled since 20 May (7 pending) | Daily approval habit; hardware reply templates that attach an HS sample package |
| Platform accounts | PRO360 expert account exists but cannot quote (identity verification); Tasker and Upwork profiles not checked here | Verification, plus a hardware profile pack: renders, a sample package, a price list |
| Quoting | Software rate card (NT$) | Hardware rate card from the scraped budgets, plus a scope-to-price estimator (hours, risk, parts and fab cost from `jlcparts_lookup`) |
| Contract, milestones, invoicing | None | Simple milestone template (deposit, design, revisions, delivery), invoice and payment tracking, tax status for freelance income (to check) |
| Delivery and QA | HS checks per project | The client report (section 2), a revision log, and a rule that nothing ships without passing HS's checks |
| Spend control | Prepaid-only API rule and harness guard (2026-11-26) | Per-job cost tracking: platform fees, fab, parts, API |

## 5. Owner-only gates

1. Thesis defense on 7 January 2027 comes first; this plan assumes little of your time before then.
2. Work status: confirm with YZU's international office whether platform freelancing is allowed on a student work permit
   (20 h/week cap in term, fines NT$30,000-150,000 for unauthorized work). Your notes say the graduate extension after
   graduation removes the separate permit, so February 2027 is the clean start.
3. PRO360 identity verification.
4. A proof budget: each build quoted first, approved by you.

## 6. Order of work

| Window | HS engineering (mine) | Business (mine, your approval) | You |
|---|---|---|---|
| Now to 7 Jan | P1 items: drawings, client report, enclosure-from-board, quoting estimator, intake from pin map; arm cost-down design | Fix the Tasker parser and add hardware keywords (in Molina-Optiplex, after checking no other session is editing it); hardware lane in scoring; hardware rate card | Thesis; YZU work-status question |
| 8-31 Jan | Order and test HS-BUS-A; print the cost-down arm | Profile pack from the proof pieces | Approve proof spend; housing move |
| From Feb 2027 | Rover and drone proof pieces between jobs | Approval queue daily; 20-30 quotes a month | PRO360 verification; client calls |
| After 3 paid jobs | P2/P3 items driven by what clients asked | Upwork profile; decide on Stage 3 bench | Decide |

Sources: as in `COMMERCE_CONVERSION_RESEARCH_20261126.md`, plus ITRI's verification platform and Green UAS authority
([Taiwan News](https://www.taiwannews.com.tw/news/6434577), [TaiwanPlus](https://www.taiwanplus.com/news/taiwan-news/taiwan-us-relations/260129021/taiwans-itri-joins-drone-security-framework),
[Focus Taiwan](https://focustaiwan.tw/business/202606040018)) and Altium's KiCad import ([Altium migration guide](https://www.altium.com/altium-designer/migrate/kicad-pcb),
[Altium interfacing docs](https://www.altium.com/documentation/altium-designer/design-tools-interfacing)).
