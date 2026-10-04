from dataclasses import dataclass

from filesteward.visualization.camera import (
    AtlasCamera,
    CameraLevel,
    fit_rect_transform,
    is_direct_target,
)


@dataclass(frozen=True)
class Rect:
    node_id: str
    x: float
    y: float
    width: float
    height: float


def test_micro_sector_is_not_direct_target_until_magnified() -> None:
    rect = Rect("tiny", 75, 80, 0.5, 0.5)
    assert not is_direct_target(
        rect, viewport_width_px=1000, viewport_height_px=700
    )
    fitted = fit_rect_transform(rect)
    assert fitted.scale > 1


def test_fit_selected_then_chamber_then_back_is_reversible() -> None:
    rect = Rect("node-a", 60, 20, 4, 8)
    camera = AtlasCamera()
    cell = camera.fit_selected(rect)
    assert cell.level is CameraLevel.CELL
    assert cell.selected_id == "node-a"
    assert cell.transform.scale > 1

    chamber = camera.open_selected()
    assert chamber.level is CameraLevel.CHAMBER
    assert camera.back().level is CameraLevel.CELL
    assert camera.back().level is CameraLevel.HOME


def test_home_preserves_selection_but_resets_camera_history() -> None:
    rect = Rect("node-a", 60, 20, 4, 8)
    camera = AtlasCamera()
    camera.fit_selected(rect)
    camera.open_selected()
    home = camera.home()
    assert home.level is CameraLevel.HOME
    assert home.selected_id == "node-a"
    assert home.transform.scale == 1
    assert camera.history_depth == 0


def test_fit_transform_centers_selected_geometry() -> None:
    rect = Rect("center-me", 80, 20, 10, 20)
    transform = fit_rect_transform(rect, viewport_width=100, viewport_height=100)
    center_x = (
        (rect.x + rect.width / 2) * transform.scale + transform.translate_x
    )
    center_y = (
        (rect.y + rect.height / 2) * transform.scale + transform.translate_y
    )
    assert center_x == 50
    assert center_y == 50
