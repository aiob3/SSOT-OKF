#!/usr/bin/env python3
"""Atesta um binding MCP Deja-vu sem alterar config nem fontes monitoradas."""

from __future__ import annotations

import argparse
import json
import os
import signal
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from preview_real import (  # noqa: E402
    BINARY,
    ISOLATED_DIRS,
    PROJECT_ROOT,
    WORK,
    real_env,
    real_roots,
)
from homologate import _sha256, snapshot_paths  # noqa: E402

WRAPPER = str(SCRIPT_DIR / "mcp_wrapper.py")
EXPECTED_TOOLS = ("recall", "recall_context", "blame")
EXPECTED_BINARY_SHA256 = "22dd2f152f8b9fc79eea3c17d4f99166807d3be3d9d1db5ec2215b1b95dcea14"
TIMEOUT_SECONDS = 30


class ValidationError(RuntimeError):
    """O gate não conseguiu provar o binding com segurança."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("raiz deve ser objeto")
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as error:
        raise ValueError("pyyaml requerido para configs YAML") from error
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("raiz deve ser objeto")
    return value


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ModuleNotFoundError as error:
        raise ValueError("tomllib requer Python 3.11+") from error
    value = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("raiz deve ser tabela")
    return value


def _configured_server(data: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    matches: list[dict[str, Any]] = []
    errors: list[str] = []
    for mapping_name in ("mcpServers", "mcp_servers"):
        mapping = data.get(mapping_name)
        if mapping is None:
            continue
        if not isinstance(mapping, dict):
            errors.append(f"mapping {mapping_name} deve ser objeto")
            continue
        server = mapping.get("deja-ssot")
        if server is not None:
            if not isinstance(server, dict):
                errors.append(f"servidor deja-ssot em {mapping_name} deve ser objeto")
            else:
                matches.append(server)
    if len(matches) != 1:
        errors.append("deve haver exatamente um mapping de servidor deja-ssot")
        return None, errors
    return matches[0], errors


def validate_config(path: Path, fmt: str) -> list[str]:
    """Valida o documento de configuração e seu único mapping de servidor."""
    path = Path(path)
    try:
        _validate_regular_tree(path, "config", expect_file=True)
    except ValidationError as error:
        return [str(error)]
    loaders = {"json": _load_json, "toml": _load_toml, "yaml": _load_yaml}
    try:
        data = loaders[fmt](path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"erro ao ler {path}: {error}"]
    server, errors = _configured_server(data)
    if server is None:
        return errors
    if server.get("command") != "python3":
        errors.append(f"command deve ser python3, encontrado {server.get('command')!r}")
    if server.get("args") != ["-B", WRAPPER]:
        errors.append(f"args devem ser [-B, {WRAPPER}], encontrado {server.get('args')!r}")
    if "env" in server:
        errors.append("env override não é permitido")
    return errors


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _assert_no_symlink(path: Path, root: Path, label: str) -> None:
    path = _absolute(path)
    root = _absolute(root)
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise ValidationError(f"{label} escapa do projeto: {path}") from error
    current = root
    for part in relative.parts:
        current /= part
        if current.exists() and current.is_symlink():
            raise ValidationError(f"{label} não pode conter symlink: {current}")


def _validate_regular_tree(root: Path, label: str, *, expect_file: bool = False) -> None:
    try:
        metadata = root.lstat()
    except FileNotFoundError as error:
        raise ValidationError(f"{label} ausente: {root}") from error
    expected = stat.S_ISREG if expect_file else stat.S_ISDIR
    if not expected(metadata.st_mode):
        kind = "arquivo regular" if expect_file else "diretório"
        raise ValidationError(f"{label} deve ser {kind}: {root}")
    paths = (root,) if expect_file else (root, *sorted(root.rglob("*")))
    for path in paths:
        metadata = path.lstat()
        mode = metadata.st_mode
        if stat.S_ISLNK(mode):
            raise ValidationError(f"{label} não pode conter symlink: {path}")
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValidationError(f"{label} contém entrada não regular: {path}")
        if stat.S_ISREG(mode) and metadata.st_nlink != 1:
            raise ValidationError(f"{label} não pode conter hardlink: {path}")


def validate_real_work_tree(work: Path) -> None:
    _validate_regular_tree(work, "árvore gravável")


def validate_real_roots(roots: dict[str, Path]) -> None:
    expected = {
        "hermes": True,
        "claude": False,
        "codex": False,
        "copilot": False,
    }
    if set(roots) != set(expected):
        raise ValidationError("roots reais incompletos")
    for name, expect_file in expected.items():
        _validate_regular_tree(roots[name], name, expect_file=expect_file)


def prepare_isolated_work() -> Path:
    """Cria somente os diretórios isolados conhecidos dentro de .work/real."""
    project = Path(PROJECT_ROOT).resolve(strict=True)
    expected_work = project / ".work" / "real"
    work = _absolute(WORK)
    if work != expected_work:
        raise ValidationError("WORK deve ser exatamente .work/real do projeto")
    work_root = expected_work.parent
    if not work_root.is_dir() or work_root.is_symlink():
        raise ValidationError(".work deve existir e não pode ser symlink")
    _assert_no_symlink(work_root, project, ".work")
    if work.is_symlink() or (work.exists() and not work.is_dir()):
        raise ValidationError("WORK deve ser diretório regular")
    if not work.exists():
        work.mkdir()
    _assert_no_symlink(work, project, "WORK")
    for name in ISOLATED_DIRS:
        target = work / name
        if target.is_symlink() or (target.exists() and not target.is_dir()):
            raise ValidationError(f"diretório isolado inválido: {target}")
        if not target.exists():
            target.mkdir()
        _assert_no_symlink(target, project, f"diretório isolado {name}")
    validate_real_work_tree(work)
    return work


def validate_binary() -> Path:
    project = Path(PROJECT_ROOT).resolve(strict=True)
    binary = _absolute(BINARY)
    expected = project / ".work" / "bin" / "deja"
    try:
        metadata = binary.lstat()
    except FileNotFoundError as error:
        raise ValidationError("binário Deja ausente ou fora de .work/bin/deja") from error
    if binary != expected or not stat.S_ISREG(metadata.st_mode):
        raise ValidationError("binário Deja ausente ou fora de .work/bin/deja")
    _assert_no_symlink(binary, project, "binário")
    if metadata.st_nlink != 1:
        raise ValidationError("binário Deja não pode conter hardlink")
    if _sha256(binary) != EXPECTED_BINARY_SHA256:
        raise ValidationError("digest do binário Deja não confere")
    return binary


def _validate_monitored_paths(config: Path, roots: dict[str, Path]) -> None:
    for label, path in {"config": config, **roots}.items():
        path = _absolute(path)
        if path.is_symlink() or path.resolve(strict=False) != path:
            raise ValidationError(f"{label} não pode conter symlink ou escape: {path}")


def _run_checked(
    command: list[str], env: dict[str, str], input_text: str | None = None
) -> str:
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(input_text, timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as error:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise ValidationError(f"comando falhou: {error}") from error
    except OSError as error:
        raise ValidationError(f"comando falhou: {error}") from error
    if process.returncode != 0:
        raise ValidationError(f"comando retornou {process.returncode}")
    if stderr.strip():
        raise ValidationError(f"stderr relevante: {stderr.strip()[:400]}")
    return stdout


def _request_lines(query: str) -> str:
    requests = (
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "validate-binding", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "remember", "arguments": {"text": "validation probe"}},
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "recall", "arguments": {"query": query}},
        },
    )
    return "".join(json.dumps(request) + "\n" for request in requests)


def mcp_command(work: Path, home: Path) -> list[str]:
    return [
        "python3",
        "-B",
        WRAPPER,
        "--work",
        str(work),
        "--home",
        str(home),
    ]


def validate_session_output(output: str, expect: str) -> list[str]:
    """Exige os quatro envelopes de resposta e todo o contrato read-only."""
    errors: list[str] = []
    responses: dict[int, dict[str, Any]] = {}
    for line in output.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            errors.append("JSON-RPC inválido na saída")
            continue
        if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
            errors.append("envelope JSON-RPC inválido")
            continue
        identifier = payload.get("id")
        if type(identifier) is not int:
            errors.append("resposta sem ID inteiro")
            continue
        if identifier in responses:
            errors.append(f"ID duplicado: {identifier}")
            continue
        responses[identifier] = payload
    for identifier in (1, 2, 3, 4):
        if identifier not in responses:
            errors.append(f"ID ausente: {identifier}")
    extras = set(responses) - {1, 2, 3, 4}
    if extras:
        errors.append(f"IDs inesperados: {sorted(extras)}")
    if not all(identifier in responses for identifier in (1, 2, 3, 4)):
        return errors
    expected_envelopes = {1: "result", 2: "result", 3: "error", 4: "result"}
    for identifier, field in expected_envelopes.items():
        if set(responses[identifier]) != {"jsonrpc", "id", field}:
            errors.append(f"envelope inesperado para ID {identifier}")
    initialize = responses[1].get("result")
    capabilities = initialize.get("capabilities") if isinstance(initialize, dict) else None
    server_info = initialize.get("serverInfo") if isinstance(initialize, dict) else None
    if (
        not isinstance(initialize, dict)
        or initialize.get("protocolVersion") != "2024-11-05"
        or not isinstance(capabilities, dict)
        or not isinstance(capabilities.get("tools"), dict)
        or not isinstance(server_info, dict)
        or not isinstance(server_info.get("name"), str)
        or not server_info["name"]
        or not isinstance(server_info.get("version"), str)
        or not server_info["version"]
    ):
        errors.append("initialize sem result válido")
    listing = responses[2].get("result")
    tools = listing.get("tools") if isinstance(listing, dict) and set(listing) == {"tools"} else None
    if (
        not isinstance(tools, list)
        or len(tools) != len(EXPECTED_TOOLS)
        or not all(isinstance(tool, dict) for tool in tools)
        or not all(isinstance(tool.get("name"), str) for tool in tools)
    ):
        errors.append("tools/list deve conter exatamente recall, recall_context e blame")
    else:
        names = [tool.get("name") for tool in tools]
        if set(names) != set(EXPECTED_TOOLS) or len(set(names)) != len(EXPECTED_TOOLS):
            errors.append("tools/list deve conter exatamente recall, recall_context e blame")
    remember = responses[3].get("error")
    if (
        not isinstance(remember, dict)
        or remember.get("code") != -32601
        or "read-only" not in str(remember.get("message", "")).lower()
    ):
        errors.append("remember deve falhar com JSON-RPC -32601 read-only")
    recall = responses[4].get("result")
    content = recall.get("content") if isinstance(recall, dict) and set(recall) == {"content"} else None
    if not isinstance(content, list) or not all(
        isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str)
        for item in content
    ):
        errors.append("recall sem content válido")
        content = []
    text = "\n".join(item["text"] for item in content)
    if expect not in text:
        errors.append("recall não retornou o conteúdo esperado")
    return errors


def _index_present(snapshot: dict[str, dict[str, object]], index: Path) -> bool:
    fingerprint = snapshot.get(str(index))
    if not isinstance(fingerprint, dict) or fingerprint.get("state") != "directory":
        return False
    return any(stat.S_ISREG(path.lstat().st_mode) for path in index.rglob("*"))


def validate_binding(config: Path, fmt: str, *, query: str, expect: str) -> dict[str, object]:
    if not query or not expect:
        raise ValidationError("--query e --expect não podem ser vazios")
    config = _absolute(config)
    config_errors = validate_config(config, fmt)
    if config_errors:
        raise ValidationError("; ".join(config_errors))
    work = prepare_isolated_work()
    binary = validate_binary()
    home = Path.home()
    source_roots = real_roots(home)
    _validate_monitored_paths(config, source_roots)
    validate_real_roots(source_roots)
    roots = [config, *source_roots.values()]
    before = snapshot_paths(roots)
    env = real_env(work, home)
    index = Path(env["DEJA_INDEX_DIR"])
    operation_error: Exception | None = None
    snapshot_error: Exception | None = None
    report: dict[str, object] | None = None
    try:
        index_before = snapshot_paths([index])
        _run_checked([str(binary), "index"], env)
        validate_real_work_tree(work)
        _validate_regular_tree(config, "config", expect_file=True)
        validate_real_roots(source_roots)
        index_after = snapshot_paths([index])
        if not _index_present(index_after, index):
            raise ValidationError("índice ausente após deja index")
        wrapper_env = dict(env)
        wrapper_env["HOME"] = str(home)
        validate_binary()
        session_errors = validate_session_output(
            _run_checked(mcp_command(work, home), wrapper_env, _request_lines(query)), expect
        )
        if session_errors:
            raise ValidationError("; ".join(session_errors))
        report = {
            "status": "PASS",
            "index_updated": index_before != index_after,
            "index_noop": index_before == index_after,
            "monitored_content_structure_stable": True,
            "writes_configured_under": str(work),
            "claim": (
                "conteúdo SHA-256 + estrutura/tipo de config/fontes monitoradas "
                "estáveis; escritas configuradas sob .work/real"
            ),
        }
    except Exception as error:
        operation_error = error
    finally:
        try:
            _validate_regular_tree(config, "config", expect_file=True)
            validate_real_roots(source_roots)
            validate_real_work_tree(work)
            after = snapshot_paths(roots)
        except Exception as error:
            after = None
            snapshot_error = error
    if snapshot_error is not None:
        message = f"snapshot posterior falhou: {snapshot_error}"
        if operation_error is not None:
            message = f"{operation_error}; {message}"
        raise ValidationError(message) from (operation_error or snapshot_error)
    if before != after:
        message = "config ou fontes monitoradas mudaram"
        if operation_error is not None:
            message = f"{operation_error}; {message}"
        raise ValidationError(message) from operation_error
    if operation_error is not None:
        if isinstance(operation_error, ValidationError):
            raise operation_error
        raise ValidationError(str(operation_error)) from operation_error
    assert report is not None
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "toml", "yaml"), default="json")
    parser.add_argument("--query", required=True)
    parser.add_argument("--expect", required=True)
    args = parser.parse_args(argv)
    try:
        report = validate_binding(args.config, args.format, query=args.query, expect=args.expect)
    except ValidationError as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
