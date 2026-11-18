# First customer pilot for Hardware Splicer

This was an internal rehearsal of a possible design service. The selected
company direction is to develop and publish HS-owned products. The first
[inspection nest release candidate](../../projects/pcb-inspection-nest/README.md)
exercises that workflow. The offer and outreach draft below are historical.

Start with a small digital design service. A workshop already owns a machine and needs one change it can describe and check. The founder finds that job, agrees a price and decides whether the customer accepted it. HS prepares and revises the design, runs the supported checks, and packages the evidence. Each completed order provides data on demand, engineering effort and which families are worth supporting. The same workflow can later serve devices the company sells itself.

## Sample a buyer can inspect

A fictional workshop wanted to use a wider marker in an original Ender-3 pen plotter and draw on a wider area. HS regenerated the 10 mm reference design and revised it for a 12 mm marker and a 125 × 80 mm viewport. Both exported saddle diameters increased from 11.2 to 13.2 mm, preserving the modeled clearance allowance. The carriage mounting pitch stayed at 14 mm. All 12 simulated strokes stayed in the requested area. Grip strength, paper setup and real drawing accuracy remain physical questions. [Original brief](brief.md) · [Design files and verification package](marker-study.zip) · [Run record](run.json)

Open `exports/plotter.step` in the ZIP for the assembly or `simulation/plotted_drawing.png` for the drawing replay. Start with `STUDY_README.md` for reproduction. The reference rebuild took 21.3 seconds, the revision 11.8 seconds, and the subsequent compare, native audit and export 6.9 seconds combined. This existing family already had an engineered mount, parametric CAD and verifier. Preparing the brief, measuring the delivered STEP geometry, inspecting the output and preparing this handoff occurred outside the timed CLI calls. Human cost, previous development cost, customer review and a manual comparison are unmeasured.

## The offer to test

> Send us one recurring machine or fixture change, the exact model, and a drawing or measured interface you can share. Tell us what the revised design must do and how you would judge it. If the job fits our capabilities, we will quote a fixed fee for editable CAD, a digital check against the agreed requirements, one revision within that brief, and a handoff explaining what still needs a physical test.

Prospects include small print shops and prototyping workshops that already customize equipment. Look for someone who made a similar change recently and can tell you what it cost them. Ask to see the last drawing, what required rework, who signs off and what they would use instead. A lab directory can identify people to interview. A paid brief from a buyer with the problem is the demand test. [Fab Labs directory](https://www.fablabs.io/labs) · [SBA guidance on direct customer research](https://www.sba.gov/business-guide/plan-your-business/market-research-competitive-analysis)

**Draft first message**

> Do you have a fixture or machine attachment that someone on your team keeps redrawing? I’m testing a digital design service for small workshops. I can show you a pen-plotter mount we revised for a larger marker, including the CAD and the drawing simulation. I’d like to hear about the last change that cost your team time. If you have a similar job coming up, I can quote one revision against dimensions and checks we agree on.

## Run the first orders

| Decision | Action | Record |
|---|---|---|
| Find a paying problem | As a first experiment, interview five relevant operators, starting with warm contacts. Pick a repeated, in-scope modification. | Current workaround, frequency, typical labor, purchasing authority and whether the buyer supplies a brief. |
| Quote the outcome | Agree on exact machine revision, files the buyer permits us to use, critical dimensions, acceptance checks, fee, delivery date and included revision. Identify any new design-family setup before quoting. | Written scope, customer price, expected hours and maximum affordable NRE. |
| Deliver digitally | Track hands-on time from intake to acceptance, including sourcing, prompts, failed attempts, independent checks, customer messages and rework. Add tool costs. Package original assumptions, changed CAD and evidence. | Minutes by person and activity, tool spend, accepted revision or rejection reason. Keep first-family setup visible. |
| Decide whether to repeat | For the next comparable order, compare actual contribution and human time with order one and the buyer's previous approach. Include every failed trial in the pilot totals. | Repeat order, price accepted, open defects, realized margin, and what could be reused without another engineer reconstructing it. |

**Example quote arithmetic in USD.** At a hypothetical $150 fee, retaining $75 for overhead and profit and allowing $15 for nonlabor delivery costs leaves $60 for engineering labor. At a loaded $60/hour that's one hour across intake, design, review and revisions. Two hours at that rate leaves only $15 after direct costs. These are trial assumptions. Obtain a buyer's price response and measure actual effort before treating the service as economical. Track shared platform investment separately and recover it across credible order volume.

**Decision after three comparable paid jobs.** As a pilot target, continue investing in that family if customers accept the work, delivery stays inside the quoted labor allowance, and reuse cuts the effort of subsequent changes at the same quality. If buyers pay but review consumes the budget, improve the specific check that took the time. If interviews produce praise but no paid briefs, change the offer or audience before investing in another design family. A buyer asking for a repeat unit with physical acceptance would open a separate hardware pilot.
