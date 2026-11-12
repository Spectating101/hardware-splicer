# Hardware Splicer — repair & electrical-services market: operator playbook
**Dated 2026-10-27 | Taiwan-first, Taoyuan/Pingzhen/Zhongli | research-and-validation only**

## Decision memo
**Primary wedge:** a documented **repair / replace / exchange / source / defer / retire** decision packet for obsolete *low-voltage* electronics and business equipment. First sell or partner as decision-support, **not** as an unqualified autonomous repair technician. Potential entry customers: existing repair shops, small machine integrators, POS/label-printer resellers, and factory maintenance/procurement coordinators.

**Secondary wedge:** exact-variant obsolete spare-part sourcing and partner hand-off. **Do not stock inventory** for the first experiment.

**Do not build:** a generic ticketing CRM, a photodiagnostic chatbot, unlicensed electrical installation, a walk-in phone store, a high-voltage industrial bench, or an open-loop autonomously operated physical repair service.

This is a market desk study and proposed validation protocol, **not** evidence of any customer demand, sale, repair yield, licensed activity, or validated unit profit.

## 1. Where money actually changes hands
| Lane | Actual customer | What they buy | Revenue form | Main economics / limits | HS role |
| --- | --- | --- | --- | --- | --- |
| Phone/tablet walk-in | End consumer | fast part replacement | fee + parts markup | density, location, OEM parts, privacy, churn | weak entry |
| PC/laptop small office | Individual / micro-SME | diagnosis and working workstation | fee, upgrade, service agreement | time, remote support, data protection | assisted triage only |
| Barcode/label/POS | retail shop / logistics / POS integrator | restore checkout/label uptime | paid diagnosis, repair, spare/exchange | new-unit replacement ceiling, exact connectivity | strong early data source |
| Industrial HMI/PLC/servo | factory + system integrator | production continuity | repair fee, exchange, urgency charge, parts | labor, test jigs, plant risk, specialist trust | choose safe qualified route; partner executes |
| Obsolete component search | maintainer / buyer / specialist trader | correct spare and lead-time | sourcing fee / purchase-resale spread / managed inventory | authenticity, SKU revision, stock, delivery | strongest information wedge |
| Refurbished asset trading | business buyer / hobbyist | working tested used device | resale margin | donor selection, yield, returns, storage, working capital | condition and cost screen |
| Repair coordination / brokerage | business owner / service desk | correct technician, vendor, quote | project fee or transparent referral (legal review) | customer trust, partner availability, conflicts, liability | compare offers, consent and traceability |
| On-site low-voltage field service | SME / system integrator | onsite fault isolation | callout + time + parts | travel, insurance, qualified personnel | supporting report, not solo field work |
| Preventive O&M / uptime | factory | recurring inspections and availability | retainer/contract | coverage 24/7, equipment + response obligations | future value, not initial promise |
| Electrical installation | property owner / contractor | installation, panel/wiring, compliance | project contracting | Taiwan `電器承裝業` registration/qualified technical workforce | outside initial scope |
| Test & refurbishment outsourcing | OEM / distributor | RMA, refurbished stock, warranty fulfillment | per-unit contract | throughput, QA, traceability, reverse logistics | source-bound triage and repair-routing |
| Lab/calibration and test | laboratory / engineering firm | traceable measurement and calibration | test/calibration fee | accredited standards, equipment, uncertainty, expertise | future only, no implied accreditation |

The economically decisive question is frequently **restore an asset's function at an acceptable risk/lead time**, not 'can the board be soldered?'. Repair, exchange, used spare, OEM order, upgrade and retirement compete for the same customer decision.

## 2. Public competitor observations and lessons
* **DAFENG Instrument, Zhongli:** published minimum **NT$3,000** basic successful repair, formula choosing the lowest of approximately one-third new value, half used value or peer repair price. Free initial diagnosis and no-fee unsuccessful repair; three-month warranty. Their process states hardware repair **excludes onsite installation, parameter setup and testing** and that detailed repair reports are withheld for trade-secret reasons. Do **not** interpret this as the typical Taiwan price, typical outcome rate, or customer preference. Source: https://yalechen.myds.me/repair.html
* **LIZYU Technology (立裕), Pingzhen:** publicly advertises model-specific industrial-drive repairs and replacement/sales categories; commercial and documentation presence. Source: https://www.lizyu.com.tw/ — incumbent; not necessarily a partner.
* **Cheng Feng Technology (丞鋒), Pingzhen:** servo drive/motor, PLC and VFD specialist with location/contact details; another established local supplier/repairer. Source: https://www.cft-server.com/
* **Radwell:** a full-stack industrial repair/parts/exchange/stock/remote-support operator. Site describes 2-year warranty and 20m+ products; these are **company-reported** scale claims. Source: https://www.radwell.com/
* **EU Automation:** expressly sells a *service exchange* path: send defective equipment back while buying a working replacement. Source: https://www.euautomation.com/sg-zh/support/products-and-services?faq=what-is-the-service-exchange-program
* **iFixit FixBot Pro:** enterprise AI troubleshooting using photos, parts search and existing repair guides. **Directly undermines the claim that 'AI photo diagnosis' is unique.** Source: https://www.ifixit.com/Info/FixBot_Pro
* **RepairDesk / RepairShopr:** quote/ticket/POS/customer/inventory software. RepairDesk's stated starting Essentials price USD99/store/month, or USD79 billed annually; RepairShopr advertises USD69.99/month starter. Pricing is vendor-listed as checked, not a Taiwan willingness-to-pay survey. Sources: https://www.repairdesk.co/pricing/ ; https://www.repairshopr.com/pricing
* **Odoo Repairs / ERPNext:** general-purpose, existing repair-order and asset-repair workflows. Do **not** recreate generic serial number, parts, invoice and return management. Sources: https://www.odoo.com/documentation/master/applications/inventory_and_mrp/repairs/repair_orders.html ; https://docs.frappe.io/erpnext/asset-repair
* **MaintainX / Limble:** industrial work orders, asset history, field procedures and inventory; enterprise incumbents for maintenance workflows. Sources: https://www.getmaintainx.com/pricing ; https://limble.com/products/cmms

**Defensible HS hypothesis, yet to be proven:** on a previously unseen device and a dated set of actual offers, HS makes **better route and sourcing decisions** than (i) an expert's existing process, (ii) generic model + search, and (iii) repair software. The measurable advantage must be cost, decision latency, correct variant match, or avoided rework **after competent human review**. Richer reports alone do not imply willingness to pay.

## 3. Market-size integrity
Published global 'electronic equipment repair' estimates use different boundaries. For example, a 2026 report projects **US$138.38bn for 2026** while another estimates **US$158.7bn for 2026**. These cannot be treated as comparable measured Taiwanese industrial-service demand, nor converted into a bottom-up obtainable market. Sources: https://www.thebusinessresearchcompany.com/report/electronic-equipment-repair-service-global-market-report ; https://www.persistencemarketresearch.com/market-research/electronic-equipment-repair-service-market.asp
**Decision:** no TAM headline or top-down revenue forecast in launch materials. Build SOM from counted accessible organizations, conversations, actual qualified cases, paid conversion, case frequency, labor hours, refund/warranty burden, and permission to operate.

## 4. Initial commercial offers: test them, do not assume prices
### A. HS 'Recovery Options Packet' (preferred)
**Deliverable:** identity/board revision, symptoms and evidence provenance, physical-risk exclusion, independent checks needed, repair vs replacement vs exchange vs spare vs retirement paths, confirmed supplier quote status, total landed costs, latency, warranty and confidence; contradictory or missing fields shown prominently. **No unsupported 'verified repair' claims.**

**Potential charging mode:** flat-case **diagnostic decision report** to a business or subscription volume deal *after* interviews. Do not invent an accepted price. For first validation, supply a benchmark report to a qualified reviewer without paid operations.

**Failure mode:** partner says they can already make the decision in minutes or the report contains generic information.

### B. Obsolete-Part Sourcing Diligence
**Deliverable:** exact manufacturer SKU, suffix/revision/configuration, official lifecycle, compatible alternative constraints, evidence of quoted stock rather than marketplace badges, warranty, tax/freight/lead time, two independent suppliers when possible, exchange and repair comparison.

**Charging mode:** agreed fixed diligence fee or contracted service; a commission model raises conflict-of-interest and permit/commercial issues and must be disclosed. No guarantee that a nominal 'compatible' part is safe for a production installation.

**Failure mode:** quote quality cannot be verified, or incumbents already match the requirement with equal accuracy and less time.

### C. Partner routing (later)
Commission or project-management margin only when licensed/permitted and the responsible qualified physical service provider, warranty holder, consent/data custody and dispute procedure are unambiguous. Referral-only economics can be thin after non-converting leads and customer support.

### D. In-house used equipment (only after evidence)
Use small low-voltage, fully-owned exact-model devices. Do not buy institutional e-waste lots or repair high-voltage equipment without the required qualifications and procedures. Prefer using owned equipment for demonstrated internal productivity **only if it beats existing Optiplex/commodity alternatives**.

## 5. Unit economics: explicit *hypothetical* sensitivity screens
All values are **illustrative in NT$; not market quotes or earnings forecasts**. Labor is an economic cost, not a statement about Taiwan statutory wage.

**Decision packet:** assumed paid ticket NT$1,200; 0.8h analyst x NT$500 = 400, independent technical QA 200, tools/data 120, admin/payment 100. Paid case contribution = **NT$380**. If only 70% of qualified prepared cases pay and each unsuccessful lead consumes NT$150, expected contribution/intake = 0.7(380) - 0.3(150) = **NT$221** *before fixed overhead and acquisition*. At 40% conversion, contribution = 0.4(380) - 0.6(150) = **NT$62**. A recurring B2B report must justify more than writing time.

**Sourcing service:** assumed paid sourcing fee NT$3,000; successful work 1.5h x NT$500 = 750, supplier verification NT$600, compliance/QA NT$250, admin NT$100 => **NT$1,300 collected-success contribution**. If only 25% pay and all other investigated leads cost NT$350, expectation = 0.25(1,300)-0.75(350) = **NT$62.50 per investigated lead**. At 15% payable conversions it becomes **-NT$102.50**, before overhead. A high headline sourcing fee is no substitute for lead qualification.

**Repair-resale:** assumed NT$2,500 donor + NT$500 inspection; working sale NT$7,000 at assumed 60% yield; if repaired, another NT$3,100 parts/labor/testing/freight/warranty; if failed, NT$400 salvage receipts minus NT$200 disposition costs. Expected collected proceeds = 0.6(7,000)+0.4(400) = **NT$4,360**. Expected cost = 2,500+500+0.6(3,100)+0.4(200) = **NT$4,940**. Result **-NT$580** per donor before marketing, taxes and capital. Profitability cannot be inferred from cheap listings.

**Software productivity:** if human-reviewed HS output saves a measured 30 min per case at an assumed fully burdened NT$500/hour, it creates **NT$250 theoretical labor capacity** per case. For 20 cases/month this is NT$5,000 theoretical capacity, **not** automatically cash savings; it must reduce overtime, increase successfully invoiced capacity, or avoid genuine spend, net of review/API errors. Measure with paired blinded cases.

## 6. Which customer to investigate first
**1. Repair shops / industrial service integrators:** existing case data, known failure rates, practical reviewer. Ask whether an external packet gives time savings, better quote, avoided incompatible part, or credible customer approval. They may be *competitors* as well as partners; respect confidentiality.

**2. POS/label/scanning service distributors:** specific low-voltage SKUs, real replacement ceilings, manageable physical test path, outage costs. Ask for ordinary repair cases and whether exchange is more useful.

**3. Small factory maintenance/procurement:** strongest willingness-to-pay hypothesis for obsolete parts, but hardest access and safety verification. Initial service should be non-invasive commercial triage and sourcing assistance, not plant control, live testing, or downtime guarantees.

**Reject as beachhead:** consumer smartphone walk-in (local acquisition and Apple parts infrastructure), regulated electronics electrical installations (licensed trade), and turnkey semiconductor line repair (acceptance/liability far beyond current capability).

## 7. No-purchase, evidence-first experiment: 12 held-out cases
**Sampling, before seeing outcomes:** 4 POS/scanners/printers, 4 low-voltage industrial interface/IPC units, 4 obsolete-part acquisition decisions. Obtain legitimately accessible, anonymized **previously resolved** examples with at least 3 genuinely unrepairable/returned/no-deal cases. Keep prior outcome and the original decision hidden from HS until scoring. Obtain consent to use private data; redact personal or proprietary fields.

**Baselines:** (A) human technician's original decision and time, (B) generic model + search under the same source access and time, (C) HS with existing PR #214 routing. Freeze prompts, versions, relevant date of source prices, case data and reviewer scoring before unblinding. Do not let the new model access the original outcome.

**For each case capture:** exact model/suffix, symptoms, known electrical safety status, evidence source; monetary repair/replacement/used/exchange prices (or UNKNOWN), failure labor and freight, human route, HS route, qualified technician judgment, unsafe statements, source validity, time-to-decision, actual historical outcome, and measured avoided cost if possible. Mark historical market snapshot as historical.

**Gates:** zero unflagged hazardous physical action recommendations; zero invented verified prices/repairs; **>=95% exact provenance** on facts used for quoted economic decisions; 10/12 routes judged acceptable by qualified independent reviewer; and **>=20% reduction in verified triage time or >=NT$300 actual saved/avoided cost per applicable paid case**, with no higher safety/warranty risk. These are predeclared experiment thresholds, not observed performance. If sample lacks enough cost data, report inconclusive rather than declaring success.

**Commercial qualification:** at least 5 stakeholder interviews across two segments; at least 2 explicitly willing to run a second case; at least 1 permitted partner prepared to discuss a paid written scope (not a guaranteed buyer). No customer validation achieved yet. Only contact real counterparties with explicit approved outreach and appropriate work/commercial authorization.

**Stop criteria:** exact source links/variants fail; safety risks become uncontrolled; technicians reject >2/12 results; no demonstrable cost/time gain; qualified buyers want only free reports; integration overhead eclipses benefits. In that case maintain HS as internal intelligence, don't hire or buy a bench.

## 8. Interview prompts (use without leading the respondent)
1. Walk through the last three cases where you repaired, replaced, exchanged or abandoned an asset; what were the actual invoice and delay?
2. What went wrong on a recent repair quote or part substitution, and how much time or money did it cost?
3. What exact identifiers/photographs/manufacturer details prevent you from quoting without new inspection?
4. How frequently do you encounter wrong revision, unavailable parts or repeat warranty work?
5. Which person authorizes repair vs replacement, and what evidence do they demand?
6. Which existing software, wholesaler, technician or supplier already handles these steps?
7. If a second opinion saved 20 minutes or prevented a wrong part, who would pay for it, and through what approval channel?
8. What would make you reject an automated recommendation immediately?

Log objections, not just interest. Do not report positive interview sentiment as a sale.

## 9. Business, safety, and personal authorization gates
Taiwan authorities distinguish ordinary commercial registration and **special regulated electrical-contractor** registration. The latter has its own legal and technical requirements; do not conflate `JA02010` consumer device repair with `E601010` electrical contracting. Sources: https://www.gov.tw/News_Content_2_828377 ; https://laws.gov.taipei/Law/SOPContent/SOPContent?id=P04000039
For foreign/overseas Chinese founders, government guidance includes investment/registration approval pathways; neither company registration nor a student work permit can be assumed to confer permission to work as a business operator. Source: https://investtaiwan.nat.gov.tw/showPageengInvestmentStatus?lang=eng&search=InvestmentStatus ; https://english.moe.gov.tw/cp-96-25406-b2053-1.html
EU Directive 2024/1799 applies through member-state implementation from July 31, 2026, but is **not Taiwan law**. Source: https://commission.europa.eu/law/law-topic/consumer-protection-law/directive-repair-goods_en

Before compensated services: verify role/immigration, business classification, taxes, data custody/consent, insurance, warranty allocation, export controls/parts authenticity and product-specific safety obligations. Any mains work, energized VFDs, battery-pack remediation, industrial safety circuits, medical devices, semiconductor machine controls or plant commissioning must remain with properly qualified and insured humans.

## 10. Build integration against #214, not another parallel shop product
Existing PR #214 (https://github.com/Spectating101/hardware-splicer/pull/214) offers multi-route economic routing, quote lineage, historical evidence screening, seller quote gates, 30 concepts, outcome receipts and replay artifacts. Its **implementation tests are not commercial proof**.

Recommended narrowly scoped next backlog after a *passing blinded partner replay*:
1. Portable **Recovery Options Packet** exporter with explicit unknown/unsafe sections and total cost by state.
2. Non-deceptive asset identity, exact variant and dated-source cross-check at handoff.
3. Single-page human decision sign-off and partner review outcomes; no physical-autonomy authority.
4. Optional adapter into Odoo/ERPNext/RepairDesk/MaintainX; only if a partner actually uses one.
5. Capture **payment-settled receipt, return/warranty exposure, technician minutes and real supplier invoice** for updating expected unit economics.

Do not clone CRM, accept claims of satisfied customers, promote marketplace list prices to settled sales, or treat a PR CI badge as a physical repair result.

## 11. Confidence and next integration decision
**Observed:** actual published Taiwan repair terms, existing industrial trading/repair competitors, global exchange practices, incumbent repair AI and maintenance/repair software, official business/visa/regulatory signposts.

**Inferred:** HS might add value by reducing the time and risk of choose-repair-vs-source decisions.

**Unknown and blocking monetization:** paid buyer, access to anonymized cases, repair technician/partner reviewer, validated improvement over ordinary model+search, settled supplier pricing, compliant operating entity, any proven repair outcome.

**Immediate recommendation:** freeze new feature expansion and execute **the 12-case blinded commercial/technical replay** and five properly authorized buyer conversations. If qualified case material isn't available yet, start from published resolved non-sensitive cases and clearly label the results as weaker research benchmarks. This is the shortest path to evidence that a repair-market customer would actually purchase.
