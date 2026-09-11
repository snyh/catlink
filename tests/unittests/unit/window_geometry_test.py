#!/usr/bin/env python3
# This file is part of Xpra.
# Copyright (C) 2026 Xpra
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import unittest

from xpra.util.window_geometry import clamp_window_to_root, clamp_window_to_visible_area


class WindowGeometryTest(unittest.TestCase):

    def test_visible_window_is_unchanged(self):
        areas = ((0, 0, 100, 100), (100, 0, 100, 100))
        self.assertEqual(clamp_window_to_visible_area(75, 10, 50, 50, areas), (75, 10))

    def test_window_is_clamped_to_best_monitor(self):
        areas = ((0, 0, 100, 100), (150, 0, 100, 100))
        self.assertEqual(clamp_window_to_visible_area(60, 10, 100, 50, areas), (0, 10))
        self.assertEqual(clamp_window_to_visible_area(120, 10, 100, 50, areas), (150, 10))

    def test_offscreen_and_oversized_windows_use_first_monitor(self):
        areas = ((-100, 0, 100, 100), (0, 0, 100, 100))
        self.assertEqual(clamp_window_to_visible_area(300, 300, 50, 50, areas), (-50, 50))
        self.assertEqual(clamp_window_to_visible_area(300, 300, 150, 150, areas), (-100, 0))

    def test_margin(self):
        self.assertEqual(clamp_window_to_visible_area(0, 0, 90, 90, ((0, 0, 100, 100),), 5), (5, 5))

    def test_invalid_areas_use_fallback(self):
        self.assertEqual(
            clamp_window_to_visible_area(
                5000, 5000, 500, 500, ((0, 0, 0, 1080),), fallback_area=(0, 0, 1920, 1080),
            ),
            (1420, 580),
        )

    def test_legacy_root_clamp(self):
        self.assertEqual(clamp_window_to_root(5000, 5000, 1920, 1080), (1856, 1016))
        self.assertEqual(clamp_window_to_root(-100, -100, 1920, 1080), (-100, -100))


def main():
    unittest.main()


if __name__ == "__main__":
    main()
