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
            "review",
            "delete-manifest",
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
        target = 1_001_500  # gap 1500: covered only after plan row 2
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
        assert plan
        assert all(row["disposition"] == "RECLAIM_PROVEN" for row in plan)
        plan_paths = {row["path"] for row in plan}
        assert str(root / "cache" / "pip" / "http" / "body.whl") in plan_paths
        assert str(root / "misc" / "notes.txt") not in plan_paths

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

        # Honest stop math: baseline + cumulative >= target reached on row 2.
        metadata = json.loads(
            (s1_run_dir / "run.json").read_text(encoding="utf-8")
        )
        assert metadata["authorization_state"] == "UNAPPROVED"
        assert metadata["baseline_free_bytes"] == baseline
        assert metadata["target_free_bytes"] == target
        assert metadata["stop_row"] == 2
        cumulative = metadata["cumulative_projected_reclaim_bytes"]
        assert baseline + cumulative >= target
        assert (
            baseline
            + int(plan[0]["cumulative_projected_reclaim_bytes"])
            < target
        )

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
        assert str(root / "cache" / "hit.bin") in plan_paths

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
