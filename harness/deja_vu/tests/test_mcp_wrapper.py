from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "mcp_wrapper.py"
SPEC = importlib.util.spec_from_file_location("deja_mcp_wrapper", MODULE_PATH)
assert SPEC and SPEC.loader
wrapper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wrapper)


def _roundtrip(messages: list[dict[str, object]], timeout: float = 30.0) -> list[dict[str, Any]]:
    payload = "".join(json.dumps(message) + "\n" for message in messages)
    completed = subprocess.run(
        [sys.executable, "-B", str(MODULE_PATH)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]


class McpWrapperTests(unittest.TestCase):
    def test_tools_list_exposes_only_read_only_tools(self) -> None:
        responses = _roundtrip([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ])

        tools = next(r for r in responses if r.get("id") == 2)["result"]["tools"]
        names = {tool["name"] for tool in tools}
        self.assertEqual(names, {"recall", "recall_context", "blame"})

    def test_remember_is_rejected_with_jsonrpc_error(self) -> None:
        responses = _roundtrip([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "remember", "arguments": {"text": "test"}}},
        ])

        error = next(r for r in responses if r.get("id") == 3)["error"]
        self.assertEqual(error["code"], -32601)
        self.assertIn("read-only", error["message"])

    def test_recall_delegates_to_real_binary(self) -> None:
        responses = _roundtrip([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "recall", "arguments": {"query": "SSOT namespace ontologia", "limit": 1}}},
        ], timeout=60.0)

        result = next(r for r in responses if r.get("id") == 4)["result"]
        self.assertIn("SSOT", result["content"][0]["text"])

    def test_environment_does_not_leak_secrets(self) -> None:
        work = ROOT / ".work" / "test-wrapper-env"
        env = wrapper.real_env(work, Path("/tmp/fake-home"))
        self.assertNotIn("GH_TOKEN", env)
        self.assertNotIn("DEJA_NO_REDACT", env)
        self.assertTrue(Path(env["HOME"]).is_relative_to(work))


if __name__ == "__main__":
    unittest.main()
