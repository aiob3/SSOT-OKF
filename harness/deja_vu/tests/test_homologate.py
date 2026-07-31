from __future__ import annotations

import hashlib
import importlib.util
import io
import os
import shutil
import tarfile
import unittest
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

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
            "XDG_DATA_HOME",
            "XDG_STATE_HOME",
            "XDG_RUNTIME_DIR",
            "TMPDIR",
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

    def test_environment_does_not_inherit_secrets_or_external_xdg_paths(self) -> None:
        work = ROOT / ".work" / "test-environment-allowlist"
        inherited = {
            "AWS_SECRET_ACCESS_KEY": "synthetic-secret",
            "DEJA_NO_REDACT": "1",
            "XDG_DATA_HOME": "/outside/data",
            "XDG_STATE_HOME": "/outside/state",
            "TMPDIR": "/outside/tmp",
        }

        with patch.dict(os.environ, inherited, clear=False):
            env = homologate.isolated_env(work)

        self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
        for name in ("XDG_DATA_HOME", "XDG_STATE_HOME", "TMPDIR"):
            self.assertTrue(Path(env[name]).is_relative_to(work), name)

    def test_github_transport_is_separate_from_deja_environment(self) -> None:
        work = ROOT / ".work" / "test-gh-env"
        inherited = {
            "HTTPS_PROXY": "http://proxy.invalid:8080",
            "GH_TOKEN": "synthetic-token",
            "AWS_SECRET_ACCESS_KEY": "synthetic-secret",
        }
        with patch.dict(os.environ, inherited, clear=False):
            gh_env = homologate.github_env(work)
            deja_env = homologate.isolated_env(work)

        self.assertEqual(gh_env["HTTPS_PROXY"], inherited["HTTPS_PROXY"])
        self.assertNotIn("GH_TOKEN", gh_env)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", gh_env)
        self.assertNotIn("HTTPS_PROXY", deja_env)

    def test_attestation_token_is_explicit_and_never_reaches_deja(self) -> None:
        work = ROOT / ".work" / "test-gh-token"

        with patch.dict(os.environ, {"GH_TOKEN": "inherited-token"}, clear=False):
            gh_env = homologate.github_env(work, "explicit-token")
            deja_env = homologate.isolated_env(work)

        self.assertEqual(gh_env["GH_TOKEN"], "explicit-token")
        self.assertTrue(Path(gh_env["GH_CONFIG_DIR"]).is_relative_to(work))
        self.assertNotIn("GH_TOKEN", deja_env)


class WorkPathSafetyTests(unittest.TestCase):
    def test_symlinked_work_is_rejected_without_touching_target(self) -> None:
        sandbox = ROOT / ".work" / "test-work-path"
        shutil.rmtree(sandbox, ignore_errors=True)
        project = sandbox / "project"
        target = sandbox / "external-target"
        project.mkdir(parents=True)
        target.mkdir()
        marker = target / "preserve.txt"
        marker.write_text("preserve", encoding="utf-8")
        (project / ".work").symlink_to(target, target_is_directory=True)

        with self.assertRaisesRegex(RuntimeError, "symlink"):
            homologate.validate_work_path(project / ".work", project)

        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
        shutil.rmtree(sandbox, ignore_errors=True)

    def test_non_work_project_path_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "project-owned .work"):
            homologate.validate_work_path(ROOT / "docs", ROOT)


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

    def test_oversized_download_is_never_published(self) -> None:
        work = ROOT / ".work" / "test-download-limit"
        shutil.rmtree(work, ignore_errors=True)
        self.addCleanup(shutil.rmtree, work, True)
        target = work / "asset.bin"

        with self.assertRaisesRegex(RuntimeError, "size limit"):
            homologate.download_asset(
                "data:application/octet-stream;base64,QUJDREVGR0g=",
                target,
                max_bytes=4,
            )

        self.assertFalse(target.exists())
        self.assertEqual(list(work.glob("*.part")), [])

    def test_archive_rejects_links_before_publishing_binary(self) -> None:
        work = ROOT / ".work" / "test-archive-link"
        shutil.rmtree(work, ignore_errors=True)
        self.addCleanup(shutil.rmtree, work, True)
        work.mkdir(parents=True)
        archive = work / "bundle.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            binary = tarfile.TarInfo("deja")
            binary.size = 4
            bundle.addfile(binary, io.BytesIO(b"deja"))
            link = tarfile.TarInfo("escape")
            link.type = tarfile.SYMTYPE
            link.linkname = "/outside"
            bundle.addfile(link)

        with self.assertRaisesRegex(RuntimeError, "links are forbidden"):
            homologate.extract_release(archive, work / "bin")
        self.assertFalse((work / "bin" / "deja").exists())

    def test_archive_rejects_hardlinks(self) -> None:
        work = ROOT / ".work" / "test-archive-hardlink"
        shutil.rmtree(work, ignore_errors=True)
        self.addCleanup(shutil.rmtree, work, True)
        work.mkdir(parents=True)
        archive = work / "bundle.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            binary = tarfile.TarInfo("deja")
            binary.size = 4
            bundle.addfile(binary, io.BytesIO(b"deja"))
            link = tarfile.TarInfo("copy")
            link.type = tarfile.LNKTYPE
            link.linkname = "deja"
            bundle.addfile(link)

        with self.assertRaisesRegex(RuntimeError, "links are forbidden"):
            homologate.extract_release(archive, work / "bin")

    def test_archive_enforces_member_limit_and_one_deja(self) -> None:
        work = ROOT / ".work" / "test-archive-limits"
        shutil.rmtree(work, ignore_errors=True)
        self.addCleanup(shutil.rmtree, work, True)
        work.mkdir(parents=True)
        archive = work / "bundle.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            for name in ("deja", "nested/deja"):
                member = tarfile.TarInfo(name)
                member.size = 4
                bundle.addfile(member, io.BytesIO(b"deja"))

        with self.assertRaisesRegex(RuntimeError, "exactly one regular deja"):
            homologate.extract_release(archive, work / "bin")
        with patch.object(homologate, "MAX_TAR_MEMBERS", 1):
            with self.assertRaisesRegex(RuntimeError, "member count limit"):
                homologate.extract_release(archive, work / "bin")

    def test_spdx_must_bind_archive_digest(self) -> None:
        digest = "a" * 64
        document = {
            "spdxVersion": "SPDX-2.3",
            "SPDXID": "SPDXRef-DOCUMENT",
            "dataLicense": "CC0-1.0",
            "name": homologate.ASSET,
            "documentNamespace": "https://example.invalid/spdx/release",
            "creationInfo": {
                "creators": ["Tool: test"],
                "created": "2026-07-30T00:00:00Z",
            },
            "packages": [
                {
                    "name": homologate.ASSET,
                    "SPDXID": "SPDXRef-Archive",
                    "versionInfo": f"sha256:{digest}",
                }
            ],
        }

        homologate.validate_sbom(document, homologate.ASSET, digest)
        document["packages"][0]["versionInfo"] = "sha256:" + ("b" * 64)
        with self.assertRaisesRegex(RuntimeError, "archive digest"):
            homologate.validate_sbom(document, homologate.ASSET, digest)

    def test_attestation_requires_archive_subject_and_sanitizes_certificate(self) -> None:
        digest = "a" * 64
        payload = [
            {
                "verificationResult": {
                    "statement": {
                        "predicateType": "https://slsa.dev/provenance/v1",
                        "subject": [
                            {"name": homologate.ASSET, "digest": {"sha256": digest}}
                        ],
                    },
                    "signature": {
                        "certificate": {
                            "sourceRepositoryURI": "https://github.com/vshulcz/deja-vu",
                            "sourceRepositoryDigest": "b" * 40,
                            "sourceRepositoryRef": "refs/tags/v0.16.4",
                        }
                    },
                    "verifiedTimestamps": [{"type": "Tlog"}],
                }
            }
        ]

        evidence = homologate.validate_attestation(
            payload, {homologate.ASSET: digest}
        )

        self.assertEqual(evidence["subjects"], {homologate.ASSET: digest})
        self.assertNotIn("certificate", evidence)
        payload[0]["verificationResult"]["statement"]["subject"] = []
        with self.assertRaisesRegex(RuntimeError, "subject"):
            homologate.validate_attestation(payload, {homologate.ASSET: digest})

class RetrievalEvaluationTests(unittest.TestCase):
    def _payload(self) -> dict[str, Any]:
        fixture = (
            ROOT
            / ".work"
            / "fixtures"
            / "claude"
            / "-data-SSOT-OKF"
            / "homolog-claude-001.jsonl"
        )
        return {
            "schema_version": 2,
            "tier": "exact",
            "hits": [
                {"session": {"harness": "claude", "id": "other"}},
                {
                    "tier": "exact",
                    "session": {
                        "harness": "claude",
                        "id": "homolog-claude-001",
                        "path": str(fixture),
                        "source": {
                            "origin": "local",
                            "instance": "ssot-okf-homologation",
                        },
                    },
                },
            ],
        }

    def test_only_exact_hit_for_expected_project_owned_session_passes(self) -> None:
        payload = self._payload()

        self.assertTrue(
            homologate.query_passed(payload, "claude", "homolog-claude-001")
        )
        self.assertFalse(homologate.query_passed(payload, "codex", "homolog-codex-001"))
        payload["tier"] = "relevance"
        self.assertFalse(
            homologate.query_passed(payload, "claude", "homolog-claude-001")
        )
        payload["tier"] = "close"
        self.assertFalse(
            homologate.query_passed(payload, "claude", "homolog-claude-001")
        )
        payload["tier"] = "exact"
        payload["schema_version"] = 999
        self.assertFalse(
            homologate.query_passed(payload, "claude", "homolog-claude-001")
        )

    def test_missing_provenance_fails_closed(self) -> None:
        payload = self._payload()
        del payload["hits"][1]["session"]["source"]

        self.assertFalse(
            homologate.query_passed(payload, "claude", "homolog-claude-001")
        )

    def test_retrieval_gate_requires_all_eight_exact_hits(self) -> None:
        results = [
            {"passed": True, "tier": "exact", "harness": harness}
            for harness in (
                "claude",
                "claude",
                "codex",
                "codex",
                "copilot",
                "copilot",
                "hermes",
                "hermes",
            )
        ]

        self.assertTrue(homologate.retrieval_gate(results))
        results[-1]["passed"] = False
        self.assertFalse(homologate.retrieval_gate(results))


class IsolationGateTests(unittest.TestCase):
    def test_sources_require_expected_counts_and_project_owned_paths(self) -> None:
        work = ROOT / ".work" / "test-source-gate"
        lines = [
            f"claude\t{work / 'fixtures/claude'}\tsessions=1 messages=2 size=1 B redacted=1",
            f"codex\t{work / 'fixtures/codex'}\tsessions=1 messages=2 size=1 B redacted=0",
            f"copilot\t{work / 'fixtures/copilot'}\tsessions=1 messages=2 size=1 B redacted=0",
            f"hermes\t{work / 'home/.hermes/profiles'}\tsessions=1 messages=2 size=1 B redacted=0",
            f"gemini\t{work / 'home/.gemini'}\tsessions=0 messages=0 size=0 B redacted=0",
        ]

        self.assertTrue(homologate.sources_are_isolated("\n".join(lines), work))
        self.assertFalse(
            homologate.sources_are_isolated(
                "\n".join(lines + ["aider\t/outside\tsessions=1 messages=1"]),
                work,
            )
        )

    def test_mcp_gate_requires_known_clients_explicitly_missing(self) -> None:
        work = ROOT / ".work" / "test-mcp-gate"
        clients = ["claude-code", "codex", "copilot", "hermes"]
        doctor = {
            "schema_version": 2,
            "mcp": [
                {
                    "name": name,
                    "state": "config-missing",
                    "path": str(work / "home" / f"{name}.json"),
                }
                for name in clients
            ],
        }

        self.assertTrue(homologate.mcp_is_unwired(doctor, work))
        doctor["mcp"][0]["state"] = "unknown"
        self.assertFalse(homologate.mcp_is_unwired(doctor, work))
        doctor.pop("mcp")
        self.assertFalse(homologate.mcp_is_unwired(doctor, work))


class ReversibilityTests(unittest.TestCase):
    def test_clean_propagates_failure_and_checks_absence(self) -> None:
        sandbox = ROOT / ".work" / "test-clean"
        shutil.rmtree(sandbox, ignore_errors=True)
        self.addCleanup(shutil.rmtree, sandbox, True)
        project = sandbox / "project"
        work = project / ".work"
        work.mkdir(parents=True)

        with patch.object(homologate.shutil, "rmtree", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "still exists"):
                homologate.clean_work(work, project)

        homologate.clean_work(work, project)
        self.assertFalse(os.path.lexists(work))

    def test_snapshot_detects_creation_in_xdg_config(self) -> None:
        work = ROOT / ".work" / "test-config-snapshot"
        shutil.rmtree(work, ignore_errors=True)
        self.addCleanup(shutil.rmtree, work, True)
        xdg = work / "xdg"
        paths = homologate.live_config_paths(
            {"HOME": str(work / "home"), "XDG_CONFIG_HOME": str(xdg)}
        )
        config = xdg / "opencode" / "opencode.json"
        self.assertIn(config, paths)
        before = homologate.snapshot_paths(paths)
        config.parent.mkdir(parents=True)
        config.write_text("{}", encoding="utf-8")

        self.assertNotEqual(before, homologate.snapshot_paths(paths))

    def test_generated_results_link_to_report_hash_without_egress_claim(self) -> None:
        report = {
            "timestamp_utc": "2026-07-30T00:00:00Z",
            "environment": "synthetic-project-owned",
            "verdict": "PASS",
            "release": {
                "asset": homologate.ASSET,
                "sha256": "a" * 64,
                "attestation": {
                    "status": "verified",
                    "repository": "vshulcz/deja-vu",
                    "signer_identity": "https://github.com/vshulcz/deja-vu",
                    "source_digest": "b" * 40,
                },
                "sbom": {
                    "asset": f"{homologate.ASSET}.spdx.json",
                    "sha256": "c" * 64,
                    "spdx_version": "SPDX-2.3",
                },
            },
            "quality_gates": {
                "unittest": {"passed": True},
                "ruff": {"passed": True},
            },
            "queries": [
                {"harness": harness, "passed": True}
                for harness in ("claude", "claude", "codex", "codex", "copilot", "copilot", "hermes", "hermes")
            ],
            "criteria": {"retrieval_8_of_8_exact": True},
        }

        rendered = homologate.render_results(report, "d" * 64)

        self.assertIn("`" + ("d" * 64) + "`", rendered)
        self.assertIn("não afirma egress zero", rendered)
        self.assertIn("attestation separada para o SBOM", rendered)


if __name__ == "__main__":
    unittest.main()
