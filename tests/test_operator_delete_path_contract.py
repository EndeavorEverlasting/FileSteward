"""Regression guard for the operator-authorized delete-to-done harness contract."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_operator_delete_path_is_routed_from_agent_entry() -> None:
    agents = _read("AGENTS.md")
    assert "docs/agent/OPERATOR-DELETE-PATH.md" in agents
    assert "Continue through live deletion and runtime proof" in agents
    assert "magic phrases" in agents


def test_local_agent_protections_allow_only_gated_permanent_delete() -> None:
    protections = _read("docs/agent/LOCAL-AGENT-PROTECTIONS.md")
    assert "Permanent deletion is supported only through the gated delete lifecycle" in protections
    assert "exact manifest-enumerated" in protections
    assert "Do not substitute a generic" in protections
    assert "If `succeeded=0`, the deletion outcome is not complete." in protections


def test_delete_path_terminal_gate_requires_observed_mutation() -> None:
    contract = _read("docs/agent/OPERATOR-DELETE-PATH.md")
    assert "deleted_items > 0" in contract
    assert "execution_receipt = present" in contract
    assert "pre_free_bytes = observed" in contract
    assert "post_free_bytes = observed" in contract
    assert "If `succeeded=0`, the requested outcome is not complete." in contract
    assert "repair it, add the regression, validate it, integrate the exact fix" in contract
