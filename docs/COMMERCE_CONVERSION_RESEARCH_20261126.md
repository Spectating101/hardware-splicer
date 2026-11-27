# From Hardware-Splicer to revenue: conversion research (2026-11-26)

Question from the owner: how close is HS to an actual commerce foundation, and can the products it designs (drone, CCTV
rover, FieldDeck, robot arm, boards) be the proof? Evidence: web research of 2026-11-26 (sources at the end), the owner's
own Taiwan freelance scrape (`Molina-Optiplex/data/tw_freelance.db`, 461,575 posts, 2026-05-16 to 2026-11-26), and HS's
state on branch `agent/propulsion-energy-sizing`. Figures from vendor or marketplace pages are marked as such.

## Bottom line

1. **Selling HS-designed consumer products directly is the slowest and most expensive route.** Each product with a radio
   (drone, Wi-Fi rover) needs Taiwan NCC type approval, about NT$70,000-170,000 per product by a test lab's estimate, and
   Indonesia's DJID (formerly SDPPI) certification needs a local company and an in-country lab. Every category already has
   cheap, finished competitors: an assembled SO-ARM101 arm is US$299 from Seeed, budget 3-inch FPV drones are
   US$110-150, robot home cameras start around US$20-135, and Ring's patrol rover is US$999.
2. **Selling engineering work done with HS is the fastest route, and the demand is measured.** On PRO360 alone, Taiwan
   customers file about 19 PCB-layout, 14 mechanism-design, 14 product-design, 53 3D-modelling and 49 3D-printing requests
   a month. Tasker shows 120 hardware posts with budgets: the median is NT$20,000-30,000, and recent ones include a USB-C
   charging circuit (NT$22,000), an MP3 player's circuit, PCB and firmware (NT$15,000), a voice-player prototype
   (NT$80,000), drone ground control (NT$50,000) and a Raspberry Pi stepper controller (NT$50,000). This is exactly what
   HS now produces: schematics, routed boards, fab files, parts prices, CAD.
3. **The products are still the right proof, but as portfolio pieces, not as the business.** A built, working drone,
   rover and arm, each with its HS design package, is what makes a stranger trust you with NT$20,000-80,000 of design
   work. Build each one once, document it, and do not take on certification or inventory until a buyer asks.
4. **The block to the first sale is not engineering.** Your PRO360 seller account has shown "須完成身分認證才能接案"
   (identity verification needed before taking jobs) since May 2026, so six months of scraping has produced zero quotes.
   Your legal right to do freelance work before graduating also needs confirming (below).

## The three routes compared

| Route | What is sold | Evidence of demand | Cost and risk to start | Verdict |
|---|---|---|---|---|
| A. Products (drone, rover, arm, boards) | Finished units or kits | Large consumer markets, but served by funded companies at lower prices | Radio certification per product (NT$70k-170k, vendor estimate), BSMI for power supplies, CAA seller registration and labelling for drones over 250 g, inventory, returns | Not first. Revisit for one niche product after services prove demand |
| B. Design and prototyping services, done with HS | Schematic + PCB + fab package, 3D CAD and prints, small prototypes | Measured locally: about 150 hardware-category requests a month on PRO360, 120 budgeted hardware posts on Tasker | PRO360 charges NT$173-650 per quote sent (your May audit); time per job | **Start here.** Highest evidence, lowest cost, uses HS directly |
| C. HS as software or a compliance tool | Subscriptions, or a "non-red" component-origin check for Taiwan drone makers | Flux charges about US$20-142 a month (third-party trackers) and raised US$37M; Taiwan funds a NT$44.2B drone plan and requires non-red government drones, while editorials note upstream component origin is hard to check | Crowded software market; a B2B compliance product needs customer interviews first | Later. The non-red idea fits HS's evidence model and is worth five customer conversations, not code |

## Product by product: market, legal load, and what HS still needs

| Product | Market reference | Legal load to sell in Taiwan | HS state today | What HS still needs to reach "sellable" |
|---|---|---|---|---|
| Robot arm (HS-ARM-A) | SO-ARM101 assembled US$299 (Seeed); third-party resellers US$430-530 | No radio: low (BSMI only if a power adapter ships with it) | Full design: CAD, URDF, checks, US$1,089.50 BOM; controller board HS-BUS-A routed and checked | A cost-down version on Feetech STS3215 servos to reach the SO-ARM101 class, then one physical print and test |
| Bus board (HS-BUS-A) | ROBOTIS U2D2 + hub US$51.10; cheap ready-made servo adapters exist | No radio: low | Routed, DRC clean, fab files, US$9.18 parts per board | One small fabricated batch and a test with real servos |
| FPV drone (HS-3G) | 3" BNF US$110-150 (budget) to US$330-590 (cinewhoop); GEPRC Cinelog30 class | Video transmitter and receiver: NCC; drones over 250 g: CAA registration and seller labelling; remote ID rules conflict across sources | Propulsion and energy sizing on par with GEPRC's 3" quads | Frame CAD, flight-controller choice and configuration, then a real flight test. Selling ready-to-fly units means radio certification |
| CCTV rover | Robot cameras US$20-230; Enabot EBO X US$1,025; Ring Rover Cam US$999 | Wi-Fi streaming: NCC unless the radio part is a separately certified device | Drive sizing (25D MP 47:1 pick); no chassis, camera or streaming stack | Chassis CAD, camera and streaming software, controller board, a driving test. Better aimed at inspection niches (crawlspace, pipe, warehouse) than home security |
| FieldDeck handheld | Loses to a used Panasonic Toughpad on price (HS casefile #291: 18% margin) | Depends on radios; Pi modules carry their own certification | Pi 4 design, 310 x 285 mm, 2.8 h | Compact CM5 redesign; portfolio piece only |

## The Taiwan demand data (your own scrape, May to November 2026)

PRO360 requests per category (customer requests; most hide the budget):

| Category | Requests | About per month | Median stated budget |
|---|---:|---:|---|
| 模型代工 (model and prototype fabrication) | 556 | 79 | not stated |
| 3D建模 (3D modelling) | 368 | 53 | NT$10,000 (157 with budgets) |
| 3D列印 (3D printing) | 342 | 49 | NT$10,000 (90 with budgets) |
| PCB Layout | 134 | 19 | not stated |
| PLC設計 (PLC design) | 132 | 19 | not stated |
| 機構設計 (mechanism design) | 101 | 14 | not stated |
| 產品設計 (product design) | 101 | 14 | not stated |
| 無人機課程 (drone courses) | 92 | 13 | not stated |

Tasker, hardware posts with budgets: 120. Keyword medians: PCB and circuits NT$20,000 (p75 NT$50,000), firmware and
embedded NT$30,000 (p75 NT$100,000), hardware prototypes NT$30,000 (p75 NT$83,200). Note that budgets are what clients
post, not closed prices, and PRO360 charges a fee to quote.

## What blocks the first sale (owner actions)

1. **Work status.** University guidance: international students need a work permit for any work, capped at 20 hours a
   week in term, with fines of NT$30,000-150,000 for working without one. None of the sources covered freelance or
   self-employed work. Ask YZU's international office whether platform freelancing counts and whether your permit covers
   it. Your notes say the graduate extension after January 2027 lets you work without a separate permit, which would make
   February 2027 the clean start.
2. **PRO360 identity verification** (ARC upload). Without it no quote can be sent.
3. **A small proof budget**, decided by you: one HS-BUS-A batch, one arm print, one drone or rover build. Each needs
   quotes first; nothing has been ordered.

## Plan

| When | Step | Cost | Gate |
|---|---|---|---|
| Now to January (thesis first) | Confirm work status with YZU; complete PRO360 verification; prepare a hardware profile pack from HS-ARM-A and HS-BUS-A renders, checks and fab files | NT$0 | You confirm you may quote |
| December to January | Build proof pieces, one at a time: fabricate HS-BUS-A (JLCPCB economic assembly is about US$8 setup per order plus parts; get a live quote), print the arm | Your call, quoted first | Each piece works on the bench |
| From February 2027 | Quote 10-20 well-fitting PRO360/Tasker hardware requests (PCB layout, 3D modelling, small prototypes) using HS for the engineering | NT$173-650 per PRO360 quote | First paid job |
| After 3 paid jobs | Decide between a niche product (with certification costs known) and the non-red component check, using what clients asked for | — | Evidence from real buyers |

HS work that serves this plan, in order: cost-down arm on STS3215 servos; CCTV rover intake (chassis, camera, streaming,
board); drone airframe and flight-controller package; then the compact FieldDeck. Each ends in a physical build, not only
a design.

## Sources

- Taiwan drone rules: [Taipei Times 2023](https://taipeitimes.com/News/taiwan/archives/2023/03/13/2003796018), [Taipei Times 2025](https://www.taipeitimes.com/News/taiwan/archives/2025/02/16/2003831966), [Focus Taiwan](https://focustaiwan.tw/society/201902090010), [drone-laws.com](https://drone-laws.com/drone-laws-in-taiwan), [Taipei Times 2026](https://www.taipeitimes.com/News/taiwan/archives/2026/09/07/2003863816)
- Taiwan NCC: [TÜV Rheinland](https://tuv.com/taiwan/en/ncc-certification.html), [EMC China Lab cost estimate](https://www.jjrlab.com/news/how-much-does-ncc-certification-cost.html), [Taipei Times 2017](https://www.taipeitimes.com/News/taiwan/archives/2017/05/18/2003670820)
- Taiwan BSMI: [Nemko](https://www.nemko.com/blog/taiwan-amends-requirements-for-it-and-power-supply-equipment), [TÜV SÜD](https://www.tuvsud.com/en/knowledge-hub/technical-updates/consumer-products-and-retail-essentials/taiwan-updated-safety-inspection-requirements-for-power-supply-and-it-products), [Trade.gov](https://www.trade.gov/knowledge-product/taiwan-standards-trade)
- Indonesia DJID/SDPPI: [TÜV SÜD](https://www.tuvsud.com/en-us/services/product-certification/indonesia-sdppi), [Nemko](https://www.nemko.com/blog/indonesia-renames-regulatory-body-and-makes-sweeping-changes-to-telecom-regulations?hs_amp=true), [Trade.gov](https://www.trade.gov/country-commercial-guides/indonesia-standards-trade); drones: [ICAO 2026 paper](https://www.icao.int/sites/default/files/APAC/Meetings/2026/2026%20DGCA61/Agenda%20Item03-Aviation%20Safety/61-DP-03-23_IDN_UAS-REGULATORY-SANDBOX.pdf), [The Star](https://www.thestar.com.my/aseanplus/aseanplus-news/2025/10/23/indonesia-targets-commercial-drone-operations-by-end-of-2026)
- Market prices: [Seeed SO-ARM101](https://www.seeedstudio.com/SO-ARM-101-Assembled-Kit-Pro-p-6691.html), [TechCrunch on SO-101](https://techcrunch.com/?p=2999850), [Pyrodrone 3" BNF](https://pyrodrone.com/collections/bnf-pnp-rtf/frame-size_3), [RaceDayQuads 3"](https://racedayquads.com/collections/3-bnfs-pnps-rtfs-bind-n-flys-plug-n-plays-ready-to-flys/manufacturer_happymodel), [Ring robots](https://pulse2.com/ring-launches-with-249-99-drone-cam-and-999-99-rover-cam-for-autonomous-security/), [SwitchBot review](https://www.pcworld.com/article/2924138/switchbot-k20-plus-pro-patrol-kit-review.html), [Enabot EBO X](https://www.staples.com/enabot-ebo-x-home-robot-black-ebo-x/product_24617639)
- Manufacturing: [JLCPCB assembly price](https://jlcpcb.com/help/article/pcb-assembly-price), [TechOverflow overview](https://techoverflow.net/2024/04/09/jlcpcb-pcba-assembly-price-overview/)
- Selling hardware: [3D Printing Industry on Tindie](https://3dprintingindustry.com/?p=27097), [Crowd Supply via TNW](https://thenextweb.com/news/crowd-supply-is-succeeding-where-kickstarter-and-indiegogo-are-failing-miserably), [Linux Magazine](https://www.linux-magazine.com/Online/Features/Crowd-Supply-Boosts-Open-Hardware), [Predictable Designs](https://predictabledesigns.com/sell-before-build/), [Cofactr](https://www.cofactr.com/blog/what-to-think-about-before-launching-a-hardware-startup)
- Design-service rates: [Fiverr 2026 guide](https://www.fiverr.com/resources/guides/costs/electronics-design-engineer), [Upwork PCB designers](https://www.upwork.com/hire/pcb-layout-freelancers/us/), [Upwork Indonesia](https://www.upwork.com/hire/pcb-designers/id/), [PRO360 PCB layout](https://www.pro360.com.tw/category/pcb_layout)
- AI design tools: [Flux pricing tracker](https://aiproductivity.ai/pricing/flux/), [PricingSaaS](https://pricingsaas.com/companies/flux), [SiliconANGLE on Flux funding](https://siliconangle.com/2026/02/27/flux-nabs-37m-automate-printed-circuit-board-development-ai/), [Quilter pricing guide](https://www.quilter.ai/blog/generative-pcb-design-tool-pricing-in-2026-a-guide-to-saas-credits-and-subscriptions)
- Taiwan drone supply chain: [The Star](https://www.thestar.com.my/aseanplus/aseanplus-news/2026/03/28/can-taiwan-fulfil-its-asia-pacific-drone-hub-goal-with-a-non-red-supply-chain-push), [Focus Taiwan](https://focustaiwan.tw/sci-tech/202605190019), [Taipei Times editorial](https://www.taipeitimes.com/News/editorials/archives/2026/08/08/2003862125), [East Asia Forum](https://eastasiaforum.org/2026/10/21/taiwans-drone-ambitions-outpace-its-capabilities/), [AmCham](https://topics.amcham.com.tw/2026/04/taiwans-drone-industry-take-off-but-can-it-scale/)
- Indonesia robotics education: [Asia Education Review](https://www.asiaeducationreview.com/others/news/indonesia-pushes-inclusive-robotics-education-nationwide-nwid-5468.html), [RCTI+](https://www.rctiplus.com/news/detail/sindonews/5432992/kemendikdasmen-siapkan-lulusan-smk-hadapi-era-robotika--prospek-karier-menjanjikan)
- Student work rules: [NTU OIA](https://oia.ntu.edu.tw/en/internationalstudents/degreestudent/survivalguide/workpermit), [NCCU](https://oic.nccu.edu.tw/Post/430), [TMU](https://oge.tmu.edu.tw/student-work-permit/)
