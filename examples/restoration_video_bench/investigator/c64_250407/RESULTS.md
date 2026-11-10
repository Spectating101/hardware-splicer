# Frozen C64 Repair Investigator pilot — actual results

Experiment registered before model calls at:
e3a609a31d2ee788f1362e677a82218cdbd991b1.

## Real source and model calls

- Video: Jan Beta, Commodore 64 ASSY 250407 blank-screen repair,
  https://www.youtube.com/watch?v=mkGEXlQ84wk.
- Actual auto-generated YouTube English VTT file pinned SHA256:
  59f29eaf1c236b2f621facd9e810619be657cc4cde9ac3e5977e73d42cfe0dcb.
- Source: bwack's CERN-OHL-1.2 250407 KiCad reverse-engineered
  replica, Git revision 9bf17bb868248b12fb12210d66be3a37ec4ab832.
- KiCad export 9.0.2: 230 components, 250 nets; all 17 selected net
  records and 199 pin instances reexported exactly. Source has
  annotation warnings, and physical board revision is not verified.
- Both model arms: Gemini 3.8 Flash Low, actual Antigravity CLI calls,
  same E-coded video evidence and stages, zero direct paid API fallback.
- Source stage 1: first 120 seconds, opening narration only.
- Source stage 2: next 90 seconds, pre-repair inspection only.
  No later creator-reported repair result was passed.

## Source-frozen real model comparison

| Evidence phase | Plain Gemini first-ranked mechanism | HS + source-KiCad first-ranked mechanism | Plain seconds | HS seconds |
| --- | --- | --- | ---: | ---: |
| 0–120 seconds | Missing critical ICs prevent operation | Missing functional ICs inhibit startup, video and clock pathways | 10.22 | 8.88 |
| 0–210 seconds | Missing main processing/support silicon prevents boot | Missing CPU, clock, logic and bus ICs prevent clock generation and bus operation | 10.18 | 10.92 |

Both arms had **2/2 valid, source-cited JSON diagnostic responses**.
Total inference seconds: plain 20.40s, HS-assisted 19.80s.
This difference is too small and the sample too weak to establish
a speed or accuracy advantage. Treatment prompts include additional
actual schematic facts and different instructions.

## Measured process difference

On the opening, plain Gemini proposed a comprehensive inspection and
unpowered supply-rail resistance measurement. The HS-assisted
model first recommended clear unpowered photographs of front/back
board, identification of vacant IC sockets, and verification of actual
PCB revision before internal tests.

After 120–210 seconds, plain suggested continuity/short checks
around supply nets and desoldered KERNAL pads; HS-assisted first
recommended board/rework photographs and verification of the
silkscreen marking.

The latter is a more defensible safety/provenance boundary given
the schematic is a replica and physical target revision is unverified.
It is **not proven more accurate** in locating the ultimate fault,
and no physical actions were undertaken.

## Interactive report

The standalone browser report is investigation.html. It offers:
- functioning control to switch plain vs HS model;
- functioning control to switch opening vs later inspection stage;
- original evidence IDs and timestamped short EDITORIAL paraphrases;
- real selected KiCad net/pin references with no invented conduction
  through components;
- case revision, caption source SHA and genuine source graph hash;
- diagnosis, next test and explicit uncertainty for every stage;
- browser-side export of the redacted machine-readable record.

Browser smoke testing verified BOTH controls changed visible content
with Google Chrome headless. All reporting is offline; no network
or model inference occurs while opening or using the HTML.

**Source copyright:** The full caption text supplied to the model
is not included in this public repository artifact. Public evidence
strings are brief human-authored paraphrases (total <200 words) with
the original excerpt hashes and timecodes retained. The full original
model-input record remains on the authorized local Optiplex under
/tmp/hs_c64_full_original_inference.json, not committed. To reproduce
the exact full original prompts, obtain the YouTube caption source
matching the pinned SHA-256 and rerun the source bounded experiment.

- Public redacted record: live_investigation_public.json
- Source-independent offline audit metadata: offline_audit.json
- Original private model/input receipts retained locally; NOT publicly
  redistributed.

## Honest acceptance result

**Pass:** one working, real-source end-to-end HS workflow from video
observations and actual engineering topology through source-grounded
two-stage model analysis to a functional inspected HTML report.

**Not passed:** independent device-repair success, physical board
revision verification, independently measured instrument readings,
video-frame visual understanding or significant advantage over
plain Gemini in fault accuracy.

The source graph did contribute *genuine* electrical reference
information. It did not prove that information improved the specific
root cause diagnosis. The technical next gate is independently
captured, source-authenticated bench measurements and a newly
adjudicated unseen device outcome.
