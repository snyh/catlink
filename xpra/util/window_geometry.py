# This file is part of Xpra.
# Copyright (C) 2026 Xpra
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

from collections.abc import Sequence


Rectangle = tuple[int, int, int, int]


def clamp_window_to_root(x: int, y: int, screen_w: int, screen_h: int,
                         minimum_visible: int = 64) -> tuple[int, int]:
    """Preserve the legacy server clamp for a window outside the root bounds."""
    if x >= screen_w or y >= screen_h:
        return min(x, screen_w - minimum_visible), min(y, screen_h - minimum_visible)
    return x, y


def intersection(rect: Rectangle, area: Rectangle) -> Rectangle | None:
    x = max(rect[0], area[0])
    y = max(rect[1], area[1])
    right = min(rect[0] + rect[2], area[0] + area[2])
    bottom = min(rect[1] + rect[3], area[1] + area[3])
    if right <= x or bottom <= y:
        return None
    return x, y, right - x, bottom - y


def subtract(rect: Rectangle, area: Rectangle) -> list[Rectangle]:
    overlap = intersection(rect, area)
    if not overlap:
        return [rect]
    x, y, w, h = rect
    ix, iy, iw, ih = overlap
    result = []
    if iy > y:
        result.append((x, y, w, iy - y))
    if iy + ih < y + h:
        result.append((x, iy + ih, w, y + h - iy - ih))
    if ix > x:
        result.append((x, iy, ix - x, ih))
    if ix + iw < x + w:
        result.append((ix + iw, iy, x + w - ix - iw, ih))
    return result


def clamp_window_to_visible_area(x: int, y: int, w: int, h: int,
                                 areas: Sequence[Sequence[int]], margin: int = 0,
                                 fallback_area: Sequence[int] = ()) -> tuple[int, int]:
    """Return a position that keeps the window within the visible monitor union."""
    margin = max(0, margin)
    visible_areas: list[tuple[int, int, int, int]] = []
    for area in areas:
        if len(area) < 4:
            continue
        ax, ay, aw, ah = (int(v) for v in area[:4])
        ax += margin
        ay += margin
        aw -= margin * 2
        ah -= margin * 2
        if aw > 0 and ah > 0:
            visible_areas.append((ax, ay, aw, ah))
    if not visible_areas and len(fallback_area) >= 4:
        fx, fy, fw, fh = (int(v) for v in fallback_area[:4])
        fx += margin
        fy += margin
        fw -= margin * 2
        fh -= margin * 2
        if fw > 0 and fh > 0:
            visible_areas.append((fx, fy, fw, fh))
    if not visible_areas:
        return x, y

    w = max(1, w)
    h = max(1, h)
    window_rect = (x, y, w, h)
    remaining = [window_rect]
    overlaps: list[tuple[int, int]] = []
    for index, (ax, ay, aw, ah) in enumerate(visible_areas):
        new_remaining = []
        area = (ax, ay, aw, ah)
        for rect in remaining:
            new_remaining += subtract(rect, area)
        remaining = new_remaining
        if not remaining:
            return x, y
        overlap = intersection(window_rect, area)
        if overlap:
            overlaps.append((overlap[2] * overlap[3], index))

    index = max(overlaps)[1] if overlaps else 0
    ax, ay, aw, ah = visible_areas[index]
    nx = ax if w >= aw else max(ax, min(x, ax + aw - w))
    ny = ay if h >= ah else max(ay, min(y, ay + ah - h))
    return nx, ny
