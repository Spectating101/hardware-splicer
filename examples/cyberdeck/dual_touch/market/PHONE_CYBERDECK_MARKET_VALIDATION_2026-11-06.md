**Execution update:** [HS cross-agent evidence bridge](AGENT_PIPELINE_HANDOFF_2026-11-06.md) now consumes pinned pricing, engineering and demand signals.

# Phone + Cyberdeck: Research-backed product family decision

**Dated:** 2026-11-06 (Taiwan) | **Owner:** Hardware Splicer (HS) research pipeline
**Decision:** Has purchasing demand been demonstrated, and can HS ship a phone edition and developer-first foldable cyberdeck?
**Classification:** Source-backed product research / proposed gates. **No interviews, customer purchase commitments, new hardware, manufacturing quotes or delivered device were obtained here.**

## Answer

**Agent-controlled development: strongly substantiated.** **Paid specialty handheld demand: substantively demonstrated in adjacent categories.** **Paying demand for our exact phone + two-touchscreen cyberdeck family: not yet substantiated.** **HS CAD+integration: demonstrated in software.** **HS production-ready dual touchscreen, complete smartphone hardware, secure firmware or real device: not demonstrated.**

Treat the products as *one remote-development service with two clients*. The lowest-risk smartphone edition is an **app/PWA on already-owned Android/iOS phones**, not a newly designed cellular phone. Cyberdeck should earn its existence by *measurably improving review/control over that phone*, not by featuring a hinge.

## Core hard evidence and careful denominators

| Observation | Original source | What it actually proves |
|---|---|---|
| GitHub >225M developers, >40% of Sept 2026 PRs start with an agent vs 17% in March | https://github.blog/news-insights/octoverse/octoverse-commits-pushes-reach-new-highs-in-2026-as-developers-build-with-agents/ | Coding-agent activity expanding; NOT hardware buyers |
| 2026 Stack Overflow survey: 65.9% of respondents (n=17,464) use coding assistants/agents; 26.2% use agent/automated workflows; 73% of assistant/agent users use them daily | https://survey.stackoverflow.co/2026/ai/data | Frequent need to manage development tools; self-selected survey and work context, NOT mobile purchase intent |
| 54.2% of respondents to AI mistakes question cited hard-to-review generated code (n=13,648); source is general AI code review, **not phone usability** | https://survey.stackoverflow.co/2026/technology/data | Review and validation matter to developers; do not turn into phone-friction prevalence |
| Codex reported >4M weekly users when shipping mobile Codex May 2026 | https://openai.com/index/work-with-codex-from-anywhere/ | Vendor-reported Codex users overall, NOT number on phones |
| Codex, Copilot, Claude officially offer remote/mobile management | https://openai.com/index/work-with-codex-from-anywhere/ ; https://github.blog/news-insights/product-news/take-your-local-github-sessions-anywhere/ ; https://support.claude.com/en/articles/14554000-claude-code-power-user-tips | Use case is real but standardizing into existing vendor apps |
| Kode Dot programmable handheld: 16,193 Kickstarter backers, US$3.37m pledged | https://www.kickstarter.com/projects/kode/kode-dot-the-all-in-one-pocket-size-maker-device | Strong paid intent for general maker device, not AI agent cockpit |
| Mecha Comet modular Linux handheld: 3,346 Kickstarter backers, US$1.20m pledged | https://www.kickstarter.com/projects/mecha-systems/mecha-comet-modular-linux-handheld-computer | Strong niche buying; company pushed shipping to January 2027 after hardware revisions: https://www.hackster.io/news/mecha-systems-delays-the-comet-handheld-again-opens-new-pre-orders-with-a-january-2027-target-574a3684cccd |
| PocketMage: 1,205 Crowd Supply backers, US$463,365 pledged | https://www.crowdsupply.com/talisman-design/pocketmage | Paid adjacent niche for special input/display and tactile keyboard, NOT glass-only |
| Some mobile CLI developers explicitly report painful phone typing and lost prompts | https://github.com/anthropics/claude-code/issues/25115 ; https://github.com/anthropics/claude-code/issues/85187 | Direct anecdotes of friction; not representative sample |
| Marketed mobile paid/free alternatives: Termius Pro US$10/mo annually; Blink paid; Moshpit US$6.99; Happy free; Moshi mobile | https://www.termius.com/pricing ; https://apps.apple.com/us/app/blink-shell-build-code/id1594898306 ; https://moshpit.cluas.eu.org/ ; https://happy.engineering/mobile-app/ ; https://getmoshi.app/ | Functional competition and advertised prices, not verified revenue or conversion |
| Closest announced foldable: Playard One 5.5in Linux clamshell + optional second-display module, waitlist with no verified shipments | https://playard.dev/ | Foldable dual-screen form NOT unique and exact buyer demand not yet evidenced |

**Do not combine Kickstarter backers into TAM.** Kode/Comet/PocketMage segments, price points, geographies, marketing, delivery status and product functions differ. GitHub account totals are also not qualified phone/cyberdeck buyers.

## Three technical versions, not two equally easy builds

### 1. Phone edition: existing phone app (RECOMMENDED FIRST)

Use the customer's existing Android/iOS hardware and cellular service. Add secure authenticated remote workspaces, agent task inbox, diff/test review, text/voice commands, explicit approval, notifications, offline draft queue and reconnection. Backend sits with the user's opt-in connected workstation or managed server; default to established security primitives rather than public SSH access. This can be piloted without developing a new baseband, camera, radio, antenna, cellular stack, charger or phone manufacturing supply chain.

**Business obstacle:** Codex mobile, Claude Remote Control, GitHub Mobile, Moshi, Moshpit, Happy and others already solve much of it, including multi-agent dashboards, diffs and reconnect. Differentiation must be demonstrated through provider-independent sessions, trustworthy reviews and improved ergonomics. Free and ~US$7 one-time alternatives limit easy software monetization.

### 2. Low-cost dual ESP32-S3 cyberdeck (VALID RESEARCH PROTOTYPE)

[Existing HS PR #292](https://github.com/Spectating101/hardware-splicer/pull/292): two Waveshare ESP32-S3-Touch-LCD-4.3 dev boards, each **4.3-inch 800×480, 106.1×67.8mm**, 16MB flash/8MB PSRAM, onboard RS485. Two real SCAD/STLs with zero nonmanifold edges, six empty CGAL shell-intersection samples. Estimated **NT$2,965 bare BOM**, but ICShop NT$1,250 board marked **sold out**, and no final power, enclosure Z, hinges, battery, thermal, keyboard behavior, physical validation or SSH host-key authentication.

Manufacturer: https://docs.waveshare.com/ESP32-S3-Touch-LCD-4.3 ; retailer: https://www.icshop.com.tw/en/products/368031700131 .

**Hard limitation:** ESP32 boards cannot natively provide general-purpose Linux, Chromium web IDE or rendered browser preview. Both 4.3in panels have only ~94mm active landscape width each; two glass panels do not combine into one large diff screen. Good for **SSH text and button/status console**. Bad default for comprehensive app editing and review.

**Physical constraints:** RS485 A/B is differential; verify shared reference, A/B wiring, termination, hinge cable fatigue; power both through correct USB inputs first. Manufacturer rates ~5V × 450mA each, nominal combined 4.5W, not runtime proof. No claim that both chargers can safely share/paralleled batteries. Current case **120×85×29.6mm nominal shell envelope**, no real measured board stack/mounting details.

### 3. Full Linux/Android developer cyberdeck (MORE CAPABLE, NOT YET ENGINEERED)

Use an actual Linux main controller or a reused Android smartphone assembly to drive a **larger higher-resolution upper screen**, plus lower touch/macro input over safe MCU interface. Browser IDE/preview, real Git diff, modern authentication and app ecosystem are easier here than with ESP32. The optional lower MCU can preserve input separation.

Radxa ZERO 3W is a plausible *Linux controller* (65×30mm, RK3566 1–8GB, Wi-Fi6, micro-HDMI, 5V/2A reference). **Important correction**: Radxa documents MIPI **CSI CAMERA**, not a ready-to-use DSI LCD output. Its main display uses HDMI; the existing Waveshare RGB panel is **not a drop-in Radxa monitor**. Need a supported HDMI touch panel/interface and mechanical/thermal/power engineering. https://docs.radxa.com/en/zero/zero3 ; https://docs.radxa.com/en/zero/zero3/hardware-design/hardware-interface .

**Actual own-brand cellular smartphone hardware is a separate, high-risk ODM/RF certification project**; not shown feasible by HS. Even PINE64 says its Linux phone is early adopter software: https://pine64.org/documentation/PinePhone/Introduction/ . Don't add cellular calling to the first product to bolster a "phone" label; use existing phone tethering or Wi-Fi.

## Existing HS proof and precise status

Research readback (Nov 6): [design_evidence.json](../evidence/native_mecha/design_evidence.json) reports both CAD meshes zero nonmanifold edges, and six tested shell poses without intersection. [hs_release_assessment.json](../evidence/native_mecha/hs_release_assessment.json) requested operational authorization but only achieved design_ready, **six explicit blockers**: RS485 electrical interface, USB power, SSH identity interface, power safety, SSH-security verification, release state. [budget.json](../evidence/native_mecha/budget.json) says no supplier quote; screen asking-price subtotal NT$2,500. [Earlier real engineering trial](https://github.com/Spectating101/hardware-splicer/blob/experiment/hs-cyberdeck-physics-20261021/projects/cyberdeck-real-trial-20261020/README.md) revealed source-semantic engineering and execution gaps.

Conclusion: HS presently demonstrates **design-stage artifact generation, mechanical sampling and evidence-aware governance**. It does not autonomously wire, flash, authenticate, physically fit or manufacture either product.

## Economic boundaries and Taiwan/Indonesia obligations

The existing [scenario CSV](unit_price_sensitivity.csv) uses **NT$2,965 estimated parts, NT$4,775 hypothetical fully variable cost, 13% payment/marketplace fee, NO batteries/shipping surprises/certification/R&D**:
- NT$5,990 retail -> ~NT$436 contribution.
- NT$6,990 -> ~NT$1,306 contribution.
- NT$7,990 -> ~NT$2,176 contribution.

These figures are **for the ESP32 dual-touch case only**, not an unknown Linux/Android full dev cyberdeck or a cellular phone. Any Linux version needs a new sourced and delivered BOM, tooling, warranty and lifetime estimate. Buying retail development boards for every unit has poor scale economics; true manufacturer savings require real component quotations and validated production yield.

For cross-border commercial hardware: Indonesia telecommunications device certification Permenkominfo 3/2024 https://jdih.komdigi.go.id/produk_hukum/view/id/892/t/peraturan%2Bmenteri%2Bkomunikasi%2Bdan%2Binformatika%2Bnomor%2B3%2Btahun%2B2024 . Taiwan NCC radio-frequency equipment import/marketing authorization https://web.customs.gov.tw/en/singlehtml/1865?cntId=cus16_180022_1865 . Personal-use exemptions **do not automatically cover sale/import batches**. Exact certification, battery and customs cost are **not yet quoted**.

## Demand / product go-no-go test

1. **Benchmark actual best available phone competitor**: Codex mobile, Claude Remote Control, Happy/Moshi, phone+portable keyboard. Have 20 real operators attempt (a) task dispatch, (b) find deliberate bug in ~100-line AI diff, (c) approve or reject after reviewing context, (d) recover from network loss, (e) swap 3 agents. Track completion, error, time, session loss and satisfaction.
2. **Prototype phone client** only if a well-defined existing competitor gap survives. Use existing agent session protocols and code under lawful license; no fake chat transcript/demo.
3. **Physical input/display A/B**: with the same operator tasks, compare phone, phone + keyboard, 4.3in ESP32 mock, and genuinely larger-screen Linux hybrid. If the cyberdeck can't materially improve review accuracy and workflow over phone, its hardware premium fails.
4. **WTP survey** across 30-40 qualified people, recruited across remote agent operators, maker/collector and less-experienced builders (plus TW and ID separately); show real build/functional videos, firm variants, clear shipped-product readiness, and real quoted price. Ask for exact buy/no-buy and next-best alternative. Likes/intent don't equal purchases.
5. **Proposed gate**: ≥30% shorter median task time with **no worse defect-review accuracy**, reliable resume, and ≥10 verified price-specific conditional purchase commitments **after working demos**, plus delivered margin after all compliance/testing/warranty cost. This is a pilot rule, not statistical proof. No nonrefundable orders or batch manufacturing before functionality/regulatory readiness.

**Investment decision:** GO for software-first and one physical feasibility prototype; NO-GO on own-brand cellular phone manufacturing or dual-touch inventory orders today. Demand for *remote AI work* is substantiated; *paying preference for our specialized form factor* is still a hypothesis. Commercial outcome depends on measured superiority to existing excellent phone apps.
