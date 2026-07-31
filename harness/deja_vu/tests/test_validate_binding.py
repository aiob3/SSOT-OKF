from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from contextlib import redirect_stderr
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_binding.py"
SPEC = importlib.util.spec_from_file_location("deja_validate_binding", MODULE_PATH)
assert SPEC and SPEC.loader
binding = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = binding
SPEC.loader.exec_module(binding)


class _FakeProcess:
    def __init__(self, responder) -> None:
        self._responder = responder
        self.pid = 12345
        self.returncode: int | None = None

    def communicate(self, input_text: str | None = None, timeout: float | None = None) -> tuple[str, str]:
        completed = self._responder(input_text)
        self.returncode = completed.returncode
        return completed.stdout, completed.stderr


class BindingValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sandbox = ROOT / ".work" / "test-validate-binding"
        shutil.rmtree(self.sandbox, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.sandbox, True)
        self.home = self.sandbox / "operator-home"
        (self.home / ".hermes").mkdir(parents=True)
        (self.home / ".hermes" / "state.db").write_text("db", encoding="utf-8")
        for relative in (
            ".claude/projects/session.jsonl",
            ".codex/sessions/session.jsonl",
            ".copilot/events.jsonl",
        ):
            path = self.home / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("source", encoding="utf-8")
        self.config = self.sandbox / "config.json"
        self.config_data = json.dumps(
            {
                "mcpServers": {
                    "deja-ssot": {
                        "command": "python3",
                        "args": ["-B", binding.WRAPPER],
                    }
                }
            }
        )
        self.config.write_text(self.config_data, encoding="utf-8")
        self.work = self.sandbox / ".work" / "real"
        self.work.parent.mkdir(parents=True)
        self.binary = self.sandbox / ".work" / "bin" / "deja"
        self.binary.parent.mkdir(parents=True)
        self.binary.write_text("fake", encoding="utf-8")
        self.binary.chmod(0o700)

    def test_writable_tree_rejects_descendant_symlink(self) -> None:
        self.work.mkdir()
        (self.work / "escape").symlink_to(self.sandbox / "outside")

        with (
            patch.object(binding, "PROJECT_ROOT", self.sandbox),
            patch.object(binding, "WORK", self.work),
        ):
            with self.assertRaisesRegex(binding.ValidationError, "árvore gravável"):
                binding.prepare_isolated_work()

    def test_writable_tree_rejects_hardlinked_regular_file(self) -> None:
        self.work.mkdir()
        original = self.work / "original"
        original.write_text("content", encoding="utf-8")
        os.link(original, self.work / "hardlink")

        with self.assertRaisesRegex(binding.ValidationError, "hardlink"):
            binding.validate_real_work_tree(self.work)

    def test_real_roots_require_expected_types_and_regular_descendants(self) -> None:
        roots = binding.real_roots(self.home)
        (self.home / ".codex" / "escape").symlink_to(self.sandbox / "outside")

        with self.assertRaisesRegex(binding.ValidationError, "symlink"):
            binding.validate_real_roots(roots)

        (self.home / ".codex" / "escape").unlink()
        (self.home / ".hermes" / "state.db").unlink()
        with self.assertRaisesRegex(binding.ValidationError, "hermes"):
            binding.validate_real_roots(roots)
        (self.home / ".hermes" / "state.db").mkdir()
        with self.assertRaisesRegex(binding.ValidationError, "arquivo regular"):
            binding.validate_real_roots(roots)

    def test_real_roots_reject_hardlinked_regular_file(self) -> None:
        source = self.home / ".claude" / "projects" / "session.jsonl"
        os.link(source, source.with_name("hardlink.jsonl"))

        with self.assertRaisesRegex(binding.ValidationError, "hardlink"):
            binding.validate_real_roots(binding.real_roots(self.home))

    def test_content_fingerprint_detects_same_size_empty_dir_and_symlink(self) -> None:
        source = self.home / ".claude" / "projects"
        session = source / "session.jsonl"
        original_mtime = session.stat().st_mtime_ns
        before = binding.snapshot_paths([source])
        session.write_text("change", encoding="utf-8")
        os.utime(session, ns=(session.stat().st_atime_ns, original_mtime))
        self.assertNotEqual(before, binding.snapshot_paths([source]))

        empty_before = binding.snapshot_paths([source])
        empty = source / "empty"
        empty.mkdir()
        self.assertNotEqual(empty_before, binding.snapshot_paths([source]))
        empty.rmdir()
        self.assertEqual(empty_before, binding.snapshot_paths([source]))

        (source / "escape").symlink_to(self.sandbox / "outside")
        with self.assertRaisesRegex(binding.ValidationError, "symlink"):
            binding.validate_real_roots(binding.real_roots(self.home))

    def test_real_roots_reject_special_descendants(self) -> None:
        special = self.home / ".copilot" / "pipe"
        os.mkfifo(special)

        with self.assertRaisesRegex(binding.ValidationError, "entrada não regular"):
            binding.validate_real_roots(binding.real_roots(self.home))

    def test_binary_digest_is_required(self) -> None:
        with (
            patch.object(binding, "PROJECT_ROOT", self.sandbox),
            patch.object(binding, "BINARY", self.binary),
            patch.object(binding, "_sha256", return_value=binding.EXPECTED_BINARY_SHA256),
        ):
            self.assertEqual(binding.validate_binary(), self.binary)
        with (
            patch.object(binding, "PROJECT_ROOT", self.sandbox),
            patch.object(binding, "BINARY", self.binary),
            patch.object(binding, "_sha256", return_value="0" * 64),
        ):
            with self.assertRaisesRegex(binding.ValidationError, "digest"):
                binding.validate_binary()

    def test_binary_rejects_hardlink(self) -> None:
        os.link(self.binary, self.binary.with_name("deja-linked"))

        with (
            patch.object(binding, "PROJECT_ROOT", self.sandbox),
            patch.object(binding, "BINARY", self.binary),
            patch.object(binding, "_sha256", return_value=binding.EXPECTED_BINARY_SHA256),
        ):
            with self.assertRaisesRegex(binding.ValidationError, "hardlink"):
                binding.validate_binary()

    def test_config_rejects_hardlinked_regular_file(self) -> None:
        os.link(self.config, self.sandbox / "config-linked.json")

        self.assertTrue(any(
            "hardlink" in error for error in binding.validate_config(self.config, "json")
        ))

    def test_timeout_kills_the_process_group(self) -> None:
        class TimedOutProcess:
            pid = 12345
            returncode = -9

            def __init__(self) -> None:
                self.calls = 0

            def communicate(self, input_text: str | None = None, timeout: float | None = None) -> tuple[str, str]:
                self.calls += 1
                if self.calls == 1:
                    raise subprocess.TimeoutExpired(["deja", "index"], 30)
                return "", ""

        process = TimedOutProcess()
        with (
            patch.object(binding.subprocess, "Popen", return_value=process),
            patch.object(binding.os, "killpg") as killpg,
        ):
            with self.assertRaises(binding.ValidationError):
                binding._run_checked(["deja", "index"], {})

        killpg.assert_called_once_with(process.pid, binding.signal.SIGKILL)

    def _completed(
        self,
        command: list[str],
        *,
        env: dict[str, str],
        input_text: str | None,
    ) -> subprocess.CompletedProcess[str]:
        if command == [str(self.binary), "index"]:
            index = Path(env["DEJA_INDEX_DIR"])
            index.mkdir(exist_ok=True)
            (index / "manifest.gob").write_text("indexed", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "indexed\n", "")
        if command == binding.mcp_command(self.work, self.home):
            requests = [json.loads(line) for line in str(input_text).splitlines()]
            self.assertEqual(
                [request["method"] for request in requests],
                [
                    "initialize",
                    "notifications/initialized",
                    "tools/list",
                    "tools/call",
                    "tools/call",
                ],
            )
            responses = [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "fake", "version": "1"},
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "tools": [
                            {"name": "recall"},
                            {"name": "recall_context"},
                            {"name": "blame"},
                        ]
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "error": {"code": -32601, "message": "read-only profile"},
                },
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "result": {
                        "content": [{"type": "text", "text": "resultado esperado"}]
                    },
                },
            ]
            return subprocess.CompletedProcess(
                command, 0, "".join(json.dumps(item) + "\n" for item in responses), ""
            )
        self.fail(f"comando inesperado: {command}")

    def _popen(self, command: list[str], **kwargs: object) -> _FakeProcess:
        env = kwargs["env"]
        assert isinstance(env, dict)
        return _FakeProcess(
            lambda input_text: self._completed(command, env=env, input_text=input_text)
        )

    def _assert_mutation_rejected(self, mutate, *, after_wrapper: bool) -> None:
        commands: list[list[str]] = []

        def runner(command: list[str], **kwargs: object) -> _FakeProcess:
            env = kwargs["env"]
            assert isinstance(env, dict)
            commands.append(command)

            def responder(input_text: str | None) -> subprocess.CompletedProcess[str]:
                completed = self._completed(command, env=env, input_text=input_text)
                if command == [str(self.binary), "index"] and not after_wrapper:
                    mutate()
                if command == binding.mcp_command(self.work, self.home) and after_wrapper:
                    mutate()
                return completed

            return _FakeProcess(responder)

        with (
            patch.object(binding, "PROJECT_ROOT", self.sandbox),
            patch.object(binding, "BINARY", self.binary),
            patch.object(binding, "WORK", self.work),
            patch.object(binding.Path, "home", return_value=self.home),
            patch.object(binding, "_sha256", return_value=binding.EXPECTED_BINARY_SHA256),
            patch.object(binding.subprocess, "Popen", side_effect=runner),
        ):
            with self.assertRaises(binding.ValidationError):
                binding.validate_binding(self.config, "json", query="consulta", expect="esperado")

        expected = [[str(self.binary), "index"]]
        if after_wrapper:
            expected.append(binding.mcp_command(self.work, self.home))
        self.assertEqual(commands, expected)

    def _assert_unsafe_monitored_mutations(self, *, after_wrapper: bool) -> None:
        source = self.home / ".claude" / "projects"
        unsafe_source = source / "unsafe"
        unsafe_config = self.sandbox / "config-unsafe"
        for target in ("config", "source"):
            for kind in ("hardlink", "symlink", "special"):
                with self.subTest(target=target, kind=kind):
                    shutil.rmtree(self.work, ignore_errors=True)
                    for path in (unsafe_config, unsafe_source):
                        if os.path.lexists(path):
                            path.unlink()
                    if os.path.lexists(self.config):
                        self.config.unlink()
                    self.config.write_text(self.config_data, encoding="utf-8")

                    def mutate(target: str = target, kind: str = kind) -> None:
                        if target == "config":
                            if kind == "hardlink":
                                os.link(self.config, unsafe_config)
                            else:
                                self.config.unlink()
                                if kind == "symlink":
                                    self.config.symlink_to(self.sandbox / "outside")
                                else:
                                    os.mkfifo(self.config)
                        elif kind == "hardlink":
                            os.link(source / "session.jsonl", unsafe_source)
                        elif kind == "symlink":
                            unsafe_source.symlink_to(self.sandbox / "outside")
                        else:
                            os.mkfifo(unsafe_source)

                    self._assert_mutation_rejected(mutate, after_wrapper=after_wrapper)

    def test_binding_happy_path_runs_index_then_one_complete_mcp_session(self) -> None:
        with (
            patch.object(binding, "PROJECT_ROOT", self.sandbox),
            patch.object(binding, "BINARY", self.binary),
            patch.object(binding, "WORK", self.work),
            patch.object(binding.Path, "home", return_value=self.home),
            patch.object(
                binding, "_sha256", return_value=binding.EXPECTED_BINARY_SHA256
            ) as binary_hash,
            patch.object(binding.subprocess, "Popen", side_effect=self._popen) as run,
        ):
            report = binding.validate_binding(
                self.config, "json", query="consulta", expect="esperado"
            )

        self.assertTrue(report["index_updated"])
        self.assertFalse(report["index_noop"])
        self.assertTrue(report["monitored_content_structure_stable"])
        self.assertEqual(report["writes_configured_under"], str(self.work))
        self.assertEqual([call.args[0] for call in run.call_args_list], [
            [str(self.binary), "index"],
            binding.mcp_command(self.work, self.home),
        ])
        self.assertTrue(all(call.kwargs["start_new_session"] for call in run.call_args_list))
        self.assertEqual(binary_hash.call_count, 2)

    def test_config_rejects_any_environment_override(self) -> None:
        self.config.write_text(
            json.dumps({
                "mcpServers": {
                    "deja-ssot": {
                        "command": "python3",
                        "args": ["-B", binding.WRAPPER],
                        "env": {},
                    }
                }
            }),
            encoding="utf-8",
        )

        self.assertIn("env override", "\n".join(binding.validate_config(self.config, "json")))

    def test_file_root_snapshot_is_exact_and_detects_a_change(self) -> None:
        before = binding.snapshot_paths([self.config])
        self.config.write_text("changed", encoding="utf-8")
        self.assertNotEqual(before, binding.snapshot_paths([self.config]))

    def test_session_fails_closed_for_duplicate_tool_and_id(self) -> None:
        output = "\n".join(
            json.dumps(payload)
            for payload in (
                {"jsonrpc": "2.0", "id": 1, "result": {}},
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "tools": [
                            {"name": "recall"},
                            {"name": "recall"},
                            {"name": "recall_context"},
                            {"name": "blame"},
                        ]
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "error": {"code": -32601, "message": "read-only"},
                },
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "result": {"content": [{"type": "text", "text": "esperado"}]},
                },
                {"jsonrpc": "2.0", "id": 4, "result": {}},
            )
        )

        errors = binding.validate_session_output(output, "esperado")

        self.assertTrue(any("duplicado" in error for error in errors))
        self.assertTrue(any("tools" in error for error in errors))

    def test_session_rejects_non_mapping_tool_and_mixed_envelope(self) -> None:
        output = "\n".join(
            json.dumps(payload)
            for payload in (
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"capabilities": {}},
                    "error": {"code": 0, "message": "unexpected"},
                },
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "tools": [
                            {"name": "recall"},
                            {"name": "recall_context"},
                            {"name": "blame"},
                            "not-a-tool",
                        ]
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "error": {"code": -32601, "message": "read-only"},
                },
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "result": {"content": [{"type": "text", "text": "esperado"}]},
                },
            )
        )

        errors = binding.validate_session_output(output, "esperado")

        self.assertTrue(any("envelope" in error for error in errors))
        self.assertTrue(any("tools" in error for error in errors))

    def test_session_requires_complete_initialize_handshake(self) -> None:
        output = "\n".join(
            json.dumps(payload)
            for payload in (
                {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}},
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "tools": [
                            {"name": "recall"},
                            {"name": "recall_context"},
                            {"name": "blame"},
                        ]
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "error": {"code": -32601, "message": "read-only"},
                },
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "result": {"content": [{"type": "text", "text": "esperado"}]},
                },
            )
        )

        self.assertTrue(
            any("initialize" in error for error in binding.validate_session_output(output, "esperado"))
        )

    def test_session_requires_exact_protocol_and_named_versioned_server(self) -> None:
        for initialize in (
            {
                "protocolVersion": "not-2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake", "version": "1"},
            },
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "", "version": "1"},
            },
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake", "version": ""},
            },
        ):
            with self.subTest(initialize=initialize):
                output = "\n".join(
                    json.dumps(payload)
                    for payload in (
                        {"jsonrpc": "2.0", "id": 1, "result": initialize},
                        {
                            "jsonrpc": "2.0",
                            "id": 2,
                            "result": {
                                "tools": [
                                    {"name": "recall"},
                                    {"name": "recall_context"},
                                    {"name": "blame"},
                                ]
                            },
                        },
                        {
                            "jsonrpc": "2.0",
                            "id": 3,
                            "error": {"code": -32601, "message": "read-only"},
                        },
                        {
                            "jsonrpc": "2.0",
                            "id": 4,
                            "result": {
                                "content": [{"type": "text", "text": "esperado"}]
                            },
                        },
                    )
                )
                self.assertTrue(any(
                    "initialize" in error
                    for error in binding.validate_session_output(output, "esperado")
                ))

    def test_session_requires_tools_capability_mapping(self) -> None:
        for capabilities in ({}, {"tools": []}, {"tools": None}):
            with self.subTest(capabilities=capabilities):
                output = "\n".join(
                    json.dumps(payload)
                    for payload in (
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "result": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": capabilities,
                                "serverInfo": {"name": "fake", "version": "1"},
                            },
                        },
                        {
                            "jsonrpc": "2.0",
                            "id": 2,
                            "result": {
                                "tools": [
                                    {"name": "recall"},
                                    {"name": "recall_context"},
                                    {"name": "blame"},
                                ]
                            },
                        },
                        {
                            "jsonrpc": "2.0",
                            "id": 3,
                            "error": {"code": -32601, "message": "read-only"},
                        },
                        {
                            "jsonrpc": "2.0",
                            "id": 4,
                            "result": {
                                "content": [{"type": "text", "text": "esperado"}]
                            },
                        },
                    )
                )
                self.assertTrue(any(
                    "initialize" in error
                    for error in binding.validate_session_output(output, "esperado")
                ))

    def test_index_requires_a_recursive_regular_file(self) -> None:
        index = self.sandbox / "index"
        index.mkdir()
        (index / "empty").mkdir()

        self.assertFalse(binding._index_present(binding.snapshot_paths([index]), index))

        (index / "empty" / "manifest.gob").write_text("indexed", encoding="utf-8")
        self.assertTrue(binding._index_present(binding.snapshot_paths([index]), index))

    def test_index_output_rejects_unsafe_tree_before_wrapper(self) -> None:
        for kind in ("hardlink", "symlink", "special"):
            with self.subTest(kind=kind):
                shutil.rmtree(self.work, ignore_errors=True)
                commands: list[list[str]] = []

                def runner(command: list[str], **kwargs: object) -> _FakeProcess:
                    env = kwargs["env"]
                    assert isinstance(env, dict)
                    commands.append(command)

                    def responder(input_text: str | None) -> subprocess.CompletedProcess[str]:
                        completed = self._completed(command, env=env, input_text=input_text)
                        if command == [str(self.binary), "index"]:
                            index = Path(env["DEJA_INDEX_DIR"])
                            manifest = index / "manifest.gob"
                            if kind == "hardlink":
                                os.link(manifest, index / "manifest-linked.gob")
                            elif kind == "symlink":
                                (index / "escape").symlink_to(self.sandbox / "outside")
                            else:
                                os.mkfifo(index / "pipe")
                        return completed

                    return _FakeProcess(responder)

                with (
                    patch.object(binding, "PROJECT_ROOT", self.sandbox),
                    patch.object(binding, "BINARY", self.binary),
                    patch.object(binding, "WORK", self.work),
                    patch.object(binding.Path, "home", return_value=self.home),
                    patch.object(
                        binding, "_sha256", return_value=binding.EXPECTED_BINARY_SHA256
                    ),
                    patch.object(binding.subprocess, "Popen", side_effect=runner),
                ):
                    with self.assertRaisesRegex(binding.ValidationError, "árvore gravável"):
                        binding.validate_binding(
                            self.config, "json", query="consulta", expect="esperado"
                        )

                self.assertEqual(commands, [[str(self.binary), "index"]])

    def test_post_index_monitored_structure_stops_before_wrapper(self) -> None:
        self._assert_unsafe_monitored_mutations(after_wrapper=False)

    def test_post_wrapper_monitored_structure_rejects_finally(self) -> None:
        self._assert_unsafe_monitored_mutations(after_wrapper=True)

    def test_monitored_source_mutation_fails_after_the_session(self) -> None:
        def runner(command: list[str], **kwargs: object) -> _FakeProcess:
            env = kwargs["env"]
            assert isinstance(env, dict)

            def responder(input_text: str | None) -> subprocess.CompletedProcess[str]:
                completed = self._completed(command, env=env, input_text=input_text)
                if command == binding.mcp_command(self.work, self.home):
                    (self.home / ".copilot" / "events.jsonl").write_text(
                        "mutated", encoding="utf-8"
                    )
                return completed

            return _FakeProcess(responder)

        with (
            patch.object(binding, "PROJECT_ROOT", self.sandbox),
            patch.object(binding, "BINARY", self.binary),
            patch.object(binding, "WORK", self.work),
            patch.object(binding.Path, "home", return_value=self.home),
            patch.object(binding, "_sha256", return_value=binding.EXPECTED_BINARY_SHA256),
            patch.object(binding.subprocess, "Popen", side_effect=runner),
        ):
            with self.assertRaisesRegex(binding.ValidationError, "fontes monitoradas"):
                binding.validate_binding(
                    self.config, "json", query="consulta", expect="esperado"
                )

    def test_writable_tree_mutation_fails_after_the_session(self) -> None:
        def runner(command: list[str], **kwargs: object) -> _FakeProcess:
            env = kwargs["env"]
            assert isinstance(env, dict)

            def responder(input_text: str | None) -> subprocess.CompletedProcess[str]:
                completed = self._completed(command, env=env, input_text=input_text)
                if command == binding.mcp_command(self.work, self.home):
                    (self.work / "escape").symlink_to(self.sandbox / "outside")
                return completed

            return _FakeProcess(responder)

        with (
            patch.object(binding, "PROJECT_ROOT", self.sandbox),
            patch.object(binding, "BINARY", self.binary),
            patch.object(binding, "WORK", self.work),
            patch.object(binding.Path, "home", return_value=self.home),
            patch.object(binding, "_sha256", return_value=binding.EXPECTED_BINARY_SHA256),
            patch.object(binding.subprocess, "Popen", side_effect=runner),
        ):
            with self.assertRaisesRegex(binding.ValidationError, "árvore gravável"):
                binding.validate_binding(
                    self.config, "json", query="consulta", expect="esperado"
                )

    def test_mutation_is_reported_even_when_index_fails(self) -> None:
        def runner(command: list[str], **kwargs: object) -> _FakeProcess:
            if command == [str(self.binary), "index"]:
                (self.home / ".copilot" / "events.jsonl").write_text(
                    "mutated", encoding="utf-8"
                )
                return _FakeProcess(
                    lambda _input: subprocess.CompletedProcess(command, 1, "", "")
                )
            self.fail(f"comando inesperado: {command}")

        with (
            patch.object(binding, "PROJECT_ROOT", self.sandbox),
            patch.object(binding, "BINARY", self.binary),
            patch.object(binding, "WORK", self.work),
            patch.object(binding.Path, "home", return_value=self.home),
            patch.object(binding, "_sha256", return_value=binding.EXPECTED_BINARY_SHA256),
            patch.object(binding.subprocess, "Popen", side_effect=runner),
        ):
            with self.assertRaisesRegex(
                binding.ValidationError,
                "comando retornou 1; config ou fontes monitoradas mudaram",
            ):
                binding.validate_binding(
                    self.config, "json", query="consulta", expect="esperado"
                )

    def test_cli_requires_query_and_expect(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            binding.main(["--config", str(self.config)])

    def test_empty_query_or_expect_is_rejected(self) -> None:
        for query, expect in (("", "expect"), ("query", "")):
            with self.subTest(query=query, expect=expect):
                with self.assertRaisesRegex(binding.ValidationError, "não podem ser vazios"):
                    binding.validate_binding(self.config, "json", query=query, expect=expect)

    def test_command_failures_are_not_accepted(self) -> None:
        for label, failure in (
            ("timeout", subprocess.TimeoutExpired(["deja", "index"], 30)),
            ("returncode", subprocess.CompletedProcess(["deja", "index"], 1, "", "")),
            ("stderr", subprocess.CompletedProcess(["deja", "index"], 0, "", "warning")),
            ("invalid-json", subprocess.CompletedProcess(["deja", "mcp"], 0, "not json\n", "")),
        ):
            def runner(command: list[str], **kwargs: object) -> _FakeProcess:
                env = kwargs["env"]
                assert isinstance(env, dict)
                timed_out = False

                def responder(input_text: str | None) -> subprocess.CompletedProcess[str]:
                    nonlocal timed_out
                    if label == "invalid-json" and command == [str(self.binary), "index"]:
                        return self._completed(command, env=env, input_text=input_text)
                    if isinstance(failure, BaseException):
                        if timed_out:
                            return subprocess.CompletedProcess(command, -9, "", "")
                        timed_out = True
                        raise failure
                    return failure

                return _FakeProcess(responder)

            with self.subTest(label=label):
                with (
                    patch.object(binding, "PROJECT_ROOT", self.sandbox),
                    patch.object(binding, "BINARY", self.binary),
                    patch.object(binding, "WORK", self.work),
                    patch.object(binding.Path, "home", return_value=self.home),
                    patch.object(binding, "_sha256", return_value=binding.EXPECTED_BINARY_SHA256),
                    patch.object(binding.subprocess, "Popen", side_effect=runner),
                    patch.object(binding.os, "killpg"),
                ):
                    with self.assertRaises(binding.ValidationError):
                        binding.validate_binding(
                            self.config, "json", query="consulta", expect="esperado"
                        )


if __name__ == "__main__":
    unittest.main()
