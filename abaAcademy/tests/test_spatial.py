# -*- coding: utf-8 -*-
"""Tests for the spatial audio engine and maze generation."""

import os
import struct
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.spatial.audio3d import SpatialScene
from abaAcademy.gui.spatial_maze import generate_maze
import random


def _rms(pcm):
    L = R = 0
    n = max(1, len(pcm) // 4)
    for i in range(0, len(pcm), 4):
        l, r = struct.unpack_from("<hh", pcm, i)
        L += l * l
        R += r * r
    return (L / n) ** 0.5, (R / n) ** 0.5


class TestSpatialAudio(unittest.TestCase):
    def setUp(self):
        self.sc = SpatialScene(10, 10)

    def test_left_source_pans_left(self):
        pcm = self.sc.cue((5, 5), (1, 5))
        l, r = _rms(pcm)
        self.assertGreater(l, r)

    def test_right_source_pans_right(self):
        pcm = self.sc.cue((5, 5), (9, 5))
        l, r = _rms(pcm)
        self.assertGreater(r, l)

    def test_near_louder_than_far(self):
        near = self.sc.cue((5, 5), (6, 5))
        far = self.sc.cue((5, 5), (5, 5))  # distance 0 is loudest; use far below
        far = self.sc.cue((0, 0), (9, 9))
        nl, nr = _rms(near)
        fl, fr = _rms(far)
        self.assertGreater(max(nl, nr), max(fl, fr))

    def test_direction_words(self):
        # The up arrow moves to a SMALLER y, so a smaller y is "ahead" and a
        # larger y is "behind". A goal two steps ahead must be reachable by
        # pressing up twice.
        self.assertIn("أمامك", self.sc.direction_word((5, 5), (5, 1)))
        self.assertIn("يمينك", self.sc.direction_word((5, 5), (9, 5)))
        self.assertIn("خلفك", self.sc.direction_word((5, 5), (5, 9)))

    def test_forward_steps_reach_goal(self):
        # goal exactly two steps ahead: walking up twice lands on it
        player, goal = (3, 5), (3, 3)
        self.assertIn("أمامك", self.sc.direction_word(player, goal))
        py = player[1]
        for _ in range(2):
            py -= 1          # what the up arrow does
        self.assertEqual((player[0], py), goal)

    def test_pcm_stereo_aligned(self):
        pcm = self.sc.cue((5, 5), (8, 8), kind="goal")
        self.assertEqual(len(pcm) % 4, 0)
        self.assertGreater(len(pcm), 100)


class TestMaze(unittest.TestCase):
    def test_maze_fully_connected(self):
        rng = random.Random(1)
        for n in (5, 8, 12):
            maze = generate_maze(n, n, rng)
            dirs = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
            seen = {(0, 0)}
            stack = [(0, 0)]
            while stack:
                x, y = stack.pop()
                for d in maze[y][x]:
                    dx, dy = dirs[d]
                    nx, ny = x + dx, y + dy
                    if (nx, ny) not in seen:
                        seen.add((nx, ny))
                        stack.append((nx, ny))
            self.assertEqual(len(seen), n * n, f"{n}x{n} maze not fully connected")

    def test_walls_are_symmetric(self):
        rng = random.Random(2)
        maze = generate_maze(6, 6, rng)
        opp = {"N": "S", "S": "N", "E": "W", "W": "E"}
        dirs = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
        for y in range(6):
            for x in range(6):
                for d in maze[y][x]:
                    dx, dy = dirs[d]
                    nx, ny = x + dx, y + dy
                    # the neighbour must have the opposite opening
                    self.assertIn(opp[d], maze[ny][nx])


if __name__ == "__main__":
    unittest.main(verbosity=2)
