def test_agent_offline_stub(monkeypatch):
    """
    Ensure CircuitAgent returns stubbed LLM output without network/keys and
    can be instantiated without loading heavy vision models.
    """
    import sys, os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))
    # Patch detector to a lightweight stub to avoid model loads during init
    class DummyDetector:
        def __init__(self, *args, **kwargs):
            self.model_source = "test-stub"
            self.custom_model_found = False
            self.fallback_used = False

    import circuit_agent

    monkeypatch.setattr(circuit_agent, "EnhancedComponentDetector", DummyDetector)

    agent = circuit_agent.CircuitAgent(knowledge_path="knowledge_base")
    result = asyncio_stub(agent.process_request("hello"))

    assert result["llm_response"] == circuit_agent.LLM_STUB_RESPONSE
    assert result["detection_summary"]["count"] == 0


def asyncio_stub(coro):
    """Helper to run a coroutine inline for this simple test."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)
