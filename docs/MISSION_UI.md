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
| Accept a mission (once) | needs the person's operator token; sent only in `X-HS-Operator-Token`, held in this tab's session storage; the identity on the record comes from the token, never from anything typed |
| Build and download the package | deterministic; the page shows the package's sha256, which is the hash of the downloaded ZIP |
| Open a review of the READY design | needs the token; the backend takes the author from the token. It opens a review only; it changes nothing in the project until a person accepts that review |

Refusals come back as text on the page, and a refused action changes nothing.

## Not built yet

- **Answering a measurement request from the page.** The request, expected range and instructions are shown, with
  how to answer through the API. A form needs a backend step that builds the physical-evidence envelope from a
  reading, so that the browser never has to reproduce the hash.
- **Opening a mission from the page.** Today an agent opens one from a goal and parts list. Starting from a typed
  parts list on the device page would connect the two.
- **Deciding the staged review on this page.** It happens in Project review.
- **Donor evidence and findings** have no view yet; the page ignores `donors` and `finding_offered` events beyond a
  timeline line.

## Checks

`e2e/missions.spec.js`, run with `bash scripts/verify_device_frontend.sh real missions`. The script registers a
throwaway operator token for the run. The spec accepts a mission as that person (and checks a wrong token is
refused), lets an agent finish it over the API while the page follows, downloads the package and compares its hash,
and opens a review.
