import json
import sys
import types
from pathlib import Path

from src.api.v1 import main as main_module
from src.config import settings
from src.engines.circuit_board_graph import analyze_circuit_design, analyze_circuit_session
from src.intelligence.board_session_store import BoardSessionStore
from src.intelligence.circuit_ai_reasoner import CircuitAIReasoner, circuit_ai_model_status
from src.intelligence import circuit_ai_reasoner, copilot_provider
from src.intelligence.salvage_splice_planner import SalvageSplicePlanner


ROOT = Path(__file__).resolve().parents[4]
DEMO_NETLIST = ROOT / "examples" / "main_ctrl_esp32_servo.net"


def _demo_circuit():
    return analyze_circuit_design(
        {
            "board": {
                "board_id": "main_ctrl",
                "path": str(DEMO_NETLIST),
                "kind": "netlist",
            }
        }
    )


def _find_block(circuit, connector_ref):
    for block in circuit["boards"][0]["functional_salvage"]["reusable_blocks"]:
        if connector_ref in (block.get("connector_refs") or []):
            return block
    raise AssertionError(f"missing block for connector {connector_ref}")


def test_circuit_ai_reasoner_uses_model_claims_but_blocks_unverified_ready_splice():
    circuit = _demo_circuit()
    j3 = _find_block(circuit, "J3")

    def fake_llm(_prompt):
        return json.dumps(
            {
                "hypotheses": [
                    {
                        "id": "model_claim_j3_ready",
                        "claim_type": "functional_reuse",
                        "block_id": j3["block_id"],
                        "claim": "J3 is ready to splice into the target motor driver.",
                        "confidence": 0.94,
                        "entry_points": ["main_ctrl:J3"],
                        "required_evidence": [],
                        "status": "reuse_ready",
                    }
                ],
                "proposed_splices": [
                    {
                        "block_id": j3["block_id"],
                        "status": "reuse_ready",
                        "entry_points": ["main_ctrl:J3"],
                        "rationale": "Model thinks the connector is a motor output.",
                    }
                ],
                "recommended_next_actions": ["cut traces around J3 and connect it to the target actuator"],
            }
        )

    reasoning = CircuitAIReasoner(llm_client=fake_llm, enable_llm=True).assess(
        {"goal": "reuse the servo connector", "analysis": circuit}
    )

    assert reasoning["mode"] == "circuit_ai_reasoning"
    assert reasoning["ai_integration"]["not_chatbot"] is True
    assert reasoning["backend"]["status"] == "llm_used"
    assert reasoning["verifier"]["status"] == "blocked_model_claims"
    assert reasoning["evidence_packet"]["strict_block_id_required"] is True
    assert reasoning["evidence_packet"]["candidate_blocks"]
    assert reasoning["model_hypotheses"][0]["verification"]["status"] == "blocked"
    assert reasoning["model_hypotheses"][0]["verification"]["reason"] == "block_not_reuse_ready"
    assert reasoning["proof_summary"]["operational_verdict"] == "evidence_needed_before_splice"
    assert reasoning["recommended_first_action"]["action_type"] == "measurement"
    model_proposal = [row for row in reasoning["proposed_splices"] if row.get("source") == "llm_reasoner"][0]
    assert model_proposal["verification"]["status"] == "blocked"
    assert not any("cut traces around J3" in item for item in reasoning["recommended_next_actions"])
    assert any("Do not cut traces" in item for item in reasoning["recommended_next_actions"])


def test_circuit_ai_reasoner_does_not_match_invented_block_id_by_connector_only():
    circuit = _demo_circuit()

    def fake_llm(_prompt):
        return json.dumps(
            {
                "hypotheses": [
                    {
                        "id": "invented_block",
                        "claim_type": "functional_reuse",
                        "block_id": "main_ctrl:actuator_driver",
                        "claim": "This invented actuator block is isolated and safest to reuse.",
                        "confidence": 0.8,
                        "entry_points": ["main_ctrl:J2"],
                        "required_evidence": [],
                    }
                ],
                "proposed_splices": [
                    {
                        "block_id": "main_ctrl:actuator_driver",
                        "status": "proposed",
                        "entry_points": ["main_ctrl:J2"],
                        "rationale": "Use connector J2.",
                    }
                ],
                "recommended_next_actions": [],
            }
        )

    reasoning = CircuitAIReasoner(llm_client=fake_llm, enable_llm=True).assess(
        {"goal": "reuse a connector", "analysis": circuit}
    )

    assert reasoning["verifier"]["status"] == "model_claims_need_review"
    assert reasoning["verifier"]["needs_review_model_claim_count"] == 2
    assert reasoning["model_hypotheses"][0]["verification"]["reason"] == "claim_does_not_match_known_block"
    proposal = [row for row in reasoning["proposed_splices"] if row.get("source") == "llm_reasoner"][0]
    assert proposal["verification"]["reason"] == "claim_does_not_match_known_block"


def test_circuit_ai_reasoner_builds_expert_evidence_packet_with_connectors_parts_and_adapters():
    circuit = _demo_circuit()

    reasoning = CircuitAIReasoner(enable_llm=False).assess(
        {"goal": "build expert board reuse context", "analysis": circuit}
    )

    summary = reasoning["input_summary"]
    packet = reasoning["evidence_packet"]
    assert summary["known_connector_contract_count"] >= 4
    assert summary["known_part_evidence_count"] >= 1
    assert any(row["connector_ref"] == "J2" for row in packet["connector_contracts"])

    j2 = next(row for row in packet["connector_contracts"] if row["connector_ref"] == "J2")
    assert {pin["net"] for pin in j2["pins"]} >= {"+3V3", "0", "SCL", "SDA"}

    assert any(row.get("part_number") == "ESP32" and row.get("pinout_known") for row in packet["known_part_evidence"])
    j2_block = next(row for row in packet["candidate_blocks"] if row["block_id"] == "main_ctrl_external_interface_j2")
    assert any(net["net"] == "+3V3" and net["kind"] == "power" for net in j2_block["net_neighborhood"])
    assert any(adapter["adapter_id"] == "i2c_protected_sensor_harness" for adapter in reasoning["adapter_recommendations"])
    assert any(adapter["adapter_id"] == "protected_power_breakout" for adapter in reasoning["adapter_recommendations"])
    matrix = reasoning["proof_matrix"]
    j2_rows = [
        row
        for row in matrix
        if str(row.get("block_id", "")).endswith("_j2") or "main_ctrl:J2" in (row.get("entry_points") or [])
    ]
    assert j2_rows
    assert any(row["proof_status"] == "blocked_until_evidence" for row in j2_rows)
    assert reasoning["proof_summary"]["schema_version"] == "circuit_ai_proof_matrix.v1"
    assert reasoning["proof_summary"]["operational_verdict"] == "evidence_needed_before_splice"
    assert reasoning["recommended_first_action"]["action_type"] == "measurement"
    assert "J2" in reasoning["recommended_first_action"]["instruction"]
    assert any("i2c_protected_sensor_harness" in (row.get("compatible_adapter_ids") or []) for row in matrix)
    training = reasoning["expert_training_record"]
    assert training["schema_version"] == "circuit_ai_expert_training_record.v1"
    assert training["features"]["known_connector_contract_count"] >= 4
    assert training["features"]["proof_summary"]["operational_verdict"] == "evidence_needed_before_splice"
    assert "measurement_values" in training["outcome_fields_required"]


def test_circuit_ai_reasoner_finds_verified_first_splice_from_closed_measurement_gates(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    circuit = _demo_circuit()
    session = store.create_session(
        {
            "description": "J2 sensor connector salvage proof",
            "route": "circuit",
            "analysis": circuit,
            "source": "test",
        },
        user_id="operator-1",
        commit=True,
    )
    for measurement in [
        {"type": "voltage", "target": "J2 +3V3", "value": 3.31, "unit": "V"},
        {"type": "continuity", "target": "J2 ground", "value": "pass"},
        {"type": "logic_level", "target": "J2 SCL SDA", "value": "pass", "notes": "logic idle high at 3.3V"},
        {"type": "voltage", "target": "+3V3", "value": 3.31, "unit": "V"},
    ]:
        store.add_measurement(session["session_id"], measurement)
    advanced = analyze_circuit_session(store.get_session(session["session_id"]))

    reasoning = CircuitAIReasoner(enable_llm=False).assess(
        {"goal": "reuse the verified sensor connector", "analysis": advanced}
    )

    assert reasoning["backend"]["status"] == "not_requested"
    assert reasoning["verifier"]["status"] == "pass_with_gates"
    assert any(
        row.get("status") == "reuse_ready" and "main_ctrl:J2" in (row.get("entry_points") or [])
        for row in reasoning["proposed_splices"]
    )
    assert any(
        "main_ctrl:J2" in (row.get("entry_points") or [])
        for row in reasoning["hypotheses"]
    )
    ready_rows = [
        row
        for row in reasoning["proof_matrix"]
        if row["proof_status"] == "reuse_ready"
        and (str(row.get("block_id", "")).endswith("_j2") or "main_ctrl:J2" in (row.get("entry_points") or []))
    ]
    assert ready_rows
    assert reasoning["proof_summary"]["operational_verdict"] == "verified_splice_available"
    assert reasoning["recommended_first_action"]["action_type"] == "first_splice"
    assert reasoning["recommended_first_action"]["block_id"] in {row["block_id"] for row in ready_rows}


def test_circuit_reasoning_api_returns_structured_backend_reasoning(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    circuit = _demo_circuit()

    response = main_module.circuit_reasoning_assess(
        {
            "goal": "reuse useful low-voltage functions",
            "analysis": circuit,
            "use_llm_reasoner": False,
        },
        current_user={"user_id": "operator-1"},
        store=store,
        planner=SalvageSplicePlanner(),
    )

    assert response["status"] == "success"
    assert response["reasoning"]["schema_version"] == "circuit_ai_reasoning.v1"
    assert response["reasoning"]["ai_integration"]["location"] == "circuit_graph_and_salvage_pipeline"
    assert response["salvage_plan"]["circuit_reasoning"]["mode"] == "circuit_ai_reasoning"
    assert response["metadata"]["llm_requested"] is False


def test_circuit_model_status_reports_live_llm_readiness_without_secrets():
    status = circuit_ai_model_status()

    assert status["status"] in {"ready", "not_ready"}
    assert isinstance(status["ready_for_live_model"], bool)
    assert status["capabilities"]["structured_circuit_reasoning"] is True
    assert status["capabilities"]["deterministic_verification"] is True
    assert status["capabilities"]["automatic_model_training"] is False
    assert "selected" in status
    assert "providers" in status
    assert all("api_key_configured" in row for row in status["providers"].values())

    response = main_module.circuit_reasoning_model_status(
        current_user={"user_id": "operator-1"},
    )

    assert response["status"] == "success"
    assert response["model_runtime"]["status"] in {"ready", "not_ready"}
    assert response["metadata"]["user_id"] == "operator-1"


def test_deepseek_provider_uses_openai_compatible_client(monkeypatch):
    calls = {}

    class FakeCompletions:
        def create(self, **kwargs):
            calls["create"] = kwargs
            return types.SimpleNamespace(
                choices=[
                    types.SimpleNamespace(
                        message=types.SimpleNamespace(
                            content=json.dumps(
                                {
                                    "hypotheses": [
                                        {
                                            "id": "deepseek_h1",
                                            "claim_type": "functional_reuse",
                                            "claim": "Inspect connector gates before reuse.",
                                            "confidence": 0.7,
                                            "entry_points": [],
                                            "required_evidence": ["measure connector voltage"],
                                        }
                                    ],
                                    "proposed_splices": [],
                                    "recommended_next_actions": ["measure connector voltage"],
                                }
                            )
                        )
                    )
                ]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            calls["client"] = kwargs
            self.chat = types.SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_provider", "deepseek")
    monkeypatch.setattr(settings, "llm_model", "command-r")
    monkeypatch.setattr(settings, "deepseek_api_key", "test-deepseek-key")
    monkeypatch.setattr(settings, "deepseek_model", None)
    monkeypatch.setattr(settings, "deepseek_base_url", None)
    monkeypatch.setattr(settings, "deepseek_thinking", "disabled")
    monkeypatch.setattr(settings, "deepseek_reasoning_effort", None)
    monkeypatch.setattr(settings, "llm_api_base", None)

    reasoning = CircuitAIReasoner(enable_llm=True).assess(
        {"goal": "reason over a circuit with sparse evidence"}
    )

    assert calls["client"]["api_key"] == "test-deepseek-key"
    assert calls["client"]["base_url"] == "https://api.deepseek.com"
    assert calls["create"]["model"] == "deepseek-v4-flash"
    assert calls["create"]["response_format"] == {"type": "json_object"}
    assert calls["create"]["extra_body"] == {"thinking": {"type": "disabled"}}
    assert calls["create"]["messages"][0]["role"] == "system"
    assert reasoning["backend"]["status"] == "llm_used"
    assert reasoning["backend"]["model"] == "deepseek/deepseek-v4-flash"
    assert reasoning["model_runtime"]["selected"]["provider"] == "deepseek"
    assert reasoning["model_runtime"]["selected"]["model"] == "deepseek-v4-flash"


def test_deepseek_specific_env_aliases_override_generic_defaults(monkeypatch):
    calls = {}

    class FakeCompletions:
        def create(self, **kwargs):
            calls["create"] = kwargs
            return types.SimpleNamespace(
                choices=[
                    types.SimpleNamespace(
                        message=types.SimpleNamespace(
                            content=json.dumps(
                                {
                                    "hypotheses": [],
                                    "proposed_splices": [],
                                    "recommended_next_actions": ["collect connector evidence"],
                                }
                            )
                        )
                    )
                ]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            calls["client"] = kwargs
            self.chat = types.SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_provider", "deepseek")
    monkeypatch.setattr(settings, "llm_model", "command-r")
    monkeypatch.setattr(settings, "deepseek_api_key", "test-deepseek-key")
    monkeypatch.setattr(settings, "deepseek_model", "deepseek-circuit-test")
    monkeypatch.setattr(settings, "deepseek_base_url", "https://deepseek.example/v1")
    monkeypatch.setattr(settings, "deepseek_thinking", "enabled")
    monkeypatch.setattr(settings, "deepseek_reasoning_effort", "medium")
    monkeypatch.setattr(settings, "llm_api_base", None)

    reasoning = CircuitAIReasoner(enable_llm=True).assess(
        {"goal": "reason over a circuit with DeepSeek-specific config"}
    )

    assert calls["client"]["base_url"] == "https://deepseek.example/v1"
    assert calls["create"]["model"] == "deepseek-circuit-test"
    assert calls["create"]["extra_body"] == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "medium",
    }
    assert reasoning["backend"]["model"] == "deepseek/deepseek-circuit-test"
    assert reasoning["model_runtime"]["selected"]["deepseek_native_openai_compatible"] is True


def test_qwen_provider_uses_direct_openai_compatible_http(monkeypatch):
    calls = {}
    monkeypatch.delenv("QWEN_DISABLED", raising=False)
    monkeypatch.delenv("QWEN_OUT_OF_QUOTA", raising=False)

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "model": "qwen3-max-test",
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "hypotheses": [],
                                        "proposed_splices": [],
                                        "recommended_next_actions": ["collect thermal and current evidence"],
                                    }
                                )
                            }
                        }
                    ],
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout=None):
        calls["url"] = request.full_url
        calls["timeout"] = timeout
        calls["body"] = json.loads(request.data.decode("utf-8"))
        calls["headers"] = dict(request.header_items())
        return FakeResponse()

    monkeypatch.setattr(circuit_ai_reasoner.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_provider", "qwen")
    monkeypatch.setattr(settings, "llm_model", "command-r")
    monkeypatch.setattr(settings, "qwen_api_key", "test-qwen-key")
    monkeypatch.setattr(settings, "dashscope_api_key", None)
    monkeypatch.setattr(settings, "qwen_model", "qwen3-max-test")
    monkeypatch.setattr(settings, "qwen_base_url", "https://qwen.example/compatible-mode/v1")
    monkeypatch.setattr(settings, "qwen_json_mode_disabled", False)
    monkeypatch.setattr(settings, "qwen_disabled", False)
    monkeypatch.setattr(settings, "qwen_out_of_quota", False)
    monkeypatch.setattr(settings, "llm_api_base", "https://wrong-generic.example/v1")

    reasoning = CircuitAIReasoner(enable_llm=True).assess(
        {"goal": "reason over a circuit with Qwen-specific config"}
    )

    assert calls["url"] == "https://qwen.example/compatible-mode/v1/chat/completions"
    assert calls["timeout"] == 30
    assert calls["body"]["model"] == "qwen3-max-test"
    assert calls["body"]["response_format"] == {"type": "json_object"}
    assert calls["headers"]["Authorization"] == "Bearer test-qwen-key"
    assert reasoning["backend"]["model"] == "qwen/qwen3-max-test"
    assert reasoning["model_runtime"]["selected"]["provider"] == "qwen"
    assert reasoning["model_runtime"]["selected"]["qwen_native_openai_compatible"] is True


def test_qwen_provider_routes_away_from_low_quota_qwen_plus(monkeypatch):
    calls = {}
    monkeypatch.delenv("QWEN_DISABLED", raising=False)
    monkeypatch.delenv("QWEN_OUT_OF_QUOTA", raising=False)

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "model": calls["body"]["model"],
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "hypotheses": [],
                                        "proposed_splices": [],
                                        "recommended_next_actions": ["collect measured pinout evidence"],
                                    }
                                )
                            }
                        }
                    ],
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout=None):
        calls["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setenv("QWEN_LOW_QUOTA_MODELS", "qwen-plus")
    monkeypatch.setenv("QWEN_MODEL_ROTATION", "qwen3.5-122b-a10b,qwen3-max")
    monkeypatch.setattr(circuit_ai_reasoner.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_provider", "qwen")
    monkeypatch.setattr(settings, "llm_model", "qwen-plus")
    monkeypatch.setattr(settings, "qwen_api_key", "test-qwen-key")
    monkeypatch.setattr(settings, "dashscope_api_key", None)
    monkeypatch.setattr(settings, "qwen_model", "qwen-plus")
    monkeypatch.setattr(settings, "qwen_base_url", "https://qwen.example/compatible-mode/v1")
    monkeypatch.setattr(settings, "qwen_json_mode_disabled", False)
    monkeypatch.setattr(settings, "qwen_disabled", False)
    monkeypatch.setattr(settings, "qwen_out_of_quota", False)
    monkeypatch.setattr(settings, "llm_api_base", None)

    reasoning = CircuitAIReasoner(enable_llm=True).assess(
        {"goal": "reason over a circuit without burning qwen-plus quota"}
    )

    assert calls["body"]["model"] == "qwen3.5-122b-a10b"
    assert reasoning["backend"]["model"] == "qwen/qwen3.5-122b-a10b"
    assert reasoning["model_runtime"]["selected"]["model"] == "qwen3.5-122b-a10b"
    assert "qwen-plus" in reasoning["model_runtime"]["selected"]["qwen_low_quota_models"]


def test_qwen_provider_disabled_blocks_http_even_with_key(monkeypatch):
    def fail_urlopen(*_args, **_kwargs):
        raise AssertionError("Qwen HTTP must not be called when disabled")

    monkeypatch.setenv("QWEN_DISABLED", "true")
    monkeypatch.setattr(circuit_ai_reasoner.urllib.request, "urlopen", fail_urlopen)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_provider", "qwen")
    monkeypatch.setattr(settings, "llm_model", "qwen3-max-test")
    monkeypatch.setattr(settings, "qwen_api_key", "test-qwen-key")
    monkeypatch.setattr(settings, "dashscope_api_key", None)
    monkeypatch.setattr(settings, "qwen_model", "qwen3-max-test")
    monkeypatch.setattr(settings, "qwen_base_url", "https://qwen.example/compatible-mode/v1")
    monkeypatch.setattr(settings, "qwen_disabled", False)
    monkeypatch.setattr(settings, "qwen_out_of_quota", False)
    monkeypatch.setattr(settings, "llm_api_base", None)

    reasoning = CircuitAIReasoner(enable_llm=True).assess(
        {"goal": "try qwen while quota is exhausted"}
    )

    assert reasoning["backend"]["status"] == "not_configured"
    assert "Qwen is disabled" in reasoning["backend"]["reason"]
    assert reasoning["model_runtime"]["ready_for_live_model"] is False
    assert reasoning["model_runtime"]["selected"]["qwen_disabled"] is True


def test_copilot_provider_uses_local_cli_without_api_key(monkeypatch):
    calls = {}

    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_provider", "copilot")
    monkeypatch.setattr(settings, "llm_model", "deepseek-v4-flash")
    monkeypatch.setattr(settings, "copilot_model", "gpt-4.1")
    monkeypatch.setattr(settings, "copilot_timeout_seconds", 1)
    monkeypatch.setattr(
        copilot_provider,
        "copilot_provider_status",
        lambda model=None: {
            "status": "ready",
            "ready_for_live_model": True,
            "selected": {"provider": "copilot", "model": model or "gpt-4.1", "node_runner": "npx -y node@20"},
            "providers": {"copilot_cli": {"ready": True, "gh_authenticated": True, "token_marker_configured": False}},
            "blockers": [],
            "capabilities": {"secrets_returned": False},
        },
    )

    def fake_call(prompt, *, model=None, timeout_seconds=None):
        calls["prompt"] = prompt
        calls["model"] = model
        calls["timeout_seconds"] = timeout_seconds
        return json.dumps(
            {
                "hypotheses": [
                    {
                        "id": "copilot_h1",
                        "claim_type": "functional_reuse",
                        "claim": "Measure connector voltage before reuse.",
                        "confidence": 0.7,
                        "entry_points": [],
                        "required_evidence": ["measure connector voltage"],
                    }
                ],
                "proposed_splices": [],
                "recommended_next_actions": ["measure connector voltage"],
            }
        ), "copilot/gpt-4.1"

    monkeypatch.setattr(copilot_provider, "call_copilot_prompt", fake_call)

    reasoning = CircuitAIReasoner(enable_llm=True).assess(
        {"goal": "reason over sparse board evidence with Copilot"}
    )

    assert calls["model"] == "gpt-4.1"
    assert calls["timeout_seconds"] == 1
    assert reasoning["backend"]["status"] == "llm_used"
    assert reasoning["backend"]["model"] == "copilot/gpt-4.1"
    assert reasoning["model_runtime"]["selected"]["provider"] == "copilot"
    assert reasoning["model_runtime"]["selected"]["model"] == "gpt-4.1"
    assert reasoning["model_runtime"]["providers"]["copilot"]["cli_ready"] is True
