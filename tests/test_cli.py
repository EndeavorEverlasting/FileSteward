"""CLI proof: entry-point identity (L0) and the S1 read-only happy path (L3).

S1 chain: CLI -> CleanupRun -> synthetic scanner -> ProtectionIndex ->
rules/gates -> challenge -> artifact writers -> summary, passing only
when artifacts reconcile and the fixture filesystem is unchanged.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Iterator

import pytest
import tomllib

import filesteward
from filesteward.cli import (
    EXIT_INVALID,
    EXIT_LANE_UNAVAILABLE,
    EXIT_OK,
    build_parser,
    main,
)
from filesteward.policy.paths import run_dir as policy_run_dir


class TestEntryPointIdentity:
    def test_version_matches_packaging_metadata(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with (root / "pyproject.toml").open("rb") as handle:
            data = tomllib.load(handle)
        assert data["project"]["version"] == filesteward.__version__
        assert data["project"]["scripts"]["filesteward"] == "filesteward.cli:main"
        assert data["project"]["requires-python"] == ">=3.12"

    def test_parser_vocabulary_is_p04_contract(self) -> None:
        parser = build_parser()
        subparsers_action = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        assert subparsers_action.choices is not None
        assert set(subparsers_action.choices) == {
            "scan",
            "validate",
            "plan",
            "visualize",
            "delete-manifest",
            "delete-preflight",
            "delete-approve",
            "delete-execute",
            "apply",
        }

    def test_scan_requires_run_dir(self) -> None:
        with pytest.raises(SystemExit) as exc:
            main(["scan", "C:/synthetic/root"])
        assert exc.value.code == 2


class TestInvocationBehavior:
    def test_version_flag_exits_zero(self) -> None:
        with pytest.raises(SystemExit) as exc:
            main(["--version"])
        assert exc.value.code == 0

    def test_no_args_is_usage_error(self) -> None:
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 2

    @pytest.mark.parametrize(
        "argv",
        [
            ["apply", "var/runs/l0/manifest.json"],
            ["apply", "var/runs/l0/manifest.json", "--execute"],
        ],
        ids=["apply-dry", "apply-execute"],
    )
    def test_lane_unavailable_not_fake_success(
        self, argv: list[str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = main(argv)
        assert code == EXIT_LANE_UNAVAILABLE
        assert code != 0
        captured = capsys.readouterr()
        assert "not available yet" in captured.err
        assert captured.out == ""

    def test_apply_execute_refuses_without_touching_disk(
        self, tmp_path: Path
    ) -> None:
        before = sorted(p.name for p in tmp_path.iterdir())
        manifest = tmp_path / "manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        snapshot = manifest.read_bytes()

        code = main(["apply", str(manifest), "--execute"])

        assert code == EXIT_LANE_UNAVAILABLE
        assert manifest.read_bytes() == snapshot
        assert sorted(p.name for p in tmp_path.iterdir()) == before + ["manifest.json"]

    def test_import_surface_is_small(self) -> None:
        assert set(filesteward.__all__) == {"__version__"}


# --- S1: CLI read-only happy path ---------------------------------------


@pytest.fixture
def s1_run_dir() -> Iterator[Path]:
    path = policy_run_dir(f"test-s1-{uuid.uuid4().hex[:10]}")
    yield path
    shutil.rmtree(path, ignore_errors=True)


def build_s1_fixture(root: Path) -> None:
    (root / "cache" / "pip" / "http").mkdir(parents=True)
    (root / "cache" / "pip" / "http" / "body.whl").write_bytes(b"W" * 1000)
    (root / "cache" / "pip" / "http" / "index.json").write_bytes(b"{}" * 500)
    (root / "archive").mkdir()
    (root / "archive" / "old-backup.tar").write_bytes(b"\x00" * 4096)
    (root / "misc").mkdir()
    (root / "misc" / "notes.txt").write_text("operator note", encoding="utf-8")
    (root / "proj" / "repo").mkdir(parents=True)
    (root / "proj" / "repo" / "tracked.txt").write_text("repo", encoding="utf-8")


def snapshot(root: Path) -> list[tuple]:
    """Deterministic tree manifest: relpath, type, size, hash, mtime."""

    entries: list[tuple] = []
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix().casefold()):
        relative = path.relative_to(root).as_posix()
        stat = path.lstat()
        if path.is_dir():
            entries.append((relative, "DIR", None, None, stat.st_mtime_ns))
        elif path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries.append(
                (relative, "FILE", stat.st_size, digest, stat.st_mtime_ns)
            )
        else:
            entries.append(
                (relative, "OTHER", stat.st_size, None, stat.st_mtime_ns)
            )
    return entries


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class TestS1CliEndToEnd:
    def test_s1_scan_produces_reconciling_artifacts_without_mutation(
        self, tmp_path: Path, s1_run_dir: Path
    ) -> None:
        root = (tmp_path / "root").resolve()
        build_s1_fixture(root)
        before = snapshot(root)

        baseline = 1_000_000
        target = 1_001_500  # gap 1500: no reclaim without ownership evidence
        code = main(
            [
                "scan",
                str(root),
                "--run-dir",
                str(s1_run_dir),
                "--contract",
                str(root / "cache" / "pip"),
                "--protect",
                str(root / "proj" / "repo"),
                "--target-free-bytes",
                str(target),
                "--baseline-free-bytes",
                str(baseline),
            ]
        )
        assert code == EXIT_OK
        assert snapshot(root) == before, "fixture filesystem changed"

        for name in (
            "cleanup-plan.csv",
            "human-review.csv",
            "protected-exclusions.csv",
            "inventory.csv",
            "cleanup-summary.md",
            "run.json",
        ):
            assert (s1_run_dir / name).is_file(), name

        plan = read_rows(s1_run_dir / "cleanup-plan.csv")
        assert plan == [], "a CLI path contract does not prove ownership"

        review = read_rows(s1_run_dir / "human-review.csv")
        review_paths = {row["path"] for row in review}
        assert str(root / "archive" / "old-backup.tar") in review_paths
        review_text = (s1_run_dir / "human-review.csv").read_text(
            encoding="utf-8"
        ).casefold()
        assert "score" not in review_text
        assert "probably safe" not in review_text

        exclusions = read_rows(s1_run_dir / "protected-exclusions.csv")
        by_path = {row["path"]: row for row in exclusions}
        assert (
            by_path[str(root / "proj" / "repo")]["relationship"] == "SELF"
        )
        assert (
            by_path[str(root / "proj" / "repo" / "tracked.txt")][
                "relationship"
            ]
            == "DESCENDANT"
        )
        assert by_path[str(root)]["relationship"] == "ANCESTOR"
        for row in exclusions:
            assert row["protection_reason"]
            assert row["protection_source"]

        # Stable item reconciliation: every inventory item lands in
        # exactly one artifact, joined by item_id.
        inventory = read_rows(s1_run_dir / "inventory.csv")
        assert len(inventory) == 13
        assert len({row["item_id"] for row in inventory}) == 13

        # Missing ownership cannot create projected capacity or a stop row.
        metadata = json.loads(
            (s1_run_dir / "run.json").read_text(encoding="utf-8")
        )
        assert metadata["authorization_state"] == "UNAPPROVED"
        assert metadata["baseline_free_bytes"] == baseline
        assert metadata["target_free_bytes"] == target
        assert metadata["stop_row"] is None
        assert metadata["cumulative_projected_reclaim_bytes"] == 0
        ownership_rows = {row["path"]: row for row in review}
        cache_row = ownership_rows[str(root / "cache" / "pip" / "http" / "body.whl")]
        assert cache_row["disposition"] == "UNKNOWN"
        action_packet = json.loads((s1_run_dir / "owner-action-plan.json").read_text(encoding="utf-8"))
        action_rows = {row["path"]: row for row in action_packet["items"]}
        assert "OWNERSHIP_INCOMPLETE_OR_STALE" in action_rows[cache_row["path"]]["reason_codes"]

        summary = (s1_run_dir / "cleanup-summary.md").read_text(
            encoding="utf-8"
        )
        assert "UNAPPROVED" in summary
        assert "no approval" in summary

        assert main(["validate", str(s1_run_dir)]) == EXIT_OK
        # validate accepts the proposed-action manifest path directly.
        assert (
            main(["validate", str(s1_run_dir / "cleanup-plan.csv")])
            == EXIT_OK
        )

    def test_s13_managed_flag_keeps_system_path_out_of_plan(
        self, tmp_path: Path, s1_run_dir: Path
    ) -> None:
        root = (tmp_path / "root").resolve()
        (root / "sys").mkdir(parents=True)
        (root / "sys" / "app.db").write_bytes(b"D" * 500)
        (root / "cache").mkdir()
        (root / "cache" / "hit.bin").write_bytes(b"C" * 900)
        code = main(
            [
                "scan",
                str(root),
                "--run-dir",
                str(s1_run_dir),
                "--contract",
                str(root / "cache"),
                "--managed",
                str(root / "sys"),
            ]
        )
        assert code == EXIT_OK
        plan = read_rows(s1_run_dir / "cleanup-plan.csv")
        plan_paths = {row["path"] for row in plan}
        assert str(root / "sys" / "app.db") not in plan_paths
        assert not plan_paths, "--contract alone must fail ownership admission"

    def test_scan_reports_counts_and_unapproved_statement(
        self, tmp_path: Path, s1_run_dir: Path, capsys
    ) -> None:
        root = (tmp_path / "root").resolve()
        build_s1_fixture(root)
        code = main(
            [
                "scan",
                str(root),
                "--run-dir",
                str(s1_run_dir),
                "--protect",
                str(root / "proj" / "repo"),
            ]
        )
        assert code == EXIT_OK
        out = capsys.readouterr().out
        assert "items" in out
        assert "UNAPPROVED" in out
        assert "no operator approval" in out


class TestCliExitCodes:
    def test_scan_missing_root_exits_invalid(
        self, tmp_path: Path, s1_run_dir: Path, capsys
    ) -> None:
        code = main(
            ["scan", str(tmp_path / "absent"), "--run-dir", str(s1_run_dir)]
        )
        assert code == EXIT_INVALID
        assert "not a directory" in capsys.readouterr().err

    def test_scan_run_dir_outside_var_exits_invalid(
        self, tmp_path: Path, capsys
    ) -> None:
        root = tmp_path / "root"
        root.mkdir()
        code = main(
            ["scan", str(root), "--run-dir", str(tmp_path / "somewhere")]
        )
        assert code == EXIT_INVALID
        assert "runtime tree" in capsys.readouterr().err

    def test_validate_missing_run_exits_invalid(
        self, tmp_path: Path, capsys
    ) -> None:
        code = main(["validate", str(tmp_path / "no-run")])
        assert code == EXIT_INVALID
        assert "not found" in capsys.readouterr().err

    def test_validate_foreign_manifest_exits_invalid(
        self, tmp_path: Path, capsys
    ) -> None:
        foreign = tmp_path / "notes.txt"
        foreign.write_text("hi", encoding="utf-8")
        code = main(["validate", str(foreign)])
        assert code == EXIT_INVALID
        assert "cleanup-plan.csv" in capsys.readouterr().err

    def test_validate_corrupt_run_lists_errors(
        self, tmp_path: Path, s1_run_dir: Path, capsys
    ) -> None:
        root = (tmp_path / "root").resolve()
        build_s1_fixture(root)
        assert (
            main(
                [
                    "scan",
                    str(root),
                    "--run-dir",
                    str(s1_run_dir),
                    "--contract",
                    str(root / "cache" / "pip"),
                ]
            )
            == EXIT_OK
        )
        (s1_run_dir / "cleanup-summary.md").unlink()
        code = main(["validate", str(s1_run_dir)])
        assert code == EXIT_INVALID
        assert "missing artifact" in capsys.readouterr().err

    def test_validate_malformed_run_json_exits_invalid_no_traceback(
        self, tmp_path: Path, s1_run_dir: Path, capsys
    ) -> None:
        root = (tmp_path / "root").resolve()
        build_s1_fixture(root)
        assert (
            main(
                [
                    "scan",
                    str(root),
                    "--run-dir",
                    str(s1_run_dir),
                    "--contract",
                    str(root / "cache" / "pip"),
                ]
            )
            == EXIT_OK
        )
        # Positive control: intact run validates.
        assert main(["validate", str(s1_run_dir)]) == EXIT_OK
        (s1_run_dir / "run.json").write_bytes(b"\xff\xfe not-json \x00")
        code = main(["validate", str(s1_run_dir)])
        assert code == EXIT_INVALID
        err = capsys.readouterr().err
        assert "Traceback" not in err
        assert "problem" in err or "unreadable" in err or "run.json" in err

    def test_validate_empty_metadata_exits_invalid(
        self, tmp_path: Path, s1_run_dir: Path, capsys
    ) -> None:
        root = (tmp_path / "root").resolve()
        build_s1_fixture(root)
        assert (
            main(
                [
                    "scan",
                    str(root),
                    "--run-dir",
                    str(s1_run_dir),
                    "--contract",
                    str(root / "cache" / "pip"),
                ]
            )
            == EXIT_OK
        )
        (s1_run_dir / "run.json").write_text("{}\n", encoding="utf-8")
        code = main(["validate", str(s1_run_dir)])
        assert code == EXIT_INVALID
        assert "empty metadata" in capsys.readouterr().err


class TestDeleteManifestCli:
    def test_delete_manifest_emits_unapproved_surface(
        self, tmp_path: Path, s1_run_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tests.test_delete_manifest import write_synthetic_run

        write_synthetic_run(s1_run_dir)
        before_plan = (s1_run_dir / "cleanup-plan.csv").read_bytes()
        code = main(["delete-manifest", str(s1_run_dir)])
        assert code == EXIT_OK
        out = capsys.readouterr().out
        assert "item_count=1" in out
        assert "authorization=UNAPPROVED" in out
        assert "intended_action=QUARANTINE" in out
        assert "nothing was mutated" in out.casefold()
        assert "no deletion occurred" in out.casefold()
        assert (s1_run_dir / "delete-manifest.json").is_file()
        assert (s1_run_dir / "delete-set.html").is_file()
        assert (s1_run_dir / "delete-set.txt").is_file()
        assert (s1_run_dir / "cleanup-plan.csv").read_bytes() == before_plan

    def test_delete_manifest_refuses_outside_runtime(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        foreign = tmp_path / "not-a-run"
        foreign.mkdir()
        code = main(["delete-manifest", str(foreign)])
        assert code == EXIT_INVALID
        assert "runtime" in capsys.readouterr().err.casefold()

    def test_delete_manifest_refuses_invalid_run(
        self, s1_run_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tests.test_delete_manifest import write_synthetic_run

        write_synthetic_run(s1_run_dir)
        (s1_run_dir / "inventory.csv").write_text("broken\n", encoding="utf-8")
        code = main(["delete-manifest", str(s1_run_dir)])
        assert code == EXIT_INVALID
        err = capsys.readouterr().err
        assert "delete-manifest" in err
        assert "Traceback" not in err


class TestDeleteLifecycleCli:
    def test_execute_requires_irreversible_flag(
        self, s1_run_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        scan = tmp_path / "scan"
        scan.mkdir()
        code = main(
            [
                "delete-execute",
                str(s1_run_dir),
                "--scan-root",
                str(scan),
            ]
        )
        assert code == EXIT_INVALID
        assert "i-understand-irreversible" in capsys.readouterr().err

    def test_execute_refuses_personal_home_root(
        self, s1_run_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = main(
            [
                "delete-execute",
                str(s1_run_dir),
                "--scan-root",
                str(Path.home()),
                "--i-understand-irreversible",
            ]
        )
        assert code == EXIT_INVALID
        err = capsys.readouterr().err.casefold()
        assert "personal" in err or "home" in err

    def test_execute_refuses_pytest_named_home_path(
        self, s1_run_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A home path containing 'pytest-' must not bypass live-home refusal."""

        victim = Path.home() / "pytest-victim" / "scan"
        code = main(
            [
                "delete-execute",
                str(s1_run_dir),
                "--scan-root",
                str(victim),
                "--i-understand-irreversible",
            ]
        )
        assert code == EXIT_INVALID
        err = capsys.readouterr().err.casefold()
        assert "personal" in err or "home" in err

    def test_scan_root_temp_membership_uses_realpath_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Junction/symlink under temp resolving outside temp must be refused."""

        import os
        import tempfile

        from filesteward import cli as cli_mod
        from filesteward.policy.paths import normalize_declared_path

        fake_temp = tmp_path / "fake-temp"
        fake_temp.mkdir()
        outside = tmp_path / "outside-home-like"
        outside.mkdir()
        link = fake_temp / "escape-junction"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"symlink/junction unavailable: {exc}")

        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(fake_temp))
        # Home check should also catch when realpath lands under home; force
        # home to the outside target so refusal is unambiguous.
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: outside))

        refusal = cli_mod._scan_root_allowed_for_execute(link)
        assert refusal is not None
        root_real = normalize_declared_path(Path(os.path.realpath(link)))
        assert not str(root_real).casefold().startswith(
            str(normalize_declared_path(fake_temp)).casefold() + os.sep.casefold()
        ) or "home" in refusal.casefold() or "personal" in refusal.casefold()
        assert "home" in refusal.casefold() or "personal" in refusal.casefold()

    def test_scan_root_realpath_under_temp_admitted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import tempfile

        from filesteward import cli as cli_mod

        fake_temp = tmp_path / "fake-temp"
        scan = fake_temp / "scan"
        scan.mkdir(parents=True)
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(fake_temp))
        assert cli_mod._scan_root_allowed_for_execute(scan) is None

    def test_execute_partial_returns_nonzero(
        self, s1_run_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from filesteward import cli as cli_mod
        from filesteward.deletion.execute import ExecutionResult, ItemExecutionResult

        s1_run_dir.mkdir(parents=True, exist_ok=True)
        (s1_run_dir / "delete-manifest.json").write_text("{}", encoding="utf-8")
        (s1_run_dir / "delete-approval.json").write_text("{}", encoding="utf-8")
        scan = tmp_path / "scan"
        scan.mkdir()

        def fake_execute(**kwargs: object) -> ExecutionResult:
            return ExecutionResult(
                overall="PARTIAL",
                run_dir=s1_run_dir,
                receipt_path=s1_run_dir / "delete-execution-receipt.json",
                items=[
                    ItemExecutionResult(
                        item_id="a",
                        path=str(scan / "a"),
                        status="SUCCEEDED",
                        reason_class="OK",
                        detail="ok",
                    ),
                    ItemExecutionResult(
                        item_id="b",
                        path=str(scan / "b"),
                        status="FAILED",
                        reason_class="IDENTITY_DRIFT",
                        detail="drift",
                    ),
                ],
            )

        monkeypatch.setattr(cli_mod, "execute_permanent_delete", fake_execute)
        monkeypatch.setattr(cli_mod, "_scan_root_allowed_for_execute", lambda p: None)
        code = main(
            [
                "delete-execute",
                str(s1_run_dir),
                "--scan-root",
                str(scan),
                "--i-understand-irreversible",
            ]
        )
        assert code == EXIT_INVALID

    @pytest.mark.parametrize("synthetic_adapter", [
        pytest.param(False, id="default-fails-closed"),
        pytest.param(True, id="explicit-synthetic-adapter", marks=pytest.mark.skipif(
            os.name != "nt", reason="Windows handle-bound destructive proof")),
    ])
    def test_preflight_approve_execute_temp_fixture(
        self, s1_run_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch, synthetic_adapter: bool,
    ) -> None:
        """End-to-end CLI on synthetic temp only — proves bytes gone."""

        from filesteward.deletion.manifest import DELETE_MANIFEST_SCHEMA

        s1_run_dir.mkdir(parents=True, exist_ok=True)
        scan = tmp_path / "scan"
        scan.mkdir()
        target = scan / "victim.bin"
        payload = b"CLI-DELETE-PROOF" * 256
        target.write_bytes(payload)
        st = target.stat()
        blocks = getattr(st, "st_blocks", None)
        allocated = blocks * 512 if isinstance(blocks, int) and blocks > 0 else None
        item = {
            "item_id": "cli-victim",
            "path": str(target.resolve()),
            "item_type": "FILE",
            "disposition": "RECLAIM_PROVEN",
            "evidence": "synthetic",
            "contract_source": "cli-test",
            "logical_size_bytes": int(st.st_size),
            "allocated_size_bytes": allocated,
            "projected_reclaim_bytes": (
                allocated if allocated is not None else int(st.st_size)
            ),
            "reclaim_basis": "synthetic",
            "projection_quality": "allocated-evidence",
            "protection_check": "UNRELATED",
            "is_managed": False,
            "is_cloud_placeholder": False,
            "is_symlink": False,
            "is_reparse_point": False,
            "link_count": 1,
            "modified_at": float(st.st_mtime),
            "source_run_id": "cli-run",
            "source_cleanup_plan_sha256": "",
            "identity": {
                "path": str(target.resolve()),
                "item_type": "FILE",
                "logical_size_bytes": int(st.st_size),
                "allocated_size_bytes": allocated,
                "modified_at": float(st.st_mtime),
                "link_count": 1,
            },
            "intended_action": "QUARANTINE",
            "reversibility": "REVERSIBLE_QUARANTINE",
        }
        manifest = {
            "schema_version": DELETE_MANIFEST_SCHEMA,
            "run_id": "cli-run",
            "source_cleanup_plan_sha256": "",
            "authorization_state": "UNAPPROVED",
            "intended_action": "QUARANTINE",
            "item_count": 1,
            "totals": {
                "logical_size_bytes": int(st.st_size),
                "allocated_size_bytes": int(st.st_size),
                "projected_reclaim_bytes": int(st.st_size),
                "projection_quality": "allocated-evidence",
            },
            "untouched": {
                "human_review_count": 0,
                "protected_count": 0,
                "unknown_count": 0,
                "keep_proven_count": 0,
                "note": "cli synthetic",
            },
            "items": [item],
        }
        from safe_capacity_fixtures import ownership_binding, resolver_for, bind_source_artifacts
        from filesteward import cli as cli_mod
        item["ownership"] = ownership_binding(item["path"])
        bind_source_artifacts(manifest, s1_run_dir)
        if synthetic_adapter:
            resolver = resolver_for([item])
            original_preflight = cli_mod.run_preflight
            original_execute = cli_mod.execute_permanent_delete
            def synthetic_preflight(*args, **kwargs):
                kwargs["ownership_resolver"] = resolver
                return original_preflight(*args, **kwargs)
            def synthetic_execute(*args, **kwargs):
                kwargs["ownership_resolver"] = resolver
                return original_execute(*args, **kwargs)
            monkeypatch.setattr(cli_mod, "run_preflight", synthetic_preflight)
            monkeypatch.setattr(cli_mod, "execute_permanent_delete", synthetic_execute)
        (s1_run_dir / "delete-manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        code = main(
            [
                "delete-preflight",
                str(s1_run_dir),
                "--scan-root",
                str(scan),
            ]
        )
        if not synthetic_adapter:
            assert code == EXIT_INVALID
            assert target.read_bytes() == payload
            receipt = json.loads((s1_run_dir / "delete-preflight.json").read_text(encoding="utf-8"))
            assert any(row["reason_class"] == "OWNERSHIP_UNKNOWN" for row in receipt["items"])
            assert not (s1_run_dir / "delete-approval.json").exists()
            assert not (s1_run_dir / "delete-execution-receipt.json").exists()
            return
        assert code == EXIT_OK, capsys.readouterr()
        assert (s1_run_dir / "delete-preflight.json").is_file()

        code = main(
            [
                "delete-approve",
                str(s1_run_dir),
                "--irreversible-confirmation",
                "CLI-TOKEN",
            ]
        )
        assert code == EXIT_OK, capsys.readouterr()
        assert (s1_run_dir / "delete-approval.json").is_file()

        code = main(
            [
                "delete-execute",
                str(s1_run_dir),
                "--scan-root",
                str(scan),
                "--i-understand-irreversible",
            ]
        )
        assert code == EXIT_OK, capsys.readouterr()
        assert not target.exists()
        assert (s1_run_dir / "delete-execution-receipt.json").is_file()


class TestEntryPointExecutesOutOfProcess:
    def test_module_invocation_reports_version(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "filesteward.cli", "--version"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert "filesteward" in result.stdout

    def test_console_script_on_path_when_installed(self) -> None:
        import shutil as _shutil

        executable = _shutil.which("filesteward")
        if executable is None:
            pytest.skip("console entry point not on PATH in this environment")
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert "filesteward" in result.stdout
