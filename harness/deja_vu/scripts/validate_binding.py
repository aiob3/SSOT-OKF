#!/usr/bin/env python3
"""Valida a configuração MCP de um harness local para o Deja-vu read-only.

Uso:
    python3 -B scripts/validate_binding.py --config ~/.claude.json
    python3 -B scripts/validate_binding.py --config ~/.codex/config.toml --format toml
    python3 -B scripts/validate_binding.py --config ~/.copilot/mcp-config.json

Verifica:
1. o arquivo contém um servidor chamado deja-ssot;
2. command e args apontam para o wrapper homologado;
3. o wrapper responde a initialize/tools/list com as três tools de leitura;
4. remember não aparece na lista.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

WRAPPER = "/data/SSOT-OKF/harness/deja_vu/scripts/mcp_wrapper.py"
EXPECTED_TOOLS = {"recall", "recall_context", "blame"}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        print("pyyaml requerido para configs YAML", file=sys.stderr)
        raise SystemExit(1)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_toml(path: Path) -> dict:
    try:
        import tomllib
    except ImportError:
        print("tomllib requer Python 3.11+", file=sys.stderr)
        raise SystemExit(1)
    return tomllib.loads(path.read_text(encoding="utf-8"))


def validate_config(path: Path, fmt: str) -> list[str]:
    errors: list[str] = []
    loaders = {"json": _load_json, "toml": _load_toml, "yaml": _load_yaml}
    try:
        data = loaders[fmt](path)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return [f"erro ao ler {path}: {error}"]
    servers = data.get("mcpServers") or data.get("mcp_servers") or {}
    server = servers.get("deja-ssot")
    if server is None:
        errors.append(f"servidor deja-ssot ausente em {path}")
        return errors
    if server.get("command") != "python3":
        errors.append(f"command deve ser python3, encontrado {server.get('command')!r}")
    args = server.get("args") or []
    if args != ["-B", WRAPPER]:
        errors.append(f"args devem ser [-B, {WRAPPER}], encontrado {args!r}")
    return errors


def validate_wrapper() -> list[str]:
    errors: list[str] = []
    try:
        proc = subprocess.run(
            ["python3", "-B", WRAPPER],
            input=json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "validate-binding", "version": "0"},
                },
            }) + "\n" + json.dumps({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            }) + "\n",
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return [f"wrapper falhou: {error}"]
    tools = set()
    for line in proc.stdout.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("id") == 2:
            tools = {
                tool.get("name")
                for tool in payload.get("result", {}).get("tools", [])
                if isinstance(tool, dict)
            }
    if tools != EXPECTED_TOOLS:
        errors.append(f"tools esperadas {EXPECTED_TOOLS}, encontradas {tools}")
    if "remember" in tools:
        errors.append("remember não deveria estar exposta")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "toml", "yaml"), default="json")
    args = parser.parse_args()

    errors = validate_config(args.config, args.format)
    errors.extend(validate_wrapper())

    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        return 1
    print(f"PASS {args.config} + wrapper read-only OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
