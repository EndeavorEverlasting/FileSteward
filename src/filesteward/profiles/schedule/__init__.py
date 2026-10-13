"""Opt-in Windows Task Scheduler adapter for read-only workstation profile capture.

Synthetic-only by default: injectable schtasks runners exercise all paths on any
OS. Live schtasks is used only when platform is Windows AND the caller passes
``allow_live_schtasks=True`` (CLI: ``--live-schtasks``). Installed-task
registration was NOT live-exercised by the F4 synthetic suite; proof is
preview/register/disable/unregister against a mock runner only.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from filesteward.policy.paths import repository_root, runtime_root
from filesteward.profiles import KEY as HOST_KEY_RE
from filesteward.profiles import ProfileError, load_latest

SCHEMA = "filesteward.workstation-profile-schedule/v1"
OWNER_MARKER = "FileSteward.workstation-performance-profile/v1"
TASK_NAME_PREFIX = "FileSteward-WorkstationProfile-"
AUTHORIZE_REGISTER = "OPERATOR_OPT_IN_REGISTER_PROFILE_SCHEDULE"
AUTHORIZE_DISABLE = "OPERATOR_OPT_IN_DISABLE_PROFILE_SCHEDULE"
AUTHORIZE_UNREGISTER = "OPERATOR_OPT_IN_UNREGISTER_PROFILE_SCHEDULE"

# DAILY/HH:MM or WEEKLY/DAY/HH:MM — no silent default cadence.
_CADENCE_DAILY = re.compile(r"^DAILY/([01]\d|2[0-3]):([0-5]\d)\Z")
_CADENCE_WEEKLY = re.compile(
    r"^WEEKLY/(MON|TUE|WED|THU|FRI|SAT|SUN)/([01]\d|2[0-3]):([0-5]\d)\Z"
)
_DAY_TO_SCHTASKS = {
    "MON": "MON",
    "TUE": "TUE",
    "WED": "WED",
    "THU": "THU",
    "FRI": "FRI",
    "SAT": "SAT",
    "SUN": "SUN",
}


class ScheduleError(ValueError):
    """Fail-closed schedule/config/registration refusal."""


class SchtasksRunner(Protocol):
    def __call__(
        self,
        args: Sequence[str],
        *,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        ...


CaptureRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class ScheduleBinding:
    """Host-bound schedule inputs; never invents cadence or volumes."""

    host_key: str
    volumes: tuple[str, ...]
    python_executable: str
    checkout_path: str
    cadence: str

    @property
    def task_name(self) -> str:
        return task_name_for(self.host_key)


@dataclass(frozen=True)
class TaskPreview:
    schema_version: str
    task_name: str
    host_key: str
    cadence: str
    python_executable: str
    checkout_path: str
    volumes: tuple[str, ...]
    capture_command: tuple[str, ...]
    working_directory: str
    task_xml: str
    schtasks_create_args: tuple[str, ...]
    owner_marker: str
    authorization_state: str
    registers: bool


@dataclass(frozen=True)
class RegistrationState:
    task_name: str
    registered: bool
    file_steward_owned: bool
    enabled: bool | None
    status_text: str | None
    last_run_time: str | None
    last_result: str | None
    next_run_time: str | None
    foreign_collision: bool
    detail: str


@dataclass(frozen=True)
class CaptureRunReport:
    exit_code: int
    stdout: str
    stderr: str
    profile_artifact_path: str | None
    latest_snapshot_id: str | None


def task_name_for(host_key: str) -> str:
    alias = _require_host_key(host_key)
    return TASK_NAME_PREFIX + alias


def parse_cadence(cadence: str) -> dict[str, str]:
    text = (cadence or "").strip()
    if not text:
        raise ScheduleError("cadence required; no default schedule is invented")
    daily = _CADENCE_DAILY.fullmatch(text)
    if daily:
        return {
            "kind": "DAILY",
            "hour": daily.group(1),
            "minute": daily.group(2),
            "schtasks_sc": "DAILY",
            "schtasks_st": f"{daily.group(1)}:{daily.group(2)}",
            "schtasks_d": "",
        }
    weekly = _CADENCE_WEEKLY.fullmatch(text)
    if weekly:
        day = weekly.group(1)
        return {
            "kind": "WEEKLY",
            "day": day,
            "hour": weekly.group(2),
            "minute": weekly.group(3),
            "schtasks_sc": "WEEKLY",
            "schtasks_st": f"{weekly.group(2)}:{weekly.group(3)}",
            "schtasks_d": _DAY_TO_SCHTASKS[day],
        }
    raise ScheduleError(
        "unsupported cadence; use DAILY/HH:MM or WEEKLY/DAY/HH:MM "
        "(DAY=MON..SUN); never omit cadence"
    )


def _require_host_key(host_key: str) -> str:
    if not HOST_KEY_RE.fullmatch(host_key or ""):
        raise ScheduleError("invalid host alias; use 1-48 letters/digits/_/-")
    return host_key


def _normalize_volume(volume: str) -> str:
    root = os.path.abspath(os.path.expanduser(volume))
    if not os.path.isdir(root):
        raise ScheduleError("inaccessible approved volume root: " + volume)
    return root


def _resolve_checkout(checkout_path: str | None) -> Path:
    checkout = Path(checkout_path) if checkout_path else repository_root()
    try:
        checkout = checkout.resolve()
    except OSError as exc:
        raise ScheduleError("checkout path unresolvable") from exc
    marker = checkout / "pyproject.toml"
    if not marker.is_file():
        raise ScheduleError("missing canonical checkout (pyproject.toml not found)")
    try:
        expected = repository_root().resolve()
    except RuntimeError as exc:
        raise ScheduleError("canonical checkout unavailable") from exc
    if checkout != expected:
        raise ScheduleError(
            "checkout_path must match filesteward.policy.paths.repository_root"
        )
    return checkout


def _resolve_python(python_executable: str) -> Path:
    py = Path(python_executable)
    if not py.is_file():
        raise ScheduleError("inaccessible Python executable: " + python_executable)
    name = py.name.casefold()
    if os.name == "nt" and not name.endswith((".exe", ".cmd", ".bat")):
        raise ScheduleError("Python executable must be a runnable Windows binary")
    return py.resolve()


def _resolve_volumes(volumes: Sequence[str]) -> tuple[str, ...]:
    if not volumes:
        raise ScheduleError("declare at least one approved volume root")
    if len(volumes) > 32:
        raise ScheduleError("too many volume roots (max 32)")
    resolved_volumes: list[str] = []
    seen: set[str] = set()
    for volume in volumes:
        root = _normalize_volume(volume)
        key = os.path.normcase(root).casefold()
        if key in seen:
            raise ScheduleError("duplicate approved volume root")
        seen.add(key)
        resolved_volumes.append(root)
    return tuple(resolved_volumes)


def validate_binding(
    *,
    host_key: str,
    volumes: Sequence[str],
    python_executable: str,
    checkout_path: str | None = None,
    cadence: str,
) -> ScheduleBinding:
    alias = _require_host_key(host_key)
    parse_cadence(cadence)  # validated; stored as original string
    return ScheduleBinding(
        host_key=alias,
        volumes=_resolve_volumes(volumes),
        python_executable=str(_resolve_python(python_executable)),
        checkout_path=str(_resolve_checkout(checkout_path)),
        cadence=cadence.strip(),
    )


def validate_capture_binding(
    *,
    host_key: str,
    volumes: Sequence[str],
    python_executable: str,
    checkout_path: str | None = None,
) -> ScheduleBinding:
    """Binding for one-shot capture; cadence is intentionally unset (not scheduled)."""
    alias = _require_host_key(host_key)
    return ScheduleBinding(
        host_key=alias,
        volumes=_resolve_volumes(volumes),
        python_executable=str(_resolve_python(python_executable)),
        checkout_path=str(_resolve_checkout(checkout_path)),
        cadence="",
    )


def build_capture_command(binding: ScheduleBinding) -> tuple[str, ...]:
    args = [
        binding.python_executable,
        "-m",
        "filesteward.profiles",
        "capture",
        "--host-key",
        binding.host_key,
    ]
    for volume in binding.volumes:
        args.extend(["--volume", volume])
    return tuple(args)


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def render_task_xml(binding: ScheduleBinding) -> str:
    """Render a complete Task Scheduler 1.2 XML document (preview/register)."""
    if not binding.cadence:
        raise ScheduleError("cadence required to render task XML")
    cadence = parse_cadence(binding.cadence)
    command = build_capture_command(binding)
    exe = _escape_xml(command[0])
    args = _escape_xml(subprocess.list2cmdline(list(command[1:])))
    workdir = _escape_xml(binding.checkout_path)
    start = f"2026-01-01T{cadence['hour']}:{cadence['minute']}:00"
    if cadence["kind"] == "DAILY":
        calendar = (
            "<CalendarTrigger>\n"
            f"      <StartBoundary>{start}</StartBoundary>\n"
            "      <Enabled>true</Enabled>\n"
            "      <ScheduleByDay>\n"
            "        <DaysInterval>1</DaysInterval>\n"
            "      </ScheduleByDay>\n"
            "    </CalendarTrigger>"
        )
    else:
        day_elems = {
            "MON": "Monday",
            "TUE": "Tuesday",
            "WED": "Wednesday",
            "THU": "Thursday",
            "FRI": "Friday",
            "SAT": "Saturday",
            "SUN": "Sunday",
        }
        day = cadence["day"]
        calendar = (
            "<CalendarTrigger>\n"
            f"      <StartBoundary>{start}</StartBoundary>\n"
            "      <Enabled>true</Enabled>\n"
            "      <ScheduleByWeek>\n"
            "        <WeeksInterval>1</WeeksInterval>\n"
            "        <DaysOfWeek>\n"
            f"          <{day_elems[day]}/>\n"
            "        </DaysOfWeek>\n"
            "      </ScheduleByWeek>\n"
            "    </CalendarTrigger>"
        )

    description = (
        f"{OWNER_MARKER}; host_key={binding.host_key}; "
        f"cadence={binding.cadence}; observation-only; no delete authority"
    )
    return (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
        "  <RegistrationInfo>\n"
        f"    <Description>{_escape_xml(description)}</Description>\n"
        f"    <URI>\\{binding.task_name}</URI>\n"
        "  </RegistrationInfo>\n"
        "  <Triggers>\n"
        f"    {calendar}\n"
        "  </Triggers>\n"
        "  <Principals>\n"
        "    <Principal id=\"Author\">\n"
        "      <LogonType>InteractiveToken</LogonType>\n"
        "      <RunLevel>LeastPrivilege</RunLevel>\n"
        "    </Principal>\n"
        "  </Principals>\n"
        "  <Settings>\n"
        "    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n"
        "    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n"
        "    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n"
        "    <AllowHardTerminate>true</AllowHardTerminate>\n"
        "    <StartWhenAvailable>false</StartWhenAvailable>\n"
        "    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>\n"
        "    <AllowStartOnDemand>true</AllowStartOnDemand>\n"
        "    <Enabled>true</Enabled>\n"
        "    <Hidden>false</Hidden>\n"
        "    <RunOnlyIfIdle>false</RunOnlyIfIdle>\n"
        "    <WakeToRun>false</WakeToRun>\n"
        "    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>\n"
        "    <Priority>7</Priority>\n"
        "    <RestartOnFailure>\n"
        "      <Interval>PT0S</Interval>\n"
        "      <Count>0</Count>\n"
        "    </RestartOnFailure>\n"
        "  </Settings>\n"
        "  <Actions Context=\"Author\">\n"
        "    <Exec>\n"
        f"      <Command>{exe}</Command>\n"
        f"      <Arguments>{args}</Arguments>\n"
        f"      <WorkingDirectory>{workdir}</WorkingDirectory>\n"
        "    </Exec>\n"
        "  </Actions>\n"
        "</Task>\n"
    )


def preview_task_config(binding: ScheduleBinding) -> TaskPreview:
    """Generate a complete safe task config WITHOUT registering."""
    cadence = parse_cadence(binding.cadence)
    xml_text = render_task_xml(binding)
    command = build_capture_command(binding)
    # Preview documents the eventual create argv shape only; it never invokes schtasks.
    create_args = (
        "/Create",
        "/TN",
        binding.task_name,
        "/XML",
        "<operator-supplied-temp-xml>",
        "/RU",
        os.environ.get("USERNAME", "InteractiveUser"),
    )
    return TaskPreview(
        schema_version=SCHEMA,
        task_name=binding.task_name,
        host_key=binding.host_key,
        cadence=binding.cadence,
        python_executable=binding.python_executable,
        checkout_path=binding.checkout_path,
        volumes=binding.volumes,
        capture_command=command,
        working_directory=binding.checkout_path,
        task_xml=xml_text,
        schtasks_create_args=create_args,
        owner_marker=OWNER_MARKER,
        authorization_state="PREVIEW_ONLY_NOT_REGISTERED",
        registers=False,
    )


def default_schtasks_runner(
    args: Sequence[str],
    *,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Real schtasks runner. Callers must gate with allow_live_schtasks on Windows."""
    return subprocess.run(
        ["schtasks", *args],
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


def _require_live_windows(allow_live_schtasks: bool) -> None:
    if not allow_live_schtasks:
        raise ScheduleError(
            "live schtasks refused; pass allow_live_schtasks=True / --live-schtasks "
            "only on an explicit operator opt-in path"
        )
    if platform.system().casefold() != "windows":
        raise ScheduleError("unsupported OS for live Task Scheduler integration")


def _resolve_runner(
    runner: SchtasksRunner | None,
    *,
    allow_live_schtasks: bool,
) -> SchtasksRunner:
    if runner is not None:
        return runner
    _require_live_windows(allow_live_schtasks)
    return default_schtasks_runner


def _query_task_xml(
    task_name: str,
    runner: SchtasksRunner,
) -> tuple[bool, str, str]:
    result = runner(["/Query", "/TN", task_name, "/XML", "/V"])
    if result.returncode != 0:
        stderr = (result.stderr or "") + (result.stdout or "")
        if "ERROR: The system cannot find the file specified" in stderr or (
            "cannot find" in stderr.casefold()
        ):
            return False, "", stderr
        # Some hosts return non-zero with empty XML for missing tasks.
        if "ERROR:" in stderr.upper() and "not find" in stderr.casefold():
            return False, "", stderr
        return False, "", stderr
    return True, result.stdout or "", result.stderr or ""


def _is_file_steward_owned_xml(xml_text: str) -> bool:
    return OWNER_MARKER in xml_text


def _parse_query_table(stdout: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in stdout.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip().casefold()] = value.strip()
    return fields


def inspect_schedule(
    host_key: str,
    *,
    runner: SchtasksRunner | None = None,
    allow_live_schtasks: bool = False,
) -> RegistrationState:
    alias = _require_host_key(host_key)
    name = task_name_for(alias)
    active = _resolve_runner(runner, allow_live_schtasks=allow_live_schtasks)
    found, xml_text, err = _query_task_xml(name, active)
    if not found:
        # Distinguish missing vs query failure when possible.
        if err and "ERROR" in err.upper() and "not find" not in err.casefold() and (
            "cannot find" not in err.casefold()
        ):
            # Try a non-XML query for richer status when XML path failed oddly.
            table = active(["/Query", "/TN", name, "/V", "/FO", "LIST"])
            if table.returncode != 0:
                return RegistrationState(
                    task_name=name,
                    registered=False,
                    file_steward_owned=False,
                    enabled=None,
                    status_text=None,
                    last_run_time=None,
                    last_result=None,
                    next_run_time=None,
                    foreign_collision=False,
                    detail="not registered: " + (err or table.stderr or "missing"),
                )
            found = True
            xml_text = ""
            fields = _parse_query_table(table.stdout or "")
        else:
            return RegistrationState(
                task_name=name,
                registered=False,
                file_steward_owned=False,
                enabled=None,
                status_text=None,
                last_run_time=None,
                last_result=None,
                next_run_time=None,
                foreign_collision=False,
                detail="not registered",
            )
    else:
        fields = {}

    owned = _is_file_steward_owned_xml(xml_text) if xml_text else False
    if not fields:
        table = active(["/Query", "/TN", name, "/V", "/FO", "LIST"])
        if table.returncode == 0:
            fields = _parse_query_table(table.stdout or "")
            if not owned:
                # Ownership may appear in Task To Run / Comment fields.
                blob = (table.stdout or "") + xml_text
                owned = OWNER_MARKER in blob

    enabled: bool | None = None
    status = fields.get("status")
    scheduled = fields.get("scheduled task state")
    if scheduled:
        enabled = scheduled.casefold() not in {"disabled"}
    elif status:
        enabled = status.casefold() not in {"disabled"}

    foreign = found and not owned
    return RegistrationState(
        task_name=name,
        registered=True,
        file_steward_owned=owned,
        enabled=enabled,
        status_text=status or scheduled,
        last_run_time=fields.get("last run time"),
        last_result=fields.get("last result"),
        next_run_time=fields.get("next run time"),
        foreign_collision=foreign,
        detail="foreign task occupies FileSteward name" if foreign else "registered",
    )


def _write_receipt(kind: str, payload: Mapping[str, Any]) -> Path:
    root = runtime_root() / "profiles" / "schedule"
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = root / f"{kind}-{stamp}.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def register_schedule(
    binding: ScheduleBinding,
    *,
    authorize: str,
    runner: SchtasksRunner | None = None,
    allow_live_schtasks: bool = False,
    xml_writer: Callable[[str, str], Path] | None = None,
) -> RegistrationState:
    """Register recurring task ONLY with explicit cadence + authorization token."""
    if authorize != AUTHORIZE_REGISTER:
        raise ScheduleError(
            "registration refused; pass authorize="
            + AUTHORIZE_REGISTER
            + " after operator opt-in"
        )
    parse_cadence(binding.cadence)  # re-validate; no default
    active = _resolve_runner(runner, allow_live_schtasks=allow_live_schtasks)
    existing = inspect_schedule(
        binding.host_key,
        runner=active,
        allow_live_schtasks=False if runner is not None else allow_live_schtasks,
    )
    if existing.registered:
        if existing.foreign_collision or not existing.file_steward_owned:
            raise ScheduleError(
                "FOREIGN_TASK_COLLISION: refusing to replace non-FileSteward task "
                + existing.task_name
            )
        raise ScheduleError(
            "task already registered under FileSteward name; "
            "unregister explicitly before re-register (no silent replace)"
        )

    preview = preview_task_config(binding)
    xml_text = preview.task_xml

    def _default_xml_writer(content: str, task_name: str) -> Path:
        directory = runtime_root() / "profiles" / "schedule"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{task_name}.task.xml"
        path.write_text(content, encoding="utf-16")
        return path

    writer = xml_writer or _default_xml_writer
    xml_path = writer(xml_text, binding.task_name)
    result = active(
        [
            "/Create",
            "/TN",
            binding.task_name,
            "/XML",
            str(xml_path),
        ]
    )
    receipt = {
        "schema_version": SCHEMA,
        "action": "register",
        "task_name": binding.task_name,
        "host_key": binding.host_key,
        "cadence": binding.cadence,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "xml_path": str(xml_path),
        "authorization": AUTHORIZE_REGISTER,
    }
    try:
        _write_receipt("register", receipt)
    except OSError:
        pass
    if result.returncode != 0:
        raise ScheduleError(
            "schtasks create failed: "
            + ((result.stderr or result.stdout or "").strip() or str(result.returncode))
        )
    return inspect_schedule(
        binding.host_key,
        runner=active,
        allow_live_schtasks=False if runner is not None else allow_live_schtasks,
    )


def disable_schedule(
    host_key: str,
    *,
    authorize: str,
    runner: SchtasksRunner | None = None,
    allow_live_schtasks: bool = False,
) -> RegistrationState:
    if authorize != AUTHORIZE_DISABLE:
        raise ScheduleError(
            "disable refused; pass authorize=" + AUTHORIZE_DISABLE
        )
    alias = _require_host_key(host_key)
    active = _resolve_runner(runner, allow_live_schtasks=allow_live_schtasks)
    state = inspect_schedule(
        alias,
        runner=active,
        allow_live_schtasks=False if runner is not None else allow_live_schtasks,
    )
    if not state.registered:
        raise ScheduleError("no FileSteward schedule registered for host")
    if not state.file_steward_owned:
        raise ScheduleError(
            "incorrect task owner; refusing to disable foreign task "
            + state.task_name
        )
    result = active(["/Change", "/TN", state.task_name, "/DISABLE"])
    if result.returncode != 0:
        raise ScheduleError(
            "schtasks disable failed: "
            + ((result.stderr or result.stdout or "").strip() or str(result.returncode))
        )
    return inspect_schedule(
        alias,
        runner=active,
        allow_live_schtasks=False if runner is not None else allow_live_schtasks,
    )


def unregister_schedule(
    host_key: str,
    *,
    authorize: str,
    runner: SchtasksRunner | None = None,
    allow_live_schtasks: bool = False,
) -> RegistrationState:
    if authorize != AUTHORIZE_UNREGISTER:
        raise ScheduleError(
            "unregister refused; pass authorize=" + AUTHORIZE_UNREGISTER
        )
    alias = _require_host_key(host_key)
    active = _resolve_runner(runner, allow_live_schtasks=allow_live_schtasks)
    state = inspect_schedule(
        alias,
        runner=active,
        allow_live_schtasks=False if runner is not None else allow_live_schtasks,
    )
    if not state.registered:
        raise ScheduleError("no FileSteward schedule registered for host")
    if not state.file_steward_owned:
        raise ScheduleError(
            "incorrect task owner; refusing to unregister foreign task "
            + state.task_name
        )
    result = active(["/Delete", "/TN", state.task_name, "/F"])
    if result.returncode != 0:
        raise ScheduleError(
            "schtasks delete failed: "
            + ((result.stderr or result.stdout or "").strip() or str(result.returncode))
        )
    return inspect_schedule(
        alias,
        runner=active,
        allow_live_schtasks=False if runner is not None else allow_live_schtasks,
    )


def _default_capture_runner(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        check=False,
        cwd=str(repository_root()),
    )


def run_once_capture(
    binding: ScheduleBinding,
    *,
    capture_runner: CaptureRunner | None = None,
) -> CaptureRunReport:
    """Run one read-only capture via ``python -m filesteward.profiles capture``."""
    command = build_capture_command(binding)
    runner = capture_runner or _default_capture_runner
    result = runner(command)
    artifact: str | None = None
    stdout = result.stdout or ""
    for line in stdout.splitlines():
        if line.startswith("PROFILE_OBSERVED_ONLY:"):
            artifact = line.split(":", 1)[1].strip()
            break
    latest_id: str | None = None
    if result.returncode == 0:
        try:
            latest = load_latest(binding.host_key)
            latest_id = str(latest.get("snapshot_id") or "") or None
        except (ProfileError, OSError, ValueError):
            latest_id = None
    return CaptureRunReport(
        exit_code=result.returncode,
        stdout=stdout,
        stderr=result.stderr or "",
        profile_artifact_path=artifact,
        latest_snapshot_id=latest_id,
    )


def status_report(
    host_key: str,
    *,
    runner: SchtasksRunner | None = None,
    allow_live_schtasks: bool = False,
    profiles_root: Path | None = None,
) -> dict[str, Any]:
    """Combine scheduler registration state with latest profile artifact when present."""
    state = inspect_schedule(
        host_key,
        runner=runner,
        allow_live_schtasks=allow_live_schtasks,
    )
    artifact_path: str | None = None
    snapshot_id: str | None = None
    try:
        latest = load_latest(host_key, profiles_root=profiles_root)
        snapshot_id = str(latest.get("snapshot_id") or "") or None
        # latest.json path is not returned by load_latest; leave null unless known.
    except (ProfileError, OSError, ValueError):
        pass
    return {
        "schema_version": SCHEMA,
        "registration": asdict(state),
        "last_profile_snapshot_id": snapshot_id,
        "profile_artifact_path": artifact_path,
        "authorization_state": "OBSERVATION_ONLY",
        "profile_provides_delete_authority": False,
    }


def _binding_from_args(args: argparse.Namespace) -> ScheduleBinding:
    checkout = getattr(args, "checkout", None)
    return validate_binding(
        host_key=args.host_key,
        volumes=list(args.volume or []),
        python_executable=args.python or sys.executable,
        checkout_path=checkout,
        cadence=args.cadence,
    )


def _capture_binding_from_args(args: argparse.Namespace) -> ScheduleBinding:
    return validate_capture_binding(
        host_key=args.host_key,
        volumes=list(args.volume or []),
        python_executable=args.python or sys.executable,
        checkout_path=getattr(args, "checkout", None),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Opt-in Windows Task Scheduler adapter for read-only profile capture"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def add_binding_args(p: argparse.ArgumentParser, *, cadence_required: bool) -> None:
        p.add_argument("--host-key", required=True)
        p.add_argument("--volume", action="append", required=True)
        p.add_argument(
            "--python",
            default=sys.executable,
            help="Absolute path to the known Python executable",
        )
        p.add_argument(
            "--checkout",
            default=None,
            help="Canonical checkout path (must match repository_root)",
        )
        p.add_argument(
            "--cadence",
            required=cadence_required,
            help="DAILY/HH:MM or WEEKLY/DAY/HH:MM (required; no default)",
        )

    preview_p = commands.add_parser("preview", help="Generate task config without registering")
    add_binding_args(preview_p, cadence_required=True)

    inspect_p = commands.add_parser("inspect", help="Inspect registration state")
    inspect_p.add_argument("--host-key", required=True)
    inspect_p.add_argument("--live-schtasks", action="store_true")

    register_p = commands.add_parser("register", help="Register only with explicit authorize")
    add_binding_args(register_p, cadence_required=True)
    register_p.add_argument("--authorize", required=True)
    register_p.add_argument("--live-schtasks", action="store_true")

    once_p = commands.add_parser("run-once", help="Run one read-only capture now")
    once_p.add_argument("--host-key", required=True)
    once_p.add_argument("--volume", action="append", required=True)
    once_p.add_argument("--python", default=sys.executable)
    once_p.add_argument("--checkout", default=None)

    status_p = commands.add_parser("status", help="Registration + last capture summary")
    status_p.add_argument("--host-key", required=True)
    status_p.add_argument("--live-schtasks", action="store_true")

    disable_p = commands.add_parser("disable", help="Disable exact FileSteward-owned task")
    disable_p.add_argument("--host-key", required=True)
    disable_p.add_argument("--authorize", required=True)
    disable_p.add_argument("--live-schtasks", action="store_true")

    unregister_p = commands.add_parser(
        "unregister", help="Unregister exact FileSteward-owned task"
    )
    unregister_p.add_argument("--host-key", required=True)
    unregister_p.add_argument("--authorize", required=True)
    unregister_p.add_argument("--live-schtasks", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "preview":
            binding = _binding_from_args(args)
            preview = preview_task_config(binding)
            payload = asdict(preview)
            print(json.dumps(payload, indent=2))
            assert preview.registers is False
        elif args.command == "inspect":
            state = inspect_schedule(
                args.host_key,
                allow_live_schtasks=bool(args.live_schtasks),
            )
            print(json.dumps(asdict(state), indent=2))
        elif args.command == "register":
            binding = _binding_from_args(args)
            state = register_schedule(
                binding,
                authorize=args.authorize,
                allow_live_schtasks=bool(args.live_schtasks),
            )
            print(json.dumps(asdict(state), indent=2))
        elif args.command == "run-once":
            binding = _capture_binding_from_args(args)
            report = run_once_capture(binding)
            print(json.dumps(asdict(report), indent=2))
            return 0 if report.exit_code == 0 else 2
        elif args.command == "status":
            report = status_report(
                args.host_key,
                allow_live_schtasks=bool(args.live_schtasks),
            )
            print(json.dumps(report, indent=2))
        elif args.command == "disable":
            state = disable_schedule(
                args.host_key,
                authorize=args.authorize,
                allow_live_schtasks=bool(args.live_schtasks),
            )
            print(json.dumps(asdict(state), indent=2))
        elif args.command == "unregister":
            state = unregister_schedule(
                args.host_key,
                authorize=args.authorize,
                allow_live_schtasks=bool(args.live_schtasks),
            )
            print(json.dumps(asdict(state), indent=2))
        else:
            parser.error("unknown command")
    except (ScheduleError, ProfileError, OSError, ValueError, TypeError, RuntimeError) as exc:
        print("schedule refused: " + str(exc), file=sys.stderr)
        return 2
    return 0
