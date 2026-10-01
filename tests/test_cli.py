"""L0 proof: the installed console entry point executes and never mutates."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
import tomllib

import filesteward
from filesteward.cli import EXIT_LANE_UNAVAILABLE, build_parser, main


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
        assert set(subparsers_action.choices) == {"scan", "validate", "apply"}

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
            ["scan", "C:/synthetic/root", "--run-dir", "var/runs/l0"],
            ["validate", "var/runs/l0"],
            ["apply", "var/runs/l0/manifest.json"],
            ["apply", "var/runs/l0/manifest.json", "--execute"],
        ],
        ids=["scan", "validate", "apply-dry", "apply-execute"],
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
