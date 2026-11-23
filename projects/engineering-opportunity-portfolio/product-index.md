# Hardware Splicer product index

The [engineering reader](catalog/engineering/trials.html) links each exercised product to its design inputs, digital results and remaining physical acceptance checks. [Coverage for all 270 offers](catalog/engineering/coverage.csv) includes the 25-sale result for comparison.

Start with the [270-offer manufacturing catalog](catalog/index.html) for the current build-versus-buy and resale analysis. It includes 219 additional product briefs, individually costed scenarios and Taiwan and Indonesia references. [Research findings](catalog/README.md) · [Download the offline archive](HS-manufacturing-catalog.zip)

The [19 November manufacturing archive](archive/README.md) ranks 51 offers by return on total cost and includes editable assumptions, Taiwan and Indonesia evidence, and a 620-configuration concept index. [Download the complete archive](HS-product-archive.zip)

**18 November 2026.** Start with the offer table to see what a buyer would get. Use the supplier table to see which parts HS could buy, which equipment the buyer already needs, and which listings establish a competing price. The digital projects and the 620-row device list below cover the wider design portfolio. Taiwan and US figures each assume domestic fulfillment.

For ranked margins, buyer counts and entry costs across 27 offers, open the [expanded market comparison](expanded-market-comparison.md) or the [sortable unit economics](offer-comparison.csv).

## Products HS could offer

| Product and intended buyer | What HS supplies and what the buyer brings | Design evidence and next question | Delivered price → contribution per unit |
|---|---|---|---|
| PCB inspection design download for electronics makers | Editable dock and three carriers. The maker prints one dock and the carrier for their board. | Local v0.1 package includes STEP, STL, board references, source and checks. First publication candidate. Demand and willingness to pay for files are unknown. [Download package](../pcb-inspection-nest/inspection-nest-v0.1.zip) | Digital price and support cost unmodeled |
| Printed PCB inspection dock for a repair bench | One dock and one carrier. Buyer brings a microscope or camera. The job is to return the same board to a known position for repeat photos. | Three carrier layouts exist. The cost model covers the OpenLog version. Verify populated-board clearance and camera-to-board registration. [Design and board revisions](../pcb-inspection-nest/README.md) | TW NT$499 → **NT$155.88 (31.2%)** |
| Entry inspection station for a small repair shop | Same dock and carrier plus Sily USB microscope and stand. Buyer brings a compatible host. | Optical module listed. A common locating feature between stand and dock and a repeat-image test remain open. A microscope and a generic holder together list at NT$801. | TW NT$1,290 → **NT$293.05 (22.7%)** |
| Inspection station with adjustable lighting and scale | Same fixture plus DM-500X microscope set. Buyer brings a compatible host. | Module identified. Check working distance, visible board detail and whether the added features justify the price. | TW NT$1,990 → **NT$163.05 (8.2%)** |
| 35 mm film carrier for photographers who already scan with a camera | HS makes a passive carrier for a specified film strip. Buyer supplies camera, macro lens, stand and light. | Retail holder comparator exists. HS CAD and tests for film flatness, scratches and light leaks are outstanding. | US $44 → **$18.28 (41.5%)** |
| Illuminated 35 mm film carrier for photographers | HS carrier plus CineStill CS-LITE. Buyer supplies camera, macro lens and stand. | Direct kit comparator exists. Adding a retail light consumes most of the contribution. Check evenness of illumination and interface geometry. | US $84.99 → **$5.99 (7.0%)** |
| CNC workholding fixture for shops repeating one job | HS designs the locating and clamping parts for one stock shape and one named machine bed. Buyer owns the host machine. | Machine campaigns show buyers exist. Choose a bed revision and repeated job, then establish clamp retention, tool clearance and demand for that fixture. | Unpriced. US$19.99 is a generic spoilboard comparison |
| Complete desktop CNC for small workshops | HS would supply the machine, controller, enclosure as applicable and commissioning instructions. | Competitor machines have paid campaign evidence. HS lacks a complete costed CNC design and yield data for this offer. | US$349 competitor benchmark. **US$198.93** ceiling for all direct costs outside fees and reserve at the 30% target |
| Quick-change PCB fixture for small-batch assembly | HS supplies a carrier for one board and one placement-machine interface. Buyer owns the LumenPnP and changes boards between jobs. | Opulo sells a build plate for switching jobs. The HS static nest contributes board geometry. Positive retention, repeatable height, nozzle clearance, visible fiducials and ESD still need evidence. | Unpriced. US$70 is the maker’s build plate price |
| Complete desktop pick-and-place machine for an electronics workshop | HS would integrate motion, vision, feeders, controller and calibration. | Opulo reports installed users. A complete HS design, landed parts list, placement yield and support estimate are missing. | US$1,995 competitor benchmark. **US$1,137.15** direct-cost ceiling on the same basis |

The five contribution estimates price **physical units**. Each deducts a modeled 8% selling/payment fee, 5% returns reserve, bought-in module, materials, labor and fulfillment. Customer acquisition, fixed overhead, tax adjustments and engineering still come out of the balance. At 25 sales, the standalone inspection dock leaves **NT$154.50 total** for engineering or customer acquisition if the business retains 30% of revenue. The film carrier leaves **US$127 total** under the same assumption. That makes engineering reuse especially valuable for the dock. Sales volume, realized margin and engineering hours per accepted product are open for every offer. [Cost inputs, formula and sensitivity](market-screen-2026-11-18.md)

## E-commerce listings and demand evidence

Prices are the recorded screen values for one unit unless otherwise specified. Listing prices, campaign pledges, customer reviews and completed listings answer different questions. The campaign figures apply to the named commercial product. A buyer of a complete machine may never need our accessory.

| Product family | Buyable inputs | Competing products and observed demand |
|---|---|---|
| PCB inspection | eSUN PLA+ at NT$450/kg costing basis, NT$405 promotion, preorder notice. Sily listing DGAD57-A900GYQFB at NT$521. DM-500X with stand, light and scale at NT$1,260. [Filament](https://shop.qts.tw/products/esun-pla-filament) · [Sily](https://24h.pchome.com.tw/prod/DGAD57-A900GYQFB) · [DM-500X](https://shop.cpu.com.tw/product/45310/info/) | Pro’sKit SN-390 generic adjustable holder at NT$280. The Sily listing showed 12 reviews. Paid board-specific carrier sales remain unknown. [SN-390](https://www.icshop.com.tw/zh-hant/products/368040100475) |
| Film scanning | CS-LITE at US$44.95. The modeled bundle can spend up to US$25.44 on the light to retain 30%. [Light source](https://cinestillfilm.com/collections/lig/products/cs-litecamera-scanning-light-source-1) | VALOI 35 mm holder US$47, starter light/holder bundle US$84.99, lens-mounted easy35 v2 US$271. The original system drew 840 backers and €102,108. Two October 2026 easy35 listings closed with undisclosed accepted prices. [Holder](https://valoi.co/en-us/products/360-film-holder-for-35mm) · [Starter kit](https://cinestillfilm.com/collections/shop-all/products/valoi360-starter-scanning-bundle) · [easy35](https://valoi.co/en-us/products/easy35) · [Campaign](https://www.kickstarter.com/projects/valoi360/valoi-360-scan-your-film-with-a-digital-camera) · [Oct 12 listing](https://www.ebay.com/itm/189056285812) · [Oct 16 listing](https://www.ebay.com/itm/407288493734) |
| Desktop CNC | A 3018-format MDF spoilboard lists at US$19.99. It is a reference for generic workholding. Confirm the actual host mounting pattern before selecting materials. [Spoilboard](https://www.sainsmart.com/products/genmitsu-cnc-mdf-spoilboard-for-3018-cnc-router-30-x-18-x1-2-cm) | GORDIX raised NT$10.78m from 181 unique backers. Cubiio X raised NT$28.05m from 525 unique backers. Genmitsu Cubiko drew 3,328 backers and lists at US$349. These are the strongest historical machine campaign figures in this screen. [GORDIX](https://www.zeczec.com/projects/gordix-cnc) · [Cubiio X](https://www.zeczec.com/projects/cubiioX-2025-07-11) · [Cubiko campaign](https://www.kickstarter.com/projects/genmitsu/cubiko/) · [Retail machine](https://www.sainsmart.com/products/cubiko) |
| Desktop PCB assembly | Opulo build plate US$70, strip feeder from US$9.99. Both are existing accessories against which a buyer can assess our proposed fixture. [Plate](https://www.opulo.io/products/staging-plate) · [Feeder](https://www.opulo.io/products/lumenpnp-strip-feeder) | LumenPnP lists at US$1,995. Opulo reported hundreds of users following 2022. Sales of third-party board-specific fixtures remain unknown. [Machine](https://www.opulo.io/products/lumenpnp) · [Manufacturer account](https://www.opulo.io/blogs/news/product-updates-for-2023) |

## Other designs, donor routes and device studies

These entries show what a builder can take from HS today. Their selling prices, contribution and paid volumes have yet to be established.

| Product or route | Materials, work already done, and open question |
|---|---|
| Ender-3 pen plotter | Retain the original Ender-3 frame, drives, bed and controller. HS supplies an adjustable pen mount, parking plate, parts list and replayable drawing. The marker variant shows how the same design changes for a different pen. Physical line accuracy and clamp force are unknown. [Conversion](../ender3-penplotter-digital/README.md) · [Marker revision](../../examples/design_revision_pilot/README.md) |
| Fielddeck 7 portable Linux terminal | Pi 4 SC0193, SC1635 display, Adafruit 1736 keyboard and Anker A1259 power bank in a 20-part printable case. Includes assembly, wiring and exact BOM. Historical parts reference about US$337. Runtime and cooling are estimates, and boot is unverified. [Digital prototype and BOM](../cyberdeck-real-trial-20261020/digital_v1/README.md) |
| HS-3G-B quadcopter | Editable assembly, offline viewer and simulated flight scenarios. Reference components have representative geometry. Physical behavior and hardware cost of a delivered unit remain open. [Digital study](../../examples/drone_proving_ground/digital/README.md) |
| MK3S-size parts tray | Editable 245 × 205 × 20 mm tray. The model fits the nominal printer volume. Slicing and printed tolerances remain open. [Tray and models](../../eval/unseen_devices/README.md) |
| ClearBench S1 non-potable sediment filter demonstrator | Commercial filter housing, cartridge and conceptual instrument layout for bench study. The flow and turbidity figures are design targets. [Product specification](../../examples/products/clearbench_s1_product.json) |
| Keyboard, handheld, logger and audio builds | Sweep v2.2 has a board-traced 34-key wiring map. PyGamer, OpenLog Artemis and MAX9744 have revision-specific compatibility findings useful for selecting modules. Their study records answer individual build questions. The three inspection carriers are separate HS deliverables. [Sweep](../../eval/unseen_sweep/README.md) · [Board studies](../../eval/unseen_devices/README.md) |
| Robot arms and indoor rovers | myCobot 280 M5 has a joint-limit study. Robotics references cover mobile bases and manipulators. A separate indoor inspection rover has an integration brief. Physical payload and complete machine economics remain open. [Arm study](../../eval/unseen_devices/README.md) · [Robot catalog](../../examples/robot_reference_corpus/robot_reference_catalog.json) · [Rover](../../examples/robot_reference_e2e/reference_rich_indoor_inspection_rover.json) |
| Donor inspection station | Scanner carriage, USB desk lamp and webcam form a proposed repeat-imaging station. The intake used fictional donors. Exact working parts, optical performance and supply volume remain open. [Donor study](../../docs/SALVAGE_COMPANY_FEASIBILITY.md) |
| Diagnostic bench, ESP32 environmental monitor and observation camera | Earlier concepts for bench measurement, air-quality logging and wildlife observation. The portfolio has use cases and external references. Calibration, a costed HS configuration and buyer demand are open. [Opportunity portfolio](README.md) |
| Refurbished computers and consoles | ThinkPad T480/T480s, business mini-PCs, Switch Lite, PSP-300x UMD drive and Steam Deck OLED storage. These require a specific donor condition and repair cost. The historic listings are asking prices. [Donor comparisons](README.md) · [Repair case files](../../eval/real_hardware_projects/README.md) |

## Search all 620 device configurations

Open the [filterable device list](device-configurations.csv) and filter by family, search for a job such as “parts counter,” or search for a donor you want to reuse. Each row contains the configuration ID, intended function, commercial analogues, assumed parts with condition, and expected capabilities. Use the ID to retrieve constraints and other details from the [source catalog](../../examples/product_corpus/enabot_depth_corpus.json). Controller and power variants have separate rows. The briefs describe hypothetical inventory. Market demand, supplier quotes, HS design completion and margins require their own evidence.

| Category | Configurations | Examples to search for |
|---|---:|---|
| Agriculture | 24 | Greenhouse vent, grain-bin temperature logger |
| Air and climate | 30 | Room air-quality station, humidity-controlled fan |
| Aquatics and vivariums | 24 | Reef top-off, terrarium mister |
| Audio and communications | 21 | Guitar practice amp, workshop pager |
| Cleaning and mobility | 18 | Pool skimmer, miniature vacuum drive |
| Desktop fabrication | 24 | Pen plotter, clay extruder, CNC probe jig |
| Displays and information | 28 | Bus arrival board, e-ink calendar |
| Educational robotics | 21 | Line follower, three-axis robot arm |
| Health and accessibility | 15 | Handwashing timer, reminder box |
| Home assistance | 18 | Curtain opener, wardrobe humidity monitor |
| Light industrial machinery | 15 | Parts counter, label applicator, vibratory feeder |
| Inspection and cameras | 24 | Focus-stacking rail, microscope stage |
| Kitchen appliances | 24 | Fridge door alarm, fermentation chamber |
| Laboratory and bench | 32 | Motor test jig, load-cell scale |
| Lighting | 21 | Dimmable task light, photography softbox |
| Mobile telepresence | 60 | Rolling home camera, inspection rover |
| Mobility and vehicles | 12 | Battery gauge, trailer brake light |
| Outdoor water systems | 18 | Rain-barrel level gauge, pond pump timer |
| Pet care | 24 | Portion feeder, water fountain |
| Plants and gardens | 30 | Soil-moisture drip system, compost temperature logger |
| Power and energy | 12 | Solar charge monitor, USB power-delivery bench |
| Retail and hospitality | 18 | Queue pager, espresso shot timer |
| Science and education | 24 | Weather station, classroom robotics kit |
| Security and access | 30 | Mailbox notifier, driveway alert |
| Sensor networks | 32 | Under-sink leak detector, freezer temperature alarm |
| Studio and media | 21 | Camera slider, teleprompter scroller |
