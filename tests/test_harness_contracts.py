from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_harness_contracts", ROOT / "scripts" / "validate_harness_contracts.py"
)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def test_p01_harness_contracts_validate() -> None:
    assert module.validate(ROOT) == []


def test_scheduler_never_authorizes_permanent_delete() -> None:
    schedule = module._load(ROOT / "harness" / "contracts" / "housekeeping-schedule.v1.json")
    assert "PERMANENT_DELETE" not in schedule["actions"]["allowed"]
    assert "PERMANENT_DELETE" in schedule["actions"]["forbidden"]


def test_dev_profile_is_on_but_product_profile_is_opt_in() -> None:
    schedule = module._load(ROOT / "harness" / "contracts" / "housekeeping-schedule.v1.json")
    assert schedule["profiles"]["development"]["enabled_by_default"] is True
    assert schedule["profiles"]["product"]["enabled_by_default"] is False
