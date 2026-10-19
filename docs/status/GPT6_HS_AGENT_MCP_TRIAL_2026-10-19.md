# GPT-6 interactive salvage mission: independent engineering checkpoint

Date: 2026-10-19 (Asia/Taipei). Base: PR #138 at commit 48b12b2948ee0b17bb4ec95dfbb37bbe829cc59d.

## Honest scope

GPT-6 acted as an engineering agent through a real, interactive canonical MCP session on Optiplex: it discovered the interface, read actual mission context, authored two different proposed designs, ran their checks, read the hashed run artifacts, downloaded both ZIP outputs, and recorded physical-evidence needs. The host prepared an isolated, accepted software-only mission and a credential-free MCP interface before those calls.

This is **not** a blind cold-agent usability benchmark. The model had read Hardware Splicer code, prior mouse examples, and the PR documentation earlier in the conversation. Its source packet was an earlier host-transcribed manufacturer/HID document study, not physical donor observations. The console transport and independent verifier were scripts; proposal reasoning and the 17 individual MCP calls were selected interactively by GPT-6, rather than performed by a prescribed demo-script sequence. No provider API token or exact model token counts are available.

## Source and mission

- Project gpt6-mouse-footcontrol; mission mission-6d5af3fc1aba4db0
- Source upload-b98f9a76a04dc4a97add, packet SHA-256 b98f9a76a04dc4a97addf69fb25d3e54255c03d5a6b01052ef2f5c2c8d4057c5
- Original source packet: docs/status/generated/cold-usb-mouse-2026-10-19/SOURCES.md
- Two candidate slots, three software-job budget; two jobs used.
- A separate MCP SDK2 environment was required because the repository's historical .venv uses the incompatible SDK1.

## Actual engineering decision

| Candidate | Design | Check | Physical warnings |
| --- | --- | --- | --- |
| intact_lever | Preferred intact mouse with separate supported pedal frame, independent return, mechanical travel stop; no electrical modification | 7 of 7 normalized-event scenarios passed | 4 |
| remote_contact | Conditional alternative using donor USB board with remote switch contact; would require evidence of internal contacts, no generated wiring | 7 of 7 normalized-event scenarios passed | 5 |

Both generated software review bundles were downloaded from the real MCP endpoint and independently extracted and replayed from the delivered exact bytes. Each generated one symbolic activate action in the example run, not a real OS input. No physical device was powered, connected, examined, modified, or actuated.

| ZIP | SHA-256 | Bytes |
| --- | --- | ---: |
| intact_lever-review.zip | 534765fcf1c827133065f3ea2f6a606b1c746f5dfbba447306d0e6c7121fc22b | 5,070 |
| remote_contact-review.zip | 2d286e117c1f029d9bb2139226955f652b9b0bc57066921e05c50eca1337db55 | 5,052 |

## Retained status

The model completed **17 MCP calls and no HTTP/tool errors** (excluding scripted host preparation, independent verification, and previous repo work). Read-only delivery inspection listed four currently available files: two check JSONs and two software review ZIPs. There was no READY build package, and the prototype generation gate was BLOCKED. The mission reached event sequence 10; physical correctness is UNPROVEN; neither power-on nor fabrication is authorized.

The agent recorded two specific open evidence requirements:

1. BLOCKED_NEEDS_REVERSE_ENGINEERING: human identification of the actual salvaged device, its condition and permitted USB/host-event mapping; the Logitech exemplar does not establish specimen identity.
2. BLOCKED_NEEDS_PHYSICAL_MEASUREMENT: nonpowered specimen-specific mouse-button travel and force, support geometry, frame/return/stop and cable-strain observations and separate suitability assessment before fabrication.

**Recommendation:** Keep the intact external-actuator design as the preferred *proposal*, because it minimizes additional electrical unknowns. Advance with a read-only, separately authorized HID/evdev-to-normalized-event host bridge and verified real donor observations. Neither is proven here.

## Inspectable evidence

- AGENT_MCP_TRACE.jsonl contains the chronological real MCP request/response log, including model-authored design specs, hashed run results and returned ZIP bytes.
- VERIFICATION.json contains the independent ZIP/check summary. The two ZIPs are the actual downloaded bundles, not recreated equivalents.
- VERIFY.py performs a second, standard-library-only hash verification and seven-scenario replay against each archived delivered program. It does not access hardware.

Do not report a 48-to-17 or 9-to-17 usability improvement: the task setup, prior model knowledge, level of coaching, and measured call scopes differ. Do not claim physical correctness or readiness from symbolic software tests.
