# Raw restoration video flexibility — first nine-domain challenge

This extends HS PR #318 and #319 to **nine genuinely distinct repair
domains**, not nine cases fitted to the original deterministic taxonomy.

The case manifest lists public YouTube videos across: A53 touch/data, Tab S6
Lite no-power, DeLonghi coffee machine mixed faults, DeWalt blower
intermittency, Bosch dryer slow heat, Canon DSLR no power, Reebok treadmill
no power, PS5 Pro mixed faults and Xbox Series S no power.

**Source boundary:** video title plus a manually paraphrased summary of up
to the FIRST 120 seconds of public English auto-captions, for eight videos;
Xbox uses title alone. No full video footage, late transcript, repaired
outcome, or testbench measurements supplied to predictor. Caption downloads
were kept in an uncommitted Optiplex temp directory. Results are provisional
and may contain caption or observer error.

**Native HS result:** native repair_intake normalizes all nine, while the
PR #318 code-based triage accepts zero of nine free-text cases without
preassigned observation codes. That is a limitation of this SPECIFIC engine
entrypoint, not proof about the entire HS agent system.

**External comparison:** evidence/gpt6_text_control_preoutcome.json stores
nine GPT-6 text-only case predictions authored in this ChatGPT conversation
and saved manually before later outcomes were reviewed. These are NOT HS
outputs, NOT automated video analysis, NOT repaired devices, and are not
claimed as independent blind science. They are a comparison for a future
actual flexible HS agent. All proposed physical repairs remain unauthorized.

**Runtime limitation:** Optiplex Claude Code authentication expired, Gemini
CLI was rejected, Codex launcher failed to install, and local CPU Qwen2.5
7B timed out. No frontier-model run was substituted. The next valid agent
experiment needs working inference and evidence-aware HS integration, not
simply more hardcoded rules.

Reproduce:
    PYTHONPATH=src python3 examples/restoration_video_bench/diversity/run_diversity.py \
      --out examples/restoration_video_bench/diversity/evidence/raw_rule_baseline.json \
      --agent-packet examples/restoration_video_bench/diversity/evidence/open_agent_packet.json

    PYTHONPATH=src python3 -m pytest -q tests/test_restoration_diversity.py

The separate score_external.py loads independently adjudicated final outcomes
only AFTER the prediction commit SHA and file digest have been published.
Resolved outcomes need evidence and reviewers; unknown or ambiguous outcomes
do NOT count as successful diagnoses. A creator-reported repair is not
independently verified electrical proof. No labels are included in this branch.
