# The mission page

`/engineering/missions` in the Next workbench. It is where a person reads a fabrication mission, makes the two
decisions that are theirs, and takes the result. The agent contract is [`AGENT_MISSION.md`](AGENT_MISSION.md); the
state machine behind it is in the mission section of [`MACHINE_PROJECT_SPINE.md`](MACHINE_PROJECT_SPINE.md).

## The one design rule

**Say who established each thing.** A mission has three kinds of voice, and a verdict is only as strong as whoever
established it, so the page never shows a verdict without it:

| Voice | Colour | What it is |
|---|---|---|
| You | amber | the goal, parts, budget and requirements; acceptance; evidence only a person can give |
| Agent | fuchsia | proposals: designs, repairs, requests, the reason it ended the mission |
| Hardware Splicer (HS) | cyan | the checks it ran itself, its reading of your parts list, its package |

- The verdict card shows **"Established by"**: *HS checked this*, *HS counted this*, or *The agent's word, not
  checked*. An agent-asserted stop (for example a safety concern) has a dashed border and says HS did not check it.
- The agent's own wording of the reason is shown separately, labelled *The agent wrote*, never under HS's name.
- A note the agent recorded without a request is listed as *Concerns the agent recorded*, never as something waiting
  on you.
- What is established about the physical world (works on real hardware, flashing, powering) is on every mission, read
  from the mission itself. READY says *Ready for you to build* and then *Still yours to do*; it does not say "done".
- Free-text constraints are labelled *noted, not enforced by HS*. Structured requirements are labelled as enforced.
- The list has a status bar per mission: green ready, blue a stop HS checked, amber the agent's word or waiting on
  you, grey stopped.

## What a person can do here

| Action | How it is protected |
|---|---|
| Read any mission and its full evidence trail | read-only; refreshes itself every few seconds while an agent works |
| **Start a mission** from a goal and a typed parts list | needs the operator token; the backend names the token's owner as the opener, never a name in the request. Before it opens, the page shows how HS reads each line (matched, a different board, a generic word, a part number it cannot place, no data) through `POST /v1/devices/parts-reading`, which reads and nothing else |
| Accept a mission (once) | needs the token; the identity on the record comes from the token |
| **Answer a measurement request** by typing the reading | needs the token. HS builds the evidence envelope itself from what was typed, then applies every check `supply_evidence` applies: bound to this mission and need, used once, compared with the requested range. A reading out of range is recorded, shown, and leaves the request open. A typed reading is the person's own report; no instrument is recorded |
| Build and download the package | deterministic; the page shows the package's sha256, which is the hash of the downloaded ZIP |
| Open a review of the READY design, and **accept or reject it** | needs the token. A review that adds or changes a mission design can be decided only by a verified person, however it was opened; the decider on the record is the token's owner. It adds the design to the project's record as a new revision and authorizes nothing physical |

An accepted mission with no design yet shows how to point an agent at it. A mission's donor hardware is shown with each
fact's grade (measured by a person, from a document, observed, the agent's claim), what is still missing, and the
agent's findings, which are labelled as observations and never as measurements.

Refusals come back as text on the page, and a refused action changes nothing. The token field stays put while you type,
so a mistyped token can be corrected, and only collapses to "Token set · Change · Forget" when a token was already set
before the panel appeared.

## Not built yet

- A view of what accepting the staged review will change (the review's diff). The page says what accepting does in words.
- Editing a mission's structured requirements and measurements when starting it; today those come through the API.
- Deciding other kinds of reviews here. They stay in Project review.

## Known gap outside this page

The older review decision route (`POST /v1/projects/{id}/reviews/{id}/decision`) takes the decider's name from the
request body for reviews that are not mission designs. That is how the Project review console works today and this
page does not change it, but it means such a review is not decided by a *verified* person. Mission designs are
protected; the rest are not.

## Checks

`e2e/missions.spec.js`, run with `bash scripts/verify_device_frontend.sh real missions` against a production build and
the real backend, with a throwaway operator token registered for the run. It covers: accepting (a wrong token is
refused), an agent finishing a mission while the page follows, the package's hash, opening and deciding the review
(refused with no token or an unknown one), starting a mission from an awkward parts list, answering a measurement out of
range and then in range, and the donor view.
