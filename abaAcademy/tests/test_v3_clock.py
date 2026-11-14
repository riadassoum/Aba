# -*- coding: utf-8 -*-
"""Tests for the talking clock, timers and resistor networks."""

import datetime
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.tools import clock
from abaAcademy.science import physics as ph


class FakeTime:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class TestClock(unittest.TestCase):
    def test_spoken_time(self):
        dt = datetime.datetime
        self.assertEqual(clock.spoken_time(dt(2026, 1, 1, 9, 15)), "الساعة 9 والربع صباحًا")
        self.assertEqual(clock.spoken_time(dt(2026, 1, 1, 13, 30)), "الساعة 1 والنصف ظهرًا")
        self.assertEqual(clock.spoken_time(dt(2026, 1, 1, 16, 45)), "الساعة 5 إلا ربعًا عصرًا")
        self.assertEqual(clock.spoken_time(dt(2026, 1, 1, 0, 5)), "الساعة 12 و5 دقائق ليلًا")
        self.assertEqual(clock.spoken_time(dt(2026, 1, 1, 7, 3), False), "الساعة 07:03")

    def test_durations(self):
        self.assertEqual(clock.spoken_duration(3725), "ساعة واحدة ودقيقتان و5 ثوانٍ")
        self.assertEqual(clock.clock_text(3725), "1:02:05")
        self.assertEqual(clock.parse_duration("1:30"), 90)
        self.assertEqual(clock.parse_duration("2د"), 120)
        self.assertEqual(clock.parse_duration("٥"), 300)
        with self.assertRaises(ValueError):
            clock.parse_duration("قليل")

    def test_stopwatch(self):
        sw = clock.Stopwatch()
        ft = FakeTime()
        sw.now = ft
        sw.start()
        ft.t += 5
        n, lap, total = sw.lap()
        self.assertEqual((n, lap, total), (1, 5, 5))
        ft.t += 3
        sw.stop()
        ft.t += 100
        self.assertEqual(sw.elapsed(), 8)

    def test_countdown(self):
        cd = clock.Countdown()
        ft = FakeTime()
        cd.now = ft
        cd.set(70)
        cd.start()
        ft.t += 15
        self.assertIn("دقيقة", cd.tick())
        ft.t += 50
        self.assertEqual(cd.tick(), "5")
        ft.t += 10
        self.assertEqual(cd.tick(), "انتهى الوقت!")
        self.assertFalse(cd.running)
        with self.assertRaises(ValueError):
            cd.set(0)

    def test_world(self):
        lines = clock.world_times(datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.timezone.utc))
        self.assertTrue(any(l.startswith("مكّة المكرّمة: 15:00") for l in lines))


class TestResistors(unittest.TestCase):
    def test_networks(self):
        self.assertEqual(ph.series([100, 200])[0], 300)
        self.assertAlmostEqual(ph.parallel([100, 100])[0], 50)
        self.assertEqual(ph.parse_resistors("1k 2k"), [1000, 2000])
        lines = ph.circuit_report([100, 200, 1000], 12, "parallel")
        self.assertTrue(any("62.5" in l for l in lines))
        with self.assertRaises(ValueError):
            ph.parse_resistors("100")
        with self.assertRaises(ValueError):
            ph.circuit_report([1, 2], 0, "series")


if __name__ == "__main__":
    unittest.main()
