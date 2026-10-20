"""Exercise the shipped placement solver, including crowded and edge geometry."""
import json
import math
import shutil
import subprocess

import pytest

from filesteward.visualization.context_geometry import context_placement_javascript


def solve(cases):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required to execute the shipped JavaScript solver")
    script = context_placement_javascript() + "\nconsole.log(JSON.stringify(" + json.dumps(cases) + ".map(placeContextPanel)));"
    return json.loads(subprocess.check_output([node], input=script, text=True, timeout=15))


def specimen(x=400, y=300, obstacles=None, width=200, height=70):
    return dict(anchor=dict(left=x, right=x, top=y, bottom=y), width=width, height=height,
                viewport=dict(width=1000, height=700), obstacles=obstacles or [])


def overlaps(a, b):
    return a["left"] < b["right"] and a["right"] > b["left"] and a["top"] < b["bottom"] and a["bottom"] > b["top"]


def test_nearby_positive_control_and_crowded_negative():
    clear = specimen()
    blocked = specimen(obstacles=[dict(left=0, top=0, right=1000, bottom=700)])
    normal, unavailable = solve([clear, blocked])
    assert normal is not None
    assert unavailable is None  # Never fall back to an occluding or distant dock.


def test_related_subject_forces_a_different_legal_seat():
    case = specimen()
    original = solve([case])[0]
    case["obstacles"] = [original]
    alternative = solve([case])[0]
    assert alternative is not None
    assert not overlaps(original, alternative)


def test_viewport_grid_has_no_occlusion_clipping_or_remote_docking():
    cases = [specimen(x, y, [dict(left=450, top=200, right=650, bottom=500)])
             for x in range(0, 1001, 50) for y in range(0, 701, 50)]
    results = solve(cases)
    assert sum(result is not None for result in results) > 100
    for case, result in zip(cases, results):
        if result is None:
            continue
        assert 8 <= result["left"] < result["right"] <= 992
        assert 8 <= result["top"] < result["bottom"] <= 692
        assert not any(overlaps(result, obstacle) for obstacle in case["obstacles"])
        anchor = case["anchor"]
        distance = math.hypot(max(result["left"] - anchor["right"], anchor["left"] - result["right"], 0),
                              max(result["top"] - anchor["bottom"], anchor["top"] - result["bottom"], 0))
        assert 18 <= distance <= 48


def test_compact_retry_fits_when_full_panel_cannot():
    full = specimen(width=1200)
    compact = {**full, "width": 100, "height": 30}
    a, b = solve([full, compact])
    assert a is None
    assert b is not None


def test_keyboard_anchor_is_the_focused_control_rectangle():
    case = specimen()
    case["anchor"] = dict(left=400, right=520, top=300, bottom=344)
    case["obstacles"] = [case["anchor"]]
    result = solve([case])[0]
    assert result is not None
    assert not overlaps(result, case["anchor"])
