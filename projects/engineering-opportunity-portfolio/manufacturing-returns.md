# Products worth manufacturing, Taiwan workshop assumptions

19 November 2026. The [32-offer comparison](manufacturing-returns.csv) covers the 27 products and variants in the existing sales screen plus five machinery and robotics offers. The [full product index](product-index.md) includes the other engineering studies and links to 620 concept configurations. Only the 32 offers have sale-price and recurring-cost scenarios here.

## Which product pays for its design?

All figures below are estimates in NT$. The 25-unit case assumes 25 units made and sold at the proposed price. Return divides proceeds after all modeled costs by the total modeled cost of those 25 units, including one-time design and prototypes. It is sensitive to sell-through. The CSV also includes contribution per sale and the effect of a 20% price cut.

| Product | Price | Recurring cost | Left per sale | Upfront budget | Units to recover upfront | Return on cost at 25 sales |
|---|---:|---:|---:|---:|---:|---:|
| Switch endurance tester | 3,990 | 2,329 | 1,662 | 5,600 | 4 | 56% |
| 6×6 film carrier | 1,944 | 988 | 956 | 9,200 | 10 | 43% |
| 35 mm film carrier | 1,450 | 800 | 650 | 9,200 | 15 | 24% |
| Kodak Disc adapter for an Epson scanner | 1,153 | 736 | 417 | 6,000 | 15 | 18% |
| Dry indoor 4WD inspection rover | 16,900 | 13,704 | 3,196 | 45,250 | 15 | 9% |
| Six guards for one model of underwater ROV | 1,290 | 744 | 547 | 13,100 | 24 | 2% |
| Consumer shallow-water camera ROV | 13,146 | 14,229 | −1,083 | 56,300 | None at this price | −20% |
| Toy 4WD camera car | 1,100 | 1,368 | −268 | 5,600 | None at this price | −31% |

**The switch tester** can earn its keep internally and potentially sell to another small hardware lab. Our single-station first build was estimated at NT$3,200 including design time, against a US$300 sample listing for a three-position commercial machine with adjustable force. For a repeatable product, the recurring estimate is NT$800 parts, NT$150 process loss, one hour of assembly and testing, NT$180 packing and delivery, and 15% of sales for fees and after-sale costs. The NT$3,990 asking price is a hypothesis. The one-time budget includes eight design hours and one NT$800 prototype allowance. If a lab needs adjustable force, the commercial unit has a known specification that our version presently lacks. [Detailed build-or-buy comparison](machine-value-trials/README.md) · [Commercial tester](https://gonoava.en.made-in-china.com/product/fAKrTsIzOPVl/China-Key-Life-Testing-Machine-Button-Press-Force-Life-Key-Durability-Test-Machine.html)

**Film adapters** have the strongest direct purchasing evidence. A seller shows 227 sold for a Kodak Disc adapter, at a current US$27.50 plus US$10.20 US delivery. We modeled US$35 including a US$9 fulfillment allowance. VALOI lists a system-specific 6×6 holder at US$73, against our US$59 proposed price. Check fit, focus height, film flatness and print marks for a named scanner or camera system. The 6×6 and 35 mm scenarios allow twelve design hours and NT$2,000 for prototypes each. The Disc model allows eight hours plus NT$1,200. Scanner and camera access is assumed. Growing international postage can quickly erase the margin. [Disc listing](https://www.ebay.com/itm/283794454015) · [6×6 comparator](https://valoi.co/en-us/products/easy120-film-holder-for-120-6x6) · [Regional evidence](expanded-market-comparison.md)

## Camera rover on four driven wheels

**Generic camera car.** Taiwan already has a listing at NT$1,100 for both camera-equipped color variants. It showed zero sales. For a small run, allow NT$250 for a four-motor chassis, NT$232 for a camera controller, and NT$318 for motor electronics, battery, charger, wiring and housing. The latter is a budget. Add 30 minutes of assembly and testing, NT$45 process allowance, NT$80 packing and delivery and a 13% fee and returns reserve. Even eliminating all 30 minutes leaves only NT$32 per sale before design. For internal use the repeat build subtotal of parts, processing and labor is NT$1,145 versus the NT$1,100 retail ask, before first-unit engineering. [Taiwan finished car](https://www.ruten.com.tw/item/22533551376181/) · [Chassis options](https://www.icshop.com.tw/categories/robot) · [ESP32 camera](https://www.mc-cvi.com/products/esp32-cam-dev-board)

**Inspection rover.** The proposed buyer is a maintenance shop that needs a recorded view under low, dry machinery. Buy the four-wheel platform and camera. Engineer low-profile lighting, wheel and lens protection, retrieval attachment and repeatable image capture for a specified clearance. The Waveshare RaspRover lists at US$174.99–419.99 depending on computer and pan/tilt options. Budget NT$5,765 for the camera-equipped base kit, NT$1,800 for the host, NT$750 for cells and power accessories and NT$935 for lighting, protection, storage and hardware. Those additions and inbound pricing need local quotes. Add two hours of assembly and testing, NT$200 for process losses, NT$350 to pack and deliver, and a 16% selling and after-sale reserve. The scenario requires the buyer to supply a phone or computer. [Waveshare package contents](https://www.waveshare.com/product/robotics/rasprover.htm)

At a proposed NT$16,900, the margin is 18.9%. A 20% discount leaves **NT$357** before design recovery. It needs about NT$20,370 at these costs to retain 30% contribution. The NT$45,250 launch budget allows 60 hours and one NT$9,250 prototype. The cheaper alternatives are purchasing the kit directly, or using a camera on a pole where it can reach. Professional robot demand exists overseas. SuperDroid reports one customer used its GPK-32 for over 1,500 inspections. Its package includes customer support and different mechanical and camera capabilities. We have no measured clearance, footage, traction, retrieval data or paid orders for this HS variant. [Professional 4WD rover and customer use](https://www.superdroidrobots.com/product/gpk-32-wheeled-inspection-robot/)

## Tethered underwater camera ROV

The entry benchmark is the **CHASING Dory at US$399 promotional / US$499 regular**, with a 15 m depth specification. It is a foreign retail benchmark before Taiwan freight or taxes. In Taiwan a FIFISH V-EVO standard package is NT$63,900 with 4K/60 video and omnidirectional movement. Its retail price represents a substantially more capable product. Taiwan also has a 15/30 m cable-lowered fishing camera and screen advertised at NT$3,594–3,972 for a pond operator who only needs to see directly below. [Dory price](https://www.offgridlux.com/collections/chasing/products/chasing-dory-underwater-drone) · [Dory specs](https://www.chasing.com/en/chasing-dory.html) · [Taiwan FIFISH](https://www.esentra.com.tw/product/qysea-fifish-v-evo/) · [Taiwan cable camera](https://www.ruten.com.tw/item/22617579603637/)

For an inexpensive calm-freshwater prototype with live video, the NT$8,300 materials allowance consists of NT$2,200 for propulsion and drivers, NT$1,600 for enclosure, seals and penetrations, NT$1,200 for tether and surface interface, NT$1,150 for camera, control and lights, NT$1,250 for power and charging and NT$900 for frame, buoyancy and hardware. These are procurement targets. The design has no demonstrated working depth. Assume four recurring hands-on hours, NT$300 process loss, NT$600 packing and freight, and 20% of revenue for fees, returns and warranty. One repair involving water ingress could cost more than the reserve on several sales. The budget assumes the buyer supplies a screen. It excludes access to a pressure-test facility.

At US$399 the model loses NT$1,083 per sale. At US$499 it leaves roughly NT$1,553, about 9%, before design. At US$399 with the above labor and reserve, the materials ceiling is roughly NT$7,217 to break even and **NT$3,273** to retain a 30% contribution. Reaching NT$3,273 while matching the Dory would require roughly 61% off the modeled parts budget. The first engineering case allows 80 hours and one parts set. Even for internal use the first prototype carries substantial development cost. The same recurring build costs NT$11,000 before packing and selling fees, leaving only about NT$2,146 against the promotional Dory to pay for first-unit engineering and testing.

A builder reports a roughly US$150 camera ROV prototype. A more elaborate TinkerSub with a surface computer and six thrusters lists US$1,100–1,300 in purchases. These references show how strongly the cost depends on what is included. Neither establishes the depth, image quality, production yield, or warranty we could deliver. A more promising initial water product is a **model-specific six-piece propeller guard set**. The OEM sells a set for US$50. At our proposed NT$1,290, allow NT$140 materials, NT$100 processing and rejects, 20 hands-on minutes, NT$110 delivery, and 15% in fees and reserve. The launch budget assumes 16 hours plus NT$3,500 for prototypes and access to a host. Buying a NT$63,900 host instead of borrowing one would overwhelm a 25-set run. Physical checks include retention, thrust loss, visibility and snag behavior. [Budget camera ROV](https://carterturn.com/h/projects/turn_rov) · [TinkerSub open project and BOM](https://github.com/bgreig/TinkerSub) · [OEM six-piece set](https://store.qysea.com/products/propeller-protectors)

**Indonesia.** CNC Store Bandung lists a camera-equipped 4WD educational kit at Rp990,000, marked sold out. A Tangerang marketplace seller advertised a Dory Explore preorder at Rp14,999,000. Those listings establish local alternatives and asking prices. No local dealer purchase orders, landed import quotes, warranty costs or HS sell-through are available. Published prices alone cannot identify the share attributable to country of manufacture. [Bandung rover kit](https://cncstorebandung.com/product/esp32-cam-4wd-smart-robot-car-kit-wifi-app-control-kuongshun/) · [Dory Explore preorder](https://shopee.co.id/CHASING-Dory-Explore-%E2%80%93-Drone-Selam-Kompak-Dengan-Detektor-Logam-Kamera-Underwater-Drone-CHASING-Dory-Explore-i.216262557.29618541235)

## Other products and accounting

The full comparison includes six scanner-specific flatbed formats, camera-scanning holders and lighting bundle, photo turntables, extension platform, two folding light boxes, cabinet and shelf jigs, drawer-slide guides, PCB docks and microscope bundles, bench vise, repair trays, keyboard supports, switch feel sampler and three download offers. On the internal equipment list, the specialty harness fixture, board-positioning pallet and inspection nest can serve several products. The [arm and solder-cell cost comparison](../arm-solder-cell/BUILD_OR_BUY.md), [dip coater and coil winder](machine-value-trials/README.md), [bench tools](taiwan-lab-seeds.md), and pond equipment in the [regional market comparison](expanded-market-comparison.md) have separate engineering or make-or-buy evidence. Their external sell-through and sale-ready unit costs remain open.

The sales screen uses NT$600 per active labor hour and NT$32.947 per US dollar throughout. It reuses channel-specific materials, shipping and fee assumptions from the [earlier screen](offer-comparison.csv), including US fulfillment allowances on export offers. Overseas retail comparisons are converted for readability. Inbound landed prices, actual outbound rates, taxes, advertising, inventory financing, compliance work and general overhead require separate quotes or allocation. All fees, warranty provisions and design hours in the five new cases are assumptions. We gave no labor credit for a robotic arm. Credit a future measured reduction in assembly time after charging the arm's tooling, setup and interventions. Paid demand for HS products and actual manufacturing yields remain unmeasured. [Taiwan central bank exchange rate, 18 November](https://www.cbc.gov.tw/en/lp-700-2-1-40.html)

## Every priced offer, sorted by contribution margin

Channel indicates the intended sales market. USD and NT$ columns show the same modeled unit contribution. Products with paid-sales evidence can be preferable to higher-margin concepts.

| Product | Channel | Asking price, NT$ | Left per sale, NT$ | Left per sale, US$ | Margin |
|---|---|---:|---:|---:|---:|
| Ender-3 plotter conversion files | Download | 494 | 329 | 10.00 | 66.7% |
| PCB inspection dock files | Download | 297 | 187 | 5.68 | 63.1% |
| Parametric cabinet-handle layout files | Download | 297 | 177 | 5.37 | 59.7% |
| 6×6 camera-scanning carrier | US | 1,944 | 956 | 29.02 | 49.2% |
| 35 mm camera-scanning carrier | US | 1,450 | 650 | 19.73 | 44.8% |
| Six-piece underwater ROV guard set, one host model | TW model | 1,290 | 546 | 16.59 | 42.4% |
| Switch endurance tester, single station | TW model | 3,990 | 1,662 | 50.43 | 41.6% |
| Turntable extension platform | US | 1,944 | 717 | 21.78 | 36.9% |
| Kodak Disc flatbed adapter | US | 1,153 | 417 | 12.66 | 36.2% |
| 127 strip flatbed adapter | US | 1,153 | 417 | 12.66 | 36.2% |
| 126 strip flatbed adapter | US | 1,153 | 417 | 12.66 | 36.2% |
| 120 flatbed holder for Epson V600 | US | 1,153 | 417 | 12.66 | 36.2% |
| 110 holder for Epson 4870 | US | 1,153 | 417 | 12.66 | 36.2% |
| 8 mm film inspection holder | US | 1,153 | 417 | 12.66 | 36.2% |
| Motorized indexed photo turntable | US | 3,591 | 1,044 | 31.69 | 29.1% |
| Larger folding LED photo box | US | 3,921 | 1,067 | 32.39 | 27.2% |
| Fixed-angle split-keyboard supports | US | 955 | 245 | 7.44 | 25.6% |
| Low-profile PCB bench vise | US | 1,186 | 289 | 8.77 | 24.4% |
| Compact folding LED photo box | US | 2,142 | 493 | 14.96 | 23.0% |
| 5 mm shelf-pin jig | US | 1,120 | 232 | 7.03 | 20.7% |
| Printed PCB dock with one OpenLog carrier | TW | 499 | 96 | 2.91 | 19.2% |
| Low-profile 4WD inspection rover, dry indoor use | TW model | 16,900 | 3,196 | 97.00 | 18.9% |
| Cabinet-handle drilling jig | US | 857 | 159 | 4.83 | 18.6% |
| Dock with Sily microscope | TW | 1,290 | 213 | 6.47 | 16.5% |
| Drawer-slide alignment pair | US | 955 | 146 | 4.44 | 15.3% |
| Device-specific repair screw tray | US | 725 | 102 | 3.10 | 14.1% |
| Indexed product-photo turntable | TW | 1,290 | 137 | 4.17 | 10.6% |
| 35 mm carrier with CS-LITE | US | 2,800 | 269 | 8.16 | 9.6% |
| Dock with DM-500X microscope | TW | 1,990 | 83 | 2.52 | 4.2% |
| Six-switch feel tester | US | 593 | -45 | -1.38 | -7.6% |
| Shallow-water tethered live-camera ROV | TW model | 13,146 | -1,083 | -32.88 | -8.2% |
| Toy 4WD camera car | TW model | 1,100 | -268 | -8.13 | -24.4% |
