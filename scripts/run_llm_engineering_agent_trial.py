"""Actual local-LLM next-action engineering trial, or scripted oracle tests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.engineering_agent_trial import OllamaJsonPolicy,run_agent_trial


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--case",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--model",default="qwen2.5:7b-instruct")
    parser.add_argument("--rounds",type=int,default=6)
    parser.add_argument("--max-tokens",type=int,default=850)
    parser.add_argument("--timeout",type=int,default=90)
    args=parser.parse_args()
    case=json.loads(args.case.read_text(encoding="utf-8"))
    run=run_agent_trial(case,OllamaJsonPolicy(
        model=args.model,max_tokens=args.max_tokens,timeout=args.timeout,
    ),max_rounds=args.rounds)
    args.out.parent.mkdir(exist_ok=True,parents=True)
    args.out.write_text(json.dumps(run,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
    print(json.dumps({
        "model":run["model_name"],
        "rounds":run["llm_decision_rounds"],
        "actions":run["model_actions"],
        "passed_bounded_design_oracle":run["bounded_conditional_design_accepted"],
        "complete":run["completed_agent_loop"],
        "issues":(run["independent_audit"] or {}).get("issues"),
        "model_provider_errors":run.get("model_provider_errors"),
        "physical_product_verified":False,
        "output":str(args.out),
    },indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
