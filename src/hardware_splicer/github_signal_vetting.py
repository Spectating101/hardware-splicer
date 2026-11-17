"""Report-only candidate evidence. Nothing here admits or executes an adapter.

PCM archives are metadata only: they are never downloaded, installed or run.
Missing source pins stay missing; an archive SHA-256 is not a Git commit.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import quote, urljoin, urlsplit
from urllib.error import HTTPError
from urllib.request import Request, urlopen

CHECKS = (
    "Maintained", "License", "Dangerous-Workflow", "Branch-Protection",
    "Code-Review", "Vulnerabilities", "Binary-Artifacts", "Pinned-Dependencies",
)
_REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
# GitHub URL paths whose first segment is a site section, not a repository owner.
_NOT_OWNERS = frozenset({"sponsors", "orgs", "apps", "marketplace", "topics", "features", "settings", "users", "collections"})
_SHA = re.compile(r"[0-9a-f]{40}")
_MAX_JSON = 8 * 1024 * 1024


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _result(call: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Source failures are evidence, never an exception through the vetter."""
    try:
        result = dict(call())
        result.setdefault("status", "ok")
    except Exception as exc:
        result = {"status": "error", "message": f"{type(exc).__name__}: {exc}"[:500]}
    result.setdefault("retrieved_at", _timestamp())
    return result


def _http_bytes(url: str, *, transport: Any, timeout: float) -> bytes:
    request = Request(url, headers={
        "Accept": "application/json", "User-Agent": "Hardware-Splicer-evidence/1",
    })
    with transport(request, timeout=timeout) as response:
        if not 200 <= response.status < 300:
            raise ValueError(f"HTTP {response.status}")
        raw = response.read(_MAX_JSON + 1)
    if len(raw) > _MAX_JSON:
        raise ValueError("metadata exceeds 8 MiB limit")
    return raw


def _json_object(raw: bytes) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def _repository(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    if value.startswith("https://github.com/"):
        value = urlsplit(value).path.strip("/")
        if value.endswith(".git"):
            value = value[:-4]
    if not _REPOSITORY.fullmatch(value) or value.split("/")[0].lower() in _NOT_OWNERS:
        return None
    return value


def parse_pcm_feed(data: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize packages.json (or embedded repository packages), without I/O.

    PCM does not declare Git source pins. Preserve every version and its
    archive hash, including packages without GitHub URLs or licence claims.
    A repository.json URL descriptor is resolved by load_pcm_feed instead.
    """
    packages = data.get("packages")
    if not isinstance(packages, list):
        raise ValueError("PCM packages must be a list; resolve repository.json first")
    candidates = []
    for package in packages:
        if not isinstance(package, Mapping) or not package.get("identifier"):
            raise ValueError("PCM package missing identifier")
        resources = package.get("resources", {})
        versions = package.get("versions", [])
        if not isinstance(resources, dict) or not isinstance(versions, list):
            raise ValueError("invalid PCM resources or versions")
        if any(not isinstance(version, dict) for version in versions):
            raise ValueError("invalid PCM version")
        repo = next((repo for value in resources.values()
                     if (repo := _repository(value))), None)
        candidates.append({
            "repository": repo, "commit_sha": None,
            "license_spdx_id": package.get("license") or "UNKNOWN",
            "intent": "KiCad PCM candidate for human review only",
            "pcm": {key: package.get(key) for key in (
                "identifier", "name", "type", "license", "resources", "versions",
            )},
        })
    return {
        "schema_version": "hardware_splicer.github_signal_feed.v1",
        "source": "github_signals_export", "provenance_provider": "kicad_pcm",
        "candidates": candidates,
    }


def load_pcm_feed(
    location: str | Path, *, offline: bool = False,
    transport: Any = None, timeout: float = 15,
) -> dict[str, Any]:
    """Read PCM metadata only; follow at most one repository packages pointer."""
    transport = transport or urlopen

    def read(target: str) -> bytes:
        parsed = urlsplit(target)
        if parsed.scheme in {"http", "https"}:
            if offline:
                raise ValueError("offline mode cannot read remote PCM metadata")
            return _http_bytes(target, transport=transport, timeout=timeout)
        if parsed.scheme:
            raise ValueError("unsupported PCM metadata scheme")
        raw = Path(target).read_bytes()
        if len(raw) > _MAX_JSON:
            raise ValueError("metadata exceeds 8 MiB limit")
        return raw

    location = str(location)
    data = _json_object(read(location))
    descriptor = data.get("packages")
    if isinstance(descriptor, dict):
        url, digest = descriptor.get("url"), descriptor.get("sha256")
        if not isinstance(url, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", str(digest)):
            raise ValueError("PCM packages descriptor needs URL and SHA-256")
        target = (urljoin(location, url) if urlsplit(location).scheme
                  else str(Path(location).parent / url) if not urlsplit(url).scheme else url)
        raw = read(target)
        if hashlib.sha256(raw).hexdigest() != digest.lower():
            raise ValueError("PCM packages metadata SHA-256 mismatch")
        data = _json_object(raw)
    feed = parse_pcm_feed(data)
    feed["pcm_metadata"] = {"location": location, "retrieved_at": _timestamp()}
    return feed


def parse_scorecard(data: Mapping[str, Any], pinned_commit: str | None) -> dict[str, Any]:
    score = data["score"]
    commit = data["repo"]["commit"]
    if (not isinstance(score, (int, float)) or isinstance(score, bool)
            or not -1 <= score <= 10 or not isinstance(commit, str)
            or not _SHA.fullmatch(commit)):
        raise ValueError("invalid Scorecard score or commit")
    checks = {name: None for name in CHECKS}
    for check in data["checks"]:
        name, value = check["name"], check["score"]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not -1 <= value <= 10:
            raise ValueError("invalid Scorecard check score")
        if name in checks:
            checks[name] = value
    matches = bool(pinned_commit and commit == pinned_commit)
    return {
        "status": "ok" if matches else "different_commit",
        "score": score, "scored_commit": commit,
        "matches_pinned_commit": matches, "checks": checks,
    }


class ScorecardClient:
    def __init__(self, *, transport: Any = None, timeout: float = 15):
        self.transport = transport or urlopen
        self.timeout = timeout

    def get(self, repository: str, pinned_commit: str | None) -> dict[str, Any]:
        def fetch() -> dict[str, Any]:
            repo = _repository(repository)
            if not repo:
                raise ValueError("invalid GitHub repository")
            url = "https://api.securityscorecards.dev/projects/github.com/" + repo
            try:
                raw = _http_bytes(url, transport=self.transport, timeout=self.timeout)
            except HTTPError as exc:
                if exc.code == 404:
                    # Scorecard publishes results only for repositories it scans; absence is not a failure.
                    return {"status": "not_scored", "url": url}
                raise
            return {**parse_scorecard(_json_object(raw), pinned_commit), "url": url}
        return _result(fetch)


def parse_ecosystems(data: Mapping[str, Any]) -> dict[str, Any]:
    if not any(key in data for key in ("license", "archived", "fork", "pushed_at")):
        raise ValueError("missing ecosyste.ms repository metadata")
    license_id = data.get("license")
    if isinstance(license_id, dict):
        license_id = license_id.get("spdx_id")
    if license_id is not None and not isinstance(license_id, str):
        raise ValueError("invalid ecosyste.ms SPDX licence")
    for key in ("archived", "fork"):
        if data.get(key) is not None and not isinstance(data[key], bool):
            raise ValueError(f"invalid ecosyste.ms {key}")
    pushed = data.get("pushed_at")
    if pushed is not None:
        if not isinstance(pushed, str):
            raise ValueError("invalid ecosyste.ms pushed_at timestamp")
        if datetime.fromisoformat(pushed.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("ecosyste.ms pushed_at timestamp needs a timezone")
    result = {key: data.get(key) for key in (
        "archived", "fork", "stargazers_count", "pushed_at", "default_branch",
    )}
    result["license_spdx_id"] = license_id
    if "dependent_repos_count" in data:
        result["dependent_repos_count"] = data["dependent_repos_count"]
    return result


class EcosystemsClient:
    def __init__(self, *, transport: Any = None, timeout: float = 15):
        self.transport = transport or urlopen
        self.timeout = timeout

    def get(self, repository_url: str) -> dict[str, Any]:
        def fetch() -> dict[str, Any]:
            repo = _repository(repository_url)
            if not repo:
                raise ValueError("invalid GitHub repository URL")
            url = "https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/" + quote(repo, safe="")
            data = _json_object(_http_bytes(url, transport=self.transport, timeout=self.timeout))
            return {**parse_ecosystems(data), "url": url}
        return _result(fetch)


def summarize_scancode(data: Mapping[str, Any]) -> dict[str, Any]:
    expressions, missing = set(), []
    for file in data["files"]:
        if file.get("type") != "file":
            continue
        found = []
        if file.get("detected_license_expression_spdx"):
            found.append(file["detected_license_expression_spdx"])
        found.extend(d["license_expression_spdx"] for d in file.get("license_detections", [])
                     if d.get("license_expression_spdx"))
        found.extend(d["spdx_license_key"] for d in file.get("licenses", [])
                     if d.get("spdx_license_key"))
        expressions.update(found)
        if not found:
            missing.append(file["path"])
        if file.get("scan_errors"):
            raise ValueError("ScanCode reported file scan errors")
    return {"spdx_expressions": sorted(expressions), "files_lacking_license_info": missing}


def scan_local_license(
    checkout: Path | None, pinned_commit: str | None, *, timeout: float = 120,
) -> dict[str, Any]:
    """Scan an explicit clean pinned checkout, never fetch or execute its code.

    Bubblewrap denies network and writes to the checkout. If isolation is not
    available, return evidence of that limitation rather than run on the host.
    """
    def scan() -> dict[str, Any]:
        executable = shutil.which("scancode")
        if not executable:
            return {"status": "unavailable"}
        if checkout is None:
            return {"status": "unavailable", "message": "no local checkout supplied"}
        bwrap = shutil.which("bwrap")
        if not bwrap:
            return {"status": "unavailable", "message": "network-isolated ScanCode requires bubblewrap"}
        root = Path(checkout).resolve()
        if not isinstance(pinned_commit, str) or not _SHA.fullmatch(pinned_commit):
            raise ValueError("local scan requires a full pinned commit")
        if not root.is_dir() or not (root / ".git").exists():
            raise ValueError("local scan requires an existing Git checkout")
        if Path(executable).resolve().is_relative_to(root):
            raise ValueError("refusing a ScanCode executable inside the candidate checkout")
        env = {"PATH": os.defpath, "HOME": "/tmp", "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_OPTIONAL_LOCKS": "0"}
        for args, expected in ((["rev-parse", "HEAD"], pinned_commit),
                               (["status", "--porcelain", "--untracked-files=all"], "")):
            checked = subprocess.run(
                ["git", "-C", str(root), "-c", "core.fsmonitor=false", *args],
                capture_output=True, text=True, check=True, timeout=10, env=env,
                cwd="/",
            )
            if checked.stdout.strip() != expected:
                raise ValueError("local checkout differs from clean pinned commit")
        with tempfile.TemporaryDirectory(prefix="hs-license-") as temp:
            output = Path(temp) / "scan.json"
            subprocess.run(
                [bwrap, "--die-with-parent", "--unshare-net", "--ro-bind", "/", "/",
                 "--tmpfs", "/tmp", "--bind", temp, "/output", "--chdir", "/",
                 "--ro-bind", str(root), "/checkout", "--setenv", "HOME", "/tmp",
                 executable, "--license", "--json-pp", "/output/scan.json", "/checkout"],
                capture_output=True, text=True, check=True, timeout=timeout, env=env,
                cwd="/",
            )
            return summarize_scancode(_json_object(output.read_bytes()))
    return _result(scan)


def _license(value: Any) -> str | None:
    if not isinstance(value, str) or value.strip().upper() in {"", "UNKNOWN", "NOASSERTION", "NONE"}:
        return None
    return " ".join(value.split())


def vet_candidate(
    candidate: Mapping[str, Any], *, scorecard_client: Any = None,
    ecosystems_client: Any = None, scancode_fn: Any = None,
    checkout: Path | None = None, offline: bool = False, now: datetime | None = None,
) -> dict[str, Any]:
    """Attach evidence only. This module does not import the adapter registry."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    license_claim = candidate.get("license_spdx_id", candidate.get("license_claim"))
    declared = _license(license_claim)
    sources = {"feed": _result(lambda: {
        "status": "ok" if declared else "unavailable", "license_spdx_id": license_claim,
        "pcm": candidate.get("pcm"),
    })}
    repo = _repository(candidate.get("repository"))
    pin = candidate.get("commit_sha")
    for name, call in (
        ("scorecard", lambda: (scorecard_client or ScorecardClient()).get(repo, pin)),
        ("ecosystems", lambda: (ecosystems_client or EcosystemsClient()).get("https://github.com/" + repo)),
    ):
        sources[name] = _result(
            (lambda: {"status": "unavailable", "message": "offline" if offline else "no GitHub repository"})
            if offline or not repo else call
        )
    sources["scancode"] = _result(lambda: (scancode_fn or scan_local_license)(checkout, pin))
    eco, card, scan = (sources[key] for key in ("ecosystems", "scorecard", "scancode"))
    expressions = {"feed": [declared] if declared else [], "ecosystems": [], "scancode": []}
    if eco["status"] == "ok" and (license_id := _license(eco.get("license_spdx_id"))):
        expressions["ecosystems"] = [license_id]
    if scan["status"] == "ok":
        expressions["scancode"] = [value for item in scan.get("spdx_expressions", [])
                                   if (value := _license(item))]
    card_license = card.get("checks", {}).get("License") if card["status"] == "ok" else None
    # Scorecard tests presence only; it cannot establish an SPDX expression.
    present = True if card_license == 10 else False if card_license == 0 else None
    known = {value.casefold() for values in expressions.values() for value in values}
    mismatch = len(known) > 1 or (present is False and bool(known))
    flags = []
    if mismatch:
        flags.append("licence_mismatch")
    if not known and present is not True:
        flags.append("no_licence")
    if eco["status"] == "ok":
        flags.extend(key for key in ("archived", "fork") if eco.get(key) is True)
        if eco.get("pushed_at"):
            try:
                pushed = datetime.fromisoformat(eco["pushed_at"].replace("Z", "+00:00"))
                if (now - pushed).total_seconds() > 365 * 86400:
                    flags.append("unmaintained_over_365_days")
            except (ValueError, TypeError, AttributeError):
                eco.update(status="error", message="invalid ecosyste.ms pushed_at timestamp")
    if card["status"] == "ok":
        if 0 <= card.get("score", -1) < 4:
            flags.append("scorecard_below_4")
        dangerous = card.get("checks", {}).get("Dangerous-Workflow")
        if dangerous is not None and 0 <= dangerous < 10:
            flags.append("dangerous_workflow")
    return {
        "sources": sources, "retrieved_at": now.isoformat(),
        "licence_agreement": {
            "status": ("mismatch" if mismatch else "consistent"
                       if sum(bool(values) for values in expressions.values()) > 1
                       else "insufficient_evidence"),
            "spdx_expressions": expressions, "scorecard_license_present": present,
            "note": "Scorecard checks licence presence only; SPDX expressions require human review.",
        },
        "review_flags": flags, "approval_effect": "none", "requires_human_review": True,
    }
