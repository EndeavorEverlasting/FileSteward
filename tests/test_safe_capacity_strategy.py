from dataclasses import replace

import pytest

from filesteward.models import CleanupDisposition as D
from filesteward.ownership.actions import ActionKind as A, ActionPlan
from filesteward.ownership.capacity import CapacityCandidate, plan_capacity_strategy


def candidate(name, amount=50, action=A.RAW_DELETE_REGENERABLE_ARTIFACT,
              disposition=D.RECLAIM_PROVEN, path=None, **kwargs):
    plan = ActionPlan(path or rf"C:\synthetic\{name}", disposition, (action,), (),
                      ("owner",), ("REGENERABLE_ARTIFACT",), "revision", "a" * 64, "b" * 64)
    return CapacityCandidate(name, plan, action, amount, "allocated estimate", **kwargs)


@pytest.mark.parametrize("free,status", [(0, "CRITICAL"), (99, "CRITICAL"), (100, "LOW"),
                                         (199, "LOW"), (200, "HEALTHY"), (201, "HEALTHY")])
def test_capacity_thresholds_are_priority_only(free, status):
    result = plan_capacity_strategy([candidate("legal")], total_bytes=1000, free_bytes=free)
    assert result.status == status
    assert result.target_free_bytes == 200
    if status == "HEALTHY":
        assert result.candidates == ()


@pytest.mark.parametrize("disposition", [D.UNKNOWN, D.PROTECTED, D.KEEP_PROVEN, D.HUMAN_REVIEW])
def test_critical_capacity_cannot_promote_raw_delete(disposition):
    result = plan_capacity_strategy([candidate("illegal", 999, disposition=disposition)],
                                    total_bytes=1000, free_bytes=0)
    assert result.candidates == ()
    assert result.projected_free_bytes == 0


def test_semantic_choices_remain_human_review_and_need_owner_proof():
    legal = candidate("cache", action=A.CLEAN_CACHE, disposition=D.HUMAN_REVIEW)
    no_proof = replace(legal, candidate_id="missing", plan=replace(legal.plan, regeneration_digest=""))
    no_owner = replace(legal, candidate_id="unknown", plan=replace(legal.plan, owner_ids=()))
    wrong_action = replace(legal, candidate_id="wrong", action=A.UNINSTALL_APPLICATION)
    result = plan_capacity_strategy([legal, no_proof, no_owner, wrong_action], total_bytes=1000, free_bytes=0)
    assert result.candidates == (legal,)
    assert result.candidates[0].plan.disposition is D.HUMAN_REVIEW
    assert not result.candidates[0].plan.raw_delete_eligible


def test_stop_at_projected_target_and_rank_only_legal_actions():
    large = candidate("large", 60)
    small = candidate("small", 10)
    result = plan_capacity_strategy([small, candidate("protected", 800, disposition=D.PROTECTED), large],
                                    total_bytes=1000, free_bytes=150)
    assert result.candidates == (large,)
    assert result.projected_free_bytes == 210
    assert result.projection_basis == "estimate"


def test_overlapping_paths_duplicates_and_allocation_groups_count_once():
    parent = candidate("parent", 60, path=r"C:\synthetic\tree")
    child = candidate("child", 50, path=r"c:\SYNTHETIC\tree\child")
    group_a = candidate("a", 40, reclaim_group_id="shared-allocation")
    group_b = candidate("b", 30, reclaim_group_id="shared-allocation")
    result = plan_capacity_strategy([child, group_b, parent, group_a, parent], total_bytes=1000, free_bytes=0)
    assert result.candidates == (parent, group_a)
    assert result.projected_free_bytes == 100


@pytest.mark.parametrize("amount,basis", [(None, "unknown"), (999, "unknown"), (-1, "estimate"),
                                         (True, "estimate")])
def test_unknown_or_invalid_reclaim_never_counts_as_proven(amount, basis):
    item = replace(candidate("unknown"), projected_reclaim_bytes=amount, reclaim_basis=basis)
    result = plan_capacity_strategy([item], total_bytes=1000, free_bytes=0)
    assert result.projected_free_bytes == 0
    assert result.projection_basis == "estimate"


def test_order_is_deterministic_and_semantic_tiers_precede_value_decisions():
    cache = candidate("cache", 1, action=A.CLEAN_CACHE, disposition=D.HUMAN_REVIEW)
    repo = candidate("repo", 100, action=A.ARCHIVE_OR_REMOVE_REPOSITORY, disposition=D.HUMAN_REVIEW)
    left = candidate("a", 5)
    right = candidate("b", 5)
    items = [repo, right, cache, left]
    first = plan_capacity_strategy(items, total_bytes=1000, free_bytes=0)
    assert first == plan_capacity_strategy(reversed(items), total_bytes=1000, free_bytes=0)
    assert first.candidates == (left, right, cache, repo)


@pytest.mark.parametrize("total,free", [(0, 0), (-1, 0), (100, -1), (100, 101), (True, 0)])
def test_invalid_measurements_fail_closed(total, free):
    with pytest.raises(ValueError):
        plan_capacity_strategy([], total_bytes=total, free_bytes=free)


def test_fractional_byte_target_rounds_up():
    assert plan_capacity_strategy([], total_bytes=11, free_bytes=2).target_free_bytes == 3


def test_zero_byte_exact_container_can_follow_selected_children_without_double_counting():
    parent = replace(candidate("parent", 0, path=r"C:\synthetic\tree"), reclaim_basis="container-row")
    child = candidate("child", 50, path=r"C:\synthetic\tree\child")
    result = plan_capacity_strategy([parent, child], total_bytes=1000, free_bytes=0)
    assert result.candidates == (child, parent)
    assert result.projected_free_bytes == 50


def test_container_is_not_added_after_projected_target_is_met():
    parent = replace(candidate("parent", 0, path=r"C:\synthetic\tree"), reclaim_basis="container-row")
    child = candidate("child", 50, path=r"C:\synthetic\tree\child")
    result = plan_capacity_strategy([parent, child], total_bytes=1000, free_bytes=150)
    assert result.candidates == (child,)
