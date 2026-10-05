from __future__ import annotations

import hashlib
import hmac
import io
import json
from pathlib import Path

import pytest

from hardware_splicer.operator_identity import (
    OperatorIdentity,
    OperatorRegistryError,
    OperatorTokenInvalid,
    hash_operator_token,
    main,
    resolve_operator,
)


def _token() -> str:
    return "operator-secret-token"


def _registry(token: str = _token(), *, operator_id: str = "alice", kind: str = "human") -> dict:
    return {hash_operator_token(token): {"id": operator_id, "kind": kind}}


def _env_tokens(registry: dict) -> dict[str, str]:
    return {"HARDWARE_SPLICER_OPERATOR_TOKENS": json.dumps(registry)}


def test_hash_operator_token_is_sha256_prefixed_hex() -> None:
    token = "abc"
    hashed = hash_operator_token(token)
    assert hashed == "sha256:" + hashlib.sha256(b"abc").hexdigest()
    assert hashed == hash_operator_token(token)
    assert hashed.startswith("sha256:")
    assert len(hashed) == len("sha256:") + 64


def test_cli_hash_token_reads_stdin_and_prints_registry_hash(capsys, monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("abc\n"))
    assert main(["hash-token"]) == 0
    assert capsys.readouterr().out == hash_operator_token("abc") + "\n"


def test_cli_hash_token_strips_only_one_trailing_newline(capsys, monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("abc \n\n"))
    assert main(["hash-token"]) == 0
    assert capsys.readouterr().out == hash_operator_token("abc \n") + "\n"
    monkeypatch.setattr("sys.stdin", io.StringIO("abc\t"))
    assert main(["hash-token"]) == 0
    assert capsys.readouterr().out == hash_operator_token("abc\t") + "\n"


def test_cli_generate_token_prints_token_then_hash(capsys) -> None:
    assert main(["generate-token"]) == 0
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert len(lines) == 2
    token, hashed = lines
    assert len(token) >= 43
    assert hashed == hash_operator_token(token)
    assert captured.err == "store the token with the operator; put only the hash in the registry\n"


def test_resolve_operator_returns_none_when_token_missing() -> None:
    assert resolve_operator(None, env={}) is None
    assert resolve_operator("", env={}) is None
    assert resolve_operator(None, env=_env_tokens(_registry())) is None


def test_resolve_operator_returns_registry_identity_for_valid_token() -> None:
    token = _token()
    identity = resolve_operator(token, env=_env_tokens(_registry(token, operator_id="alice", kind="human")))
    assert identity == OperatorIdentity(id="alice", kind="human")

    agent_token = "agent-token"
    agent = resolve_operator(
        agent_token,
        env=_env_tokens(_registry(agent_token, operator_id="review-bot", kind="agent")),
    )
    assert agent == OperatorIdentity(id="review-bot", kind="agent")


def test_resolve_operator_unknown_token_raises() -> None:
    with pytest.raises(OperatorTokenInvalid):
        resolve_operator("unknown-token", env=_env_tokens(_registry()))


def test_resolve_operator_missing_registry_fails_closed() -> None:
    with pytest.raises(OperatorRegistryError):
        resolve_operator(_token(), env={})


def test_resolve_operator_corrupt_registry_fails_closed() -> None:
    with pytest.raises(OperatorRegistryError):
        resolve_operator(_token(), env={"HARDWARE_SPLICER_OPERATOR_TOKENS": "{not-json"})
    with pytest.raises(OperatorRegistryError):
        resolve_operator(_token(), env={"HARDWARE_SPLICER_OPERATOR_TOKENS": "[]"})
    with pytest.raises(OperatorRegistryError):
        resolve_operator(
            _token(),
            env={"HARDWARE_SPLICER_OPERATOR_TOKENS": json.dumps({"not-a-hash": {"id": "a", "kind": "human"}})},
        )
    with pytest.raises(OperatorRegistryError):
        resolve_operator(
            _token(),
            env={
                "HARDWARE_SPLICER_OPERATOR_TOKENS": json.dumps(
                    {hash_operator_token(_token()): {"id": "", "kind": "human"}}
                )
            },
        )
    with pytest.raises(OperatorRegistryError):
        resolve_operator(
            _token(),
            env={
                "HARDWARE_SPLICER_OPERATOR_TOKENS": json.dumps(
                    {hash_operator_token(_token()): {"id": "a" * 121, "kind": "human"}}
                )
            },
        )
    with pytest.raises(OperatorRegistryError):
        resolve_operator(
            _token(),
            env={
                "HARDWARE_SPLICER_OPERATOR_TOKENS": json.dumps(
                    {hash_operator_token(_token()): {"id": "alice", "kind": "system"}}
                )
            },
        )


@pytest.mark.parametrize("kind", [" human ", "Human", "agent\n"])
def test_registry_kind_must_be_exact(kind: str) -> None:
    with pytest.raises(OperatorRegistryError):
        resolve_operator(
            _token(),
            env={
                "HARDWARE_SPLICER_OPERATOR_TOKENS": json.dumps(
                    {hash_operator_token(_token()): {"id": "alice", "kind": kind}}
                )
            },
        )


@pytest.mark.parametrize("operator_id", [" alice", "alice ", ""])
def test_registry_id_rejects_whitespace_and_empty(operator_id: str) -> None:
    with pytest.raises(OperatorRegistryError):
        resolve_operator(
            _token(),
            env={
                "HARDWARE_SPLICER_OPERATOR_TOKENS": json.dumps(
                    {hash_operator_token(_token()): {"id": operator_id, "kind": "human"}}
                )
            },
        )


def test_resolve_operator_uses_constant_time_compare(monkeypatch) -> None:
    match = "first-token"
    registry = {
        hash_operator_token(match): {"id": "alice", "kind": "human"},
        hash_operator_token("second-token"): {"id": "bob", "kind": "human"},
        hash_operator_token("third-token"): {"id": "carol", "kind": "agent"},
    }
    seen: list[tuple[str, str]] = []
    real = hmac.compare_digest

    def spy(left: str | bytes, right: str | bytes):
        seen.append((left, right))
        return real(left, right)

    monkeypatch.setattr("hardware_splicer.operator_identity.hmac.compare_digest", spy)
    identity = resolve_operator(match, env=_env_tokens(registry))
    assert identity == OperatorIdentity(id="alice", kind="human")
    assert len(seen) == 3
    expected_hex = hashlib.sha256(match.encode("utf-8")).hexdigest()
    assert expected_hex in seen[0]


def test_tokens_never_appear_in_exception_text() -> None:
    secret = "super-secret-token-value-xyz"
    cases = [
        ({}, OperatorRegistryError),
        ({"HARDWARE_SPLICER_OPERATOR_TOKENS": "{not-json"}, OperatorRegistryError),
        (_env_tokens(_registry("other-token")), OperatorTokenInvalid),
    ]
    for env, error in cases:
        with pytest.raises(error) as caught:
            resolve_operator(secret, env=env)
        text = f"{caught.value!s}{caught.value!r}{caught.value.args!r}"
        assert secret not in text


def test_file_based_registry(tmp_path: Path) -> None:
    token = _token()
    registry_path = tmp_path / "operator-tokens.json"
    registry_path.write_text(json.dumps(_registry(token, operator_id="file-user", kind="agent")), encoding="utf-8")
    identity = resolve_operator(
        token,
        env={"HARDWARE_SPLICER_OPERATOR_TOKENS_FILE": str(registry_path)},
    )
    assert identity == OperatorIdentity(id="file-user", kind="agent")

    env_wins = resolve_operator(
        token,
        env={
            **_env_tokens(_registry(token, operator_id="env-user", kind="human")),
            "HARDWARE_SPLICER_OPERATOR_TOKENS_FILE": str(registry_path),
        },
    )
    assert env_wins == OperatorIdentity(id="env-user", kind="human")

    missing = tmp_path / "missing.json"
    with pytest.raises(OperatorRegistryError):
        resolve_operator(token, env={"HARDWARE_SPLICER_OPERATOR_TOKENS_FILE": str(missing)})


@pytest.mark.parametrize("blank", ["", "  "])
def test_blank_tokens_env_does_not_fall_back_to_file(tmp_path: Path, blank: str) -> None:
    token = _token()
    registry_path = tmp_path / "operator-tokens.json"
    registry_path.write_text(json.dumps(_registry(token, operator_id="file-user", kind="agent")), encoding="utf-8")
    with pytest.raises(OperatorRegistryError, match="operator token registry is not configured"):
        resolve_operator(
            token,
            env={
                "HARDWARE_SPLICER_OPERATOR_TOKENS": blank,
                "HARDWARE_SPLICER_OPERATOR_TOKENS_FILE": str(registry_path),
            },
        )
