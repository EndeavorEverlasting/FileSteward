"""Synthetic F4 Task Scheduler adapter tests.

Installed-task path: SYNTHETIC-ONLY. No live ``schtasks`` registration was
exercised by this suite. All registration/inspect/disable/unregister coverage
uses an injectable mock runner so proofs remain valid on non-Windows hosts.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from filesteward.policy.paths import repository_root
from filesteward.profiles.schedule import (
    AUTHORIZE_DISABLE,
    AUTHORIZE_REGISTER,
    AUTHORIZE_UNREGISTER,
    OWNER_MARKER,
    ScheduleError,
    disable_schedule,
    inspect_schedule,
    main,
    parse_cadence,
    preview_task_config,
    register_schedule,
    run_once_capture,
    status_report,
    task_name_for,
    unregister_schedule,
    validate_binding,
    validate_capture_binding,
)


class RecordingRunner:
    """Injectable schtasks stand-in; records argv and never touches the OS scheduler."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.tasks: dict[str, dict[str, object]] = {}

    def __call__(
        self,
        args: list[str] | tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del input_text
        argv = tuple(args)
        self.calls.append(argv)
        if not argv:
            return subprocess.CompletedProcess(list(argv), 1, "", "empty")
        op = argv[0]
        if op == "/Query":
            return self._query(argv)
        if op == "/Create":
            return self._create(argv)
        if op == "/Change":
            return self._change(argv)
        if op == "/Delete":
            return self._delete(argv)
        return subprocess.CompletedProcess(list(argv), 1, "", f"unknown op {op}")

    def _tn(self, argv: tuple[str, ...]) -> str:
        return argv[argv.index("/TN") + 1]

    def _query(self, argv: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        name = self._tn(argv)
        task = self.tasks.get(name)
        if task is None:
            return subprocess.CompletedProcess(
                list(argv),
                1,
                "",
                "ERROR: The system cannot find the file specified.",
            )
        if "/XML" in argv:
            return subprocess.CompletedProcess(
                list(argv), 0, str(task["xml"]), ""
            )
        enabled = bool(task.get("enabled", True))
        owned = bool(task.get("owned", True))
        lines = [
            f"TaskName: {name}",
            f"Status: {'Ready' if enabled else 'Disabled'}",
            f"Scheduled Task State: {'Enabled' if enabled else 'Disabled'}",
            "Last Run Time: 10/12/2026 3:00:00 AM",
            "Last Result: 0",
            "Next Run Time: 10/13/2026 3:00:00 AM",
        ]
        if owned:
            lines.append(f"Comment: {OWNER_MARKER}")
        return subprocess.CompletedProcess(list(argv), 0, "\n".join(lines) + "\n", "")

    def _create(self, argv: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        name = self._tn(argv)
        xml_path = Path(argv[argv.index("/XML") + 1])
        xml = xml_path.read_text(encoding="utf-16")
        self.tasks[name] = {"xml": xml, "enabled": True, "owned": OWNER_MARKER in xml}
        return subprocess.CompletedProcess(list(argv), 0, "SUCCESS: The scheduled task was created.\n", "")

    def _change(self, argv: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        name = self._tn(argv)
        if name not in self.tasks:
            return subprocess.CompletedProcess(list(argv), 1, "", "missing")
        if "/DISABLE" in argv:
            self.tasks[name]["enabled"] = False
        return subprocess.CompletedProcess(list(argv), 0, "SUCCESS\n", "")

    def _delete(self, argv: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        name = self._tn(argv)
        self.tasks.pop(name, None)
        return subprocess.CompletedProcess(list(argv), 0, "SUCCESS\n", "")


def _binding(tmp_path: Path, *, cadence: str = "DAILY/03:00", host_key: str = "PTop"):
    volume = tmp_path / "vol"
    volume.mkdir()
    return validate_binding(
        host_key=host_key,
        volumes=[str(volume)],
        python_executable=sys.executable,
        checkout_path=str(repository_root()),
        cadence=cadence,
    )


def test_invalid_host_aliases_refused(tmp_path):
    volume = tmp_path / "v"
    volume.mkdir()
    for bad in ("", "../x", "a/b", "host name", ".hidden"):
        with pytest.raises(ScheduleError, match="invalid host alias"):
            validate_binding(
                host_key=bad,
                volumes=[str(volume)],
                python_executable=sys.executable,
                checkout_path=str(repository_root()),
                cadence="DAILY/03:00",
            )


def test_inaccessible_python_refused(tmp_path):
    volume = tmp_path / "v"
    volume.mkdir()
    with pytest.raises(ScheduleError, match="inaccessible Python"):
        validate_binding(
            host_key="PTop",
            volumes=[str(volume)],
            python_executable=str(tmp_path / "missing-python.exe"),
            checkout_path=str(repository_root()),
            cadence="DAILY/03:00",
        )


def test_missing_checkout_refused(tmp_path):
    volume = tmp_path / "v"
    volume.mkdir()
    with pytest.raises(ScheduleError, match="missing canonical checkout|must match"):
        validate_binding(
            host_key="PTop",
            volumes=[str(volume)],
            python_executable=sys.executable,
            checkout_path=str(tmp_path / "not-a-repo"),
            cadence="DAILY/03:00",
        )


def test_malformed_config_and_cadence_refused(tmp_path):
    volume = tmp_path / "v"
    volume.mkdir()
    with pytest.raises(ScheduleError, match="cadence required|unsupported cadence"):
        parse_cadence("")
    with pytest.raises(ScheduleError, match="unsupported cadence"):
        parse_cadence("EVERY_HOUR")
    with pytest.raises(ScheduleError, match="approved volume"):
        validate_binding(
            host_key="PTop",
            volumes=[],
            python_executable=sys.executable,
            checkout_path=str(repository_root()),
            cadence="DAILY/03:00",
        )
    missing = tmp_path / "gone"
    with pytest.raises(ScheduleError, match="inaccessible approved volume"):
        validate_binding(
            host_key="PTop",
            volumes=[str(missing)],
            python_executable=sys.executable,
            checkout_path=str(repository_root()),
            cadence="DAILY/03:00",
        )


def test_preview_never_registers(tmp_path):
    """Preview must not invoke schtasks create/query/delete."""
    runner = RecordingRunner()
    binding = _binding(tmp_path)
    preview = preview_task_config(binding)
    assert preview.registers is False
    assert preview.authorization_state == "PREVIEW_ONLY_NOT_REGISTERED"
    assert OWNER_MARKER in preview.task_xml
    assert "IgnoreNew" in preview.task_xml
    assert binding.host_key in preview.task_xml
    assert "filesteward.profiles" in " ".join(preview.capture_command)
    assert runner.calls == []
    # Even if a runner were somehow available, preview API does not accept one.
    assert "registers" in preview.__dataclass_fields__


def test_preview_cli_never_registers(tmp_path, monkeypatch):
    calls: list[tuple] = []

    def boom(*_a, **_k):
        calls.append((_a, _k))
        raise AssertionError("schtasks must not run during preview")

    monkeypatch.setattr(
        "filesteward.profiles.schedule.default_schtasks_runner",
        boom,
    )
    volume = tmp_path / "v"
    volume.mkdir()
    code = main(
        [
            "preview",
            "--host-key",
            "PTop",
            "--volume",
            str(volume),
            "--python",
            sys.executable,
            "--cadence",
            "WEEKLY/MON/04:30",
        ]
    )
    assert code == 0
    assert calls == []


def test_register_requires_authorize_and_refuses_silent_default(tmp_path):
    runner = RecordingRunner()
    binding = _binding(tmp_path)
    with pytest.raises(ScheduleError, match="registration refused"):
        register_schedule(binding, authorize="please", runner=runner)
    assert runner.calls == []


def test_register_disable_unregister_happy_path_synthetic(tmp_path):
    runner = RecordingRunner()
    binding = _binding(tmp_path)

    def xml_writer(content: str, task_name: str) -> Path:
        path = tmp_path / f"{task_name}.xml"
        path.write_text(content, encoding="utf-16")
        return path

    state = register_schedule(
        binding,
        authorize=AUTHORIZE_REGISTER,
        runner=runner,
        xml_writer=xml_writer,
    )
    assert state.registered is True
    assert state.file_steward_owned is True
    assert any(c[0] == "/Create" for c in runner.calls)

    # Duplicate FileSteward name: no silent replace.
    with pytest.raises(ScheduleError, match="already registered|no silent replace"):
        register_schedule(
            binding,
            authorize=AUTHORIZE_REGISTER,
            runner=runner,
            xml_writer=xml_writer,
        )

    disabled = disable_schedule(
        binding.host_key,
        authorize=AUTHORIZE_DISABLE,
        runner=runner,
    )
    assert disabled.enabled is False

    gone = unregister_schedule(
        binding.host_key,
        authorize=AUTHORIZE_UNREGISTER,
        runner=runner,
    )
    assert gone.registered is False


def test_foreign_task_collision_refused(tmp_path):
    runner = RecordingRunner()
    name = task_name_for("PTop")
    runner.tasks[name] = {
        "xml": "<Task><RegistrationInfo><Description>OtherApp backup</Description></RegistrationInfo></Task>",
        "enabled": True,
        "owned": False,
    }
    binding = _binding(tmp_path)
    with pytest.raises(ScheduleError, match="FOREIGN_TASK_COLLISION"):
        register_schedule(
            binding,
            authorize=AUTHORIZE_REGISTER,
            runner=runner,
            xml_writer=lambda c, n: tmp_path / "x.xml",
        )


def test_incorrect_task_owner_disable_unregister_refused(tmp_path):
    runner = RecordingRunner()
    name = task_name_for("PTop")
    runner.tasks[name] = {
        "xml": "<Task>foreign</Task>",
        "enabled": True,
        "owned": False,
    }
    with pytest.raises(ScheduleError, match="incorrect task owner"):
        disable_schedule("PTop", authorize=AUTHORIZE_DISABLE, runner=runner)
    with pytest.raises(ScheduleError, match="incorrect task owner"):
        unregister_schedule("PTop", authorize=AUTHORIZE_UNREGISTER, runner=runner)


def test_disabled_task_inspectable(tmp_path):
    del tmp_path
    runner = RecordingRunner()
    name = task_name_for("PTop")
    runner.tasks[name] = {
        "xml": f"<Task>{OWNER_MARKER}</Task>",
        "enabled": False,
        "owned": True,
    }
    state = inspect_schedule("PTop", runner=runner)
    assert state.registered is True
    assert state.enabled is False
    assert state.last_run_time is not None
    assert state.next_run_time is not None


def test_unsupported_os_live_schtasks_refused(monkeypatch):
    monkeypatch.setattr(
        "filesteward.profiles.schedule.platform.system",
        lambda: "Linux",
    )
    with pytest.raises(ScheduleError, match="unsupported OS"):
        inspect_schedule("PTop", allow_live_schtasks=True)


def test_live_schtasks_refused_without_flag():
    with pytest.raises(ScheduleError, match="live schtasks refused"):
        inspect_schedule("PTop", allow_live_schtasks=False)


def test_failed_capture_command_nonzero(tmp_path):
    binding = validate_capture_binding(
        host_key="PTop",
        volumes=[str(tmp_path)],
        python_executable=sys.executable,
        checkout_path=str(repository_root()),
    )

    def failing(args):
        return subprocess.CompletedProcess(
            list(args),
            2,
            "",
            "profile refused: CAPTURE_BUSY",
        )

    report = run_once_capture(binding, capture_runner=failing)
    assert report.exit_code == 2
    assert report.profile_artifact_path is None
    assert "CAPTURE_BUSY" in report.stderr


def test_overlapping_executions_policy_in_preview(tmp_path):
    preview = preview_task_config(_binding(tmp_path))
    assert "<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>" in preview.task_xml
    assert "<Count>0</Count>" in preview.task_xml


def test_run_once_success_parses_artifact(tmp_path):
    binding = validate_capture_binding(
        host_key="SynthHost",
        volumes=[str(tmp_path)],
        python_executable=sys.executable,
        checkout_path=str(repository_root()),
    )
    artifact = tmp_path / "snap.json"

    def ok(args):
        assert args[1:4] == ("-m", "filesteward.profiles", "capture")
        return subprocess.CompletedProcess(
            list(args),
            0,
            f"PROFILE_OBSERVED_ONLY: {artifact}\n",
            "",
        )

    report = run_once_capture(binding, capture_runner=ok)
    assert report.exit_code == 0
    assert report.profile_artifact_path == str(artifact)


def test_status_report_combines_registration(tmp_path):
    del tmp_path
    runner = RecordingRunner()
    name = task_name_for("PTop")
    runner.tasks[name] = {
        "xml": f"<Task>{OWNER_MARKER}</Task>",
        "enabled": True,
        "owned": True,
    }
    report = status_report("PTop", runner=runner, profiles_root=Path("/no/such/profiles"))
    assert report["registration"]["registered"] is True
    assert report["authorization_state"] == "OBSERVATION_ONLY"
    assert report["profile_provides_delete_authority"] is False


def test_stable_task_name_pattern():
    assert task_name_for("PTop") == "FileSteward-WorkstationProfile-PTop"
    with pytest.raises(ScheduleError):
        task_name_for("../evil")
