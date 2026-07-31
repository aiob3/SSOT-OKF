#!/usr/bin/env python3
"""Homologação isolada do Deja-vu para o harness SSOT-OKF."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tarfile
import urllib.request
from pathlib import Path
from typing import Any, cast

VERSION = "0.16.4"
ASSET = f"deja-vu_{VERSION}_linux_amd64.tar.gz"
RELEASE_URL = f"https://github.com/vshulcz/deja-vu/releases/download/v{VERSION}"
SECRET = "ghp_" + ("A" * 36)


def verify_checksum(checksums: str, archive: Path) -> str:
    expected = next(
        (line.split()[0] for line in checksums.splitlines() if line.split()[-1] == archive.name),
        None,
    )
    if not expected:
        raise ValueError(f"checksum missing for {archive.name}")
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"checksum mismatch for {archive.name}")
    return actual


def query_passed(payload: dict[str, Any], harness: str, session: str) -> bool:
    if payload.get("tier") == "relevance":
        return False
    return any(
        (candidate := hit.get("session", {})).get("harness") == harness
        and candidate.get("id") == session
        and candidate.get("source", {}).get("origin") == "local"
        and candidate.get("source", {}).get("instance") == "ssot-okf-homologation"
        for hit in payload.get("hits", [])[:5]
    )


def isolated_env(work: Path) -> dict[str, str]:
    work = work.resolve()
    env = os.environ.copy()
    env.pop("DEJA_NO_REDACT", None)
    env.update(
        {
            "HOME": str(work / "home"),
            "XDG_CACHE_HOME": str(work / "cache"),
            "XDG_CONFIG_HOME": str(work / "config"),
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
    )
    return env


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


def _run(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, env=env, check=True, text=True, capture_output=True)


def _download(name: str, target: Path) -> None:
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(f"{RELEASE_URL}/{name}", timeout=60) as response:
        target.write_bytes(response.read())


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
    json.loads(sbom.read_text(encoding="utf-8"))
    attestation = _run(
        ["gh", "attestation", "verify", str(archive), "--repo", "vshulcz/deja-vu"]
    )
    bin_dir = work / "bin"
    shutil.rmtree(bin_dir, ignore_errors=True)
    bin_dir.mkdir(parents=True)
    with tarfile.open(archive) as bundle:
        bundle.extractall(bin_dir, filter="data")
    binary = next((path for path in bin_dir.rglob("deja") if path.is_file()), None)
    if binary is None:
        raise RuntimeError("release archive does not contain deja")
    binary.chmod(0o755)
    return binary, {
        "version": VERSION,
        "asset": ASSET,
        "sha256": digest,
        "sbom": sbom.name,
        "sbom_sha256": sbom_digest,
        "attestation": "verified" if attestation.returncode == 0 else "failed",
    }


def _file_hashes(paths: list[str]) -> dict[str, str]:
    return {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in paths}


def run_homologation(work: Path) -> dict[str, object]:
    work = work.resolve()
    downloads = work / "downloads"
    if work.exists():
        for child in work.iterdir():
            if child != downloads:
                shutil.rmtree(child) if child.is_dir() else child.unlink()
    manifest = write_fixtures(work)
    sources = cast(list[str], manifest["sources"])
    queries = cast(list[dict[str, str]], manifest["queries"])
    source_hashes = _file_hashes(sources)
    user_home = Path.home()
    live_configs = [
        user_home / ".hermes" / "config.yaml",
        user_home / ".claude.json",
        user_home / ".codex" / "config.toml",
        user_home / ".copilot" / "config.json",
    ]
    existing_configs = [str(path) for path in live_configs if path.is_file()]
    config_hashes = _file_hashes(existing_configs)
    binary, release = prepare_release(work)
    env = isolated_env(work)
    version = _run([str(binary), "version"], env).stdout.strip()
    _run([str(binary), "index", "--rebuild"], env)
    source_output = _run([str(binary), "sources"], env).stdout
    doctor = json.loads(_run([str(binary), "doctor", "--json", "--offline"], env).stdout)

    results: list[dict[str, object]] = []
    passed_harnesses: set[str] = set()
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
        passed = query_passed(payload, expected["harness"], expected["session"])
        if passed:
            passed_harnesses.add(expected["harness"])
        results.append({**expected, "tier": payload.get("tier"), "passed": passed, "payload": payload})

    negative = json.loads(
        _run([str(binary), "search", "quasarzzinexistente", "--json", "--no-embed"], env).stdout
    )
    serialized_results = json.dumps(results, ensure_ascii=False)
    index_contains_secret = any(
        SECRET.encode() in path.read_bytes() for path in (work / "index").rglob("*") if path.is_file()
    )
    passed_queries = sum(bool(result["passed"]) for result in results)
    accented_queries_passed = all(
        bool(result["passed"])
        for result in results
        if any(char in str(result["query"]) for char in "áâãéêíóôõúç")
    )
    criteria = {
        "version_pinned": version == f"deja {VERSION}",
        "four_harnesses_discovered": all(f"{name}\t" in source_output for name in ("claude", "codex", "copilot", "hermes")),
        "retrieval_at_least_7_of_8": passed_queries >= 7 and len(passed_harnesses) == 4,
        "unicode": accented_queries_passed,
        "negative_is_not_claimed": negative.get("tier") == "relevance" or not negative.get("hits"),
        "redaction": SECRET not in serialized_results and not index_contains_secret,
        "sources_unchanged": source_hashes == _file_hashes(sources),
        "live_configs_unchanged": config_hashes == _file_hashes(existing_configs),
        "mcp_unwired": not any(item.get("state") == "wired" for item in doctor.get("mcp", [])),
    }
    report: dict[str, object] = {
        "schema_version": 1,
        "release": release,
        "environment": "synthetic-project-owned",
        "sources": source_output.splitlines(),
        "queries": [{key: value for key, value in result.items() if key != "payload"} for result in results],
        "negative_tier": negative.get("tier"),
        "doctor": doctor,
        "criteria": criteria,
        "verdict": "PASS" if all(criteria.values()) else "FAIL",
    }
    report_path = work / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true", help="remove o laboratório local")
    args = parser.parse_args()
    work = Path(__file__).resolve().parents[1] / ".work"
    if args.clean:
        shutil.rmtree(work, ignore_errors=True)
        return 0
    report = run_homologation(work)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
