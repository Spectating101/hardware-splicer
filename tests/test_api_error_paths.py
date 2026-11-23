"""Server-side errors are logged in full but never return on-disk paths to the client."""
import logging

from hardware_splicer import engineering_assurance_api, project_api
from hardware_splicer.project_store import CorruptProject

SECRET = "/home/someone/.cache/hardware-splicer/state/projects/p1/project.json"


def test_project_api_hides_corrupt_project_paths(caplog):
    with caplog.at_level(logging.ERROR):
        error = project_api._project_error(CorruptProject(f"cannot read valid project JSON: {SECRET}"))
    assert error.status_code == 500 and error.detail["type"] == "corrupt_project"
    assert SECRET not in str(error.detail) and SECRET in caplog.text


def test_assurance_api_hides_server_error_text(caplog):
    with caplog.at_level(logging.ERROR):
        corrupt = engineering_assurance_api._error(CorruptProject(f"project JSON must be an object: {SECRET}"))
        other = engineering_assurance_api._error(RuntimeError(f"open failed: {SECRET}"))
    for error in (corrupt, other):
        assert error.status_code == 500 and SECRET not in str(error.detail)
    assert SECRET in caplog.text
    # Client errors keep their message: they describe the request, not the server.
    assert engineering_assurance_api._error(ValueError("bad revision")).detail["message"] == "bad revision"
