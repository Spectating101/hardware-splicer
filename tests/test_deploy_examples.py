"""Invariants of the shipped systemd and nginx examples (deploy/)."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NGINX = (ROOT / "deploy/nginx/splice-agent.conf.example").read_text(encoding="utf-8")
UNIT = (ROOT / "deploy/systemd/hardware-splicer.service.example").read_text(encoding="utf-8")


def _directives(text: str) -> list[str]:
    return [line.split("#", 1)[0].strip() for line in text.splitlines() if line.split("#", 1)[0].strip()]


def _unit_values(key: str) -> list[str]:
    return [line.split("=", 1)[1] for line in _directives(UNIT) if line.startswith(key + "=")]


def test_systemd_unit_runs_hs_serve_on_loopback_as_a_service_account():
    (exec_start,) = _unit_values("ExecStart")
    argv = shlex.split(exec_start)
    assert argv[0].endswith("/bin/hs-serve")
    assert "--ui" in argv
    assert argv[argv.index("--host") + 1] == "127.0.0.1"
    assert "--allow-remote" not in argv
    (user,) = _unit_values("User")
    assert user not in {"root", "0"}


def test_systemd_unit_is_hardened_and_writes_only_its_state_directory():
    for key, value in {
        "NoNewPrivileges": "yes", "ProtectSystem": "strict", "ProtectHome": "yes", "PrivateTmp": "yes",
    }.items():
        assert _unit_values(key) == [value], key
    (writable,) = _unit_values("ReadWritePaths")
    env = dict(item.split("=", 1) for item in _unit_values("Environment"))
    for name in ("HARDWARE_SPLICER_STATE_DIR", "HARDWARE_SPLICER_TMP_ROOT", "HOME"):
        assert Path(env[name]).is_relative_to(writable), name
    assert "HARDWARE_SPLICER_TESTING_MODE" not in env


def test_nginx_requires_credentials_on_every_location():
    directives = _directives(NGINX)
    tls_server = NGINX.split("server {", 2)[1]
    # Server-level auth is inherited by every location, including the event stream.
    assert re.search(r"^\s{4}auth_basic \$splice_auth;", tls_server, re.M)
    assert re.search(r"^\s{4}auth_basic_user_file \S+;", tls_server, re.M)
    assert not any(line.startswith("auth_basic off") for line in directives)
    assert "include /etc/nginx/splice-agent-api-keys.map;" in directives
    assert 'default "Hardware Splicer";' in directives
    locations = re.findall(r"location\s+([^{]+)\{", NGINX)
    assert any("events" in item for item in locations) and any(item.strip() == "/" for item in locations)


def test_nginx_commits_no_key_and_keeps_tls_and_headers_sane():
    assert "CHANGE_ME" not in NGINX
    assert not re.search(r"\$http_x_api_key\s*!?=", NGINX), "keys belong in the included map, not the config"
    assert "ssl_protocols TLSv1.2 TLSv1.3;" in _directives(NGINX)
    assert "proxy_pass http://127.0.0.1:8787;" in _directives(NGINX)
    # proxy_set_header inside a location would silently drop the server-level set.
    for body in re.findall(r"location[^{]+\{([^}]*)\}", NGINX):
        assert "proxy_set_header" not in body
    assert 'proxy_set_header Authorization "";' in _directives(NGINX)
