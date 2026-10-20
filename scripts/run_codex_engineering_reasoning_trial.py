"""Live ChatGPT-authenticated Codex decisions using actual HS tool receipts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.codex_chatgpt_llm_adapter import CodexCliAdapter
from hardware_splicer.engineering_reasoning_agent import run_engineering_reasoning_agent


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cli-js", type=Path, required=True)
    p.add_argument("--case", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-steps", type=int, default=4)
    args = p.parse_args()
    case = json.loads(args.case.read_text(encoding="utf-8"))
    adapter = CodexCliAdapter(cli_js=args.cli_js)
    result = run_engineering_reasoning_agent(
        case, llm_callable=adapter, max_steps=args.max_steps
    )
    # Adapter identifies itself as a live model, unlike an injected test double.
    result["codex_chatgpt_cli_invoked"] = True
    result["separate_api_key_used"] = False
    result["any_real_model_actions"] = bool(result["steps"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "status": result["status"],
        "model_steps": len(result["steps"]),
        "actions": [s["model_action"] for s in result["steps"]],
        "live_model_actions": result["any_real_model_actions"],
        "physical_release": result["physical_release"],
        "output": str(args.out),
    }))
    return 0 if result["status"] == "MODEL_FINISHED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
