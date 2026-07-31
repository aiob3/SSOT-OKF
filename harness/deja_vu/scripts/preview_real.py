#!/usr/bin/env python3
"""Preview read-only do Deja-vu sobre os históricos reais do operador.

Aponta o binário já homologado para os stores reais em modo somente-leitura:
índice, HOME, cache e config ficam dentro de `.work/real`; nada é instalado,
nenhum MCP é conectado e nenhuma nota é escrita. Antes e depois da execução o
script tira um snapshot de tamanho/mtime/inode das fontes e falha se algo mudou.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORK = PROJECT_ROOT / ".work" / "real"
BINARY = PROJECT_ROOT / ".work" / "bin" / "deja"
ISOLATED_DIRS = ("home", "cache", "config", "data", "state", "tmp", "index")

# Ruído de harnesses vivos: o próprio agente em execução regrava estas
# entradas durante a leitura. Não são escrita do Deja nem evidência de fuga.
# ponytail: allowlist nominal; novos padrões voláteis entram aqui.
VOLATILE_PATTERNS = (
    "tmp/",
    ".tmp",
    ".lock",
    "-shm",
    "-wal",
    "logs_2.sqlite",
    "config.json",
)


def _is_volatile(path: str) -> bool:
    return any(pattern in path for pattern in VOLATILE_PATTERNS)


def real_roots(home: Path) -> dict[str, Path]:
    return {
        "hermes": home / ".hermes" / "state.db",
        "claude": home / ".claude" / "projects",
        # o parser do Deja espera a raiz ~/.codex; apontar direto para sessions
        # indexa 0 sessões silenciosamente.
        "codex": home / ".codex",
        "copilot": home / ".copilot",
    }


def real_env(work: Path, home: Path) -> dict[str, str]:
    work = Path(os.path.abspath(work))
    roots = real_roots(home)
    return {
        "PATH": os.environ.get("PATH", os.defpath),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "HOME": str(work / "home"),
        "XDG_CACHE_HOME": str(work / "cache"),
        "XDG_CONFIG_HOME": str(work / "config"),
        "XDG_DATA_HOME": str(work / "data"),
        "XDG_STATE_HOME": str(work / "state"),
        "TMPDIR": str(work / "tmp"),
        "DEJA_INDEX_DIR": str(work / "index"),
        "DEJA_HERMES_DB": str(roots["hermes"]),
        "DEJA_CLAUDE_ROOT": str(roots["claude"]),
        "DEJA_CODEX_ROOT": str(roots["codex"]),
        "DEJA_COPILOT_ROOT": str(roots["copilot"]),
        "DEJA_OFFLINE": "1",
        "DEJA_RECALL": "off",
        "DEJA_EMBED": "off",
    }


def stat_snapshot(roots: list[Path]) -> dict[str, object]:
    """Tamanho/mtime/inode por caminho — detecta escrita sem reler 2,5 GiB."""
    snapshot: dict[str, object] = {}
    for root in roots:
        if not root.exists():
            snapshot[str(root)] = "missing"
        elif root.is_file():
            info = root.stat()
            snapshot[str(root)] = [info.st_size, info.st_mtime_ns, info.st_ino]
        else:
            entries = []
            for child in sorted(root.rglob("*")):
                if child.is_file():
                    info = child.stat()
                    entries.append(
                        [str(child.relative_to(root)), info.st_size, info.st_mtime_ns]
                    )
            snapshot[str(root)] = entries
    return snapshot


def diff_snapshots(
    before: dict[str, object], after: dict[str, object]
) -> list[dict[str, object]]:
    """Diferenças por arquivo, para separar escrita do Deja de sessão viva."""
    changes: list[dict[str, object]] = []
    for root, old in before.items():
        new = after.get(root)
        if old == new:
            continue
        if not isinstance(old, list) or not isinstance(new, list):
            changes.append({"root": root, "kind": "replaced"})
            continue
        old_map = {
            str(entry[0]): entry[1:] for entry in old if not _is_volatile(str(entry[0]))
        }
        new_map = {
            str(entry[0]): entry[1:] for entry in new if not _is_volatile(str(entry[0]))
        }
        for name in sorted(set(new_map) - set(old_map)):
            changes.append({"root": root, "path": name, "kind": "created"})
        for name in sorted(set(old_map) - set(new_map)):
            changes.append({"root": root, "path": name, "kind": "removed"})
        for name in sorted(set(old_map) & set(new_map)):
            if old_map[name] != new_map[name]:
                changes.append({"root": root, "path": name, "kind": "modified"})
    return changes


def _run(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, env=env, text=True, capture_output=True, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queries", nargs="*", help="consultas de demonstração")
    args = parser.parse_args()
    if not BINARY.is_file():
        print("binário ausente: rode a homologação sintética primeiro", file=sys.stderr)
        return 1

    home = Path.home()
    for name in ISOLATED_DIRS:
        (WORK / name).mkdir(parents=True, exist_ok=True)
    env = real_env(WORK, home)
    roots = list(real_roots(home).values())

    before = stat_snapshot(roots)
    index = _run([str(BINARY), "index"], env)
    sources = _run([str(BINARY), "sources"], env)
    results = []
    for query in args.queries:
        completed = _run(
            [str(BINARY), "--json", "--no-embed", "--limit", "3", query], env
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"error": completed.stderr.strip()[:400]}
        results.append(
            {
                "query": query,
                "tier": payload.get("tier"),
                "hits": [
                    {
                        "harness": session.get("harness"),
                        "project": session.get("project"),
                        "started": session.get("started_at"),
                        "preview": str(
                            hit.get("preview") or hit.get("snippet") or ""
                        )[:160],
                    }
                    for hit in (payload.get("hits") or [])[:3]
                    if isinstance(hit, dict)
                    and isinstance(session := hit.get("session") or {}, dict)
                ],
            }
        )
    after = stat_snapshot(roots)

    changes = diff_snapshots(before, after)
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "real-sources-read-only",
        "index_ok": index.returncode == 0,
        "sources": [line for line in sources.stdout.splitlines() if line.strip()],
        "queries": results,
        "sources_unchanged": not changes,
        "source_changes": changes,
        "writes_confined_to": str(WORK),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["sources_unchanged"] and report["index_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
