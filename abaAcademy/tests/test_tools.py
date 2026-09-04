# -*- coding: utf-8 -*-
"""Tests for the units converter and the talking calculator's evaluation path."""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.math_engine import units
from abaAcademy.math_engine.safe_eval import SafeFunction


class TestUnits(unittest.TestCase):
    def test_length(self):
        self.assertAlmostEqual(units.convert("length", "cm", "m", 100), 1.0)
        self.assertAlmostEqual(units.convert("length", "mile", "km", 1), 1.609344)

    def test_mass(self):
        self.assertAlmostEqual(units.convert("mass", "kg", "g", 2), 2000.0)

    def test_temperature(self):
        self.assertAlmostEqual(units.convert("temperature", "c", "f", 100), 212.0)
        self.assertAlmostEqual(units.convert("temperature", "f", "c", 32), 0.0)
        self.assertAlmostEqual(units.convert("temperature", "c", "k", 0), 273.15)
        self.assertAlmostEqual(units.convert("temperature", "k", "c", 273.15), 0.0)

    def test_storage(self):
        self.assertAlmostEqual(units.convert("storage", "gb", "mb", 1), 1024.0)

    def test_roundtrip(self):
        # converting there and back returns the original
        v = units.convert("length", "m", "foot", 3)
        self.assertAlmostEqual(units.convert("length", "foot", "m", v), 3.0)

    def test_unknown_unit(self):
        with self.assertRaises(ValueError):
            units.convert("length", "xx", "m", 1)

    def test_families_and_units_listed(self):
        fams = units.families()
        self.assertTrue(any(k == "temperature" for k, _ in fams))
        self.assertTrue(len(units.units_in("length")) >= 5)


class TestCalculator(unittest.TestCase):
    def _eval(self, expr):
        return SafeFunction(expr, var="x")(0.0)

    def test_arithmetic(self):
        self.assertEqual(self._eval("(5+3)*2"), 16)
        self.assertEqual(self._eval("2^10"), 1024)

    def test_functions(self):
        self.assertAlmostEqual(self._eval("log(e)"), 1.0)
        self.assertAlmostEqual(self._eval("sqrt(2)"), 1.41421356, places=6)

    def test_undefined(self):
        self.assertIsNone(self._eval("1/0"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
