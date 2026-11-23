# Hardware Splicer manufacturing portfolio

**Research edition · 19 November 2026 · Taiwan workshop.** Of 51 offers, 41 cover their recurring costs at the proposed price and 22 also recover their launch budget within 25 sales. Nineteen of those 22 are physical products. The best first internal machine is a switch endurance tester. The strongest directly observed accessory sales are for film adapters. The robotics opportunity with the best modeled small-run return is a set of gripper fingers and a locating nest for one repeated workpiece.

Open the [editable workbook](HS-product-portfolio.xlsx) to change shop labor, price, parts, design hours, freight, acquisition cost or production quantity. The [cost inputs and product records](products.csv) and [calculated profitability index](profitability.csv) join on the product ID. The [regional evidence register](regional-evidence.csv) preserves prices in the seller's currency. For earlier-stage products, browse the [26-family guide](family-index.md) or search the [620 configurations](concept-index.csv). All results are digital estimates. No HS product has verified paid volume, production yield or realized profit in this archive.

## Which product to make

The [engineering record index](engineering-records.md) identifies the CAD, simulated runs, published reference builds and physical acceptance checks behind the shortlist.

| Decision | What the buyer gets | Why it earns or loses money |
|---|---|---|
| Build the first switch tester for the lab, then offer repeats | One holder, a servo-operated station and electrical detection of missed or stuck contacts | At NT$3,990, NT$1,662 remains per sale and four sales cover the NT$5,600 launch budget. The cheaper internal first build assumes NT$800 parts and four hours, or NT$3,200. A manufacturer advertises a US$300 sample with three positions and adjustable force. HS still needs physical contact and reset tests. [Commercial machine](https://gonoava.en.made-in-china.com/product/fAKrTsIzOPVl/China-Key-Life-Testing-Machine-Button-Press-Force-Life-Key-Durability-Test-Machine.html) |
| Sell a scanner-specific insert first | A photographer uses an existing Epson scanner for one unusual film format | A Kodak Disc listing showed 227 sold. The current 127 and 126 counters showed 183 and 112 respectively. The Disc scenario earns NT$417 per US$35 delivered and breaks even at 15 sales. Test focus height, light masking and scratches on one exact scanner before committing to adjacent formats. [Disc](https://www.ebay.com/itm/283794454015) · [127](https://www.ebay.com/itm/274330024958) · [126](https://www.ebay.com/itm/274281082913) |
| Try a 6×6 camera carrier if camera access is available | A medium-format film guide for a photographer who owns the camera, light and stand | A US$59 sale leaves US$29. The 49% unit margin falls to 43% return on total modeled cost after 25 sales. The branded US$73 comparison is system-specific. Evidence for our achievable volume is weaker than for the scanner insert. [VALOI 6×6](https://valoi.co/en-us/products/easy120-film-holder-for-120-6x6) |
| Make gripper tooling against a named repeat job | A pair of fingers and matching tray that keep one part in a known orientation | NT$2,790 price, NT$1,152 left per sale, 11 identical sales to recover launch. If each customer needs fresh geometry, allocate those hours per order. Two new hours per order cost NT$1,200 and consume the entire contribution. HP's case study documents design effort but cannot establish our selling price. [HP industrial case](https://www.hp.com/us-en/printers/3d-printers/industries/industrial/cnc-wurfel.html) |
| Develop the ground rover against a definite inspection task | Recorded, illuminated views under machinery of a stated clearance, with a means of recovering the rover | NT$16,900 per unit leaves NT$3,196, yet the launch budget is NT$45,250. At 25 sales the break-even selling price is NT$15,250. Pricing it below that erases the modeled launch return. A camera-equipped 4WD kit is readily available. [Waveshare](https://www.waveshare.com/product/robotics/rasprover.htm) |
| Use ready-made marine hardware for the first water project | Tethered live images, or a lowered camera for vertical pond observation | The US$399 shallow-ROV scenario loses NT$1,083 per sale before engineering. A third-party guard set can leave NT$547 per sale, but at 25 sales only NT$563 remains across the whole run after design. Borrowing the appropriate host is essential to that case. [Dory promotion](https://www.offgridlux.com/collections/chasing/products/chasing-dory-underwater-drone) · [OEM guards](https://store.qysea.com/products/propeller-protectors) |

## Research findings that changed the business case

* **A board-testing jig has an inexpensive custom competitor.** Makerfabs publishes a US$55 starting fee and a US$65 Uno example. Our 18-contact fixture costs an estimated NT$1,291 in recurring manufacture and NT$8,450 to develop and prototype. A NT$1,990 sale produces NT$310 of contribution, requiring 28 identical sales. With a fresh design per customer, charge engineering separately or use it internally. HS already has a reusable carrier and a digitally verified pad-location change. [Makerfabs](https://www.makerfabs.com/testing-jig-fixture-customizing-service.html) · [Taiwan spring probes](https://www.sconline.com.tw/tw/product/index.php?kind3=354)
* **The cheap substitute matters for kitting.** A Taiwan counting scale at NT$89–109 already counts loose pieces. A 1 kg load cell and amplifier alone list for NT$118. Our proposed NT$2,190 checker needs a job the cheap scale cannot handle well, such as linking a known kit to its weight record and detecting a missing item. Even with that price the 25-sale return is only 3.9%. [Retail scale](https://www.ruten.com.tw/item/22452498308816/) · [Cell and amplifier](https://www.sconline.com.tw/tw/product/index.php?kind3=244)
* **The photography rail has room for a useful machine, with little room for engineering overruns.** WeMacro lists its motorized rail at US$329–339 and a manual rail at US$24.90. Our automatic model costs an estimated NT$5,010 per unit to manufacture and NT$6,458 per sale including fulfillment and reserves. At NT$7,490, it takes 28 sales to recover NT$28,600 of development and prototypes. A proven open design could reduce that budget if its travel and image settling meet the job. [Motorized comparator](https://www.wemacro.com/?product=wemacro-rail) · [Manual substitute](https://www.wemacro.com/?product=4-way-macro-focus-rail-slider) · [Open build](https://jackw01.github.io/macro-rail/)
* **Aquarium electronics face established local supply.** A Taiwan retailer lists a finished top-off at NT$1,350. A single retail peristaltic pump can cost NT$960 before controls and housing. Indonesian listings put a four-head dosing unit around Rp950,000–1,099,000. The archive prices a single-channel unit, a complete top-off and a passive clip separately. Shared shipping may make a clip a viable add-on. The standalone single-clip scenario loses money. [Taiwan top-off](https://mall.iopenmall.tw/067112/index.php?action=product_detail&prod_no=P6711209865115) · [Taiwan pump](https://www.icshop.com.tw/categories/pumps-and-solenoids) · [Indonesian listings](https://www.blibli.com/jual/dossing-pump)
* **An actual farm workflow is stronger evidence than an expensive neighboring machine.** Indonesian operators inspect an *anco* feeding tray. A mount for repeat photos is technically plausible. At a hypothetical NT$1,490 it needs 37 sales to recover launch. A purchased seaweed dryer proves that one institution bought a dryer. It supplies no sale price for our rack-mounted logger. The register records the original currency, product scope and missing demand evidence. [JALA practice](https://jala.tech/id/blog/tips-budidaya/cek-anco-dan-sampling) · [Sulawesi asset inventory](https://bappelitbangda.sulselprov.go.id/content/new_directory/2024/Inventaris_Barang_Milik_Negara_Tahun_2024.pdf)

## In-house equipment and purchase savings

These are first-unit comparisons. A lab only saves the purchase when it actually needs equivalent capabilities.

| Asset | Estimated first build | Ready alternative | Decision |
|---|---:|---:|---|
| Switch tester | NT$3,200 / US$97 | NT$9,884 / US$300 advertised sample | Potential NT$6,684 saved for a single-station use case. Three-station throughput and force adjustment are additional commercial capabilities. |
| Standard automatic coil winder | NT$7,554 / US$229 | NT$8,204 / US$249 | Only NT$650 headroom before delivery or rework. Buy standard, or make a custom bobbin adapter. [Listing](https://www.buyandship.today/en/shopping/marketplaces/ebay/products/v1%7C800486922576%7C0/) |
| Coupon dip coater | NT$27,947 / US$848 | Ni-Lo NT$49,388 / US$1,499 | Potential NT$21,441 saved at the branded benchmark. A comparable delivered machine below NT$27,947 reverses the comparison. At the proposed NT$27,900 selling price, our repeat-unit model loses money after fulfillment. [Published BOM](https://pmc.ncbi.nlm.nih.gov/articles/PMC9526236/) · [Ni-Lo](https://niloscientific.com/products/ni-lo-x2-dip-coater-0-1-500-mm-min) |
| SO-101 follower | NT$5,655 parts / US$172, before hands-on work | NT$7,088 / US$215 assembled and calibrated | The NT$1,433 headroom buys about 2 h 23 min at NT$600/h. Designing workholding can offer a better return than assembling the standard arm. [Taiwan unit](https://robotkingdom.com.tw/product/so-arm101-followe-assembly/) |
| Cabinet environmental logger | NT$605 / US$18 parts, before assembly and host | RC-4HC NT$856 / US$26 | Only NT$251 remains for work if temperature and humidity suffice. The HS logger also streams pressure but needs a host. [Taiwan recorder](https://www.shop.anjun.com.tw/product/精創usb溫濕度記錄器rc-4hc/) |

## How to interpret and change the ratios

**Unit contribution** is selling price less parts, processing and rejects, human labor, packing and delivery, selling fees, and warranty reserve. **Contribution margin** divides that amount by selling price. **Launch cost** is design hours × NT$600 plus prototype and host-access allowances. **Break-even quantity** rounds launch cost divided by positive unit contribution up to a whole unit.

**Return on total modeled cost** divides batch revenue less total modeled cost by total modeled cost. With 25 sold, that denominator includes launch plus 25 units of all recurring costs. For example, the switch tester earns NT$99,750 in revenue against NT$63,812.50 in modeled costs. The difference is NT$35,937.50, a 56.3% return on cost. The 41.6% unit contribution margin answers a different question.

**Downside:** produce 25 physical units, sell 17 at a 20% discount, and give the eight unsold units no recovery value within the period. Charge per-sale fees and outbound shipping only on the 17 sold. Downloads incur per-order work only on sales. All 51 offers lose money under this combined stress. For the switch tester the loss is NT$1,286. Making only the 17 already ordered at the same discounted price would leave approximately NT$11,114 after development. For the rover, even building only 17 to order at that discounted price would still lose roughly NT$39,184 after development. Those differences help determine which products to stock.

For US offers the model assumes US domestic fulfillment. A Taiwan studio shipping individual items abroad should enter the extra landed cost. Taiwan scenarios use local delivery assumptions. Indonesian observations are competitor references in rupiah; a local manufacturing ROI needs local procurement, freight, taxes, channel costs and support. Editable acquisition and additional fixed-cost fields start at zero. Engineering labor, production minutes, sales, selling prices and manufacturing yields are planning assumptions, and product-specific certifications or equipment purchases may be material. No robotic labor saving is included. NT$32.947/US$ is the 18 November close. [Central Bank of Taiwan](https://www.cbc.gov.tw/en/lp-700-2-1-40.html)

The prior 32-offer screen is retained in the repository. This edition adds 19 separately costed offers and explicit launch scenarios for every row. Published counters are cumulative, may include selectable variants and have unknown observation windows. The named products and checks are research records, not supplier quotations or manufacturing releases. Treat per-revision setup as recurring if each unit needs engineering. Do not add the scenarios across alternatives to estimate company-wide earnings.

## All 51 priced offers

Sorted by projected return on total cost at 25 sales. Price and contribution are per unit. The workbook and CSV retain dollar equivalents, cost inputs and downside results.

| ID | Offer | Sale price NT$ | Left per sale NT$ | Unit margin | Break-even sales | 25-sale ROI |
|---|---|---:|---:|---:|---:|---:|
| P028 | Switch endurance tester, single station | 3,990 | 1,662 | 41.6% | 4 | 56.3% |
| P010 | 6×6 camera-scanning carrier | 1,944 | 956 | 49.2% | 10 | 43.4% |
| P001 | PCB inspection dock files | 297 | 187 | 63.1% | 15 | 36.4% |
| P047 | Gripper fingers and locating nest set | 2,790 | 1,152 | 41.3% | 11 | 31.7% |
| P002 | Ender-3 plotter conversion files | 494 | 329 | 66.7% | 17 | 28.4% |
| P018 | Turntable extension platform | 1,944 | 718 | 36.9% | 11 | 28.4% |
| P008 | 35 mm camera-scanning carrier | 1,450 | 650 | 44.8% | 15 | 24.1% |
| P011 | Kodak Disc flatbed adapter | 1,153 | 417 | 36.2% | 15 | 18.1% |
| P012 | 127 strip flatbed adapter | 1,153 | 417 | 36.2% | 15 | 18.1% |
| P013 | 126 strip flatbed adapter | 1,153 | 417 | 36.2% | 15 | 18.1% |
| P014 | 120 flatbed holder for Epson V600 | 1,153 | 417 | 36.2% | 15 | 18.1% |
| P015 | 110 holder for Epson 4870 | 1,153 | 417 | 36.2% | 15 | 18.1% |
| P016 | 8 mm film inspection holder | 1,153 | 417 | 36.2% | 15 | 18.1% |
| P020 | Larger folding LED photo box | 3,921 | 1,067 | 27.2% | 15 | 13.5% |
| P017 | Motorized indexed photo turntable | 3,591 | 1,044 | 29.1% | 17 | 10.7% |
| P030 | Low-profile 4WD inspection rover, dry indoor use | 16,900 | 3,196 | 18.9% | 15 | 8.9% |
| P003 | Parametric cabinet-handle layout files | 297 | 177 | 59.7% | 23 | 6.1% |
| P039 | USB parts-counting and kit-check scale | 2,190 | 565 | 25.8% | 22 | 3.9% |
| P026 | Fixed-angle split-keyboard supports | 955 | 245 | 25.6% | 23 | 3.1% |
| P045 | Auto-traverse pickup coil winder | 7,900 | 1,101 | 13.9% | 22 | 2.2% |
| P032 | Six-piece underwater ROV guard set, one host model | 1,290 | 546 | 42.4% | 24 | 1.8% |
| P019 | Compact folding LED photo box | 2,142 | 493 | 23.0% | 24 | 1.8% |
| P033 | 18-contact programming and test fixture | 1,990 | 310 | 15.6% | 28 | -1.4% |
| P036 | Motorized macro focus rail | 7,490 | 1,032 | 13.8% | 28 | -1.5% |
| P043 | Custom four-wire harness checker | 1,690 | 366 | 21.7% | 29 | -2.9% |
| P024 | Low-profile PCB bench vise | 1,186 | 289 | 24.4% | 29 | -3.2% |
| P022 | 5 mm shelf-pin jig | 1,120 | 232 | 20.7% | 30 | -3.8% |
| P046 | Reusable shrimp tray photo mount | 1,490 | 232 | 15.5% | 37 | -6.7% |
| P048 | Registration frame for small PCB stencils | 1,490 | 271 | 18.2% | 36 | -6.8% |
| P005 | Dock with Sily microscope | 1,290 | 213 | 16.5% | 37 | -6.9% |
| P025 | Device-specific repair screw tray | 725 | 102 | 14.1% | 41 | -7.8% |
| P009 | 35 mm carrier with CS-LITE | 2,800 | 269 | 9.6% | 48 | -8.0% |
| P051 | Drying-rack weight and humidity logger | 3,290 | 521 | 15.8% | 39 | -8.1% |
| P050 | Model-specific 3018 CNC locating fixture | 1,250 | 210 | 16.8% | 40 | -8.8% |
| P034 | Pick-and-place staging carrier | 1,690 | 328 | 19.4% | 39 | -9.4% |
| P037 | Manual XY specimen stage | 1,690 | 263 | 15.6% | 43 | -9.7% |
| P044 | Programmable coupon dip coater | 27,900 | -1,090 | -3.9% | No break-even | -10.4% |
| P023 | Drawer-slide alignment pair | 955 | 146 | 15.3% | 47 | -11.6% |
| P006 | Dock with DM-500X microscope | 1,990 | 83 | 4.2% | 116 | -13.1% |
| P021 | Cabinet-handle drilling jig | 857 | 159 | 18.6% | 51 | -16.1% |
| P031 | Shallow-water tethered live-camera ROV | 13,146 | -1,083 | -8.2% | No break-even | -20.2% |
| P004 | Printed PCB dock with one OpenLog carrier | 499 | 96 | 19.2% | 59 | -20.4% |
| P049 | Assembled SO-101 follower arm | 7,088 | -1,430 | -20.2% | No break-even | -21.5% |
| P027 | Six-switch feel tester | 593 | -45 | -7.6% | No break-even | -26.6% |
| P007 | Indexed product-photo turntable | 1,290 | 137 | 10.6% | 124 | -29.5% |
| P041 | Single-channel aquarium dosing pump | 2,250 | -300 | -13.3% | No break-even | -29.8% |
| P029 | Toy 4WD camera car | 1,100 | -268 | -24.4% | No break-even | -30.9% |
| P038 | USB dry-cabinet environmental logger | 850 | -246 | -28.9% | No break-even | -35.6% |
| P040 | Aquarium automatic top-off unit | 1,290 | -262 | -20.3% | No break-even | -41.4% |
| P035 | Single strip feeder for placement machine | 299 | -43 | -14.3% | No break-even | -46.0% |
| P042 | Aquarium dosing tube clip | 149 | -37 | -25.1% | No break-even | -49.4% |
