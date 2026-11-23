# Buying or building a Taiwan electronics bench

Checked 19 November 2026. All prices are single-unit asks or explicitly named allowances. US dollars use the 18 November close of NT$32.947 per US$1. The sterling listing uses Bank of Taiwan's same-day spot selling rate of NT$43.62 per £1. International shipping, import charges, card spreads and local freight depend on the basket and destination. No checkout or purchase was made. [Central Bank](https://www.cbc.gov.tw/en/lp-700-2-1-40.html) · [Bank of Taiwan](https://rate.bot.com.tw/xrt/quote/2026-11-18/GBP)

## Cabinet logger bill of materials

| Item, one per logger | NT$ | US$ | Price basis |
|---|---:|---:|---|
| Raspberry Pi Pico H with headers | 200 | 6.07 | NT$190 before tax, rounded to NT$200 for budgeting. [PiePie](https://piepie.com.tw/product/raspberry-pi-pico-h/) |
| GY-BME280-3.3V, 100Y item 147315 | 210 | 6.37 | Single module, tax included. [100Y](https://www.100y.com.tw/product/147315) |
| PW-3 125 × 60 × 40 mm project box | 105 | 3.19 | Blank box, needs openings and mounting. [Jin Hua](https://jin-hua.com.tw/page/product/show.aspx?lang=TW&num=3569) |
| Micro-USB data cable, four leads, insulation and fasteners | 90 | 2.73 | Allowance, comprising NT$50 for cable and NT$40 for wiring and mounting. No individual vendor quote. |
| **Complete parts budget** | **605** | **18.36** | Assumes an existing continuously available USB host, hand tools and access to the tools to modify the case. |

A suitable recovered enclosure takes the cash budget to NT$500 / US$15.18. Reusing a verified USB data cable as well takes it to NT$450 / US$13.66. At NT$600 per hour, the case and cable together justify at most 15.5 extra minutes of retrieval, testing and adaptation. For a single standalone cabinet, the host or a battery/storage redesign would be an additional cost.

## Which purchase covers the job?

| Use in the lab | Direct purchase | NT$ | US$ | What the buyer gets |
|---|---|---:|---:|---|
| Read humidity and temperature at the shelf | Xiaomi Bluetooth Temperature and Humidity Monitor 3 Mini | 199 | 6.04 | Finished battery display with Bluetooth. Remote connectivity can add a gateway. [Xiaomi Taiwan](https://buy.mi.com/tw/accessories/3378) |
| Read locally and export temperature and humidity history | SwitchBot Meter Plus | 890 | 27.01 | Finished battery display and app export. An export through the app may suffice for occasional checks. [EZONE Taiwan](https://www.ezonelife.com.tw/products/swi0009-a002) · [SwitchBot](https://support.switch-bot.com/hc/en-us/articles/360060298693-Data-Synchronization-Saving-and-Deletion-for-SwitchBot-Meter) |
| Collect temperature, humidity and pressure directly on a computer | DogRatIan USB-PA, BME280 option | ≈960 | 29.13 | Closest functional match. £22 listing plus international delivery. Manufacturer documents all three readings over USB. Choose USB-PA from the listing's two variants. Taiwan landed quote and delivery time remain unknown. [Seller](https://www.ebay.co.uk/itm/157057483828) · [Documented commands](https://www.dogratian.com/index.php/sensor/usb-pa-bme280) |
| Log temperature and humidity away from a continuously connected PC | UNI-T UT330T | 1,200 | 36.42 | Finished USB temperature/humidity recorder for later retrieval. [100Y Taiwan](https://www.100y.com.tw/product/140634) |
| Log all three channels locally with a display and SD storage | Lutron MHB-382SD | 7,056 | 214.16 | Standalone instrument. The seller prices some accessories separately. Its extra functions and physical specifications make the price gap an unsuitable estimate of DIY savings. [LTC Taiwan](https://www.ltc.com.tw/products/mtmhb382sd) |

## How much engineering time can HS afford?

For the closest comparison, both the Pico and USB-PA need a host, a capture program and installation. The same collector is included in this project. The model below counts the **extra** time for the DIY option. It assumes NT$600 per active hour, two hours of one-time design and bench bring-up, and 15 extra minutes per unit for assembly and checkout. These are scenarios, not recorded build times. Calibration, rework, maintenance, computer purchases and resale overhead are outside these figures.

| Quantity | DIY per unit including allocated labor | Purchased USB-PA per unit, before delivery | Effect |
|---:|---:|---:|---|
| 1 | NT$1,955 / US$59.34 | ≈NT$960 / US$29.13 | A bought unit saves about NT$995 before freight. |
| 6 | NT$955 / US$28.99 | ≈NT$960 / US$29.13 | Within NT$5 each. A small cost change reverses the result. |
| 10 | NT$875 / US$26.56 | ≈NT$960 / US$29.13 | DIY saves about NT$85 per unit before freight. |
| Repeated unit after design cost is recovered | NT$755 / US$22.92 | ≈NT$960 / US$29.13 | About NT$205 per unit remains for additional effort and cost. |

With equal freight, the first device allows only 35.5 minutes of extra work in total, or **20.5 minutes of design and bring-up after assembly**. The batch cost is NT$1,200 + NT$755 × quantity. Against £22 per unit, break-even is six if the purchase price stays flat. The seller advertises £20.68 from four units, roughly NT$902 / US$27.38 each. **With that tier, break-even moves to nine**, and at ten the saving shrinks to about NT$27 each. At 30 minutes of extra assembly per unit, repeat DIY becomes NT$905 and even the volume-discounted purchase beats it before delivery. [Seller quantity tiers](https://www.ebay.co.uk/itm/157057483828)

Freight can move the crossover in either direction. An individual NT$210 sensor order incurs NT$120 shipping from 100Y. Six sensors together clear the NT$1,200 free-shipping threshold. Other local orders may still have fees, and the eBay listing's displayed international rate depends on destination. Compare the two delivered baskets for the actual quantity before releasing a build. These are internal cost differences, not gross margins or evidence of a selling price. [100Y shipping terms](https://www.100y.com.tw/product/147315)

## Other assets for the first bench

| Job | DIY or reuse, materials only | Buy ready to use | Decision |
|---|---|---|---|
| Cable continuity and pin order | Manual station NT$790 / US$23.98 including a multimeter, adapters and plate. NT$270 / US$8.19 incremental if the meter exists. | Pro’sKit MT-7051N NT$520 / US$15.78 for its supported RJ and BNC connectors. | Buy for standard cables. Design swappable adapters for a recurring proprietary cable. Automating the existing manual jig adds roughly NT$200 plus design time. At two hours of design, one minute saved per cable pays back after about 140 cables, before fixture maintenance. Exact mating connectors and real fixture performance still need verification. [Pro’sKit](https://shop.prokits.com.tw/instruments/moreinfo_18397.htm) · [Manual bench and modeled harnesses](../engineering-opportunity-portfolio/taiwan-lab-seeds.md) |
| Document incoming boards and salvaged components | Reclaimed phone, stand and lighting plus NT$0–300 / US$0–9.11 for a simple mount and background, conditional on donors. | USB microscope with stand NT$1,100 / US$33.39. | Reuse for whole-board photos and labeling. For fine markings, test field of view, focus and working distance on the smallest actual target. The two setups cover different scales. [Jin Hua](https://jin-hua.com.tw/page/product/show.aspx?lang=TW&num=31546) |
| Count identical small parts for kits | NT$468 / US$14.20 including NT$118 cell and HX711, NT$200 controller and NT$150 pan, leads and support allowance. Reference weights and tuning extra. | 500 g pocket scale with piece-count mode listed at NT$240 / US$7.28. | Buy for manual kitting. Build only if automatically recording weights against a kit ID saves enough packing time. Cell capacity alone cannot establish the smallest reliably countable part. [Components](https://www.sconline.com.tw/tw/product/index.php?kind3=244) · [Finished scale](https://lifeshopping.com.tw/product/caes0031) |
| Check USB cables under load | Proposed bench already purchases the NT$750 / US$22.76 J7-D2LCD. A reclaimed holder can organize test leads. | The same complete load is NT$750 / US$22.76. | Buy the load. A custom holder or batch record could save handling time. There is no demonstrated instrument saving. [iOPEN Mall](https://mall.iopenmall.tw/011609/index.php?action=product_detail&prod_no=P1160907683471) |
| Make repeated enclosures | Reuse a suitable case or print a special insert. No physical donor or fabrication quote yet. | A new blank PW-3 starts at NT$105 / US$3.19 and still needs machining. | Buy standard outer shells. At NT$600/hour, a free shell saves money only if its extra preparation takes less than 10.5 minutes. Customize the reusable insert once a recurring board makes it worthwhile. [PW-3](https://jin-hua.com.tw/page/product/show.aspx?lang=TW&num=3569) |
| Apply solder paste to repeated boards | Open stencil-frame design exists. Costs depend on stencil size, frame, rails, alignment hardware and shared machine access. | Taiwan manual stencil-printer vendor publishes specifications and invites inquiries. Public listing provides no price. | Defer the fixture investment until a named board and batch count can support both a build estimate and a comparable supplier quote. [Open design](https://github.com/geissdoerfer/stencil-printer/) · [Taiwan vendor](https://www.fortunetell.com.tw/product/manual-stencil-printer/) |
