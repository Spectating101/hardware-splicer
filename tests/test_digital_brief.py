import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from hardware_splicer import digital_brief
from hardware_splicer.digital_engine import DigitalStudyEngine
from hardware_splicer.digital_project_api import create_digital_project_router


def response(**changes):
    data = {"status": "build", "case_id": "ender3-penplotter", "requirements": {"pen_lift_mm": 4},
            "explanation": "Use the reference Ender-3 carriage.", "drawing": [[[10, 10], [30, 50]]]}
    return {"ok": True, "provider": "test", "content": json.dumps({**data, **changes})}


def test_prompt_accepts_checked_polylines(monkeypatch):
    monkeypatch.setattr(digital_brief, "call_llm_chat", lambda *a, **kw: response())
    plan = digital_brief.interpret_brief("Make a pen plotter and draw a line.")
    assert plan["drawing"] == [[[10, 10], [30, 50]]]
    assert plan["requirements"] == {"pen_lift_mm": 4}


def test_malformed_provider_reply_gets_one_retry_before_starting_a_build(monkeypatch):
    replies = iter([{"ok": False, "error": "copilot_cli_invalid_json"}, response()])
    monkeypatch.setattr(digital_brief, "call_llm_chat", lambda *a, **kw: next(replies))
    assert digital_brief.interpret_brief("Draw a line on my Ender-3.")["status"] == "build"


@pytest.mark.parametrize("changes", [
    {"case_id": "unknown"}, {"case_id": "fielddeck-5"}, {"requirements": {"pen_lift_mm": 40}},
    {"status": "unsupported"}, {"drawing": [[[0, 0], [101, 0]]]},
    {"drawing": [[[5, 5], [5, 5]]]}, {"drawing": "run some code"},
])
def test_invalid_model_output_cannot_start_build(monkeypatch, changes):
    monkeypatch.setattr(digital_brief, "call_llm_chat", lambda *a, **kw: response(**changes))
    with pytest.raises((ValueError, digital_brief.BriefProviderError)):
        digital_brief.interpret_brief("Describe a device.")


def test_unresolved_http_prompt_creates_no_project(tmp_path, monkeypatch):
    monkeypatch.setattr(digital_brief, "call_llm_chat", lambda *a, **kw: response(
        status="needs_detail", case_id=None, requirements={}, drawing=None,
        explanation="Which donor printer should the adapter fit?"))
    with DigitalStudyEngine(project_root=tmp_path / "projects", job_db=tmp_path / "jobs.db") as engine:
        app = FastAPI()
        app.include_router(create_digital_project_router(engine.projects, engine.backend))
        result = TestClient(app).post("/v1/digital/prompt", json={"brief": "Adapt my printer."})
        assert result.status_code == 200
        assert result.json()["project"] is None
        assert not list(engine.projects.root.glob("digital-*"))


def test_followup_supplies_the_archived_drawing_and_settings(tmp_path, monkeypatch):
    from hardware_splicer import digital_cases as cases, digital_project as digital

    drawing = [[[10, 10], [30, 50]]]
    path = tmp_path / cases.DRAWING
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(drawing))
    requirements = cases.registered("ender3-penplotter").defaults()
    seal = {"case_id": "ender3-penplotter", "summary": {"requirements": requirements},
            "artifact_sha256": {cases.DRAWING: "verified"}}
    envelope = {"revision": 1, "snapshot": {"designBrief": {"brief": "Draw a single line."}}}
    monkeypatch.setattr(digital, "validated_run", lambda *args: (envelope, tmp_path, seal))
    def interpret(brief, *, current):
        assert current["drawing"] == drawing
        assert current["requirements"] == requirements
        assert current["previous_brief"] == "Draw a single line."
        return {"status": "build", "requirements": {}, "drawing": None}

    monkeypatch.setattr(digital_brief, "interpret_brief", interpret)
    with DigitalStudyEngine(project_root=tmp_path / "projects", job_db=tmp_path / "jobs.db") as engine:
        assert engine.from_prompt("Keep this drawing.", project_id="plotter")["unchanged"]
