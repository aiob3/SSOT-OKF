#!/usr/bin/env python3
"""Homologação isolada do Deja-vu para o harness SSOT-OKF."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any, IO, Mapping, cast

VERSION = "0.16.4"
ASSET = f"deja-vu_{VERSION}_linux_amd64.tar.gz"
RELEASE_URL = f"https://github.com/vshulcz/deja-vu/releases/download/v{VERSION}"
REPOSITORY = "vshulcz/deja-vu"
SECRET = "ghp_" + ("A" * 36)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parents[1]
WORK_ROOT = PROJECT_ROOT / ".work"
TEST_PATH = PROJECT_ROOT / "tests" / "test_homologate.py"
PRD_PATH = PROJECT_ROOT / "docs" / "PRD.md"
RESULTS_PATH = PROJECT_ROOT / "docs" / "HOMOLOGATION-RESULTS.md"
DOWNLOAD_LIMITS = {
    ASSET: 64 * 1024 * 1024,
    "checksums.txt": 1024 * 1024,
    f"{ASSET}.spdx.json": 8 * 1024 * 1024,
}
MAX_TAR_MEMBERS = 32
MAX_TAR_MEMBER_BYTES = 64 * 1024 * 1024
MAX_TAR_TOTAL_BYTES = 128 * 1024 * 1024
TRANSPORT_ENV = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
)
EXPECTED_HARNESSES = ("claude", "codex", "copilot", "hermes")
EXPECTED_MCP_CLIENTS = {"claude-code", "codex", "copilot", "hermes"}
ALLOWED_MCP_STATES = {"config-missing", "not-installed"}
EXPECTED_SESSION_PATHS = {
    ("claude", "homolog-claude-001"): WORK_ROOT
    / "fixtures"
    / "claude"
    / "-data-SSOT-OKF"
    / "homolog-claude-001.jsonl",
    ("codex", "homolog-codex-001"): WORK_ROOT
    / "fixtures"
    / "codex"
    / "sessions"
    / "2026"
    / "07"
    / "30"
    / "rollout-2026-07-30T12-00-00-homolog-codex-001.jsonl",
    ("copilot", "homolog-copilot-001"): WORK_ROOT
    / "fixtures"
    / "copilot"
    / "homolog-copilot-001"
    / "events.jsonl",
    ("hermes", "homolog-hermes-001"): WORK_ROOT
    / "fixtures"
    / "hermes"
    / "state.db",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum(checksums: str, archive: Path) -> str:
    matches = []
    for line in checksums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == archive.name:
            matches.append(parts[0].lower())
    if len(matches) != 1 or not re.fullmatch(r"[0-9a-f]{64}", matches[0]):
        raise ValueError(f"checksum missing for {archive.name}")
    actual = _sha256(archive)
    if actual != matches[0]:
        raise ValueError(f"checksum mismatch for {archive.name}")
    return actual


def query_passed(payload: dict[str, Any], harness: str, session: str) -> bool:
    if payload.get("schema_version") != 2 or payload.get("tier") != "exact":
        return False
    hits = payload.get("hits")
    if not isinstance(hits, list):
        return False
    expected_path = EXPECTED_SESSION_PATHS.get((harness, session))
    if expected_path is None:
        return False
    return any(
        isinstance(hit, dict)
        and isinstance((candidate := hit.get("session")), dict)
        and candidate.get("harness") == harness
        and candidate.get("id") == session
        and hit.get("tier") == "exact"
        and isinstance(candidate.get("path"), str)
        and Path(os.path.abspath(candidate["path"])).resolve(strict=False)
        == expected_path.resolve(strict=False)
        and isinstance(candidate.get("source"), dict)
        and candidate["source"].get("origin") == "local"
        and candidate["source"].get("instance") == "ssot-okf-homologation"
        for hit in hits[:5]
    )


def retrieval_gate(results: list[dict[str, object]]) -> bool:
    return (
        len(results) == 8
        and Counter(result.get("harness") for result in results)
        == Counter({name: 2 for name in EXPECTED_HARNESSES})
        and all(
            result.get("passed") is True and result.get("tier") == "exact"
            for result in results
        )
    )


def _is_project_owned_path(path: str | Path, root: Path) -> bool:
    candidate = Path(os.path.abspath(path))
    root = Path(os.path.abspath(root))
    try:
        return candidate.is_relative_to(root) and candidate.resolve(strict=False).is_relative_to(
            root.resolve(strict=False)
        )
    except (OSError, RuntimeError):
        return False


def parse_sources(output: str, work: Path) -> list[dict[str, object]]:
    work = Path(os.path.abspath(work))
    parsed: list[dict[str, object]] = []
    names: set[str] = set()
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            raise ValueError("invalid sources schema")
        name, roots, stats = parts
        match = re.fullmatch(
            r"sessions=(\d+) messages=(\d+) size=.+ redacted=(\d+)", stats
        )
        paths = roots.split(os.pathsep)
        if (
            not name
            or name in names
            or match is None
            or not paths
            or any(not _is_project_owned_path(path, work) for path in paths)
        ):
            raise ValueError("sources must be unique, valid, and project-owned")
        names.add(name)
        sessions, messages, redacted = map(int, match.groups())
        parsed.append(
            {
                "name": name,
                "paths": paths,
                "sessions": sessions,
                "messages": messages,
                "redacted": redacted,
            }
        )
    return parsed


def sources_are_isolated(output: str, work: Path) -> bool:
    try:
        parsed = parse_sources(output, work)
    except ValueError:
        return False
    expected_paths = {
        "claude": work / "fixtures" / "claude",
        "codex": work / "fixtures" / "codex",
        "copilot": work / "fixtures" / "copilot",
        "hermes": work / "home" / ".hermes" / "profiles",
    }
    expected_counts = {
        "claude": (1, 2, 1),
        "codex": (1, 2, 0),
        "copilot": (1, 2, 0),
        "hermes": (1, 2, 0),
    }
    by_name = {str(item["name"]): item for item in parsed}
    if set(expected_paths) - set(by_name):
        return False
    for name, item in by_name.items():
        counts = (item["sessions"], item["messages"], item["redacted"])
        if name in expected_paths:
            if counts != expected_counts[name] or item["paths"] != [str(expected_paths[name])]:
                return False
        elif counts != (0, 0, 0):
            return False
    return True


def mcp_is_unwired(doctor: dict[str, Any], work: Path) -> bool:
    entries = doctor.get("mcp")
    if doctor.get("schema_version") != 2 or not isinstance(entries, list) or not entries:
        return False
    work = Path(os.path.abspath(work))
    names: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            return False
        name, state, path = entry.get("name"), entry.get("state"), entry.get("path")
        if not isinstance(name, str) or name in names:
            return False
        if state not in ALLOWED_MCP_STATES:
            return False
        if state == "config-missing" and path is None:
            return False
        if path is not None and (
            not isinstance(path, str) or not _is_project_owned_path(path, work)
        ):
            return False
        names.add(name)
    return EXPECTED_MCP_CLIENTS.issubset(names)


def validate_work_path(work: Path, project_root: Path) -> Path:
    project = project_root.resolve(strict=True)
    candidate = Path(os.path.abspath(work))
    if candidate != project / ".work":
        raise RuntimeError("work directory must be the project-owned .work path")
    if candidate.is_symlink():
        raise RuntimeError("work directory must not be a symlink")
    if candidate.exists():
        if not candidate.is_dir():
            raise RuntimeError("work path must be a directory")
        symlink = next((path for path in candidate.rglob("*") if path.is_symlink()), None)
        if symlink is not None:
            raise RuntimeError(f"work tree contains symlink: {symlink}")
    return candidate


def clean_work(work: Path, project_root: Path) -> None:
    candidate = validate_work_path(work, project_root)
    if os.path.lexists(candidate):
        shutil.rmtree(candidate)
    if os.path.lexists(candidate):
        raise RuntimeError("work directory still exists after cleanup")


def _base_env(work: Path) -> dict[str, str]:
    work = Path(os.path.abspath(work))
    return {
        "PATH": os.environ.get("PATH", os.defpath),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "HOME": str(work / "home"),
        "XDG_CACHE_HOME": str(work / "cache"),
        "XDG_CONFIG_HOME": str(work / "config"),
        "XDG_DATA_HOME": str(work / "data"),
        "XDG_STATE_HOME": str(work / "state"),
        "XDG_RUNTIME_DIR": str(work / "runtime"),
        "TMPDIR": str(work / "tmp"),
    }


def isolated_env(work: Path) -> dict[str, str]:
    work = Path(os.path.abspath(work))
    return {
        **_base_env(work),
        "PYTHONDONTWRITEBYTECODE": "1",
        "DEJA_INDEX_DIR": str(work / "index"),
        "DEJA_CLAUDE_ROOT": str(work / "fixtures" / "claude"),
        "DEJA_CODEX_ROOT": str(work / "fixtures" / "codex"),
        "DEJA_COPILOT_ROOT": str(work / "fixtures" / "copilot"),
        "DEJA_HERMES_DB": str(work / "fixtures" / "hermes" / "state.db"),
        "DEJA_OFFLINE": "1",
        "DEJA_RECALL": "off",
        "DEJA_EMBED": "off",
        "DEJA_SOURCE_INSTANCE": "ssot-okf-homologation",
    }


def github_env(work: Path, token: str | None = None) -> dict[str, str]:
    work = Path(os.path.abspath(work))
    env = {
        **_base_env(work),
        "GH_CONFIG_DIR": str(work / "gh-config"),
        "GH_PROMPT_DISABLED": "1",
    }
    env.update({name: os.environ[name] for name in TRANSPORT_ENV if name in os.environ})
    if token:
        env["GH_TOKEN"] = token
    return env


def resolve_attestation_token() -> str | None:
    """Allowlist only an explicit token, falling back to the gh keyring login."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    completed = _run(["gh", "auth", "token"], check=False)
    return completed.stdout.strip() or None


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def write_fixtures(work: Path) -> dict[str, object]:
    work = work.resolve()
    fixtures = work / "fixtures"
    claude = fixtures / "claude" / "-data-SSOT-OKF" / "homolog-claude-001.jsonl"
    codex = (
        fixtures
        / "codex"
        / "sessions"
        / "2026"
        / "07"
        / "30"
        / "rollout-2026-07-30T12-00-00-homolog-codex-001.jsonl"
    )
    copilot = fixtures / "copilot" / "homolog-copilot-001" / "events.jsonl"
    hermes = fixtures / "hermes" / "state.db"
    _write_jsonl(
        claude,
        [
            {
                "type": "user",
                "sessionId": "homolog-claude-001",
                "timestamp": "2026-07-30T12:00:00Z",
                "message": {"role": "user", "content": "A ação tática adotou café aurora."},
            },
            {
                "type": "assistant",
                "sessionId": "homolog-claude-001",
                "timestamp": "2026-07-30T12:00:01Z",
                "message": {
                    "role": "assistant",
                    "content": f"Canário lilás confirmou o plano. token={SECRET}",
                },
            },
        ],
    )
    _write_jsonl(
        codex,
        [
            {
                "timestamp": "2026-07-30T12:01:00Z",
                "type": "session_meta",
                "payload": {"session_id": "homolog-codex-001", "cwd": "/data/SSOT-OKF"},
            },
            {
                "timestamp": "2026-07-30T12:01:01Z",
                "type": "response_item",
                "payload": {"role": "user", "content": [{"type": "input_text", "text": "Mapa sereno iniciou a revisão."}]},
            },
            {
                "timestamp": "2026-07-30T12:01:02Z",
                "type": "response_item",
                "payload": {"role": "assistant", "content": [{"type": "output_text", "text": "Cedro azul preservou a decisão."}]},
            },
        ],
    )
    _write_jsonl(
        copilot,
        [
            {
                "type": "session.start",
                "data": {
                    "sessionId": "homolog-copilot-001",
                    "startTime": "2026-07-30T12:02:00Z",
                    "context": {"cwd": "/data/SSOT-OKF"},
                },
                "timestamp": "2026-07-30T12:02:00Z",
            },
            {
                "type": "user.message",
                "data": {"content": "Ponte âmbar abriu o caminho."},
                "timestamp": "2026-07-30T12:02:01Z",
            },
            {
                "type": "assistant.message",
                "data": {"content": "Lápis verde registrou a evidência."},
                "timestamp": "2026-07-30T12:02:02Z",
            },
        ],
    )
    hermes.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(hermes) as db:
        db.execute(
            "CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT, timestamp REAL NOT NULL)"
        )
        db.executemany(
            "INSERT INTO messages(session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            [
                ("homolog-hermes-001", "user", "Trilha marfim guardou o contexto.", 1785412980.0),
                ("homolog-hermes-001", "assistant", "Pêssego dourado confirmou a origem.", 1785412981.0),
            ],
        )

    queries = [
        {"query": "ação tática", "harness": "claude", "session": "homolog-claude-001"},
        {"query": "canário lilás", "harness": "claude", "session": "homolog-claude-001"},
        {"query": "mapa sereno", "harness": "codex", "session": "homolog-codex-001"},
        {"query": "cedro azul", "harness": "codex", "session": "homolog-codex-001"},
        {"query": "ponte âmbar", "harness": "copilot", "session": "homolog-copilot-001"},
        {"query": "lápis verde", "harness": "copilot", "session": "homolog-copilot-001"},
        {"query": "trilha marfim", "harness": "hermes", "session": "homolog-hermes-001"},
        {"query": "pêssego dourado", "harness": "hermes", "session": "homolog-hermes-001"},
    ]
    return {"sources": [str(claude), str(codex), str(copilot), str(hermes)], "queries": queries}


def _run(
    args: list[str],
    env: dict[str, str] | None = None,
    *,
    check: bool = True,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        env=env,
        check=check,
        cwd=cwd,
        text=True,
        capture_output=True,
    )


def _atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".part",
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.chmod(mode)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def download_asset(url: str, target: Path, *, max_bytes: int) -> None:
    if os.path.lexists(target):
        metadata = target.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError(f"cached asset is not a regular file: {target.name}")
        if metadata.st_size > max_bytes:
            raise RuntimeError(f"cached asset exceeds size limit: {target.name}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".part",
    )
    temporary_path = Path(temporary)
    total = 0
    try:
        with os.fdopen(fd, "wb") as output, urllib.request.urlopen(
            url, timeout=60
        ) as response:
            length = response.headers.get("Content-Length")
            if length is not None and int(length) > max_bytes:
                raise RuntimeError(f"download exceeds size limit: {target.name}")
            while chunk := response.read(64 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise RuntimeError(f"download exceeds size limit: {target.name}")
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if total == 0:
            raise RuntimeError(f"empty download: {target.name}")
        os.replace(temporary_path, target)
    finally:
        temporary_path.unlink(missing_ok=True)


def _download(name: str, target: Path, *, max_bytes: int | None = None) -> None:
    download_asset(
        f"{RELEASE_URL}/{name}",
        target,
        max_bytes=max_bytes if max_bytes is not None else DOWNLOAD_LIMITS[name],
    )


def _copy_member(source: IO[bytes], target: Path, expected_size: int) -> None:
    fd, temporary = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".part",
    )
    temporary_path = Path(temporary)
    total = 0
    try:
        with os.fdopen(fd, "wb") as output:
            while chunk := source.read(64 * 1024):
                total += len(chunk)
                if total > expected_size or total > MAX_TAR_MEMBER_BYTES:
                    raise RuntimeError("archive member exceeds declared size")
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if total != expected_size:
            raise RuntimeError("archive member size mismatch")
        temporary_path.chmod(0o755)
        os.replace(temporary_path, target)
    finally:
        temporary_path.unlink(missing_ok=True)


def extract_release(archive: Path, bin_dir: Path) -> Path:
    if os.path.lexists(bin_dir) and bin_dir.is_symlink():
        raise RuntimeError("binary directory must not be a symlink")
    binary_member: tarfile.TarInfo | None = None
    member_count = 0
    total_size = 0
    with tarfile.open(archive, "r:*") as bundle:
        for member in bundle:
            member_count += 1
            if member_count > MAX_TAR_MEMBERS:
                raise RuntimeError("archive member count limit exceeded")
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise RuntimeError("archive path escapes extraction root")
            if member.issym() or member.islnk():
                raise RuntimeError("archive links are forbidden")
            if not (member.isfile() or member.isdir()):
                raise RuntimeError("archive contains unsupported member type")
            if member.isfile():
                if member.size < 0 or member.size > MAX_TAR_MEMBER_BYTES:
                    raise RuntimeError("archive member size limit exceeded")
                total_size += member.size
                if total_size > MAX_TAR_TOTAL_BYTES:
                    raise RuntimeError("archive total size limit exceeded")
                if name.name == "deja":
                    if binary_member is not None:
                        raise RuntimeError("archive must contain exactly one regular deja")
                    binary_member = member
        if binary_member is None:
            raise RuntimeError("archive must contain exactly one regular deja")
        if os.path.lexists(bin_dir):
            shutil.rmtree(bin_dir)
        bin_dir.mkdir(parents=True)
        extracted = bundle.extractfile(binary_member)
        if extracted is None:
            raise RuntimeError("unable to read deja from archive")
        with extracted:
            _copy_member(extracted, bin_dir / "deja", binary_member.size)
    return bin_dir / "deja"


def validate_spdx(document: object) -> dict[str, object]:
    if not isinstance(document, dict):
        raise RuntimeError("SBOM is not an SPDX object")
    required = {
        "spdxVersion": "SPDX-2.3",
        "SPDXID": "SPDXRef-DOCUMENT",
        "dataLicense": "CC0-1.0",
        "name": ASSET,
    }
    if any(document.get(key) != value for key, value in required.items()):
        raise RuntimeError("SBOM identity or SPDX schema mismatch")
    if not isinstance(document.get("documentNamespace"), str) or not document[
        "documentNamespace"
    ].startswith("https://"):
        raise RuntimeError("SBOM document namespace missing")
    creation = document.get("creationInfo")
    packages = document.get("packages")
    if (
        not isinstance(creation, dict)
        or not isinstance(creation.get("creators"), list)
        or not creation["creators"]
        or not isinstance(creation.get("created"), str)
        or not isinstance(packages, list)
        or not packages
        or any(not isinstance(package, dict) for package in packages)
    ):
        raise RuntimeError("SBOM SPDX structure is incomplete")
    return document


def validate_sbom(document: object, archive_name: str, digest: str) -> dict[str, str]:
    validated = validate_spdx(document)
    linked = [
        package
        for package in cast(list[dict[str, object]], validated["packages"])
        if package.get("name") == archive_name
        and package.get("versionInfo") == f"sha256:{digest}"
        and isinstance(package.get("SPDXID"), str)
    ]
    if len(linked) != 1:
        raise RuntimeError("SBOM does not bind the archive digest")
    return {
        "spdx_version": cast(str, validated["spdxVersion"]),
        "archive_sha256": digest,
        "document_namespace": cast(str, validated["documentNamespace"]),
    }


def validate_attestation(
    payload: object, expected_subjects: dict[str, str]
) -> dict[str, object]:
    if not isinstance(payload, list) or not payload:
        raise RuntimeError("attestation verification returned no result")
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        result = entry.get("verificationResult")
        if not isinstance(result, dict):
            continue
        statement = result.get("statement")
        signature = result.get("signature")
        certificate = signature.get("certificate") if isinstance(signature, dict) else None
        if not isinstance(statement, dict) or not isinstance(certificate, dict):
            continue
        subjects = statement.get("subject")
        if not isinstance(subjects, list):
            continue
        observed = {
            subject.get("name"): subject.get("digest", {}).get("sha256")
            for subject in subjects
            if isinstance(subject, dict) and isinstance(subject.get("digest"), dict)
        }
        if not all(observed.get(name) == digest for name, digest in expected_subjects.items()):
            continue
        repository_uri = certificate.get("sourceRepositoryURI")
        signer_identity = certificate.get("subjectAlternativeName") or repository_uri
        source_digest = certificate.get("sourceRepositoryDigest")
        source_ref = certificate.get("sourceRepositoryRef")
        if (
            statement.get("predicateType") != "https://slsa.dev/provenance/v1"
            or not isinstance(source_digest, str)
            or re.fullmatch(r"[0-9a-fA-F]{40,64}", source_digest) is None
            or not isinstance(source_ref, str)
            or source_ref != f"refs/tags/v{VERSION}"
            or repository_uri not in (None, f"https://github.com/{REPOSITORY}")
            or not isinstance(signer_identity, str)
            or not signer_identity.startswith(f"https://github.com/{REPOSITORY}")
            or len(signer_identity) > 512
        ):
            continue
        return {
            "status": "verified",
            "repository": REPOSITORY,
            "signer_identity": signer_identity,
            "source_digest": source_digest,
            "source_ref": source_ref,
            "predicate_type": statement.get("predicateType"),
            "subjects": expected_subjects,
            "verified_timestamps": len(result.get("verifiedTimestamps", [])),
        }
    raise RuntimeError("attestation identity or subject mismatch")


def prepare_release(work: Path) -> tuple[Path, dict[str, object]]:
    downloads = work / "downloads"
    archive = downloads / ASSET
    checksums = downloads / "checksums.txt"
    sbom = downloads / f"{ASSET}.spdx.json"
    for path in (archive, checksums, sbom):
        _download(path.name, path)
    published = checksums.read_text(encoding="utf-8")
    digest = verify_checksum(published, archive)
    sbom_digest = verify_checksum(published, sbom)
    sbom_evidence = validate_sbom(
        json.loads(sbom.read_text(encoding="utf-8")), ASSET, digest
    )
    attestation = _run(
        [
            "gh",
            "attestation",
            "verify",
            str(archive),
            "--repo",
            REPOSITORY,
            "--format",
            "json",
            "--deny-self-hosted-runners",
            "--source-ref",
            f"refs/tags/v{VERSION}",
        ],
        github_env(work, resolve_attestation_token()),
    )
    attestation_evidence = validate_attestation(
        json.loads(attestation.stdout), {ASSET: digest}
    )
    binary = extract_release(archive, work / "bin")
    return binary, {
        "version": VERSION,
        "asset": ASSET,
        "sha256": digest,
        "checksum": "verified",
        "attestation": attestation_evidence,
        "sbom": {
            "asset": sbom.name,
            "sha256": sbom_digest,
            "checksum": "verified",
            "attestation": "not-published-not-claimed",
            **sbom_evidence,
        },
    }


def _fingerprint(path: Path) -> dict[str, object]:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {"state": "missing"}
    if stat.S_ISLNK(metadata.st_mode):
        return {"state": "symlink", "target": os.readlink(path)}
    if stat.S_ISREG(metadata.st_mode):
        return {"state": "file", "size": metadata.st_size, "sha256": _sha256(path)}
    if stat.S_ISDIR(metadata.st_mode):
        entries = []
        for child in sorted(path.rglob("*")):
            relative = str(child.relative_to(path))
            child_metadata = child.lstat()
            if stat.S_ISLNK(child_metadata.st_mode):
                entries.append((relative, "symlink", os.readlink(child)))
            elif stat.S_ISREG(child_metadata.st_mode):
                entries.append((relative, "file", child_metadata.st_size, _sha256(child)))
            else:
                entries.append((relative, "directory"))
        encoded = json.dumps(entries, ensure_ascii=False, sort_keys=True).encode()
        return {"state": "directory", "sha256": hashlib.sha256(encoded).hexdigest()}
    return {"state": "other", "mode": stat.S_IFMT(metadata.st_mode)}


def snapshot_paths(paths: list[Path]) -> dict[str, dict[str, object]]:
    return {str(path): _fingerprint(path) for path in paths}


def live_config_paths(environ: Mapping[str, str] | None = None) -> list[Path]:
    environ = os.environ if environ is None else environ
    home = Path(environ.get("HOME", str(Path.home())))
    xdg_config = Path(environ.get("XDG_CONFIG_HOME", str(home / ".config")))
    return [
        home / ".claude.json",
        home / ".codex" / "config.toml",
        home / ".copilot" / "config.json",
        home / ".copilot" / "skills" / "deja-history" / "SKILL.md",
        home / ".cursor" / "mcp.json",
        home / ".gemini" / "settings.json",
        home / ".gemini" / "config" / "mcp_config.json",
        home / ".grok" / "config.toml",
        home / ".qwen" / "settings.json",
        home / ".kimi-code" / "mcp.json",
        home / ".cline" / "data" / "settings" / "cline_mcp_settings.json",
        home / ".pi" / "agent" / "mcp.json",
        home / ".openclaw" / "openclaw.json",
        home / ".hermes" / "config.yaml",
        xdg_config / "opencode" / "opencode.json",
        xdg_config / "goose" / "config.yaml",
    ]


def _file_hashes(paths: list[str]) -> dict[str, str]:
    return {path: _sha256(Path(path)) for path in paths}


def _reset_work(work: Path) -> None:
    downloads = work / "downloads"
    if work.exists():
        for child in work.iterdir():
            if child == downloads:
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            if os.path.lexists(child):
                raise RuntimeError(f"failed to remove work artifact: {child.name}")
    else:
        work.mkdir()
    validate_work_path(work, PROJECT_ROOT)
    for variable in (
        "HOME",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "XDG_RUNTIME_DIR",
        "TMPDIR",
    ):
        Path(_base_env(work)[variable]).mkdir(parents=True, exist_ok=True)
    (work / "gh-config").mkdir()


def _quality_gates(work: Path) -> dict[str, dict[str, object]]:
    env = {
        **_base_env(work),
        "PYTHONDONTWRITEBYTECODE": "1",
        "RUFF_CACHE_DIR": str(work / "cache" / "ruff"),
    }
    commands = {
        "unittest": [
            os.fspath(Path(sys.executable)),
            "-B",
            "-m",
            "unittest",
            os.fspath(TEST_PATH),
            "-v",
        ],
        "ruff": ["ruff", "check", os.fspath(Path(__file__)), os.fspath(TEST_PATH)],
    }
    results: dict[str, dict[str, object]] = {}
    for name, command in commands.items():
        try:
            completed = _run(command, env, check=False, cwd=REPO_ROOT)
            output = "\n".join(
                line
                for line in (completed.stdout + "\n" + completed.stderr).splitlines()
                if line.strip()
            )[-4000:]
            results[name] = {
                "passed": completed.returncode == 0,
                "returncode": completed.returncode,
                "output": output,
            }
        except FileNotFoundError as error:
            results[name] = {"passed": False, "returncode": None, "output": str(error)}
    return results


def _snapshot_digest(snapshot: dict[str, dict[str, object]]) -> str:
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _source_evidence(
    parsed: list[dict[str, object]], work: Path
) -> list[dict[str, object]]:
    evidence = []
    for item in parsed:
        evidence.append(
            {
                **{key: item[key] for key in ("name", "sessions", "messages", "redacted")},
                "paths": [
                    str(Path(path).relative_to(work))
                    for path in cast(list[str], item["paths"])
                ],
            }
        )
    return evidence


def render_results(report: dict[str, object], report_sha256: str) -> str:
    release = cast(dict[str, object], report["release"])
    attestation = cast(dict[str, object], release["attestation"])
    sbom = cast(dict[str, object], release["sbom"])
    quality = cast(dict[str, dict[str, object]], report["quality_gates"])
    queries = cast(list[dict[str, object]], report["queries"])
    criteria = cast(dict[str, bool], report["criteria"])
    counts = Counter(str(query["harness"]) for query in queries if query["passed"])
    source_digest = attestation.get("source_digest") or "não informado pelo certificado"
    lines = [
        "<!-- generated-by: harness/deja_vu/scripts/homologate.py; source: .work/report.json -->",
        f"# Evidência de homologação — Deja-vu v{VERSION}",
        "",
        f"- **Execução UTC:** {report['timestamp_utc']}",
        f"- **Ambiente:** {report['environment']}",
        f"- **Veredito:** {report['verdict']}",
        f"- **Relatório local:** `.work/report.json` (SHA-256 `{report_sha256}`)",
        "",
        "## Release",
        "",
        f"- Archive: `{release['asset']}`; SHA-256 `{release['sha256']}`; checksum verificado.",
        f"- Attestation do archive: `{attestation['status']}`; repositório `{attestation['repository']}`.",
        f"- Identidade sanitizada: `{attestation['signer_identity']}`; source digest `{source_digest}`.",
        f"- SBOM: `{sbom['asset']}`; SHA-256 `{sbom['sha256']}`; `{sbom['spdx_version']}` validado e ligado ao digest do archive.",
        "- Não foi publicada/exigida attestation separada para o SBOM; sua evidência é checksum + estrutura SPDX.",
        "",
        "## Qualidade e recuperação",
        "",
        f"- unittest: {'PASS' if quality['unittest']['passed'] else 'FAIL'}.",
        f"- ruff: {'PASS' if quality['ruff']['passed'] else 'FAIL'}.",
    ]
    lines.extend(f"- {name}: {counts[name]}/2 no tier `exact`." for name in EXPECTED_HARNESSES)
    lines.extend(
        [
            "",
            "## Critérios",
            "",
            "| Critério | Resultado |",
            "|---|---|",
            *(f"| `{name}` | {'PASS' if passed else 'FAIL'} |" for name, passed in criteria.items()),
            "",
            "## Limite de rede",
            "",
            "O Deja recebeu `DEJA_OFFLINE=1`; `doctor` recebeu `--offline`; buscas receberam `--no-embed`.",
            "Não houve sandbox/observador de egress disponível, portanto este relatório não afirma egress zero.",
            "",
            "## Gate",
            "",
            "Este resultado cobre somente fixtures sintéticas project-owned. Não autoriza fontes reais, instalação global, MCP, `remember`, hooks ou auto-recall.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_report_and_results(report: dict[str, object], work: Path) -> str:
    report_data = (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    report_path = work / "report.json"
    _atomic_write(report_path, report_data)
    digest = hashlib.sha256(report_data).hexdigest()
    if RESULTS_PATH.is_symlink() or not RESULTS_PATH.parent.resolve().is_relative_to(
        PROJECT_ROOT.resolve()
    ):
        raise RuntimeError("results document path is not project-owned")
    _atomic_write(RESULTS_PATH, render_results(report, digest).encode(), mode=0o644)
    return digest


def run_homologation(work: Path) -> dict[str, object]:
    work = validate_work_path(work, PROJECT_ROOT)
    _reset_work(work)
    quality = _quality_gates(work)
    manifest = write_fixtures(work)
    sources = cast(list[str], manifest["sources"])
    queries = cast(list[dict[str, str]], manifest["queries"])
    source_hashes = _file_hashes(sources)
    config_paths = live_config_paths()
    configs_before = snapshot_paths(config_paths)
    binary, release = prepare_release(work)
    env = isolated_env(work)
    version = _run([str(binary), "version"], env).stdout.strip()
    _run([str(binary), "index", "--rebuild"], env)
    source_output = _run([str(binary), "sources"], env).stdout
    doctor = json.loads(
        _run([str(binary), "doctor", "--json", "--offline"], env).stdout
    )

    results: list[dict[str, object]] = []
    search_payloads: list[dict[str, object]] = []
    for expected in queries:
        payload = json.loads(
            _run(
                [
                    str(binary),
                    "search",
                    expected["query"],
                    "--harness",
                    expected["harness"],
                    "--limit",
                    "5",
                    "--json",
                    "--no-embed",
                ],
                env,
            ).stdout
        )
        if isinstance(payload, dict):
            search_payloads.append(payload)
        results.append(
            {
                **expected,
                "tier": payload.get("tier"),
                "passed": query_passed(
                    payload, expected["harness"], expected["session"]
                ),
                "expected_source": {
                    "origin": "local",
                    "instance": "ssot-okf-homologation",
                },
            }
        )

    negative = json.loads(
        _run(
            [
                str(binary),
                "search",
                "quasarzzinexistente",
                "--json",
                "--no-embed",
            ],
            env,
        ).stdout
    )
    parsed_sources: list[dict[str, object]] = []
    source_parse_error: str | None = None
    try:
        parsed_sources = parse_sources(source_output, work)
    except ValueError as error:
        source_parse_error = str(error)
    serialized_results = json.dumps(search_payloads, ensure_ascii=False)
    index_contains_secret = any(
        SECRET.encode() in path.read_bytes()
        for path in (work / "index").rglob("*")
        if path.is_file()
    )
    accented_queries_passed = all(
        bool(result["passed"])
        for result in results
        if any(char in str(result["query"]) for char in "áâãéêíóôõúç")
    )
    configs_after = snapshot_paths(config_paths)
    negative_hits = negative.get("hits")
    negative_passed = (
        negative.get("schema_version") == 2
        and negative.get("tier") in {"exact", "relevance"}
        and isinstance(negative_hits, list)
        and not negative_hits
    )
    criteria = {
        "version_pinned": version == f"deja {VERSION}",
        "synthetic_sources_exact": source_parse_error is None
        and sources_are_isolated(source_output, work),
        "retrieval_8_of_8_exact": retrieval_gate(results),
        "unicode": accented_queries_passed,
        "negative_is_not_claimed": negative_passed,
        "redaction": SECRET not in serialized_results and not index_contains_secret,
        "sources_unchanged": source_hashes == _file_hashes(sources),
        "live_configs_unchanged": configs_before == configs_after,
        "mcp_unwired": isinstance(doctor, dict) and mcp_is_unwired(doctor, work),
        "project_unittest": bool(quality["unittest"]["passed"]),
        "ruff": bool(quality["ruff"]["passed"]),
    }
    mcp_entries = doctor.get("mcp", []) if isinstance(doctor, dict) else []
    report: dict[str, object] = {
        "schema_version": 2,
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "authority_sha256": {
            "script": _sha256(Path(__file__)),
            "test": _sha256(TEST_PATH),
            "prd": _sha256(PRD_PATH),
        },
        "release": release,
        "environment": "synthetic-project-owned",
        "network_controls": {
            "deja_offline": True,
            "doctor_offline": True,
            "search_no_embed": True,
            "egress_observed_or_sandboxed": False,
        },
        "quality_gates": quality,
        "sources": _source_evidence(parsed_sources, work),
        "source_parse_error": source_parse_error,
        "source_sha256": {
            str(Path(path).relative_to(work)): digest
            for path, digest in source_hashes.items()
        },
        "queries": results,
        "negative": {
            "schema_version": negative.get("schema_version"),
            "tier": negative.get("tier"),
            "hit_count": len(negative_hits) if isinstance(negative_hits, list) else None,
        },
        "doctor": {
            "schema_version": doctor.get("schema_version")
            if isinstance(doctor, dict)
            else None,
            "mcp": [
                {"name": item.get("name"), "state": item.get("state")}
                for item in mcp_entries
                if isinstance(item, dict) and item.get("name") in EXPECTED_MCP_CLIENTS
            ],
        },
        "live_config_snapshot": {
            "monitored_paths": len(config_paths),
            "before_sha256": _snapshot_digest(configs_before),
            "after_sha256": _snapshot_digest(configs_after),
        },
        "criteria": criteria,
        "verdict": "PASS" if all(criteria.values()) else "FAIL",
    }
    _write_report_and_results(report, work)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true", help="remove o laboratório local")
    args = parser.parse_args()
    work = PROJECT_ROOT / ".work"
    if args.clean:
        clean_work(work, PROJECT_ROOT)
        return 0
    report = run_homologation(work)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
