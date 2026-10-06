"""Source-contract guards for pointer reticle modality and range marquee."""

from __future__ import annotations

from filesteward.visualization.experience import render_cinematic_experience_script


def _script() -> str:
    return render_cinematic_experience_script()


def test_range_threshold_is_at_least_eight_pixels() -> None:
    script = _script()
    assert "RANGE_THRESHOLD" in script
    assert "const RANGE_THRESHOLD = 8" in script or "RANGE_THRESHOLD = 8" in script
    assert "dx < RANGE_THRESHOLD" in script
    assert "dy < RANGE_THRESHOLD" in script


def test_range_requires_eligible_map_surface() -> None:
    script = _script()
    assert "eligibleRangeSurface" in script
    assert ".map-wrap" in script
    assert "eligibleRangeSurface(event.target)" in script
    assert "if (!eligibleRangeSurface(event.target)) return;" in script


def test_focusin_does_not_teleport_reticle_while_pointer_modality() -> None:
    script = _script()
    assert "hideReticleUntilPointer" in script
    assert "pointerModality === 'pointer'" in script
    assert "paintCue(cue, lastPointer.x, lastPointer.y, true, false)" in script
    # Must not paint the reticle at the focused element's center while pointer-owned.
    focus_block_start = script.index("addEventListener('focusin'")
    focus_block = script[focus_block_start : focus_block_start + 1200]
    assert "moveReticlePos" not in focus_block or "false)" in focus_block
    assert "paintCue(cue, rect.left" not in focus_block
    assert "paintCue(cue, rect.left + rect.width / 2" not in focus_block
    assert "hideReticleUntilPointer = true" in focus_block
    assert ", false)" in focus_block


def test_cue_from_has_no_operable_explore_empty_canvas_fallback() -> None:
    script = _script()
    assert "No operable action on empty canvas." in script
    assert "actionability: 'UNAVAILABLE'" in script
    # Empty-canvas / unknown host must not invent operable EXPLORE.
    assert "label: 'EXPLORE', actionability: 'OPERABLE'" not in script
    assert "mode: 'explore', label: 'EXPLORE'" not in script
    assert "EXPLORE is reserved." in script


def test_scene_transition_hides_reticle_until_pointermove() -> None:
    script = _script()
    assert "hideReticleUntilPointer = true" in script
    assert "lastObservedScene" in script or "hideReticleUntilPointer = true" in script
    assert "hideReticleUntilPointer = false" in script  # cleared on pointermove
