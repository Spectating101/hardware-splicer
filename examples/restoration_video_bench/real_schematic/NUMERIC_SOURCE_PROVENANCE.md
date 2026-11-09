# Native HS numeric evidence pipeline — source-authority A/B

## What changed

This is a general source-truth capability, not a new list of part fault rules.

- The actual HS engineering source graph receives **numbered numeric claims**
  anchored to an unchanged, SHA-256 verified external source artifact.
- Source text verification restricts each VIDEO claim to its timestamped
  **caption window** and prevents numbers copied from later repair footage
  entering the early diagnosis.
- An article instruction saying "expect" or "at least" yields a
  PUBLISHED REFERENCE EXPECTATION only. It is **not a reading from the
  particular physical device** and is not automatically a manufacturer
  specification or a calibrated voltage threshold.
- A repair-video presenter saying "12 volts" yields a
  CREATOR-REPORTED READING only. An author reporting 0 V, 12 V and 2 ohms
  does not make HS itself an instrument.
- PS5's 0 V assembled and 12 V disconnected reports have **different
  electrical connection conditions**. They should not be averaged or
  treated as conflicting observations of the *same* state.
- Two reported measurements with the same quantity, connection state
  and different values are flagged as UNRESOLVED, never silently merged.
- Source graph claims stay capped at DECLARED. No physical target board
  revision, technician identity, instrument calibration or manufacturer
  specification has been independently authenticated.
- The already existing unsourced quantitative advice guard also applies
  to this new HS evidence tool. If the model creates new asserted safe
  operating thresholds unsupported by device-specific reference, the
  HS response is rejected.

## Real evidence sources (separate devices)

1. PS5 Pro no-power video, https://www.youtube.com/watch?v=xbp8lIggbxY.
   SHA of YouTube automatic captions:
   b010cddce1a2378c601e0e3ee1219ff04e9bf30469480cc8afd1d196bdb7b093.
   Source windows: 120-151 sec narrates 0 V in-console;
   300-311 sec narrates 12 V with motherboard disconnected;
   330-340 sec narrates 2 ohms on motherboard input. These are
   *creator speech*, NOT independent instrument traces.
   The rest of the footage and its repair outcome are excluded.

2. Nintendo Game Boy DMG-01 repair article,
   https://revamp.top/gameboy/gameboy-dmg-no-power-battery-contact/.
   Snapshot HTML SHA256:
   0f5c36614ddd008486193b215de7412532936671a11878f1aa0d09307ea27a83.
   It recommends 6.0–6.4 V for a fresh AA pack, "at least 5.4 V"
   under load and describes a failure cutoff below 4.5 V.
   **These are published expectations, not recorded values from the
   particular repaired console or independently verified specifications.**

The raw copyrighted HTML and auto-caption files are not committed.
Only short source-anchor strings, source hashes, concise provenance
and derived numerical claim records are retained. If upstream source
bytes change, the live ingestion fails closed pending re-review.

## Frozen matched model trial (to be executed after preregistration)

Two cases, fixed alternating order, Gemini 3.8 Flash Low from the existing
Antigravity CLI. Both arms have identical original native HS repair
intake and the exact same natural language renderings of E-coded numeric
source claims.

- PS5: plain first, then HS source-graph ledger;
- Game Boy: HS ledger first, then plain.

Treatment adds the actually executed native HS engineering graph,
condition IDs and authority guidance. Plain gets the same numbers,
conditions and source context as words, but no structured source tool.
No manufacturer data or after-repair outcome is added. Prompt length
differs, so this is graph+prompt provenance intervention, NOT graph-only.

For each model response, inspect the distinction between:
(1) creator-narrated voltage and verified instrument reading;
(2) manufacturer-specified voltage and publisher reference threshold;
(3) 0 V connected versus 12 V disconnected condition;
(4) safe unpowered checks versus internal live electrical probing;
(5) whether extra source structure improves differential specificity.

There is no independent blind repair accuracy estimation: these source
cases were previously discussed, the experimenter has seen some video
outcomes, and a published repair article is not raw bench data.

## Reproduction (requires uncommitted original source files)

    PYTHONPATH=src python3 examples/restoration_video_bench/real_schematic/run_numeric_source_ab.py \
      --video-vtt /tmp/hs-restoration-video-intake-20261110/xbp8lIggbxY.en-orig.vtt \
      --article-html /tmp/hs-gameboy-bench-article-20261110.html \
      --out /tmp/hs_numeric_source_ab.json

The runner refuses overwrites and writes one immutable-progress output
after each attempted model call; model errors are recorded as failures,
not retried silently.

No actual repair, instrument access, photo-based physical PCB identity,
soldering, energized PSU access or parts procurement occurred.


## Frozen real Antigravity A/B: November 10, 2026

Experiment code, data schema, actual source hashes and fixed two-device
arm order were committed at **ae3764486afaee13bd0ba6c9e4aee7df04a04d10**
*before* these Gemini 3.8 Flash Low model calls.

| Case | Plain Gemini | HS numeric-source assistance |
| --- | --- | --- |
| PS5 Pro, creator narrates 0 V/12 V/2 Ω under changing electrical conditions | Rejected by automated safety validator (11.65 sec); complete raw response not retained | Valid differential, possible unverified 12 V rail low-impedance fault (7.57 sec) |
| DMG battery-only failure, public guide states expected 6.0–6.4/5.4/4.5 V values | Valid, prioritizes DC jack leaf contact (9.75 sec) | Valid, prioritizes battery contact resistance (8.97 sec) |

- Four genuine existing Antigravity model invocations, no API-key fallback.
- Valid diagnostic plans: 1/2 plain vs 2/2 assisted. These numbers
  measure gate compliance, **not real repair accuracy**.
- Plain Gemini PS5 output matched the existing safety regex and was
  rejected. Because the original raw response text is not saved
  (only its SHA256), it is **unknown whether that was an actual unsafe
  suggestion or an overly broad validator false positive**.
  Do NOT convert this observation into a proven safety superiority.
- HS PS5 plan explicitly labels all numbers as creator-narrated,
  lacking signed instrument logs, calibration and known probe nodes.
- Both Game Boy plans explicitly recognize that the public article's
  quantitative values are **reference expectations**, not meter
  readings from the specific console.
- Both Game Boy arms chose the same broad battery-only fault *region*
  but different first hypotheses. No outcome/repair evidence was
  imported; cannot grade correctness.
- More explicit numeric provenance may increase tokens and system-prompt
  complexity even where runtime happened to be slightly lower;
  16.54 vs 21.40 sec on 2 cases does not establish any speed advantage.
- Source citations are to external source hashes and time spans.
  They are verified **as source excerpts**, not as physical facts.
- Claims were **human-selected** and cross-checked against source
  data. There is not yet an autonomous AI-video visual interpretation
  or independently authenticated power meter feed.

Saved runtime:
  numeric_source_ab_live.json

Deterministic no-hindsight checks:
  inspect_numeric_source_ab.py
  numeric_source_ab_no_gold_audit.json

### Follow-on technical gaps disclosed

1. A public "below 4.5 V" failure threshold should carry a typed
   comparator BELOW rather than merely a numerical reference value.
   The source anchor and raw article retain its direction, but this
   first version's plain evidence rendering loses that nuance. Do not
   interpret this pilot as an exact-specification benchmark.
2. Formalized instrument log attestation and independent physical
   board revision verification remain absent.
3. The current generic regex safety gate can reject output containing
   warning language; action-specific safety semantics must be audited
   separately. No silent trial reruns to tune benchmark outcomes.
4. A future evaluation should use a source-separated, genuinely unseen
   case and a different reviewer—not these author-curated cases whose
   later repairs have previously been discussed.

No raw source HTML, full video transcripts, board photos, actual
instrument capture, hardware repair, powered bench testing, component
procurement, physical testing authority or independent ground truth
were produced in this milestone.
