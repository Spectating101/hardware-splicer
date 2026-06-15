"""Structured AI reasoning over circuit facts and salvage gates.

This is intentionally not a chatbot layer. The reasoner consumes extracted
circuit facts, functional salvage blocks, and measurement gates; an optional
LLM can propose engineering hypotheses, but deterministic verifiers decide
whether those claims are reusable, blocked, or unsafe.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.intelligence.testing_mode import testing_mode_enabled


SCHEMA_VERSION = "circuit_ai_reasoning.v1"


READY_WORDS = {"ready", "reuse_ready", "verified", "approved", "safe_to_connect"}
ASSERTIVE_SAFETY_WORDS = {"safe", "safest", "isolated", "isolation", "known safe", "low voltage"}
BOARD_CUT_WORDS = {"cut trace", "cutting trace", "cut traces", "cutting traces", "desolder", "sever trace", "isolate ", "isolation cut"}


PROVIDER_KEY_ATTRS = {
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "cohere": "cohere_api_key",
    "mistral": "mistral_api_key",
    "cerebras": "cerebras_api_key",
    "deepseek": "deepseek_api_key",
    "qwen": "qwen_api_key",
    "copilot": None,
}

GENERIC_DEFAULT_MODELS = {"command-r", "gpt-3.5-turbo"}
DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-flash"
DEEPSEEK_DEFAULT_BASE_URL = "https://api.deepseek.com"
QWEN_DEFAULT_MODEL = "qwen3.5-122b-a10b"
QWEN_DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
QWEN_DEFAULT_TEXT_ROTATION = (
    "qwen3.5-122b-a10b",
    "qwen3-max",
    "qwen3.5-plus-2026-02-15",
)
QWEN_DEFAULT_LOW_QUOTA_MODELS = ("qwen-plus", "qwen-plus-2025-07-28")
COPILOT_DEFAULT_MODEL = "gpt-4.1"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _dedupe(items: Iterable[Any], *, limit: int = 40) -> List[str]:
    kept: List[str] = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        kept.append(text)
        if len(kept) >= limit:
            break
    return kept


def _compact(value: Any) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _extract_json_object(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()
    try:
        parsed = json.loads(raw, strict=False)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw[start:end], strict=False)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def _string_contains_ready(value: Any) -> bool:
    text = str(value or "").lower()
    return any(word in text for word in READY_WORDS)


def _text_has_any(value: Any, needles: Iterable[str]) -> bool:
    text = str(value or "").lower()
    return any(needle in text for needle in needles)


def _module_installed(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _env_flag(name: str, fallback: bool = False) -> bool:
    raw = str(os.environ.get(name) or "").strip().lower()
    if not raw:
        return fallback
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return fallback


def _qwen_disabled(settings: Any = None) -> bool:
    return (
        _env_flag("QWEN_DISABLED")
        or _env_flag("QWEN_OUT_OF_QUOTA")
        or bool(getattr(settings, "qwen_disabled", False))
        or bool(getattr(settings, "qwen_out_of_quota", False))
    )


def _effective_model(provider: str, model: str, settings: Any = None) -> str:
    text = str(model or "").strip()
    if provider == "copilot" and (not text or text in GENERIC_DEFAULT_MODELS or text.startswith("deepseek-")):
        if settings is not None:
            configured = str(getattr(settings, "copilot_model", "") or os.environ.get("COPILOT_MODEL") or "").strip()
            if configured:
                return configured
        return COPILOT_DEFAULT_MODEL
    if provider == "deepseek" and (not text or text in GENERIC_DEFAULT_MODELS):
        if settings is not None:
            configured = str(getattr(settings, "deepseek_model", "") or os.environ.get("DEEPSEEK_MODEL") or "").strip()
            if configured:
                return configured
        return DEEPSEEK_DEFAULT_MODEL
    if provider == "qwen" and (
        not text
        or text in GENERIC_DEFAULT_MODELS
        or text.startswith("deepseek-")
        or not text.lower().startswith("qwen")
    ):
        return _qwen_text_candidates(settings=settings)[0]
    if provider == "qwen" and _qwen_model_is_blocked(text, _qwen_low_quota_models(settings)):
        return _qwen_text_candidates(settings=settings, requested=text)[0]
    return text


def _split_csv(value: Any) -> List[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _qwen_low_quota_models(settings: Any = None) -> List[str]:
    configured = (
        os.environ.get("QWEN_LOW_QUOTA_MODELS")
        or os.environ.get("QWEN_BLOCKED_MODELS")
        or (getattr(settings, "qwen_low_quota_models", None) if settings is not None else None)
        or ",".join(QWEN_DEFAULT_LOW_QUOTA_MODELS)
    )
    return [item.lower() for item in _split_csv(configured)]


def _qwen_model_is_blocked(model: str, blocked: Iterable[str]) -> bool:
    normalized = str(model or "").strip().lower()
    return any(normalized == item or normalized.startswith(f"{item}-") for item in blocked)


def _qwen_text_candidates(settings: Any = None, requested: str = "") -> List[str]:
    configured_rotation = (
        os.environ.get("QWEN_MODEL_ROTATION")
        or (getattr(settings, "qwen_model_rotation", None) if settings is not None else None)
        or ""
    )
    configured_single = requested or os.environ.get("QWEN_MODEL") or (getattr(settings, "qwen_model", None) if settings is not None else None) or ""
    blocked = set(_qwen_low_quota_models(settings))
    candidates: List[str] = []
    seen = set()
    for raw in [str(configured_single).strip(), *_split_csv(configured_rotation), *QWEN_DEFAULT_TEXT_ROTATION]:
        model = str(raw or "").strip()
        key = model.lower()
        if not model or key in seen or _qwen_model_is_blocked(model, blocked):
            continue
        candidates.append(model)
        seen.add(key)
    return candidates or [QWEN_DEFAULT_MODEL]


def _qwen_quota_error(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(
        marker in lowered
        for marker in (
            "allocationquota",
            "freequota",
            "free quota",
            "quota",
            "insufficient",
            "billing",
        )
    )


def circuit_ai_model_status() -> Dict[str, Any]:
    """Return non-secret runtime status for live circuit LLM calls."""
    try:
        from src.config import settings
    except Exception as exc:  # pragma: no cover - defensive startup path
        return {
            "status": "not_ready",
            "ready_for_live_model": False,
            "blockers": [f"settings unavailable: {exc}"],
            "selected": {"provider": None, "model": None},
            "providers": {},
            "dependencies": {},
            "capabilities": {
                "structured_circuit_reasoning": True,
                "deterministic_verification": True,
                "training_data_capture": True,
            },
        }

    provider = str(getattr(settings, "llm_provider", "") or "").strip().lower()
    configured_model = str(getattr(settings, "llm_model", "") or "").strip()
    model = _effective_model(provider, configured_model, settings)
    providers = {}
    for name, attr in PROVIDER_KEY_ATTRS.items():
        if name == "qwen":
            disabled = _qwen_disabled(settings)
            providers[name] = {
                "disabled": disabled,
                "api_key_configured": (not disabled) and bool(
                    getattr(settings, "qwen_api_key", None)
                    or getattr(settings, "dashscope_api_key", None)
                    or os.environ.get("QWEN_API_KEY")
                    or os.environ.get("DASHSCOPE_API_KEY")
                ),
            }
            continue
        providers[name] = {
            "api_key_configured": bool(attr and (getattr(settings, attr, None) or os.environ.get(f"{name.upper()}_API_KEY"))),
        }
    try:
        from src.intelligence.copilot_provider import copilot_provider_status

        copilot_status = copilot_provider_status(model if provider == "copilot" else None)
    except Exception as exc:
        copilot_status = {
            "status": "not_ready",
            "ready_for_live_model": False,
            "blockers": [f"copilot status unavailable: {exc}"],
            "providers": {"copilot_cli": {"ready": False}},
            "selected": {},
        }
    copilot_cli = copilot_status.get("providers", {}).get("copilot_cli", {})
    providers["copilot"] = {
        "api_key_configured": False,
        "oauth_or_cli_auth_configured": bool(
            copilot_cli.get("gh_authenticated") or copilot_cli.get("token_marker_configured")
        ),
        "cli_ready": bool(copilot_status.get("ready_for_live_model")),
    }
    dependencies = {
        "litellm_installed": _module_installed("litellm"),
        "openai_sdk_installed": _module_installed("openai"),
        "legacy_llm_manager_module": _module_installed("src.services.llm_service.llm_manager"),
        "legacy_model_dispatcher_module": _module_installed("src.services.llm_service.model_dispatcher"),
    }
    selected_key = bool(
        providers.get(provider, {}).get("api_key_configured")
        or (provider == "copilot" and providers.get("copilot", {}).get("cli_ready"))
    )
    blockers = []
    if not getattr(settings, "llm_enabled", False):
        blockers.append("settings.llm_enabled is false")
    if not provider:
        blockers.append("LLM provider is not configured")
    elif provider not in providers:
        blockers.append(f"unsupported LLM provider: {provider}")
    elif not selected_key:
        if provider == "copilot":
            blockers.append("copilot CLI/OAuth provider is not ready")
        else:
            blockers.append(f"{provider} API key is not configured")
    if not model:
        blockers.append("LLM model is not configured")
    if provider == "copilot" and not providers.get("copilot", {}).get("cli_ready"):
        blockers.extend(copilot_status.get("blockers") or ["copilot CLI provider is not ready"])
    elif provider == "qwen" and _qwen_disabled(settings):
        blockers.append("Qwen is disabled because QWEN_DISABLED or QWEN_OUT_OF_QUOTA is set")
    elif provider == "deepseek" and not dependencies["openai_sdk_installed"]:
        blockers.append(f"openai SDK is not installed for {provider} OpenAI-compatible calls")
    elif provider not in {"deepseek", "qwen", "copilot"} and not dependencies["litellm_installed"]:
        blockers.append("litellm is not installed in this runtime")

    ready = not blockers
    return {
        "status": "ready" if ready else "not_ready",
        "ready_for_live_model": ready,
        "blockers": blockers,
        "selected": {
            "provider": provider or None,
            "model": model or None,
            "configured_model": configured_model or None,
            "selected_provider_key_configured": selected_key,
            "copilot_cli_provider": provider == "copilot",
            "copilot_node_runner": copilot_status.get("selected", {}).get("node_runner"),
            "deepseek_native_openai_compatible": provider == "deepseek",
            "deepseek_base_url_configured": bool(
                provider == "deepseek"
                and (
                    getattr(settings, "llm_api_base", None)
                    or getattr(settings, "deepseek_base_url", None)
                    or os.environ.get("DEEPSEEK_BASE_URL")
                )
            ),
            "qwen_native_openai_compatible": provider == "qwen",
            "qwen_disabled": provider == "qwen" and _qwen_disabled(settings),
            "qwen_base_url_configured": bool(
                provider == "qwen"
                and (
                    getattr(settings, "llm_api_base", None)
                    or getattr(settings, "qwen_base_url", None)
                    or os.environ.get("QWEN_BASE_URL")
                )
            ),
            "qwen_model_rotation": _qwen_text_candidates(settings=settings, requested=model) if provider == "qwen" else [],
            "qwen_low_quota_models": _qwen_low_quota_models(settings) if provider == "qwen" else [],
        },
        "providers": providers,
        "copilot_runtime": copilot_status,
        "dependencies": dependencies,
        "capabilities": {
            "structured_circuit_reasoning": True,
            "deterministic_verification": True,
            "training_data_capture": True,
            "copilot_cli_provider": True,
            "deepseek_native_provider": True,
            "qwen_native_provider": True,
            "model_claims_are_advisory": True,
            "automatic_model_training": False,
        },
    }


def _deterministic_model_runtime() -> Dict[str, Any]:
    return {
        "status": "not_ready",
        "ready_for_live_model": False,
        "blockers": ["external LLM reasoning was not requested for this deterministic call"],
        "selected": {
            "provider": None,
            "model": None,
            "configured_model": None,
            "selected_provider_key_configured": False,
            "copilot_cli_provider": False,
            "copilot_node_runner": None,
            "deepseek_native_openai_compatible": False,
            "deepseek_base_url_configured": False,
            "qwen_native_openai_compatible": False,
            "qwen_base_url_configured": False,
        },
        "providers": {},
        "copilot_runtime": {
            "status": "not_checked",
            "ready_for_live_model": False,
            "reason": "skipped because LLM reasoning was not requested",
        },
        "dependencies": {},
        "capabilities": {
            "structured_circuit_reasoning": True,
            "deterministic_verification": True,
            "training_data_capture": True,
            "copilot_cli_provider": True,
            "deepseek_native_provider": True,
            "model_claims_are_advisory": True,
            "automatic_model_training": False,
        },
    }


class CircuitAIReasoner:
    """Create and verify circuit/salvage hypotheses from machine facts."""

    def __init__(
        self,
        *,
        llm_client: Optional[Any] = None,
        enable_llm: bool = False,
        model: Optional[str] = None,
        max_tokens: int = 900,
    ) -> None:
        self.llm_client = llm_client
        self.enable_llm = enable_llm
        self.model = model
        self.max_tokens = max_tokens

    def assess(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = payload or {}
        goal = str(body.get("goal") or body.get("requested_goal") or "understand and safely reuse circuit functions")
        analysis = _first_dict(body.get("analysis"), body.get("circuit"))
        if not analysis and body.get("mode") in {"circuit_board_system", "circuit_ai_board_intelligence"}:
            analysis = body
        salvage_plan = _first_dict(body.get("salvage_plan"), body.get("splice_plan"))
        functional_reuse_plan = _first_dict(body.get("functional_reuse_plan"))

        reports = self._functional_salvage_reports(body, analysis, salvage_plan)
        blocks = self._blocks_from_reports(reports)
        if not blocks:
            blocks = self._blocks_from_reuse_plan(functional_reuse_plan)

        facts = self._facts(goal, analysis, salvage_plan, reports, blocks)
        deterministic = self._deterministic_reasoning(goal, facts, blocks, salvage_plan, functional_reuse_plan)
        llm_result = self._llm_reasoning(goal, facts) if self.enable_llm else self._llm_not_requested()
        model_hypotheses = llm_result.get("hypotheses") or []
        model_splices = llm_result.get("proposed_splices") or []
        verified_model = self._verify_model_claims(model_hypotheses, model_splices, blocks, facts)
        final_hypotheses = self._merge_hypotheses(
            deterministic.get("hypotheses") or [],
            verified_model.get("hypotheses") or [],
        )

        verified_proposals = self._verified_proposals(
            deterministic.get("proposed_splices") or [],
            verified_model.get("proposed_splices") or [],
        )
        adapter_recommendations = self._adapter_recommendations(facts)
        proof = self._proof_readiness(
            goal=goal,
            facts=facts,
            blocks=blocks,
            adapter_recommendations=adapter_recommendations,
            verified_proposals=verified_proposals,
        )
        model_runtime = circuit_ai_model_status() if self.enable_llm else _deterministic_model_runtime()

        verified_rows = [*(verified_model.get("hypotheses") or []), *(verified_model.get("proposed_splices") or [])]
        blocked_count = len([row for row in verified_rows if row.get("verification", {}).get("status") == "blocked"])
        review_count = len([row for row in verified_rows if row.get("verification", {}).get("status") == "needs_review"])
        verifier_status = (
            "blocked_model_claims"
            if blocked_count
            else "model_claims_need_review"
            if review_count
            else "pass_with_gates"
        )
        if llm_result.get("backend", {}).get("status") == "llm_used" and not llm_result.get("backend", {}).get("raw_response_parsed", True):
            verifier_status = "model_output_unparsed"
        if facts.get("hard_safety_hold"):
            verifier_status = "safety_hold"

        return {
            "mode": "circuit_ai_reasoning",
            "schema_version": SCHEMA_VERSION,
            "goal": goal,
            "ai_integration": {
                "role": "structured circuit reasoner",
                "location": "circuit_graph_and_salvage_pipeline",
                "not_chatbot": True,
                "policy": "model claims are advisory until deterministic evidence gates verify them",
            },
            "model_runtime": model_runtime,
            "backend": llm_result.get("backend") or {},
            "input_summary": facts.get("summary") or {},
            "evidence_packet": {
                "candidate_blocks": facts.get("candidate_blocks") or [],
                "connector_contracts": facts.get("connector_contracts") or [],
                "known_part_evidence": facts.get("known_part_evidence") or [],
                "strict_block_id_required": True,
                "known_entry_points": facts.get("entry_points") or [],
            },
            "deterministic_trace": deterministic.get("trace") or [],
            "hypotheses": final_hypotheses,
            "model_hypotheses": verified_model.get("hypotheses") or [],
            "proposed_splices": verified_proposals,
            "proof_matrix": proof.get("matrix") or [],
            "proof_summary": proof.get("summary") or {},
            "recommended_first_action": proof.get("recommended_first_action") or {},
            "measurement_plan": proof.get("measurement_plan") or [],
            "recommended_next_actions": self._recommended_next_actions(
                deterministic.get("recommended_next_actions") or [],
                llm_result.get("recommended_next_actions") or [],
                facts,
            ),
            "adapter_recommendations": adapter_recommendations,
            "verifier": {
                "status": verifier_status,
                "blocked_model_claim_count": blocked_count,
                "needs_review_model_claim_count": review_count,
                "rules": [
                    "model block_id values must match exact known candidate block IDs",
                    "no reuse-ready claim passes while required evidence gates remain open",
                    "board-section salvage remains blocked until layout/continuity/isolation evidence exists",
                    "hard safety holds override all reuse proposals",
                    "entry points must match extracted connector references",
                ],
            },
            "learning_loop": {
                "operator_labels_needed": [
                    "accept_or_reject_hypothesis",
                    "measured_voltage_current_logic",
                    "actual_connector_pinout",
                    "splice_success_or_failure",
                    "post_build_function_value",
                ],
                "training_export_ready": bool(final_hypotheses),
            },
            "expert_training_record": self._expert_training_record(
                goal=goal,
                facts=facts,
                hypotheses=final_hypotheses,
                proposed_splices=verified_proposals,
                verifier_status=verifier_status,
                proof_summary=proof.get("summary") or {},
            ),
        }

    def _functional_salvage_reports(
        self,
        payload: Dict[str, Any],
        analysis: Dict[str, Any],
        salvage_plan: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        reports: List[Dict[str, Any]] = []
        seen = set()

        def add_report(report: Any) -> None:
            if not isinstance(report, dict) or report.get("mode") != "functional_salvage_assessment":
                return
            key = (report.get("schema_version"), report.get("board_id"), len(report.get("reusable_blocks") or []))
            if key in seen:
                return
            seen.add(key)
            reports.append(report)

        roots: List[Dict[str, Any]] = [payload, analysis, salvage_plan]
        for root in roots:
            if not isinstance(root, dict):
                continue
            add_report(root)
            add_report(root.get("functional_salvage"))
            for board in root.get("boards") or []:
                if isinstance(board, dict):
                    add_report(board.get("functional_salvage"))
            for row in root.get("functional_reports") or []:
                add_report(row)
        return reports

    def _blocks_from_reports(self, reports: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []
        for report in reports:
            board_id = str(report.get("board_id") or "board")
            for row in report.get("reusable_blocks") or []:
                if not isinstance(row, dict):
                    continue
                block = dict(row)
                block["board_id"] = str(block.get("board_id") or board_id)
                block["block_id"] = str(block.get("block_id") or block.get("circuit_block_id") or block.get("name") or "functional_block")
                block["connector_refs"] = [str(ref) for ref in block.get("connector_refs") or []]
                block["source_refs"] = [str(ref) for ref in block.get("source_refs") or []]
                block["capabilities"] = [str(cap).lower() for cap in block.get("capabilities") or []]
                block["evidence_gates"] = [gate for gate in block.get("evidence_gates") or [] if isinstance(gate, dict)]
                blocks.append(block)
        return blocks

    def _blocks_from_reuse_plan(self, reuse_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = []
        for key in ("ready_blocks", "top_blocks"):
            rows.extend(row for row in reuse_plan.get(key) or [] if isinstance(row, dict))
        blocks = []
        for row in rows:
            block = dict(row)
            block["block_id"] = str(block.get("circuit_block_id") or block.get("block_id") or block.get("name") or "functional_block")
            block["connector_refs"] = [
                str(entry).split(":", 1)[-1]
                for entry in block.get("entry_points") or []
                if str(entry).strip()
            ]
            block["capabilities"] = [str(cap).lower() for cap in block.get("capabilities") or []]
            blocks.append(block)
        return blocks

    def _facts(
        self,
        goal: str,
        analysis: Dict[str, Any],
        salvage_plan: Dict[str, Any],
        reports: Sequence[Dict[str, Any]],
        blocks: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        boards = [row for row in analysis.get("boards") or [] if isinstance(row, dict)]
        indexes = self._analysis_indexes(analysis)
        statuses = self._status_counts(blocks)
        caps = sorted({cap for block in blocks for cap in block.get("capabilities") or []})
        entry_points = self._entry_points(blocks)
        candidate_blocks = [self._block_reasoning_context(block, indexes) for block in sorted(blocks, key=self._block_rank)[:10]]
        connector_contracts = self._compact_connector_contracts(indexes, candidate_blocks)
        known_part_evidence = self._known_part_evidence(indexes, candidate_blocks)
        hard_safety_hold = salvage_plan.get("verdict") == "unsafe_hold" or any(
            report.get("verdict") == "unsafe_hold" for report in reports
        )
        if testing_mode_enabled():
            hard_safety_hold = False
        summary = {
            "board_count": int(analysis.get("board_count") or len(boards) or 0),
            "overall_readiness": analysis.get("overall_readiness"),
            "workflow_state": analysis.get("workflow_state"),
            "functional_report_count": len(reports),
            "functional_block_count": len(blocks),
            "known_connector_contract_count": len(connector_contracts),
            "known_part_evidence_count": len(known_part_evidence),
            "ready_block_count": statuses.get("reuse_ready", 0),
            "blocked_block_count": sum(count for status, count in statuses.items() if status.startswith("blocked")),
            "capabilities": caps[:20],
            "entry_points": entry_points[:20],
            "salvage_verdict": salvage_plan.get("verdict"),
        }
        return {
            "goal": goal,
            "summary": summary,
            "statuses": statuses,
            "capabilities": caps,
            "entry_points": entry_points,
            "candidate_blocks": candidate_blocks,
            "connector_contracts": connector_contracts,
            "known_part_evidence": known_part_evidence,
            "hard_safety_hold": hard_safety_hold,
            "boards": [
                {
                    "board_id": board.get("board_id"),
                    "primary_role": board.get("primary_role"),
                    "readiness": board.get("readiness"),
                    "component_count": len(board.get("components") or []),
                    "net_count": len(board.get("nets") or []),
                    "connector_count": len(board.get("connector_contracts") or []),
                }
                for board in boards[:8]
            ],
        }

    def _analysis_indexes(self, analysis: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        components: Dict[str, Dict[str, Any]] = {}
        connectors: Dict[str, Dict[str, Any]] = {}
        nets: Dict[str, Dict[str, Any]] = {}
        for board in analysis.get("boards") or []:
            if not isinstance(board, dict):
                continue
            sources = [board]
            raw = board.get("raw_structure") if isinstance(board.get("raw_structure"), dict) else {}
            if raw:
                sources.append(raw)
            for source in sources:
                for component in source.get("components") or []:
                    if isinstance(component, dict) and component.get("ref"):
                        components[str(component["ref"])] = component
                for connector in source.get("connector_contracts") or []:
                    if isinstance(connector, dict) and connector.get("connector_ref"):
                        connectors[str(connector["connector_ref"])] = connector
                for net in source.get("nets") or []:
                    if isinstance(net, dict) and net.get("net"):
                        nets[str(net["net"])] = net
        return {"components": components, "connectors": connectors, "nets": nets}

    def _block_reasoning_context(self, block: Dict[str, Any], indexes: Dict[str, Dict[str, Dict[str, Any]]]) -> Dict[str, Any]:
        status = str(block.get("status") or "unknown")
        missing = self._missing_evidence(block)
        extractability = block.get("extractability") if isinstance(block.get("extractability"), dict) else {}
        entry_points = self._block_entry_points(block)
        connector_refs = [str(ref) for ref in block.get("connector_refs") or []]
        source_refs = [str(ref) for ref in block.get("source_refs") or []]
        net_names = _dedupe(
            [
                *(block.get("nets") or []),
                *[
                    pin.get("net")
                    for ref in connector_refs
                    for pin in (indexes.get("connectors", {}).get(ref, {}).get("pins") or [])
                    if isinstance(pin, dict) and pin.get("net")
                ],
            ],
            limit=12,
        )
        component_refs = [
            ref
            for ref in source_refs
            if ref in indexes.get("components", {})
        ][:6]
        if status == "reuse_ready" and not missing:
            allowed_claims = ["candidate_for_verified_splice", "reuse_ready_if_entry_point_matches"]
        else:
            allowed_claims = ["candidate_only", "missing_evidence_required", "do_not_mark_reuse_ready"]
        if extractability.get("class") == "board_section_cut_candidate":
            allowed_claims.append("layout_confirmation_required")
        return {
            "block_id": block.get("block_id"),
            "name": block.get("name"),
            "function_type": block.get("function_type"),
            "capabilities": block.get("capabilities") or [],
            "status": status,
            "confidence": block.get("confidence"),
            "component_refs": component_refs,
            "extractability": {
                "class": extractability.get("class"),
                "requires_layout_confirmation": extractability.get("requires_layout_confirmation"),
            },
            "entry_points": entry_points,
            "net_neighborhood": [self._compact_net(indexes.get("nets", {}).get(name, {"net": name})) for name in net_names[:8]],
            "missing_evidence": missing[:4],
            "allowed_claims": allowed_claims,
            "forbidden_claims": [
                "no_invented_pinout",
                "no_safest_or_isolated_claim_without_closed_gates",
                "no_cutting_or_desoldering_without_layout_evidence",
            ],
        }

    def _compact_connector_contracts(
        self,
        indexes: Dict[str, Dict[str, Dict[str, Any]]],
        candidate_blocks: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        refs = []
        for block in candidate_blocks:
            for entry in block.get("entry_points") or []:
                refs.append(str(entry).split(":", 1)[-1])
        rows = []
        for ref in _dedupe(refs, limit=12):
            connector = indexes.get("connectors", {}).get(ref)
            if not connector:
                continue
            rows.append(
                {
                    "connector_ref": ref,
                    "value": connector.get("value"),
                    "semantic_role": connector.get("semantic_role"),
                    "splice_role": connector.get("splice_role"),
                    "pins": [
                        {
                            "pin": pin.get("pin"),
                            "net": pin.get("net"),
                            "role": pin.get("role"),
                            "nominal_v": pin.get("nominal_v"),
                        }
                        for pin in (connector.get("pins") or [])[:8]
                        if isinstance(pin, dict)
                    ],
                    "interfaces": connector.get("interfaces") or [],
                    "splice_allowed_after_gates": connector.get("splice_allowed_after_gates"),
                }
            )
        return rows[:12]

    def _compact_net(self, net: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "net": net.get("net"),
            "kind": net.get("kind"),
            "nominal_v": net.get("nominal_v"),
            "component_refs": (net.get("component_refs") or [])[:8],
            "connector_refs": (net.get("connector_refs") or [])[:6],
        }

    def _known_part_evidence(
        self,
        indexes: Dict[str, Dict[str, Dict[str, Any]]],
        candidate_blocks: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        refs = []
        for block in candidate_blocks:
            refs.extend(block.get("component_refs") or [])
        evidence = []
        for ref in _dedupe(refs, limit=12):
            component = indexes.get("components", {}).get(ref)
            if not component:
                continue
            row = self._part_evidence(component)
            if row:
                evidence.append(row)
        return evidence[:12]

    def _part_evidence(self, component: Dict[str, Any]) -> Dict[str, Any]:
        ref = str(component.get("ref") or "")
        value = str(component.get("value") or component.get("part_number") or "")
        category = str(component.get("category") or "")
        evidence: Dict[str, Any] = {
            "ref": ref,
            "value": value,
            "category": category,
            "pinout_known": False,
            "datasheet_known": False,
        }
        try:
            from src.intelligence.pinout_database import pinout_database

            pinout = pinout_database.get_pinout(value) or pinout_database.search_by_component_name(value)
            if pinout:
                evidence.update(
                    {
                        "part_number": pinout.part_number,
                        "manufacturer": pinout.manufacturer,
                        "description": pinout.description,
                        "pin_count": pinout.pin_count,
                        "pinout_known": True,
                        "critical_pins": [
                            {"pin": pin.pin_number, "name": pin.pin_name, "type": getattr(pin.pin_type, "value", str(pin.pin_type))}
                            for pin in pinout.pins
                            if pin.critical
                        ][:8],
                        "datasheet_url": pinout.datasheet_url,
                    }
                )
        except Exception:
            pass
        try:
            from src.intelligence.component_datasheet_retriever import datasheet_retriever

            datasheet = datasheet_retriever.get_datasheet_info(value)
            if datasheet:
                evidence.update(
                    {
                        "part_number": evidence.get("part_number") or datasheet.part_number,
                        "manufacturer": evidence.get("manufacturer") or datasheet.manufacturer,
                        "datasheet_known": True,
                        "datasheet_url": evidence.get("datasheet_url") or datasheet.datasheet_url,
                        "key_specs": datasheet.key_specs or {},
                        "common_issues": datasheet.common_issues or [],
                    }
                )
        except Exception:
            pass
        return evidence

    def _deterministic_reasoning(
        self,
        goal: str,
        facts: Dict[str, Any],
        blocks: Sequence[Dict[str, Any]],
        salvage_plan: Dict[str, Any],
        reuse_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        trace = [
            "loaded circuit graph, functional salvage blocks, connector references, and evidence gates",
            "ranked reuse candidates by status, extractability, missing gates, and confidence",
            "kept board-section and unsafe reuse claims gated until physical evidence is present",
        ]
        if facts.get("hard_safety_hold"):
            return {
                "trace": trace,
                "hypotheses": [
                    {
                        "id": "safety_hold",
                        "source": "deterministic_verifier",
                        "claim_type": "safety",
                        "claim": "The case is under a hard safety hold; reuse proposals are blocked until the unsafe source is isolated.",
                        "confidence": 0.95,
                        "required_evidence": ["separate safety review and documented isolation"],
                        "verification": {"status": "blocked", "reason": "hard_safety_hold"},
                    }
                ],
                "proposed_splices": [],
                "recommended_next_actions": [
                    "Do not connect or power the suspect source.",
                    "Recover only isolated low-voltage subassemblies after a separate safety review.",
                ],
            }

        ranked = sorted(blocks, key=self._block_rank)
        hypotheses = []
        proposals = []
        for block in ranked[:6]:
            status = str(block.get("status") or "unknown")
            extractability = str((block.get("extractability") or {}).get("class") or "unknown")
            missing = self._missing_evidence(block)
            ready = status == "reuse_ready"
            claim = (
                f"{block.get('name') or block.get('block_id')} can be reused through verified entry point(s)."
                if ready
                else f"{block.get('name') or block.get('block_id')} is a candidate, but it is blocked until evidence gates close."
            )
            if extractability == "board_section_cut_candidate":
                claim = f"{block.get('name') or block.get('block_id')} may be salvageable as a board section, not as a blind cut-out."
            hypothesis = {
                "id": f"det_{block.get('block_id')}",
                "source": "deterministic_verifier",
                "claim_type": "functional_reuse",
                "block_id": block.get("block_id"),
                "claim": claim,
                "confidence": round(min(_safe_float(block.get("confidence"), 0.5), 0.92), 3),
                "entry_points": self._block_entry_points(block),
                "required_evidence": missing,
                "verification": self._verify_block_claim(block, wants_ready=ready),
            }
            hypotheses.append(hypothesis)
            if ready:
                proposals.append(
                    {
                        "source": "deterministic_verifier",
                        "block_id": block.get("block_id"),
                        "status": "reuse_ready",
                        "entry_points": self._block_entry_points(block),
                        "next_action": "Build the splice through this entry point under current limit.",
                        "verification": {"status": "passed", "reason": "block_status_reuse_ready"},
                    }
                )

        if reuse_plan.get("recommended_first_splice") and not proposals:
            first = reuse_plan.get("recommended_first_splice") or {}
            if isinstance(first, dict) and first.get("status") == "reuse_ready":
                proposals.append(
                    {
                        "source": "functional_reuse_plan",
                        "block_id": first.get("circuit_block_id") or first.get("block_id"),
                        "status": "reuse_ready",
                        "entry_points": first.get("entry_points") or [],
                        "next_action": first.get("next_action"),
                        "verification": {"status": "passed", "reason": "functional_reuse_plan_ready"},
                    }
                )

        next_actions = []
        if proposals:
            next_actions.append("Use the verified first splice only through the listed connector or harness.")
            next_actions.append("Power the reused function from a current-limited supply and log voltage/current.")
        elif ranked:
            next_actions.extend(self._missing_evidence(ranked[0])[:3])
        elif salvage_plan:
            next_actions.extend((salvage_plan.get("evidence_plan") or {}).get("measurement_prompts") or [])
        if not next_actions:
            next_actions.append("Provide circuit graph, board images, netlist, or measured connector evidence.")

        return {
            "trace": trace,
            "hypotheses": hypotheses,
            "proposed_splices": proposals,
            "recommended_next_actions": _dedupe(next_actions, limit=8),
        }

    def _llm_not_requested(self) -> Dict[str, Any]:
        return {
            "backend": {
                "status": "not_requested",
                "model": None,
                "reason": "external LLM reasoning was not requested for this call",
            },
            "hypotheses": [],
            "proposed_splices": [],
            "recommended_next_actions": [],
        }

    def _llm_reasoning(self, goal: str, facts: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self._reasoning_prompt(goal, facts)
        try:
            text, model = self._call_llm(prompt)
        except RuntimeError as exc:
            return {
                "backend": {
                    "status": "not_configured",
                    "model": self.model,
                    "reason": str(exc),
                },
                "hypotheses": [],
                "proposed_splices": [],
                "recommended_next_actions": [],
            }
        except Exception as exc:
            return {
                "backend": {
                    "status": "failed",
                    "model": self.model,
                    "reason": str(exc),
                },
                "hypotheses": [],
                "proposed_splices": [],
                "recommended_next_actions": [],
            }

        parsed = _extract_json_object(text)
        hypotheses = [row for row in parsed.get("hypotheses") or [] if isinstance(row, dict)]
        proposals = [row for row in parsed.get("proposed_splices") or [] if isinstance(row, dict)]
        actions = _dedupe(parsed.get("recommended_next_actions") or [], limit=8)
        return {
            "backend": {
                "status": "llm_used",
                "model": model,
                "raw_response_parsed": bool(parsed),
            },
            "hypotheses": self._normalize_model_hypotheses(hypotheses),
            "proposed_splices": self._normalize_model_splices(proposals),
            "recommended_next_actions": actions,
        }

    def _call_llm(self, prompt: str) -> Tuple[str, str]:
        if self.llm_client is not None:
            response = self._call_client(self.llm_client, prompt)
            return str(response or ""), self.model or self.llm_client.__class__.__name__

        try:
            from src.config import settings
        except Exception as exc:  # pragma: no cover - defensive startup path
            raise RuntimeError(f"settings unavailable: {exc}") from exc

        provider = str(getattr(settings, "llm_provider", "") or "").strip().lower()
        configured_model = self.model or str(getattr(settings, "llm_model", "") or "").strip()
        model = _effective_model(provider, configured_model, settings)
        if not getattr(settings, "llm_enabled", False):
            raise RuntimeError("settings.llm_enabled is false")
        if not provider or not model:
            raise RuntimeError("LLM provider/model is not configured")
        if provider == "qwen" and _qwen_disabled(settings):
            raise RuntimeError("Qwen is disabled locally because QWEN_DISABLED or QWEN_OUT_OF_QUOTA is set.")
        if not self._provider_has_key(provider, settings):
            if provider == "copilot":
                raise RuntimeError("copilot CLI/OAuth provider is not ready")
            raise RuntimeError(f"{provider} API key is not configured")
        if provider == "copilot":
            return self._call_copilot(prompt, model, settings)
        if provider == "deepseek":
            return self._call_deepseek(prompt, model, settings)
        if provider == "qwen":
            return self._call_qwen(prompt, model, settings)

        try:
            import litellm
        except Exception as exc:
            raise RuntimeError(f"litellm is unavailable: {exc}") from exc

        litellm_model = model if "/" in model or provider == "openai" else f"{provider}/{model}"
        kwargs: Dict[str, Any] = {"timeout": 30, "max_tokens": self.max_tokens, "temperature": 0.1}
        api_base = getattr(settings, "llm_api_base", None)
        if api_base:
            kwargs["api_base"] = api_base
        response = litellm.completion(
            model=litellm_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a circuit reasoning engine. Return only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            **kwargs,
        )
        choice = response["choices"][0]
        if "message" in choice and "content" in choice["message"]:
            return str(choice["message"]["content"] or ""), litellm_model
        return str(choice.get("text") or ""), litellm_model

    def _call_deepseek(self, prompt: str, model: str, settings: Any) -> Tuple[str, str]:
        try:
            from openai import OpenAI
        except Exception as exc:
            raise RuntimeError(f"openai SDK is unavailable for DeepSeek: {exc}") from exc

        api_key = getattr(settings, "deepseek_api_key", None) or os.environ.get("DEEPSEEK_API_KEY")
        base_url = str(
            getattr(settings, "llm_api_base", "")
            or getattr(settings, "deepseek_base_url", "")
            or os.environ.get("DEEPSEEK_BASE_URL")
            or DEEPSEEK_DEFAULT_BASE_URL
        ).rstrip("/")
        thinking_type = str(
            getattr(settings, "deepseek_thinking", None)
            or os.environ.get("DEEPSEEK_THINKING")
            or "disabled"
        ).strip().lower()
        thinking_type = "enabled" if thinking_type == "enabled" else "disabled"
        extra_body: Dict[str, Any] = {"thinking": {"type": thinking_type}}
        if thinking_type == "enabled":
            effort = (
                getattr(settings, "deepseek_reasoning_effort", None)
                or os.environ.get("DEEPSEEK_REASONING_EFFORT")
                or "high"
            )
            extra_body["reasoning_effort"] = str(effort)
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a circuit reasoning engine. Return only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            stream=False,
            timeout=30,
            max_tokens=self.max_tokens,
            temperature=0.1,
            response_format={"type": "json_object"},
            extra_body=extra_body,
        )
        message = response.choices[0].message
        text = getattr(message, "content", None) or getattr(message, "reasoning_content", None) or ""
        return str(text), f"deepseek/{model}"

    def _call_qwen(self, prompt: str, model: str, settings: Any) -> Tuple[str, str]:
        if _qwen_disabled(settings):
            raise RuntimeError("Qwen is disabled locally because QWEN_DISABLED or QWEN_OUT_OF_QUOTA is set.")
        api_key = (
            os.environ.get("QWEN_API_KEY")
            or os.environ.get("DASHSCOPE_API_KEY")
            or getattr(settings, "qwen_api_key", None)
            or getattr(settings, "dashscope_api_key", None)
        )
        base_url = str(
            os.environ.get("QWEN_BASE_URL")
            or getattr(settings, "qwen_base_url", "")
            or getattr(settings, "llm_api_base", "")
            or QWEN_DEFAULT_BASE_URL
        ).rstrip("/")
        endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
        candidates = _qwen_text_candidates(settings=settings, requested=model)
        selected_model = candidates[0]
        payload: Dict[str, Any] = {}
        for index, candidate in enumerate(candidates):
            body: Dict[str, Any] = {
                "model": candidate,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a circuit reasoning engine. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "max_tokens": self.max_tokens,
                "temperature": 0.1,
            }
            json_mode_disabled = bool(getattr(settings, "qwen_json_mode_disabled", False)) or str(
                os.environ.get("QWEN_JSON_MODE_DISABLED") or ""
            ).strip().lower() in {"1", "true", "yes", "on"}
            if not json_mode_disabled:
                body["response_format"] = {"type": "json_object"}
            request = urllib.request.Request(
                endpoint,
                data=json.dumps(body).encode("utf-8"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    parsed = json.loads(response.read().decode("utf-8"))
                    payload = parsed if isinstance(parsed, dict) else {}
                    selected_model = candidate
                    break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:1000]
                if index < len(candidates) - 1 and _qwen_quota_error(detail):
                    continue
                raise RuntimeError(f"Qwen HTTP {exc.code}: {detail}") from exc
        choices = payload.get("choices") if isinstance(payload, dict) else []
        message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
        text = message.get("content") if isinstance(message, dict) else ""
        response_model = str(payload.get("model") or selected_model)
        return str(text), f"qwen/{response_model}"

    def _call_copilot(self, prompt: str, model: str, settings: Any) -> Tuple[str, str]:
        try:
            from src.intelligence.copilot_provider import call_copilot_prompt
        except Exception as exc:
            raise RuntimeError(f"copilot provider is unavailable: {exc}") from exc

        timeout = getattr(settings, "copilot_timeout_seconds", None) or os.environ.get("COPILOT_TIMEOUT_SECONDS")
        copilot_prompt = (
            "You are Circuit-AI's structured circuit reasoning provider. "
            "Return raw valid JSON only. Do not edit files, run tools, call MCP servers, or mutate the repository. "
            "Keep every JSON string value on one line.\n\n"
            f"{prompt}"
        )
        return call_copilot_prompt(
            copilot_prompt,
            model=model,
            timeout_seconds=float(timeout) if timeout else None,
        )

    def _call_client(self, client: Any, prompt: str) -> Any:
        if callable(client):
            return client(prompt)
        for name in ("complete", "reason", "generate_response"):
            method = getattr(client, name, None)
            if callable(method):
                return method(prompt)
        raise RuntimeError("llm_client must be callable or expose complete/reason/generate_response")

    def _provider_has_key(self, provider: str, settings: Any) -> bool:
        if provider == "copilot":
            try:
                from src.intelligence.copilot_provider import copilot_provider_status

                return bool(copilot_provider_status(getattr(settings, "copilot_model", None)).get("ready_for_live_model"))
            except Exception:
                return False
        keys = {
            "openai": "openai_api_key",
            "anthropic": "anthropic_api_key",
            "cohere": "cohere_api_key",
            "mistral": "mistral_api_key",
            "cerebras": "cerebras_api_key",
            "deepseek": "deepseek_api_key",
            "qwen": "qwen_api_key",
        }
        if provider == "qwen":
            if _qwen_disabled(settings):
                return False
            return bool(
                os.environ.get("QWEN_API_KEY")
                or os.environ.get("DASHSCOPE_API_KEY")
                or getattr(settings, "qwen_api_key", None)
                or getattr(settings, "dashscope_api_key", None)
            )
        attr = keys.get(provider)
        env_key = f"{provider.upper()}_API_KEY"
        return bool((attr and getattr(settings, attr, None)) or os.environ.get(env_key))

    def _reasoning_prompt(self, goal: str, facts: Dict[str, Any]) -> str:
        compact_facts = {
            "goal": goal,
            "input_summary": facts.get("summary"),
            "boards": facts.get("boards"),
            "candidate_blocks": facts.get("candidate_blocks"),
            "connector_contracts": facts.get("connector_contracts"),
            "known_part_evidence": facts.get("known_part_evidence"),
            "policy": [
                "Use exact block_id values from candidate_blocks. If no exact block applies, set block_id to null.",
                "Do not mark a splice reuse_ready if gates are open.",
                "Use status 'proposed' or 'blocked_until_evidence' for model proposals unless the candidate block status is reuse_ready.",
                "Do not call a block safest, isolated, verified, or safe unless its candidate block status is reuse_ready and missing_evidence is empty.",
                "Do not recommend blind board cuts.",
                "Do not recommend trace cutting, desoldering, or board-section isolation without explicit layout/continuity/isolation evidence.",
                "Return missing evidence instead of guessing pinouts or ratings.",
            ],
        }
        return (
            "Reason over these circuit/salvage facts and propose engineering hypotheses.\n"
            "Return ONLY valid compact JSON with keys: hypotheses[], proposed_splices[], recommended_next_actions[].\n"
            "No markdown, no prose outside JSON, and no literal newline characters inside JSON string values.\n"
            "Keep output compact: at most 3 hypotheses, at most 1 proposed_splice, at most 5 next actions.\n"
            "Each hypothesis object must include id, claim_type, claim, confidence, block_id if applicable, "
            "entry_points[], required_evidence[].\n"
            "Each proposed_splice object must include block_id, status, entry_points[], rationale, required_evidence[].\n\n"
            f"{json.dumps(compact_facts, sort_keys=True)}"
        )

    def _normalize_model_hypotheses(self, rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        for index, row in enumerate(rows, start=1):
            normalized.append(
                {
                    "id": str(row.get("id") or f"model_hypothesis_{index}"),
                    "source": "llm_reasoner",
                    "claim_type": str(row.get("claim_type") or row.get("type") or "functional_reuse"),
                    "block_id": row.get("block_id") or row.get("circuit_block_id"),
                    "claim": str(row.get("claim") or row.get("rationale") or ""),
                    "confidence": round(max(0.0, min(_safe_float(row.get("confidence"), 0.5), 0.98)), 3),
                    "entry_points": _dedupe(row.get("entry_points") or row.get("connectors") or [], limit=8),
                    "required_evidence": _dedupe(row.get("required_evidence") or row.get("missing_evidence") or [], limit=8),
                    "requested_status": row.get("status") or row.get("readiness"),
                }
            )
        return normalized

    def _normalize_model_splices(self, rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        for row in rows:
            normalized.append(
                {
                    "source": "llm_reasoner",
                    "block_id": row.get("block_id") or row.get("circuit_block_id"),
                    "status": str(row.get("status") or "candidate"),
                    "entry_points": _dedupe(row.get("entry_points") or row.get("connectors") or [], limit=8),
                    "rationale": str(row.get("rationale") or row.get("claim") or ""),
                    "required_evidence": _dedupe(row.get("required_evidence") or row.get("missing_evidence") or [], limit=8),
                }
            )
        return normalized

    def _verify_model_claims(
        self,
        hypotheses: Sequence[Dict[str, Any]],
        proposals: Sequence[Dict[str, Any]],
        blocks: Sequence[Dict[str, Any]],
        facts: Dict[str, Any],
    ) -> Dict[str, Any]:
        verified_hypotheses = []
        verified_proposals = []
        for row in hypotheses:
            has_explicit_block_id = bool(str(row.get("block_id") or "").strip())
            block = self._match_block(
                row.get("block_id"),
                row.get("entry_points") or [],
                blocks,
                allow_entry_fallback=not has_explicit_block_id,
            )
            wants_ready = _string_contains_ready(row.get("requested_status")) or _string_contains_ready(row.get("claim"))
            verified = dict(row)
            verified["verification"] = self._verify_block_claim(
                block,
                wants_ready=wants_ready,
                facts=facts,
                entry_points=row.get("entry_points") or [],
                claim=row.get("claim"),
            )
            verified_hypotheses.append(verified)
        for row in proposals:
            has_explicit_block_id = bool(str(row.get("block_id") or "").strip())
            block = self._match_block(
                row.get("block_id"),
                row.get("entry_points") or [],
                blocks,
                allow_entry_fallback=not has_explicit_block_id,
            )
            wants_ready = _string_contains_ready(row.get("status"))
            verified = dict(row)
            verified["verification"] = self._verify_block_claim(
                block,
                wants_ready=wants_ready,
                facts=facts,
                entry_points=row.get("entry_points") or [],
                claim=row.get("rationale"),
            )
            verified_proposals.append(verified)
        return {"hypotheses": verified_hypotheses, "proposed_splices": verified_proposals}

    def _verify_block_claim(
        self,
        block: Optional[Dict[str, Any]],
        *,
        wants_ready: bool,
        facts: Optional[Dict[str, Any]] = None,
        entry_points: Optional[Sequence[str]] = None,
        claim: Any = "",
    ) -> Dict[str, str]:
        if facts and facts.get("hard_safety_hold"):
            return {"status": "blocked", "reason": "hard_safety_hold"}
        if not block:
            return {"status": "needs_review", "reason": "claim_does_not_match_known_block"}
        missing = self._missing_evidence(block)
        extractability = str((block.get("extractability") or {}).get("class") or "")
        if extractability == "board_section_cut_candidate":
            return {"status": "blocked", "reason": "layout_confirmation_required"}
        if wants_ready and str(block.get("status") or "") != "reuse_ready":
            return {"status": "blocked", "reason": "block_not_reuse_ready"}
        if wants_ready and missing:
            return {"status": "blocked", "reason": "open_evidence_gates"}
        if str(block.get("status") or "") != "reuse_ready" and _text_has_any(claim, ASSERTIVE_SAFETY_WORDS):
            return {"status": "needs_review", "reason": "claim_exceeds_evidence"}
        if entry_points and not self._entry_points_match(block, entry_points):
            return {"status": "needs_review", "reason": "entry_point_not_in_connector_refs"}
        return {"status": "passed", "reason": "matches_deterministic_evidence"}

    def _match_block(
        self,
        block_id: Any,
        entry_points: Sequence[str],
        blocks: Sequence[Dict[str, Any]],
        *,
        allow_entry_fallback: bool = True,
    ) -> Optional[Dict[str, Any]]:
        wanted = _compact(block_id)
        if wanted:
            for block in blocks:
                ids = [
                    block.get("block_id"),
                    block.get("circuit_block_id"),
                ]
                if any(_compact(item) == wanted for item in ids):
                    return block
            if not allow_entry_fallback:
                return None
        compact_entries = {_compact(str(entry).split(":", 1)[-1]) for entry in entry_points}
        if compact_entries:
            for block in blocks:
                refs = {_compact(ref) for ref in block.get("connector_refs") or []}
                if refs & compact_entries:
                    return block
        return None

    def _entry_points_match(self, block: Dict[str, Any], entry_points: Sequence[str]) -> bool:
        refs = {_compact(ref) for ref in block.get("connector_refs") or []}
        if not refs:
            return True
        for entry in entry_points:
            connector = str(entry).split(":", 1)[-1]
            if _compact(connector) not in refs:
                return False
        return True

    def _block_rank(self, block: Dict[str, Any]) -> Tuple[int, int, int, float, str]:
        status_rank = 0 if block.get("status") == "reuse_ready" else 1
        extractability = str((block.get("extractability") or {}).get("class") or "")
        extraction_rank = 0 if extractability == "connector_reuse" else 1 if extractability == "whole_board_reuse" else 2
        return (
            status_rank,
            extraction_rank,
            len(self._missing_evidence(block)),
            -_safe_float(block.get("reuse_value_score") or block.get("confidence"), 0.0),
            str(block.get("block_id") or ""),
        )

    def _missing_evidence(self, block: Dict[str, Any]) -> List[str]:
        direct = block.get("missing_evidence") or []
        prompts = [
            gate.get("prompt")
            for gate in block.get("evidence_gates") or []
            if isinstance(gate, dict) and str(gate.get("status", "open")) != "closed" and gate.get("prompt")
        ]
        return _dedupe([*direct, *prompts], limit=8)

    def _block_entry_points(self, block: Dict[str, Any]) -> List[str]:
        board_id = str(block.get("board_id") or "board")
        entries = []
        for ref in block.get("connector_refs") or []:
            text = str(ref).strip()
            if text:
                entries.append(text if ":" in text else f"{board_id}:{text}")
        return _dedupe(entries, limit=8)

    def _entry_points(self, blocks: Sequence[Dict[str, Any]]) -> List[str]:
        entries = []
        for block in blocks:
            entries.extend(self._block_entry_points(block))
        return _dedupe(entries, limit=40)

    def _status_counts(self, blocks: Sequence[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for block in blocks:
            status = str(block.get("status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
        return dict(sorted(counts.items()))

    def _merge_hypotheses(
        self,
        deterministic: Sequence[Dict[str, Any]],
        model: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        rows = [*deterministic, *model]
        kept = []
        seen = set()
        for row in rows:
            key = (row.get("source"), row.get("block_id"), row.get("claim"))
            if key in seen:
                continue
            seen.add(key)
            kept.append(row)
        return kept[:12]

    def _verified_proposals(
        self,
        deterministic: Sequence[Dict[str, Any]],
        model: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        proposals = list(deterministic)
        for row in model:
            if (row.get("verification") or {}).get("status") == "passed":
                proposals.append(row)
            elif row.get("source") == "llm_reasoner":
                proposals.append(row)
        return proposals[:8]

    def _proof_readiness(
        self,
        *,
        goal: str,
        facts: Dict[str, Any],
        blocks: Sequence[Dict[str, Any]],
        adapter_recommendations: Sequence[Dict[str, Any]],
        verified_proposals: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Rank candidate functions by proof, not model confidence."""

        adapter_index: Dict[str, List[Dict[str, Any]]] = {}
        for adapter in adapter_recommendations:
            if isinstance(adapter, dict) and adapter.get("source_block_id"):
                adapter_index.setdefault(str(adapter["source_block_id"]), []).append(adapter)

        rows = [
            self._proof_row(block, facts, adapter_index.get(str(block.get("block_id") or ""), []))
            for block in blocks
            if isinstance(block, dict)
        ]
        rows.sort(key=lambda row: (-_safe_float(row.get("score")), str(row.get("block_id") or "")))
        for index, row in enumerate(rows, start=1):
            row["rank"] = index

        measurement_plan = self._proof_measurement_plan(rows)
        first_action = self._proof_first_action(
            goal=goal,
            facts=facts,
            rows=rows,
            measurement_plan=measurement_plan,
            verified_proposals=verified_proposals,
        )
        counts: Dict[str, int] = {}
        for row in rows:
            status = str(row.get("proof_status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
        ready_rows = [row for row in rows if row.get("ready_now")]
        blocked_rows = [row for row in rows if not row.get("ready_now")]
        if facts.get("hard_safety_hold"):
            verdict = "safety_hold"
        elif ready_rows:
            verdict = "verified_splice_available"
        elif rows:
            verdict = "evidence_needed_before_splice"
        else:
            verdict = "insufficient_circuit_evidence"

        return {
            "matrix": rows[:16],
            "measurement_plan": measurement_plan,
            "recommended_first_action": first_action,
            "summary": {
                "schema_version": "circuit_ai_proof_matrix.v1",
                "goal": goal,
                "operational_verdict": verdict,
                "candidate_count": len(rows),
                "ready_now_count": len(ready_rows),
                "blocked_count": len(blocked_rows),
                "status_counts": dict(sorted(counts.items())),
                "top_candidate": self._proof_candidate_summary(rows[0]) if rows else None,
                "recommended_first_action_type": first_action.get("action_type"),
            },
        }

    def _proof_row(
        self,
        block: Dict[str, Any],
        facts: Dict[str, Any],
        compatible_adapters: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        proof_status = self._proof_status(block, facts)
        missing = self._missing_evidence(block)
        entries = self._block_entry_points(block)
        adapter_ids = _dedupe([adapter.get("adapter_id") for adapter in compatible_adapters], limit=6)
        row = {
            "block_id": block.get("block_id"),
            "board_id": block.get("board_id"),
            "name": block.get("name"),
            "function_type": block.get("function_type"),
            "capabilities": block.get("capabilities") or [],
            "source_status": block.get("status"),
            "proof_status": proof_status,
            "ready_now": proof_status == "reuse_ready",
            "entry_points": entries,
            "extractability": block.get("extractability") or {},
            "compatible_adapter_ids": adapter_ids,
            "next_evidence_to_close": self._proof_next_evidence(block, proof_status, missing),
            "allowed_now": self._proof_allowed_actions(block, proof_status, entries, compatible_adapters),
            "forbidden_now": self._proof_forbidden_actions(block, proof_status),
            "reason": self._proof_reason(block, proof_status, missing),
        }
        row["score"] = self._proof_score(block, proof_status, compatible_adapters, missing, entries)
        return row

    def _proof_status(self, block: Dict[str, Any], facts: Dict[str, Any]) -> str:
        if facts.get("hard_safety_hold"):
            return "unsafe_hold"
        status = str(block.get("status") or "")
        extractability = str((block.get("extractability") or {}).get("class") or "")
        missing = self._missing_evidence(block)
        if status in {"blocked_failed_evidence", "electrical_viability_hold", "unsafe_hold"}:
            return "unsafe_hold"
        if extractability == "board_section_cut_candidate" or status == "layout_review_required":
            return "layout_gated"
        if status == "review_required":
            return "needs_review"
        if status == "reuse_ready" and not missing:
            return "reuse_ready"
        return "blocked_until_evidence"

    def _proof_score(
        self,
        block: Dict[str, Any],
        proof_status: str,
        compatible_adapters: Sequence[Dict[str, Any]],
        missing: Sequence[str],
        entries: Sequence[str],
    ) -> float:
        caps = {str(cap) for cap in block.get("capabilities") or []}
        nets = {str(net).upper() for net in block.get("nets") or []}
        extractability = str((block.get("extractability") or {}).get("class") or "")
        score = _safe_float(block.get("reuse_value_score") or block.get("confidence"), 0.35)

        if extractability == "connector_reuse":
            score += 0.11
        elif extractability == "whole_board_reuse":
            score += 0.03
        elif extractability == "board_section_cut_candidate":
            score -= 0.18

        if proof_status == "reuse_ready":
            score += 0.30
        elif proof_status == "layout_gated":
            score -= 0.10
        elif proof_status == "unsafe_hold":
            score -= 0.35
        elif proof_status == "needs_review":
            score -= 0.08

        score -= min(0.26, 0.035 * len(missing))
        if entries:
            score += 0.05
        elif extractability == "connector_reuse":
            score -= 0.04
        if compatible_adapters:
            score += 0.04

        low_voltage_or_logic = bool(nets & {"+3V3", "3V3", "SCL", "SDA", "UART_RX", "UART_TX"})
        if low_voltage_or_logic:
            score += 0.12
        if "sensor_or_adc" in caps:
            score += 0.08
        if "usb_serial" in caps:
            score += 0.03
        if "wireless" in caps:
            score += 0.04
        if "motor_or_load" in caps:
            score -= 0.16
        if "actuator_driver" in caps:
            score -= 0.08
        if any("SERVO" in net or "MOTOR" in net for net in nets):
            score -= 0.08
        if any("VBUS" in net for net in nets):
            score -= 0.03

        return round(max(0.0, min(score, 0.99)), 3)

    def _proof_next_evidence(self, block: Dict[str, Any], proof_status: str, missing: Sequence[str]) -> List[str]:
        if proof_status == "reuse_ready":
            return []
        evidence = list(missing[:6])
        if proof_status == "layout_gated":
            evidence.extend(
                [
                    "Map copper continuity around the candidate section before any cut.",
                    "Prove input, output, and ground isolation for the section.",
                ]
            )
        if proof_status == "needs_review" and not evidence:
            evidence.append("Resolve the high-risk review finding tied to this block.")
        if proof_status == "unsafe_hold" and not evidence:
            evidence.append("Document isolation and safety review before touching this source.")
        return _dedupe(evidence, limit=8)

    def _proof_allowed_actions(
        self,
        block: Dict[str, Any],
        proof_status: str,
        entries: Sequence[str],
        compatible_adapters: Sequence[Dict[str, Any]],
    ) -> List[str]:
        adapter_names = _dedupe([adapter.get("name") for adapter in compatible_adapters], limit=3)
        entry_text = ", ".join(entries) if entries else "the verified entry point"
        if proof_status == "reuse_ready":
            actions = [
                f"Build the protected harness through {entry_text}.",
                "Power the reused function from a current-limited supply.",
                "Log voltage, current, and functional result after connection.",
            ]
            if adapter_names:
                actions.insert(0, f"Use adapter package: {', '.join(adapter_names)}.")
            return actions
        if proof_status == "layout_gated":
            return [
                "Inspect the board layout and photograph both copper sides.",
                "Continuity-map every boundary trace before any section plan.",
                "Keep the function intact until isolation evidence exists.",
            ]
        if proof_status == "unsafe_hold":
            return [
                "Quarantine the source and keep it unpowered.",
                "Recover only isolated low-voltage parts after safety review.",
            ]
        return [
            "Measure and label the listed voltage, ground, logic, and current gates.",
            "Keep the target board disconnected while gates are open.",
            "Use only current-limited bench power during evidence collection.",
        ]

    def _proof_forbidden_actions(self, block: Dict[str, Any], proof_status: str) -> List[str]:
        if proof_status == "reuse_ready":
            return [
                "Do not bypass current limiting.",
                "Do not connect unlisted pins or rails.",
                "Do not expand the splice beyond the verified entry point.",
            ]
        forbidden = [
            "Do not splice this block into a target board yet.",
            "Do not claim the function recovered or safe-to-use yet.",
            "Do not power unknown rails from the target board.",
        ]
        extractability = str((block.get("extractability") or {}).get("class") or "")
        if proof_status == "layout_gated" or extractability == "board_section_cut_candidate":
            forbidden.append("Do not cut traces or desolder the section until layout, continuity, and isolation evidence exists.")
        return forbidden

    def _proof_reason(self, block: Dict[str, Any], proof_status: str, missing: Sequence[str]) -> str:
        name = block.get("name") or block.get("block_id") or "candidate block"
        if proof_status == "reuse_ready":
            return f"{name} has closed evidence gates and can be reused through verified entry points."
        if proof_status == "layout_gated":
            return f"{name} is a possible section-level salvage, but board layout and isolation proof are still missing."
        if proof_status == "unsafe_hold":
            return f"{name} is blocked by failed or unsafe electrical evidence."
        if proof_status == "needs_review":
            return f"{name} has review risk that must be cleared before reuse."
        if missing:
            return f"{name} is promising, but {len(missing)} evidence gate(s) remain open."
        return f"{name} does not yet have enough circuit proof for reuse."

    def _proof_measurement_plan(self, rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        plan = []
        seen = set()
        for row in rows:
            if row.get("ready_now"):
                continue
            action_type = "layout_review" if row.get("proof_status") == "layout_gated" else "measurement"
            for evidence in row.get("next_evidence_to_close") or []:
                key = (str(row.get("block_id") or ""), str(evidence).lower())
                if key in seen:
                    continue
                seen.add(key)
                plan.append(
                    {
                        "action_type": action_type,
                        "block_id": row.get("block_id"),
                        "entry_points": row.get("entry_points") or [],
                        "evidence": evidence,
                        "unblocks_status": row.get("proof_status"),
                        "compatible_adapter_ids": row.get("compatible_adapter_ids") or [],
                    }
                )
                if len(plan) >= 12:
                    return plan
        return plan

    def _proof_first_action(
        self,
        *,
        goal: str,
        facts: Dict[str, Any],
        rows: Sequence[Dict[str, Any]],
        measurement_plan: Sequence[Dict[str, Any]],
        verified_proposals: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if facts.get("hard_safety_hold"):
            return {
                "action_type": "safety_hold",
                "instruction": "Do not power or splice this source until the unsafe condition is isolated and reviewed.",
                "block_id": None,
                "evidence": ["separate safety review and documented isolation"],
            }
        ready_rows = [row for row in rows if row.get("ready_now")]
        if ready_rows:
            row = ready_rows[0]
            proposal = self._proposal_for_block(row.get("block_id"), verified_proposals)
            return {
                "action_type": "first_splice",
                "block_id": row.get("block_id"),
                "entry_points": row.get("entry_points") or proposal.get("entry_points") or [],
                "adapter_ids": row.get("compatible_adapter_ids") or [],
                "instruction": proposal.get("next_action")
                or "Build the verified adapter/harness through the listed entry point and power it under current limit.",
                "evidence": [],
            }
        if measurement_plan:
            first = dict(measurement_plan[0])
            first["instruction"] = first.get("evidence")
            return first
        return {
            "action_type": "collect_circuit_evidence",
            "block_id": None,
            "instruction": "Provide circuit graph, netlist, board images, or connector measurements before reuse planning.",
            "evidence": [goal],
        }

    def _proposal_for_block(self, block_id: Any, proposals: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        wanted = _compact(block_id)
        for proposal in proposals:
            if _compact(proposal.get("block_id")) == wanted and (proposal.get("verification") or {}).get("status") == "passed":
                return proposal
        return {}

    def _proof_candidate_summary(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "rank": row.get("rank"),
            "block_id": row.get("block_id"),
            "name": row.get("name"),
            "proof_status": row.get("proof_status"),
            "score": row.get("score"),
            "entry_points": row.get("entry_points") or [],
            "next_evidence_to_close": (row.get("next_evidence_to_close") or [])[:3],
            "compatible_adapter_ids": row.get("compatible_adapter_ids") or [],
        }

    def _adapter_recommendations(self, facts: Dict[str, Any]) -> List[Dict[str, Any]]:
        recommendations = []
        for block in facts.get("candidate_blocks") or []:
            if not isinstance(block, dict):
                continue
            caps = set(block.get("capabilities") or [])
            nets = {str(net.get("net") or ""): net for net in block.get("net_neighborhood") or [] if isinstance(net, dict)}
            missing = block.get("missing_evidence") or []
            status = "ready_after_gates" if block.get("status") == "reuse_ready" and not missing else "blocked_until_evidence"

            def add(adapter_id: str, name: str, *, purpose: str, must_include: Sequence[str], blocks_before_use: Sequence[str]) -> None:
                recommendations.append(
                    {
                        "adapter_id": adapter_id,
                        "source_block_id": block.get("block_id"),
                        "status": status,
                        "name": name,
                        "purpose": purpose,
                        "entry_points": block.get("entry_points") or [],
                        "must_include": list(must_include),
                        "blocks_before_use": _dedupe([*missing[:4], *blocks_before_use], limit=8),
                    }
                )

            has_i2c_nets = any("SCL" in name for name in nets) and any("SDA" in name for name in nets)
            if ("sensor_or_adc" in caps or has_i2c_nets) and any("SCL" in name or "SDA" in name for name in nets):
                add(
                    "i2c_protected_sensor_harness",
                    "Protected I2C sensor harness",
                    purpose="Reuse a low-voltage sensor/control connector without guessing pinout or logic level.",
                    must_include=["3.3V rail label", "ground reference", "current limit", "optional 100-330 ohm signal series resistors"],
                    blocks_before_use=["verify pull-up voltage", "confirm SDA/SCL idle high level", "confirm target board uses compatible I2C voltage"],
                )
            if caps & {"actuator_driver", "motor_or_load"} or any("SERVO" in name or "PWM" in name for name in nets):
                add(
                    "servo_or_load_power_harness",
                    "Fused servo/load harness",
                    purpose="Reuse PWM/load connectors while keeping load power and controller logic evidence separate.",
                    must_include=["fuse or current limit", "shared ground only after isolation check", "load supply current margin", "flyback/protection if inductive"],
                    blocks_before_use=["measure load rail voltage under current limit", "record source current capability", "verify PWM logic level"],
                )
            if "usb_serial" in caps or any("USB" in name or "VBUS" in name for name in nets):
                add(
                    "usb_serial_debug_harness",
                    "USB/UART debug harness",
                    purpose="Reuse USB/serial function for bring-up logs or programming access.",
                    must_include=["VBUS current limit", "D+/D- continuity check", "ESD/strain relief", "do not backfeed target power unintentionally"],
                    blocks_before_use=["measure VBUS polarity/voltage", "confirm shared ground path", "confirm UART/USB role before cross-connection"],
                )
            if "power" in caps and any(net.get("kind") == "power" for net in nets.values()):
                add(
                    "protected_power_breakout",
                    "Protected power breakout",
                    purpose="Expose a known rail for bench testing or downstream low-voltage modules.",
                    must_include=["polarity marking", "fuse/current limit", "input/output label", "thermal/current derating"],
                    blocks_before_use=["measure rail unloaded", "measure rail under dummy load", "check resistance to ground before power"],
                )
        seen = set()
        unique = []
        for row in recommendations:
            key = (row.get("adapter_id"), row.get("source_block_id"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(row)
        return unique[:10]

    def _expert_training_record(
        self,
        *,
        goal: str,
        facts: Dict[str, Any],
        hypotheses: Sequence[Dict[str, Any]],
        proposed_splices: Sequence[Dict[str, Any]],
        verifier_status: str,
        proof_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        labels = []
        for row in [*hypotheses, *proposed_splices]:
            if not isinstance(row, dict):
                continue
            verification = row.get("verification") if isinstance(row.get("verification"), dict) else {}
            labels.append(
                {
                    "source": row.get("source"),
                    "item_type": "splice" if "rationale" in row or row.get("status") in {"proposed", "reuse_ready", "blocked_until_evidence"} else "hypothesis",
                    "block_id": row.get("block_id"),
                    "claim_type": row.get("claim_type"),
                    "verification_status": verification.get("status"),
                    "verification_reason": verification.get("reason"),
                    "operator_label_needed": verification.get("status") in {"needs_review", "blocked"},
                }
            )
        return {
            "schema_version": "circuit_ai_expert_training_record.v1",
            "goal": goal,
            "verifier_status": verifier_status,
            "features": {
                "board_count": (facts.get("summary") or {}).get("board_count"),
                "functional_block_count": (facts.get("summary") or {}).get("functional_block_count"),
                "known_connector_contract_count": (facts.get("summary") or {}).get("known_connector_contract_count"),
                "known_part_evidence_count": (facts.get("summary") or {}).get("known_part_evidence_count"),
                "candidate_block_ids": [block.get("block_id") for block in facts.get("candidate_blocks") or []],
                "entry_points": facts.get("entry_points") or [],
                "proof_summary": proof_summary or {},
            },
            "labels": labels[:24],
            "outcome_fields_required": [
                "operator_accept_reject",
                "corrected_block_id",
                "measurement_values",
                "splice_attempted",
                "splice_success",
                "damage_or_hazard_observed",
                "value_recovered_usd",
            ],
        }

    def _recommended_next_actions(
        self,
        deterministic_actions: Sequence[str],
        model_actions: Sequence[str],
        facts: Dict[str, Any],
    ) -> List[str]:
        if facts.get("hard_safety_hold"):
            return _dedupe(deterministic_actions, limit=8)
        guarded_model_actions = []
        blocked_board_cut = False
        for action in model_actions:
            if _text_has_any(action, BOARD_CUT_WORDS):
                blocked_board_cut = True
                continue
            guarded_model_actions.append(str(action))
        if blocked_board_cut:
            guarded_model_actions.append(
                "Do not cut traces, desolder blocks, or isolate board sections until layout, continuity, and power-isolation evidence is recorded."
            )
        return _dedupe([*deterministic_actions, *guarded_model_actions], limit=10)
