# -*- coding: utf-8 -*-
"""Tests for the shared braille chord engine.

These pin down the behaviour that was repeatedly broken when the logic lived
inside the GUI classes: holding keys must not commit early, order of release
must not matter, auto-repeat must be harmless, and a lost key-up must recover.
"""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.braille_engine.chord_input import (
    ChordAccumulator, KEY_TO_DOT, KEYCODE_TO_DOT,
)


class TestChord(unittest.TestCase):
    def setUp(self):
        self.a = ChordAccumulator()

    def test_commits_on_last_release(self):
        for d in (1, 2, 3):
            self.a.press(d)
        self.assertIsNone(self.a.release(2))
        self.assertIsNone(self.a.release(3))
        self.assertEqual(self.a.release(1), frozenset({1, 2, 3}))

    def test_release_order_irrelevant(self):
        for d in (1, 4, 5):
            self.a.press(d)
        got = None
        for d in (5, 1, 4):
            got = self.a.release(d) or got
        self.assertEqual(got, frozenset({1, 4, 5}))

    def test_holding_does_not_commit(self):
        self.a.press(1)
        self.a.press(2)
        for _ in range(20):
            self.assertIsNone(self.a.tick())
        self.a.release(1)
        self.assertEqual(self.a.release(2), frozenset({1, 2}))

    def test_autorepeat_harmless(self):
        for _ in range(5):
            self.a.press(1)
        self.a.press(4)
        self.a.release(1)
        self.assertEqual(self.a.release(4), frozenset({1, 4}))

    def test_single_dot(self):
        self.a.press(6)
        self.assertEqual(self.a.release(6), frozenset({6}))

    def test_lost_keyup_recovers(self):
        self.a.press(3)
        self.a.press(6)
        got = None
        for _ in range(30):
            got = self.a.tick() or got
        self.assertEqual(got, frozenset({3, 6}))

    def test_reset_abandons_chord(self):
        self.a.press(1)
        self.a.reset()
        self.assertFalse(self.a.active)
        self.assertIsNone(self.a.tick())

    def test_unknown_dot_ignored(self):
        self.a.press(9)
        self.assertFalse(self.a.active)

    def test_release_without_press_is_safe(self):
        self.assertIsNone(self.a.release(1))

    def test_key_maps_cover_six_dots(self):
        self.assertEqual(sorted(KEY_TO_DOT.values()), [1, 2, 3, 4, 5, 6])
        self.assertEqual(len(KEYCODE_TO_DOT), 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestPollingCapture(unittest.TestCase):
    """The capture the screens actually use: driven by sampling the keyboard,
    so no key event has to arrive on time for a cell to be correct."""

    def setUp(self):
        from abaAcademy.braille_engine.chord_input import PollingChordCapture
        self.held = set()
        self.cells = []
        self.active = [True]
        self.cap = PollingChordCapture(
            key_state=lambda d: d in self.held,
            on_cell=self.cells.append,
            is_active=lambda: self.active[0])

    def _tick(self, n=1):
        for _ in range(n):
            self.cap.poll()

    def test_builds_chord_over_many_polls(self):
        self.held = {1}
        self._tick(3)
        self.held = {1, 2}
        self._tick(3)
        self.held = {1, 2, 3}
        self._tick(10)                 # held a long time
        self.assertEqual(self.cells, [])
        self.held = set()
        self._tick()
        self.assertEqual(self.cells, [frozenset({1, 2, 3})])

    def test_staggered_release(self):
        self.held = {1, 4}
        self._tick(2)
        self.held = {4}
        self._tick(2)
        self.held = set()
        self._tick()
        self.assertEqual(self.cells, [frozenset({1, 4})])

    def test_single_dot(self):
        self.held = {6}
        self._tick(2)
        self.held = set()
        self._tick()
        self.assertEqual(self.cells, [frozenset({6})])

    def test_consecutive_cells(self):
        for dots in ({1}, {1, 2}, {2, 5}):
            self.held = set(dots)
            self._tick(2)
            self.held = set()
            self._tick()
        self.assertEqual(self.cells,
                         [frozenset({1}), frozenset({1, 2}), frozenset({2, 5})])

    def test_inactive_abandons_chord(self):
        self.held = {1, 2}
        self._tick()
        self.active[0] = False
        self._tick()
        self.active[0] = True
        self.held = set()
        self._tick()
        self.assertEqual(self.cells, [])

    def test_idle_polls_do_nothing(self):
        self._tick(10)
        self.assertEqual(self.cells, [])
