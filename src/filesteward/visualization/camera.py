"""Presentation-only semantic camera for Memory Atlas v3.

The camera changes how persisted treemap geometry is viewed. It never creates
hierarchy, changes evidence, or owns search/filter truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

__all__ = [
    "DIRECT_TARGET_MIN_PX",
    "AtlasCamera",
    "CameraLevel",
    "CameraState",
    "CameraTransform",
    "fit_rect_transform",
    "is_direct_target",
    "target_size_px",
]


DIRECT_TARGET_MIN_PX = 40.0


class _Rect(Protocol):
    node_id: str
    x: float
    y: float
    width: float
    height: float


class CameraLevel(str, Enum):
    """Semantic level-of-detail states; not physical filesystem depth."""

    HOME = "HOME"
    BANK = "BANK"
    FABRIC = "FABRIC"
    CELL = "CELL"
    CHAMBER = "CHAMBER"


@dataclass(frozen=True)
class CameraTransform:
    scale: float = 1.0
    translate_x: float = 0.0
    translate_y: float = 0.0

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError("camera scale must be > 0")


@dataclass(frozen=True)
class CameraState:
    level: CameraLevel = CameraLevel.HOME
    transform: CameraTransform = CameraTransform()
    selected_id: str | None = None


@dataclass
class AtlasCamera:
    """Small deterministic state machine for Atlas spatial navigation.

    Search/filter remain owned elsewhere. `home()` intentionally preserves the
    current selected_id while resetting camera position and scene history.
    """

    state: CameraState = field(default_factory=CameraState)
    _history: list[CameraState] = field(default_factory=list, init=False, repr=False)

    @property
    def history_depth(self) -> int:
        return len(self._history)

    def _push(self, state: CameraState) -> CameraState:
        if state != self.state:
            self._history.append(self.state)
            self.state = state
        return self.state

    def select(self, node_id: str) -> CameraState:
        if not node_id:
            raise ValueError("node_id must be non-empty")
        self.state = CameraState(
            level=self.state.level,
            transform=self.state.transform,
            selected_id=node_id,
        )
        return self.state

    def set_level(self, level: CameraLevel, *, scale: float | None = None) -> CameraState:
        transform = self.state.transform
        if scale is not None:
            transform = CameraTransform(
                scale=scale,
                translate_x=transform.translate_x,
                translate_y=transform.translate_y,
            )
        return self._push(
            CameraState(level=level, transform=transform, selected_id=self.state.selected_id)
        )

    def fit_selected(
        self,
        rect: _Rect,
        *,
        viewport_width: float = 100.0,
        viewport_height: float = 100.0,
        padding_ratio: float = 0.08,
        max_scale: float = 64.0,
    ) -> CameraState:
        if not rect.node_id:
            raise ValueError("rect node_id must be non-empty")
        transform = fit_rect_transform(
            rect,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            padding_ratio=padding_ratio,
            max_scale=max_scale,
        )
        return self._push(
            CameraState(
                level=CameraLevel.CELL,
                transform=transform,
                selected_id=rect.node_id,
            )
        )

    def open_selected(self, node_id: str | None = None) -> CameraState:
        selected = node_id or self.state.selected_id
        if not selected:
            raise ValueError("cannot open Chamber without a selected node")
        return self._push(
            CameraState(
                level=CameraLevel.CHAMBER,
                transform=self.state.transform,
                selected_id=selected,
            )
        )

    def back(self) -> CameraState:
        if self._history:
            self.state = self._history.pop()
        return self.state

    def home(self) -> CameraState:
        selected = self.state.selected_id
        self._history.clear()
        self.state = CameraState(
            level=CameraLevel.HOME,
            transform=CameraTransform(),
            selected_id=selected,
        )
        return self.state


def target_size_px(
    rect: _Rect,
    *,
    viewport_width_px: float,
    viewport_height_px: float,
    coordinate_width: float = 100.0,
    coordinate_height: float = 100.0,
) -> tuple[float, float]:
    """Return rendered target size for a treemap rectangle."""

    if viewport_width_px < 0 or viewport_height_px < 0:
        raise ValueError("viewport dimensions must be non-negative")
    if coordinate_width <= 0 or coordinate_height <= 0:
        raise ValueError("coordinate dimensions must be > 0")
    return (
        rect.width / coordinate_width * viewport_width_px,
        rect.height / coordinate_height * viewport_height_px,
    )


def is_direct_target(
    rect: _Rect,
    *,
    viewport_width_px: float,
    viewport_height_px: float,
    min_target_px: float = DIRECT_TARGET_MIN_PX,
) -> bool:
    """Whether a sector is large enough for direct pointer/touch targeting.

    WCAG 2.2 establishes a 24 CSS-pixel external floor, while FileSteward's
    visual-system contract deliberately uses a stronger 40px minimum. Small
    sectors remain valid evidence; they must be reached through an equivalent
    reliable control and camera-fit path instead of precision clicking.
    """

    if min_target_px <= 0:
        raise ValueError("min_target_px must be > 0")
    width_px, height_px = target_size_px(
        rect,
        viewport_width_px=viewport_width_px,
        viewport_height_px=viewport_height_px,
    )
    return width_px >= min_target_px and height_px >= min_target_px


def fit_rect_transform(
    rect: _Rect,
    *,
    viewport_width: float = 100.0,
    viewport_height: float = 100.0,
    padding_ratio: float = 0.08,
    max_scale: float = 64.0,
) -> CameraTransform:
    """Fit one persisted rectangle into the camera without changing geometry."""

    if rect.width <= 0 or rect.height <= 0:
        raise ValueError("cannot fit an empty rectangle")
    if viewport_width <= 0 or viewport_height <= 0:
        raise ValueError("viewport dimensions must be > 0")
    if not 0 <= padding_ratio < 0.5:
        raise ValueError("padding_ratio must be >= 0 and < 0.5")
    if max_scale < 1:
        raise ValueError("max_scale must be >= 1")

    usable_w = viewport_width * (1 - 2 * padding_ratio)
    usable_h = viewport_height * (1 - 2 * padding_ratio)
    scale = min(usable_w / rect.width, usable_h / rect.height)
    scale = min(max(1.0, scale), max_scale)

    center_x = rect.x + rect.width / 2
    center_y = rect.y + rect.height / 2
    tx = viewport_width / 2 - center_x * scale
    ty = viewport_height / 2 - center_y * scale
    return CameraTransform(scale=scale, translate_x=tx, translate_y=ty)
