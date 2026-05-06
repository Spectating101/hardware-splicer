# Video Repair Playbook

Source: Fixing a broken USB desk fan that will not spin
Channel: Repair video reference
URL: https://www.youtube.com/results?search_query=usb+desk+fan+repair+not+spinning

## Pattern
- Pattern: Board-level electronic fault finding (`board_level_fault_finding`)
- Pattern confidence: 0.8
- Circuit-AI device family: Small DC motor / actuator gadget (`small_dc_motor_gadget`)
- Can-follow score: 0.93
- Difficulty: hard_to_expert

## Watch Map
- before disassembly: device model, initial symptom, all labels, connector orientation, missing screws or parts
- first board view: top-side board photo, bottom-side board photo, chip markings, connector labels, corrosion/burn areas
- before power test: input voltage, polarity, rail-to-ground resistance, current limit setting
- after repair: retest result, current draw, thermal behavior, remaining symptoms

## Recreation Flow
1. capture symptoms and board history
   - Circuit-AI support: image scan, board role inference, AOI defect candidates
   - Done when: photos and notes are sufficient to reassemble and compare
2. inspect under magnification
   - Circuit-AI support: image scan, board role inference, AOI defect candidates
   - Done when: operator records pass/fail result
3. check input resistance and obvious shorts
   - Circuit-AI support: repair guide measurement plan and stop conditions
   - Done when: operator records pass/fail result
4. inject or apply current-limited power only after polarity is known
   - Circuit-AI support: repair guide measurement plan and stop conditions
   - Done when: rails and current draw are within expected limits
5. divide the circuit into power, control, IO, and load sections
   - Circuit-AI support: repair guide measurement plan and stop conditions
   - Done when: rails and current draw are within expected limits
6. replace or rework only after measurements isolate the fault
   - Circuit-AI support: fault candidate playbooks and validation gates
   - Done when: fault is confirmed fixed by measurement, not only by appearance
7. thermal and functional retest after repair
   - Circuit-AI support: fault candidate playbooks and validation gates
   - Done when: fault is confirmed fixed by measurement, not only by appearance
8. Document before touching
   - Circuit-AI support: repair encyclopedia diagnostic branch
   - Done when: device state and wiring are reproducible
9. Unpowered inspection
   - Circuit-AI support: repair encyclopedia diagnostic branch
   - Done when: no immediate stop-condition damage found
10. Power path check
   - Circuit-AI support: repair encyclopedia diagnostic branch
   - Done when: rails are present, stable, and not current-limited
11. Output/load isolation
   - Circuit-AI support: repair encyclopedia diagnostic branch
   - Done when: dummy load switches correctly and real load measures sane resistance

## Quality Gates
- no unknown input voltage or polarity
- no powered testing before rail-to-ground resistance check
- repair action tied to a confirmed fault candidate
- post-repair thermal and functional test recorded
- disconnect power before inspection
- start every powered test with a current-limited supply when possible
- label connector polarity and voltage before reconnecting loads
- treat unexpected heating as a fault; power only briefly under current limit while measuring

## Copyright Boundary
- Use the linked video as a reference source; do not clone the creator's edit, narration, or exact transcript.
- This playbook is an independent safety and repair workflow derived from observed repair intent and Circuit-AI evidence.
