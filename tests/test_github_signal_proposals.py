"""Offline proposal admission, trial isolation and independent artifact checks."""
import json
import subprocess
from types import SimpleNamespace

import pytest

from hardware_splicer import github_signal_proposals as proposals
from hardware_splicer.github_signal_pipeline import (
    ADAPTERS, SignalEvaluationError, acquire_pinned_repo, evaluate_signals, normalize_feed,
)
from hardware_splicer.github_signal_task_router import run_task, select_task

IBOM, KIKIT = proposals.IBOM, proposals.KIKIT


def _literal_base64(text):
    """Deterministic LZString stream encoder using only literal codes.

    Deliberately no compression dictionary: independent fixture construction
    exercises bit packing and width transitions without mirroring the decoder.
    """
    raw = text.encode("utf-16-le")
    units = [int.from_bytes(raw[i:i + 2], "little") for i in range(0, len(raw), 2)]
    bits = []

    def emit(value, width):
        bits.extend((value >> i) & 1 for i in range(width))

    width, remaining = 2, 0
    for index, unit in enumerate(units):
        emit(0 if unit < 256 else 1, width)
        emit(unit, 8 if unit < 256 else 16)
        if index == 0:
            width, remaining = 3, 4
        else:
            for _ in range(2):  # literal entry, then previous+first entry
                remaining -= 1
                if remaining == 0:
                    remaining = 1 << width
                    width += 1
    emit(2, width)
    # LZString always flushes the last 6-bit cell, including a zero cell
    # when the stream ends on a cell boundary.
    bits.extend([0] * (6 - len(bits) % 6))
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    result = "".join(alphabet[sum(bits[i + j] << (5 - j) for j in range(6))]
                     for i in range(0, len(bits), 6))
    return result + "=" * (-len(result) % 4)


def _page(data):
    return ('<html><script>var pcbdata = JSON.parse(LZString.decompressFromBase64("'
            + _literal_base64(json.dumps(data, ensure_ascii=False)) + '"));</script></html>')


@pytest.mark.parametrize("encoded,expected", [
    ("Q===", ""), ("IJA=", "A"), ("BYUwNmD2Q===", "hello"),
    ("BIUwNmD2AEDukCcwBMg=", "Hello world"),
    # Codes (0, 2 bits), ('a', 8), (4, 3), (2, 3): the new-entry case.
    ("IYo=", "aaa"),
])
def test_known_lzstring_vectors(encoded, expected):
    assert proposals.decompress_from_base64(encoded) == expected


@pytest.mark.parametrize("text", ["", "A", "abc", "R1 R1 R1", "板件 Ω 😀", "abcde" * 1000])
def test_deterministically_generated_lzstring_vectors(text):
    assert proposals.decompress_from_base64(_literal_base64(text)) == text


def test_literal_encoder_known_vector():
    assert _literal_base64("") == "Q==="
    assert _literal_base64("A") == "IJA="


@pytest.mark.parametrize("value", ["", "!", "A", "////", "Q===garbage"])
def test_invalid_lzstring_fails_closed(value):
    with pytest.raises(ValueError):
        proposals.decompress_from_base64(value)


@pytest.fixture
def board(tmp_path):
    path = tmp_path / "board.kicad_pcb"
    path.write_text('(kicad_pcb (footprint "R" (property "Reference" "R1")) '
                    '(module "C" (fp_text reference "C1")))')
    return path


def test_independent_ibom_check_matches_modern_and_legacy_refs(board, tmp_path):
    html = tmp_path / "ibom.html"
    html.write_text(_page({"footprints": [{"ref": "C1"}, {"ref": "R1"}], "bom": {"both": []}}))
    checked = proposals.check_ibom_output(board, html)
    assert checked["ok"] is True
    assert checked["board_reference_count"] == 2
    assert checked["bom_present"] is True


@pytest.mark.parametrize("data,missing,extra", [
    ({"footprints": [{"ref": "R1"}], "bom": {}}, ["C1"], []),
    ({"footprints": [{"ref": "R1"}, {"ref": "C1"}, {"ref": "U1"}], "bom": {}}, [], ["U1"]),
])
def test_independent_ibom_check_reports_reference_mismatches(board, tmp_path, data, missing, extra):
    html = tmp_path / "ibom.html"
    html.write_text(_page(data))
    checked = proposals.check_ibom_output(board, html)
    assert checked["ok"] is False
    assert checked["missing_refs"] == missing and checked["extra_refs"] == extra


@pytest.mark.parametrize("data", [{"footprints": []}, {"footprints": [None], "bom": {}}, []])
def test_independent_ibom_check_requires_bom_and_valid_data(board, tmp_path, data):
    html = tmp_path / "ibom.html"
    html.write_text(_page(data))
    assert proposals.check_ibom_output(board, html)["ok"] is False


@pytest.fixture
def trial(tmp_path, board, monkeypatch):
    checkout = tmp_path / "source"
    (checkout / ".git").mkdir(parents=True)
    (checkout / "InteractiveHtmlBom").mkdir()
    (checkout / "InteractiveHtmlBom/generate_interactive_bom.py").write_text("# fixture")
    (checkout / "LICENSE").write_text("MIT License\n\nFixture\n")
    state = {"head": proposals.PROPOSED_ADAPTERS[IBOM]["proposed_commit"],
             "dirty": "", "bwrap": "/usr/bin/bwrap", "calls": [],
             "capabilities": {"pcbnew": True, "wx": True, "KiCad 9": True},
             "exit": 0, "output_refs": ["R1", "C1"], "timeout": False}
    out = tmp_path / "out"

    def run(argv, **kwargs):
        if argv[0] == "git":
            assert kwargs["env"]["GIT_CONFIG_GLOBAL"] == "/dev/null"
            if "--show-toplevel" in argv:
                result = str(checkout)
            elif "HEAD" in argv:
                result = state["head"]
            else:
                assert "--ignored=matching" in argv
                result = state["dirty"]
            return SimpleNamespace(stdout=result, returncode=0)
        if argv[0] == "/usr/bin/python3":
            assert argv[1:4] == ["-I", "-B", "-c"]
            assert kwargs["cwd"] == "/" and "PYTHONPATH" not in kwargs["env"]
            return SimpleNamespace(stdout=json.dumps(state["capabilities"]), returncode=0)
        assert argv[0] == "/usr/bin/bwrap"
        state["calls"].append((argv, kwargs))
        if state["timeout"]:
            raise subprocess.TimeoutExpired(argv, 120, stderr=b"timeout detail")
        (out / "ibom.html").write_text(_page({
            "footprints": [{"ref": ref} for ref in state["output_refs"]], "bom": {"both": []},
        }))
        return SimpleNamespace(returncode=state["exit"], stderr="diagnostic" * 500, stdout="")

    monkeypatch.setattr(proposals.subprocess, "run", run)
    monkeypatch.setattr(proposals.shutil, "which", lambda _: state["bwrap"])
    return checkout, board, out, state


@pytest.mark.parametrize("failure,match", [
    ("dirty", "dirty"), ("head", "proposed commit"), ("license", "LICENSE"),
    ("bwrap", "bubblewrap required"), ("capabilities", "host capabilities unavailable"),
])
def test_trial_refusals_precede_execution(trial, failure, match):
    checkout, board, out, state = trial
    if failure == "license":
        (checkout / "LICENSE").write_text("Proprietary\n")
    elif failure == "capabilities":
        state["capabilities"]["wx"] = False
    else:
        state[failure] = {"dirty": "?? injected.py", "head": "a" * 40, "bwrap": None}[failure]
    with pytest.raises(SignalEvaluationError, match=match):
        proposals.trial_proposed_adapter(IBOM, checkout, board, out)
    assert state["calls"] == [] and not out.exists()


def test_blocked_proposal_refused_before_preflight(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("blocked proposal must not invoke subprocess")
    monkeypatch.setattr(proposals.subprocess, "run", forbidden)
    with pytest.raises(SignalEvaluationError, match="blocked.*shapely.*pinned, reviewed"):
        proposals.trial_proposed_adapter(KIKIT, tmp_path, tmp_path, tmp_path)


def test_trial_uses_exact_offline_argv_and_records_evidence(trial):
    checkout, board, out, state = trial
    record = proposals.trial_proposed_adapter(IBOM, checkout, board, out)
    expected = [x.format(checkout=checkout, board=board, out=out)
                for x in proposals.PROPOSED_ADAPTERS[IBOM]["argv_template"]]
    expected[0] = "/usr/bin/bwrap"
    assert state["calls"][0][0] == expected
    assert "--unshare-all" in expected and expected.count("--bind") == 1
    assert state["calls"][0][1]["env"] == {"PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    assert record["ok"] and record["approval_effect"] == "none"
    assert record["exit_code"] == 0 and record["checkout_clean_after"]
    assert len(record["stderr_tail"]) == 2000 and record["elapsed_seconds"] >= 0
    assert record["host_capabilities"]["wx"] is True
    assert record["input_sha256"] == proposals.sha256_file(board)
    assert record["output_sha256"] == proposals.sha256_file(out / "ibom.html")
    assert json.loads((out / proposals.TRIAL_FILENAME).read_text()) == record


@pytest.mark.parametrize("failure", ["exit", "mismatch", "timeout"])
def test_failed_trial_retains_record_with_no_approval(trial, failure):
    checkout, board, out, state = trial
    if failure == "mismatch":
        state["output_refs"] = ["R1"]
    elif failure == "timeout":
        state["timeout"] = True
    else:
        state["exit"] = 2
    record = proposals.trial_proposed_adapter(IBOM, checkout, board, out)
    assert record["ok"] is False and record["approval_effect"] == "none"
    assert (out / proposals.TRIAL_FILENAME).is_file()
    if failure == "mismatch":
        assert record["output_check"]["missing_refs"] == ["C1"]
    if failure == "timeout":
        assert record["exit_code"] is None and record["stderr_tail"] == "timeout detail"


def test_trial_refuses_output_overlapping_checkout_or_existing_files(trial):
    checkout, board, out, state = trial
    for bad_out in (checkout / "out", board.parent):
        with pytest.raises(SignalEvaluationError, match="output must be an empty, separate"):
            proposals.trial_proposed_adapter(IBOM, checkout, board, bad_out)
    assert not state["calls"]


def _feed(repo):
    return {"schema_version": "hardware_splicer.github_signal_feed.v1",
            "source": "github_repository_search", "candidates": [{
                "repository": repo, "commit_sha": proposals.PROPOSED_ADAPTERS[repo]["proposed_commit"],
                "license_spdx_id": "MIT", "approved": True,
                "vetting": {"approval_effect": "approved", "machine_tested": True},
            }]}


@pytest.mark.parametrize("repo", [IBOM, KIKIT])
def test_pipeline_never_executes_proposals(tmp_path, monkeypatch, repo):
    def forbidden(*args, **kwargs):
        pytest.fail("proposal entered normal acquisition/execution")
    monkeypatch.setattr(proposals.subprocess, "run", forbidden)
    normalized = normalize_feed(_feed(repo))[0]
    assert normalized["discovered_only"] and normalized["adapter_id"] is None
    with pytest.raises(SignalEvaluationError, match="not approved"):
        acquire_pinned_repo(normalized, tmp_path / "source", fetch=True)
    result = evaluate_signals(_feed(repo), checkout=tmp_path / "source",
                              schematic=tmp_path / "absent", output_dir=tmp_path / "out",
                              fetch=True, run_fn=forbidden)
    assert result["ok"] is False and result["capability"] is None
    assert result["candidates"][0]["executed"] is False
    assert result["candidates"][0]["state"] == proposals.PROPOSED_ADAPTERS[repo]["status"]


@pytest.mark.parametrize("objective,repo,status", [
    ("interactive assembly BOM / placement viewer for a KiCad board", IBOM, "tool_proposed_pending_approval"),
    ("Interactive HTML BOM", IBOM, "tool_proposed_pending_approval"),
    ("placement viewer", IBOM, "tool_proposed_pending_approval"),
    ("panelisation", KIKIT, "tool_blocked"),
    ("panelization", KIKIT, "tool_blocked"),
    ("fab outputs", KIKIT, "tool_blocked"),
    ("fabrication outputs for a KiCad board", KIKIT, "tool_blocked"),
])
def test_router_reports_proposal_and_never_executes(tmp_path, monkeypatch, objective, repo, status):
    def forbidden(*args, **kwargs):
        pytest.fail("router must never execute/acquire proposals")
    monkeypatch.setattr(proposals.subprocess, "run", forbidden)
    plan = select_task(objective)
    assert plan["selected_repository"] == repo
    assert plan["selection_model"] == "rules_v1_not_an_llm"
    result = run_task(objective=objective, feed=_feed(repo), output_dir=tmp_path / "out",
                      checkout_base=tmp_path / "absent", fetch=True, run_fn=forbidden)
    assert result["status"] == status and result["proposal"] == repo
    assert result["ok"] is False and result["executed"] is False
    assert result["approval_effect"] == "none"
    if repo == KIKIT:
        assert "shapely" in result["blockers"][0] and "runtime installation forbidden" in result["blockers"][0]


def test_approved_adapter_set_unchanged():
    assert set(ADAPTERS) == {"tipoLi5890/akcli", "0x12net/kdif"}
    assert set(ADAPTERS).isdisjoint(proposals.PROPOSED_ADAPTERS)
