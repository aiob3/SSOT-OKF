#!/usr/bin/env python3
"""Wrapper MCP stdio que expõe apenas tools de leitura do Deja-vu.

O Hermes (ou outro harness) conecta neste script, não diretamente no binário.
O wrapper delega `recall`, `recall_context` e `blame` ao `deja mcp` real e
rejeita `remember` e qualquer outra tool com erro JSON-RPC. O ambiente do
processo filho é o mesmo allowlist isolado usado pelo preview read-only.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORK = PROJECT_ROOT / ".work" / "real"
BINARY = PROJECT_ROOT / ".work" / "bin" / "deja"

ALLOWED_TOOLS = {"recall", "recall_context", "blame"}
BLOCKED_TOOLS = {"remember", "sync", "share", "embed", "update", "install", "uninstall"}


def real_env(work: Path, home: Path) -> dict[str, str]:
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
        "TMPDIR": str(work / "tmp"),
        "DEJA_INDEX_DIR": str(work / "index"),
        "DEJA_HERMES_DB": str(home / ".hermes" / "state.db"),
        "DEJA_CLAUDE_ROOT": str(home / ".claude" / "projects"),
        "DEJA_CODEX_ROOT": str(home / ".codex"),
        "DEJA_COPILOT_ROOT": str(home / ".copilot"),
        "DEJA_OFFLINE": "1",
        "DEJA_RECALL": "off",
        "DEJA_EMBED": "off",
    }


def _tool_error(name: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "error": {
            "code": -32601,
            "message": f"tool '{name}' is not available in this read-only profile",
        },
    }


def _spawn(env: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [str(BINARY), "mcp"],
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )


def serve(work: Path, home: Path) -> int:
    env = real_env(work, home)
    child = _spawn(env)
    assert child.stdin is not None and child.stdout is not None

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = request.get("method")
        if method == "tools/list":
            # Reescreve a lista para expor só as tools permitidas.
            child.stdin.write(line + "\n")
            child.stdin.flush()
            response = child.stdout.readline()
            try:
                payload = json.loads(response)
            except json.JSONDecodeError:
                continue
            tools = payload.get("result", {}).get("tools", [])
            payload["result"]["tools"] = [
                tool for tool in tools if tool.get("name") in ALLOWED_TOOLS
            ]
            sys.stdout.write(json.dumps(payload) + "\n")
            sys.stdout.flush()
            continue

        if method == "tools/call":
            name = request.get("params", {}).get("name", "")
            if name in BLOCKED_TOOLS or name not in ALLOWED_TOOLS:
                response = _tool_error(name)
                response["id"] = request.get("id")
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
                continue

        # Delega tudo o mais (initialize, notifications/initialized, tools/call permitidas).
        child.stdin.write(line + "\n")
        child.stdin.flush()
        if request.get("id") is not None:
            response = child.stdout.readline()
            sys.stdout.write(response)
            sys.stdout.flush()

    child.terminate()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=WORK)
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()
    return serve(args.work, args.home)


if __name__ == "__main__":
    raise SystemExit(main())
