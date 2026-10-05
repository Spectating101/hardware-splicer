"""Server-issued operator tokens for review-thread authorship.

A matching token proves only that the caller held a secret issued by whoever
controls the local registry. It does not upgrade engineering authority, and it
is not a cryptographic identity beyond this lookup.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

_TOKENS_ENV = "HARDWARE_SPLICER_OPERATOR_TOKENS"
_TOKENS_FILE_ENV = "HARDWARE_SPLICER_OPERATOR_TOKENS_FILE"
_HASH_PREFIX = "sha256:"
_HASH_HEX_LEN = 64
_OPERATOR_KINDS = frozenset({"human", "agent"})
_MAX_OPERATOR_ID = 120
_HASH_KEY_RE_LEN = len(_HASH_PREFIX) + _HASH_HEX_LEN


class OperatorIdentityError(RuntimeError):
    pass


class OperatorTokenInvalid(OperatorIdentityError):
    pass


class OperatorRegistryError(OperatorIdentityError):
    pass


@dataclass(frozen=True)
class OperatorIdentity:
    id: str
    kind: str


def hash_operator_token(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{_HASH_PREFIX}{digest}"


def _looks_like_token_hash(key: object) -> bool:
    if not isinstance(key, str) or len(key) != _HASH_KEY_RE_LEN:
        return False
    if not key.startswith(_HASH_PREFIX):
        return False
    hex_part = key[len(_HASH_PREFIX) :]
    return all(char in "0123456789abcdefABCDEF" for char in hex_part)


def _validate_entry(entry: object) -> OperatorIdentity:
    if not isinstance(entry, Mapping):
        raise OperatorRegistryError("operator token registry entry must be an object")
    extra = set(entry) - {"id", "kind"}
    if extra:
        raise OperatorRegistryError("operator token registry entry contains unknown fields")
    kind = entry.get("kind")
    if kind not in _OPERATOR_KINDS:
        raise OperatorRegistryError("operator token registry kind must be 'human' or 'agent'")
    operator_id = entry.get("id")
    if not isinstance(operator_id, str):
        raise OperatorRegistryError("operator token registry id must be a string")
    if (
        not operator_id
        or len(operator_id) > _MAX_OPERATOR_ID
        or operator_id != operator_id.strip()
        or any(unicodedata.category(ch).startswith("C") for ch in operator_id)
    ):
        raise OperatorRegistryError(
            f"operator token registry id must be 1 to {_MAX_OPERATOR_ID} characters"
        )
    return OperatorIdentity(id=operator_id, kind=kind)


def _registry_text(env: Mapping[str, str]) -> str:
    if _TOKENS_ENV in env:
        raw = env.get(_TOKENS_ENV)
        if raw is not None and str(raw).strip():
            return str(raw)
        raise OperatorRegistryError("operator token registry is not configured")
    path_value = env.get(_TOKENS_FILE_ENV)
    if path_value is None or not str(path_value).strip():
        raise OperatorRegistryError("operator token registry is not configured")
    path = Path(str(path_value).strip())
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OperatorRegistryError("operator token registry file cannot be read") from exc


def _load_registry(env: Mapping[str, str]) -> dict[str, OperatorIdentity]:
    text = _registry_text(env)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OperatorRegistryError("operator token registry is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise OperatorRegistryError("operator token registry must be a JSON object")
    registry: dict[str, OperatorIdentity] = {}
    for key, entry in payload.items():
        if not _looks_like_token_hash(key):
            raise OperatorRegistryError("operator token registry keys must be sha256 hashes")
        normalized_key = f"{_HASH_PREFIX}{str(key)[len(_HASH_PREFIX):].lower()}"
        registry[normalized_key] = _validate_entry(entry)
    return registry


def resolve_operator(token: str | None, env: Mapping[str, str] | None = None) -> OperatorIdentity | None:
    if token is None or token == "":
        return None
    registry = _load_registry(os.environ if env is None else env)
    supplied_hex = hash_operator_token(token)[len(_HASH_PREFIX) :]
    matched: OperatorIdentity | None = None
    for key, identity in registry.items():
        registry_hex = key[len(_HASH_PREFIX) :]
        if hmac.compare_digest(supplied_hex, registry_hex):
            matched = identity
    if matched is None:
        raise OperatorTokenInvalid("operator token is not recognized")
    return matched


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["hash-token"]:
        token = sys.stdin.read()
        if token.endswith("\r\n"):
            token = token[:-2]
        elif token.endswith("\n"):
            token = token[:-1]
        print(hash_operator_token(token))
        return 0
    if args == ["generate-token"]:
        token = secrets.token_urlsafe(32)
        print(token)
        print(hash_operator_token(token))
        print("store the token with the operator; put only the hash in the registry", file=sys.stderr)
        return 0
    print(
        "usage: python -m hardware_splicer.operator_identity hash-token|generate-token",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
