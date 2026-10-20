# HS engineering opportunity portfolio — three distinct decision tracks

**As of 2026-10-20.** This portfolio is a project-selection aid grounded in public examples, *not* evidence that any HS-generated design or repaired hardware is finished. Use the canonical [HS mission](../../docs/HARDWARE_SPLICER_MISSION_FREEZE.md). The objective is to build and repair actual devices, not a ranking engine.

## Track 1 — engineering integration proof

**Primary trial: an affordable functional quadcopter.** Keep the [drone build project](../drone-build/) active. Use a documented PX4/X500 design as the control and compare against cheaper individual-part or open-source alternatives. HS must generate real component choices, engineering calculations, wiring/CAD/firmware outputs, and show independent checks. Merely reproducing assembly instructions does not demonstrate the intended splicing capability.

**Alternative first trial: a practical Linux cyberdeck.** This is potentially easier to complete physically and more immediately useful. Open designs: [dinodeck-2026](https://github.com/therebelrobot/dinodeck-2026) with a Pi Zero 2W, display, PiSugar power, keyboard and radios (author's estimate around US$200 excluding case/sourcing adjustments); [RPi-5 Pelican cyberdeck](https://github.com/cubzzy/cyberdeck) with an author-reported costly US$741.64 BOM; [PiMech Deck](https://github.com/brickbots/pimech_deck) with 3D-print/cut files and keyboard. Use these as real source material, not validation of a newly built device. Preference: **keep drone as cross-disciplinary challenge, cyberdeck as fallback for a quicker useful artifact**.

## Track 2 — rank by potential *economic arbitrage*, not personal utility

These are **risk-adjusted opportunity hypotheses**, not known realized margins. Highest-ranked means the best first avenue to verify purchase/repair/resale spread, factoring component reliability, market liquidity, capital at risk and time. Marketplace **asking prices are not completed-sale prices**. No expected-profit claim is permitted until purchase condition, parts cost, labor, failure probability, fees, returns and sale realization are recorded. Re-rank with actual Taiwan transaction evidence.

| Rank | Candidate | Why examine it | Key break-even or loss risk |
|---|---|---|---|
| 1 | Ex-corporate ThinkPad T480/T480s refurbishment and resale | Taiwan parts-machine listings NT$2,200–2,500 and some working/used T480s around NT$4,400; moderate technical serviceability; teach HS intake/diagnostics/SSD/battery/thermal/market comparisons | Many low-end working laptops are already cheap, so battery/charger/SSD + labor can erase the spread; BIOS lock/motherboard damage catastrophic |
| 2 | Used business mini-PC repair, upgrading, repackaging | Dell OptiPlex micro/mini listings around NT$1,790–4,294 depending on configuration; reusable for home labs and development; fallback utility if unsold | Exact SKU, memory/storage, PSU and CPU generation vary; limited buyer premium |
| 3 | Console repair: Switch Lite, PSP, retro handhelds | Switch Lite functional listings around NT$4,000–4,450, one defective-screen/battery listing NT$2,590; specialized repairs and donor sourcing possible | After replacement screen, battery, shipping and rework the gross margin can disappear; board faults may be uneconomic |
| 4 | Handheld PC / Steam Deck diagnosis, SSD/storage refurbishment | Higher-price devices could have useful repair value; existing HS case identifies OLED/2230 and recovery constraints | Weak current Taiwan buy/sell spread evidence, high diagnostic risk; avoid buying before quote data |
| 5 | Commercially packaged ESP32 measurement/control tools | Small BOM and repeatable engineering outputs once validated; repair fixtures or sensors may support service revenue | Commodity price competition, calibration, liability, packaging, support and sales channel costs |
| 6 | Custom cyberdeck/handheld for resale | Strong skill demonstration, differentiated enclosure/accessories | Parts and hand assembly typically expensive; niche uncertain demand; user value exceeds expected resale |
| 7 | Custom quadcopter or salvaged drone build for resale | Multidisciplinary engineering, potentially high ticket | Components, test time, flight safety, regulations, customer support and established competitor prices make initial resale economics speculative |

Evidence examples and source pages (listing snapshots, not transaction evidence): [T480 parts at NT$2,200](https://www.ruten.com.tw/item/22639704581445/), [T480/T480s market listings](https://www.ruten.com.tw/search/T480/), [Dell mini-PC marketplace](https://www.ruten.com.tw/search/%E6%88%B4%E7%88%BE/?cateid=001100010011), [Switch Lite used/defective listings](https://www.ruten.com.tw/find/?cateid=00220025&q=lite), [Switch Lite used listings](https://www.ruten.com.tw/search/%E4%BA%8C%E6%89%8Bswitch%2Blite/).

**Transaction gate:** For each candidate HS must build a case-level `acquisition + parts + consumables + shipping + marketplace fees + labor + expected loss/returns + warranty reserve` model; compare conservative net resale receipts to a seller's *actual* buying cost. Estimate probability of successful repair from measured faults, not arbitrary success rates. For a first purchase require demonstrated positive conservative margin and a bounded downside. There are no approved buys in this portfolio.

## Track 3 — rank by practical *utility/demand to us*, not resale profit

Utility means real recurring use, time saved, skills/infrastructure leveraged across HS/other projects, and plausible external need; no invented revenue. This ranking reflects current project priorities and should be revised if the intended users or needs change.

| Rank | Project | Direct use case | Practical reference |
|---|---|---|---|
| 1 | Portable electronics diagnostic / repair fixture bench | HS itself needs USB-C power/PD/current, multimeter/logic measurement, safe test harnesses, ESD and evidence collection to inspect actual donor boards | Existing KiCad and instrument integrations; use manufacturer test-equipment datasheets and safe low-voltage designs |
| 2 | Linux cyberdeck / portable HS engineering workstation | A portable terminal for field repair, CAD/reference docs, logging, device flashing, offline troubleshooting and remote Optiplex access; retains value if unsold | [dinodeck-2026](https://github.com/therebelrobot/dinodeck-2026), [PiMech Deck](https://github.com/brickbots/pimech_deck) |
| 3 | Refurbished business mini-PC / portable homelab node | More local compute for HS, automated hardware validation, Copilot/agent terminals, field data processing; reusable even if not resold | Refurbished OptiPlex/ThinkCentre tiny-class machines |
| 4 | Modular low-cost observation/camera trap | Edge AI for animal charity/stray-animal observation or site monitoring, a concrete application of HS computer-vision, mechanics and power | [Raspberry Pi biodiversity camera trap](https://github.com/Content-Catalyst-LLC/raspberry-pi-biodiversity-camera-trap-edge-ai); [WildLife_AI](https://github.com/Gavinduachintha/WildLife_AI) |
| 5 | Quadcopter with camera / survey payload | A strong system-level integration challenge; could support observation, mapping or monitoring if legally operated; not yet demonstrated as cheaper than a commercial drone | PX4/X500 control design, open drone sources |
| 6 | ESP32 portable air quality / environmental sensor | Useful for reproducible environmental observation; lower cost, repeatable and potentially deployable on campus / community projects | [OpenAirProject ESP32](https://github.com/openairproject/sensor-esp32); verify calibration rigor |
| 7 | Steam Deck/handheld repair or cyberhandheld | Useful if owned, serviceable or resale acquired at attractive price; interesting service skill | Existing HS Steam Deck repair case, documented repair manuals |

**Interpretation:** the diagnostic bench is ranked highest because it enables subsequent real HS build and repair projects. Cyberdeck is next because it is usable as a standalone artifact and assists field engineering. Neither ranking implies those will generate the most sales. The drone remains Track 1's first system-level proving ground even though it ranks lower for immediate utility and arbitrage.

## Selection rules

- Always keep **engineering integration proof**, **economic arbitrage**, and **practical utility** as separate dimensions; never merge them into one unexplained score.
- For profit work, prefer *repairable, testable, liquid* assets and obtain actual donor prices, failure codes, quotes and realizable resale values before buying.
- For utility work, prioritize devices we will actually use even if their resale margin is negative.
- For integration proof, the outcome must be a defensible design or an actual supervised repair/build artifact, not merely an AI explanation or a unit-test score.
- Keep safety, battery handling, electrical/thermal and legal constraints as non-negotiable gates; physical testing and sales claims require separate evidence.

**Next actions:** complete detailed target specification of the first quadcopter or cyberdeck, and pursue *one low-risk* ThinkPad refurbishment opportunity based on inspected donor specifications and actual repair cost data. These are separate workstreams; do not force the arbitrage winner to become the engineering integration test.
