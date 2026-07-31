from __future__ import annotations

import importlib.util
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "preview_real.py"
SPEC = importlib.util.spec_from_file_location("deja_preview_real", MODULE_PATH)
assert SPEC and SPEC.loader
preview = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preview)


class ReadOnlyEnvironmentTests(unittest.TestCase):
    def test_real_roots_are_read_and_writes_stay_inside_project(self) -> None:
        work = ROOT / ".work" / "test-preview-env"
        home = Path("/tmp/fake-home")

        env = preview.real_env(work, home)

        self.assertEqual(env["DEJA_HERMES_DB"], str(home / ".hermes" / "state.db"))
        self.assertEqual(env["DEJA_CLAUDE_ROOT"], str(home / ".claude" / "projects"))
        self.assertEqual(env["DEJA_CODEX_ROOT"], str(home / ".codex"))
        for name in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "DEJA_INDEX_DIR"):
            self.assertTrue(Path(env[name]).is_relative_to(work), name)
        self.assertEqual(env["DEJA_RECALL"], "off")
        self.assertEqual(env["DEJA_EMBED"], "off")
        self.assertEqual(env["DEJA_OFFLINE"], "1")

    def test_secrets_are_not_handed_to_the_binary(self) -> None:
        work = ROOT / ".work" / "test-preview-secrets"

        with patch.dict(os.environ, {"GH_TOKEN": "t", "DEJA_NO_REDACT": "1"}, clear=False):
            env = preview.real_env(work, Path("/tmp/fake-home"))

        self.assertNotIn("GH_TOKEN", env)
        self.assertNotIn("DEJA_NO_REDACT", env)


class ReadOnlyProofTests(unittest.TestCase):
    def test_stat_snapshot_detects_any_mutation_of_the_real_stores(self) -> None:
        sandbox = ROOT / ".work" / "test-preview-snapshot"
        shutil.rmtree(sandbox, ignore_errors=True)
        self.addCleanup(shutil.rmtree, sandbox, True)
        store = sandbox / "store"
        (store / "nested").mkdir(parents=True)
        session = store / "nested" / "session.jsonl"
        session.write_text("original", encoding="utf-8")

        before = preview.stat_snapshot([store])
        session.write_text("mutated!", encoding="utf-8")

        self.assertNotEqual(before, preview.stat_snapshot([store]))

    def test_stat_snapshot_is_stable_when_nothing_changes(self) -> None:
        sandbox = ROOT / ".work" / "test-preview-stable"
        shutil.rmtree(sandbox, ignore_errors=True)
        self.addCleanup(shutil.rmtree, sandbox, True)
        store = sandbox / "store"
        store.mkdir(parents=True)
        (store / "a.jsonl").write_text("a", encoding="utf-8")

        self.assertEqual(preview.stat_snapshot([store]), preview.stat_snapshot([store]))

    def test_missing_store_is_recorded_not_crashed(self) -> None:
        snapshot = preview.stat_snapshot([Path("/nonexistent/store")])

        self.assertEqual(snapshot, {"/nonexistent/store": "missing"})

    def test_diff_names_the_changed_file_so_live_sessions_are_separable(self) -> None:
        sandbox = ROOT / ".work" / "test-preview-diff"
        shutil.rmtree(sandbox, ignore_errors=True)
        self.addCleanup(shutil.rmtree, sandbox, True)
        store = sandbox / "store"
        store.mkdir(parents=True)
        (store / "stable.jsonl").write_text("same", encoding="utf-8")
        live = store / "live.jsonl"
        live.write_text("a", encoding="utf-8")

        before = preview.stat_snapshot([store])
        live.write_text("aa", encoding="utf-8")
        (store / "new.jsonl").write_text("n", encoding="utf-8")
        changes = preview.diff_snapshots(before, preview.stat_snapshot([store]))

        self.assertEqual(
            {(change["path"], change["kind"]) for change in changes},
            {("live.jsonl", "modified"), ("new.jsonl", "created")},
        )
        self.assertEqual(preview.diff_snapshots(before, before), [])

    def test_diff_ignores_volatile_noise_from_live_agents(self) -> None:
        sandbox = ROOT / ".work" / "test-preview-volatile"
        shutil.rmtree(sandbox, ignore_errors=True)
        self.addCleanup(shutil.rmtree, sandbox, True)
        store = sandbox / "store"
        (store / "tmp" / "arg0").mkdir(parents=True)
        (store / "state.sqlite-wal").write_text("w", encoding="utf-8")
        (store / "tmp" / "arg0" / ".lock").write_text("l", encoding="utf-8")

        before = preview.stat_snapshot([store])
        (store / "state.sqlite-wal").write_text("ww", encoding="utf-8")
        (store / "tmp" / "arg0" / ".lock").write_text("ll", encoding="utf-8")
        changes = preview.diff_snapshots(before, preview.stat_snapshot([store]))

        self.assertEqual(changes, [])


if __name__ == "__main__":
    unittest.main()
