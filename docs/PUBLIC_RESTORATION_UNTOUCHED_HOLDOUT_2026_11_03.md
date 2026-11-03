# New public restoration holdout — source evidence and falsification design

**Frozen for first engine run on November 3, 2026.** Public sources are independently linked below; this is a **text-based replay of real public repair records**, not footage that HS watched or hardware that HS repaired.

Previous development cases (original Game Boy no power, 2015 MacBook USB-C, iPhone 6s charge flex and Switch OLED USB-C/no HDMI) were explicitly excluded. New holdout blob is pinned at \`b2441fb0fbdeb594e33a4f8f01deda25b3b3096a\`, and the original Circuit-AI engine is frozen at Git commit \`eb60037fb16e4b3696c4ad8197e5202606855caf\`; CI refuses changed source code or source case records. Outcome-blind inputs were predeclared before engine execution and are not modified after results.

## Cases and what the sources really show

| Case | Initial fault | Discriminating source observation or later intervention | Source's reported outcome | Integrity limitation |
| --- | --- | --- | --- | --- |
| [2020 iPhone SE](https://www.ifixit.com/Answers/View/701499/iPhone+won't+turn+on+with+charging+port+connected) | Phone won't boot after charge-port flex reassembly; boots if disconnected | Original replacement flex reportedly functioned before full reassembly; owner found removing a bracket above port allowed operation | **Owner says fixed** after bracket was reattached | Unmeasured mechanical/electrical mechanism; not proof that a known-good or bad port was the root cause |
| [Samsung NP-R580](https://www.ifixit.com/Answers/View/731169/Not+turning+on+or+charging) | Grinding noise followed by total loss of laptop charge/power | Owner subsequently tested charger cable and reported no electrical output; reply requires isolating adapter brick from cord | **No final fixed laptop reported** | No numeric photo/voltage log, original grinding symptom unresolved |
| [Original Switch dock](https://www.ifixit.com/Answers/View/503051/Fixing+the+Nintendo+Switch+Dock+(no+signal-LED+blinking)) | Dock LED blinks and docked HDMI/charging drops, direct charging works | Second dock behaves the same. Owner later reports dock plus adapter work with a different Switch, whereas original USB-C plug works only with cable movement | **Console USB-C port suspected; no original-owner repaired Switch** | Cross-device comparison makes intermittent connector plausible, not a proven component replacement or HDMI post-repair test |
| [HP Deskjet 842C](https://www.ifixit.com/Answers/View/282696/Printer+cartridges+stuck,+wont+move+back+to+print+location) | Ink carriage sticks to service side after changing cartridge | Original owner reports mechanical release trick restored carriage travel | **Movement restored; complete print test not documented** | The forum workaround involves disconnecting AC while the carriage is moving. **Not an HS-endorsed or safe automatic procedure** |
| [Game Boy Color](https://www.ifixit.com/Answers/View/676743/Cannot+get+sound+from+the+main+speaker) | Built-in speaker silent; headphones, display and games still work | Owner replaced two speakers and reported continuity of speaker, cables and jack disconnect path, yet still no built-in sound | **No owner-confirmed fix** | Expert advice about headphone switch, ground or capacitor is not measured proof |
| [Syma X5C original owner](https://www.ifixit.com/Answers/View/273962/How+do+I+fix+my+Drone+that+won't+lift+off) | Ground-impact crash; motors/props spin but drone won't lift | Other posters discuss motors, gear, calibration and propeller orientation **on their own aircraft** | **Original X5C owner never confirmed a working fix** | Not legitimate to assign a different commenter's successful repair to original poster |
| [Different commenter, Syma X5SW](https://www.ifixit.com/Answers/View/273962/How+do+I+fix+my+Drone+that+won't+lift+off) | X5SW tilted and failed to fly after propeller replacement | X5SW commenter reports blade positions compared with markings on original box and reordered | **That X5SW owner reports flying again** | Same web page but **different person and different drone**. Self-reported flight is not certified airworthiness |

Two symptom-chronological checkpoints are submitted for every case. The final outcome, selected intervention and expected device classification are held in a separate oracle and used **after** both model calls. Input notes identify uncertainty, unsafe procedures, and lack of actual measurements, rather than supplying final cause.

## Scoring discipline

The published independent report must show:

1. **Market category exact-match:** only for the four cases whose expected product categories already exist in the current market classifier, e.g., phone, laptop, modern console, retro handheld. The printer and drones are **unknown/uncovered** categories and are excluded from the exact-label denominator, not falsely counted as wins or losses against a nonexistent label.
2. **Diagnostic family exact-match:** only for the predeclared iPhone, Samsung laptop and Switch cases whose existing source code contains those family definitions. Do not claim model-level success for Game Boy Color speaker just because the original Game Boy power-family was improved previously.
3. **Keyword sanity check:** whether generated diagnostics mention any predeclared source-relevant mechanisms. This is an intentionally **weak lexical proxy**; generic symptom echoes and broad advice do not establish cause accuracy.
4. **Software workflow verdict and first fault:** print every raw case result, including inappropriate route, wrong top diagnosis, or overconfident \`solvable_now\` on an unresolved fault.
5. **Source product state:** owner self-report only; distinguish full claimed fixes, partial results and no reported repair. This outcome **does not** mean HS physically repaired a device.

The holdout may reveal weak routing or poor out-of-domain behavior. Preserve observed failures; do **not** patch the same engine then re-label this holdout as a new independent evaluation. A further routing fix requires an entirely separate pre-registered future holdout or formal cross-validation partition.

## Physical and operational limits

No user-owned device, actual photos, DMM readings, motors, flight controllers, batteries, or measured repairs were part of this study. A source forum post is a public observation, not guaranteed root-cause evidence. No drone flight, autonomous power-on, moving motor, live printer jam intervention, board rework, smartphone battery intervention or resale action is authorized. In particular, never replicate the HP owner's live-powered carriage-reset trick without qualified safety procedures; a power-isolated inspection is the safe diagnosis starting point.

The executable source is \`scripts/bench_hs_public_restoration_holdout_001.py\` calling the **existing** \`apps/circuit-ai/src/intelligence/repair_case_evaluator.py\`, \`RepairEncyclopedia\` and \`BoardSessionStore\`. Independent verification does not import the scorer and recomputes source chronology, all 14 exact input hashes, scoring denominators, and physical-authority restrictions.
