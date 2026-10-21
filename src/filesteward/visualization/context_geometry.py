"""Bounded context placement; geometry only, never action or scene authority."""


def context_placement_javascript() -> str:
    """Return the pure solver shared by the renderer and browser geometry tests."""
    return r"""
  const placeContextPanel = ({anchor, width, height, viewport, obstacles}) => {
    const inset = 8, gap = 18, maxDistance = 48;
    if (width <= 0 || height <= 0) return null;
    const xs = [anchor.right + gap, anchor.left - width - gap,
      (anchor.left + anchor.right - width) / 2];
    const ys = [anchor.bottom + gap, anchor.top - height - gap,
      (anchor.top + anchor.bottom - height) / 2];
    const intersects = (a, b) => a.left < b.right + inset && a.right > b.left - inset
      && a.top < b.bottom + inset && a.bottom > b.top - inset;
    const distance = (a, b) => Math.hypot(
      Math.max(a.left - b.right, b.left - a.right, 0),
      Math.max(a.top - b.bottom, b.top - a.bottom, 0));
    const candidates = [];
    xs.forEach(left => ys.forEach(top => {
      left = Math.max(inset, Math.min(viewport.width - width - inset, left));
      top = Math.max(inset, Math.min(viewport.height - height - inset, top));
      const box = {left, top, right: left + width, bottom: top + height};
      const separation = distance(box, anchor);
      if (box.right > viewport.width - inset || box.bottom > viewport.height - inset
          || separation < gap || separation > maxDistance
          || obstacles.some(rect => intersects(box, rect))) return;
      candidates.push({...box, score: separation
        + Math.abs((box.left + box.right - anchor.left - anchor.right) / 2) * .01
        + Math.abs((box.top + box.bottom - anchor.top - anchor.bottom) / 2) * .01});
    }));
    candidates.sort((a, b) => a.score - b.score);
    return candidates[0] || null;
  };
"""
