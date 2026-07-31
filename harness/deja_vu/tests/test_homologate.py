from __future__ import annotations

import hashlib
import importlib.util
import shutil
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "homologate.py"
SPEC = importlib.util.spec_from_file_location("deja_homologate", MODULE_PATH)
assert SPEC and SPEC.loader
homologate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(homologate)


class IsolatedEnvironmentTests(unittest.TestCase):
    def test_environment_stays_inside_project_and_disables_implicit_recall(self) -> None:
        work = ROOT / ".work" / "test-environment"

        env = homologate.isolated_env(work)

        for name in (
            "HOME",
            "XDG_CACHE_HOME",
            "XDG_CONFIG_HOME",
            "DEJA_INDEX_DIR",
            "DEJA_CLAUDE_ROOT",
            "DEJA_CODEX_ROOT",
            "DEJA_COPILOT_ROOT",
            "DEJA_HERMES_DB",
        ):
            self.assertTrue(Path(env[name]).is_relative_to(work), name)
        self.assertEqual(env["DEJA_OFFLINE"], "1")
        self.assertEqual(env["DEJA_RECALL"], "off")
        self.assertEqual(env["DEJA_EMBED"], "off")
        self.assertEqual(env["DEJA_SOURCE_INSTANCE"], "ssot-okf-homologation")
        self.assertNotIn("DEJA_NO_REDACT", env)


class SyntheticFixtureTests(unittest.TestCase):
    def test_fixtures_cover_two_queries_for_each_harness_and_unicode(self) -> None:
        work = ROOT / ".work" / "test-fixtures"
        shutil.rmtree(work, ignore_errors=True)

        manifest = homologate.write_fixtures(work)

        self.assertEqual(
            Counter(item["harness"] for item in manifest["queries"]),
            {"claude": 2, "codex": 2, "copilot": 2, "hermes": 2},
        )
        self.assertEqual(len(manifest["sources"]), 4)
        for source in manifest["sources"]:
            self.assertTrue(Path(source).is_relative_to(work), source)
        corpus = b"".join(Path(source).read_bytes() for source in manifest["sources"])
        self.assertIn("ação tática".encode(), corpus)
        self.assertIn("token=ghp_".encode(), corpus)


class ReleaseIntegrityTests(unittest.TestCase):
    def test_archive_must_match_published_checksum(self) -> None:
        work = ROOT / ".work" / "test-checksum"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        archive = work / "deja-vu.tar.gz"
        archive.write_bytes(b"published release")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        checksums = f"{digest}  {archive.name}\n"

        self.assertEqual(homologate.verify_checksum(checksums, archive), digest)
        archive.write_bytes(b"tampered release")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            homologate.verify_checksum(checksums, archive)


class RetrievalEvaluationTests(unittest.TestCase):
    def test_only_ranked_non_relevance_hit_for_expected_session_passes(self) -> None:
        payload = {
            "tier": "exact",
            "hits": [
                {"session": {"harness": "claude", "id": "other"}},
                {
                    "session": {
                        "harness": "claude",
                        "id": "homolog-claude-001",
                        "source": {
                            "origin": "local",
                            "instance": "ssot-okf-homologation",
                        },
                    }
                },
            ],
        }

        self.assertTrue(
            homologate.query_passed(payload, "claude", "homolog-claude-001")
        )
        self.assertFalse(homologate.query_passed(payload, "codex", "homolog-codex-001"))
        payload["tier"] = "relevance"
        self.assertFalse(
            homologate.query_passed(payload, "claude", "homolog-claude-001")
        )
        payload["tier"] = "exact"
        del payload["hits"][1]["session"]["source"]
        self.assertFalse(
            homologate.query_passed(payload, "claude", "homolog-claude-001")
        )


if __name__ == "__main__":
    unittest.main()
