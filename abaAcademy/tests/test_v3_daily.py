# -*- coding: utf-8 -*-
"""Tests for the Arab countries data, school arithmetic and the tasbih counter."""

import os
import random
import sys
import unittest
from fractions import Fraction

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.science import arab_countries as ac
from abaAcademy.math_engine import arithmetic as ar
from abaAcademy.tools import tasbih


class TestCountries(unittest.TestCase):
    def test_all_members(self):
        self.assertEqual(len(ac.COUNTRIES), 22)
        self.assertEqual(len({c.dial for c in ac.COUNTRIES}), 22)
        self.assertEqual(ac.BY_KEY["km"].capital, "موروني")
        self.assertEqual(ac.BY_KEY["dj"].capital, "جيبوتي")

    def test_find(self):
        self.assertEqual(ac.find("القمر").key, "km")
        self.assertEqual(ac.find("بيروت").key, "lb")
        self.assertEqual(ac.find("مصر").key, "eg")
        self.assertIsNone(ac.find("باريس"))

    def test_questions(self):
        rng = random.Random(5)
        for kind in ac.QUIZ_KINDS:
            for _ in range(30):
                q = ac.make_question(kind, rng)
                self.assertIn(q.answer, q.options)
                self.assertEqual(len(q.options), len(set(q.options)))
                self.assertGreaterEqual(len(q.options), 3)


class TestArithmetic(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(ar.parse_fraction("2 1/3"), Fraction(7, 3))
        self.assertEqual(ar.parse_fraction("-3/6"), Fraction(-1, 2))
        self.assertEqual(ar.parse_fraction("0.25"), Fraction(1, 4))
        with self.assertRaises(ValueError):
            ar.parse_fraction("1/0")

    def test_ops(self):
        rng = random.Random(1)
        for _ in range(100):
            a = Fraction(rng.randint(-20, 20), rng.randint(1, 12))
            b = Fraction(rng.randint(1, 20), rng.randint(1, 12))
            for op, f in (("+", a + b), ("-", a - b), ("×", a * b), ("÷", a / b)):
                res, steps = ar.fraction_op(f"{a.numerator}/{a.denominator}", op,
                                            f"{b.numerator}/{b.denominator}")
                self.assertEqual(res, f)
                self.assertTrue(steps)

    def test_show(self):
        self.assertEqual(ar.show(Fraction(7, 3)), "2 و1/3")
        self.assertEqual(ar.show(Fraction(-7, 3)), "-2 و1/3")
        self.assertEqual(ar.speak(Fraction(1, 2)), "1 على 2")

    def test_roman(self):
        for n in range(1, 4000):
            self.assertEqual(ar.from_roman(ar.to_roman(n)), n)
        self.assertEqual(ar.to_roman(1994), "MCMXCIV")
        with self.assertRaises(ValueError):
            ar.from_roman("IIII")
        with self.assertRaises(ValueError):
            ar.to_roman(0)

    def test_english(self):
        self.assertEqual(ar.english_words(0), "zero")
        self.assertEqual(ar.english_words(45), "forty-five")
        self.assertEqual(ar.english_words(1205), "one thousand two hundred and five")
        self.assertEqual(ar.english_words(2000000), "two million")
        self.assertEqual(ar.english_ordinal(1), "first")
        self.assertEqual(ar.english_ordinal(22), "twenty-second")
        self.assertEqual(ar.english_ordinal(30), "thirtieth")

    def test_percent(self):
        self.assertIn("= 30", ar.percent_of(15, 200))
        self.assertIn("25٪", ar.what_percent(50, 200))
        self.assertIn("زيادة", ar.change(80, 100))
        self.assertIn("170", ar.discount(200, 15))
        self.assertIn("1,102.5", ar.interest(1000, 5, 2, True))
        with self.assertRaises(ValueError):
            ar.what_percent(1, 0)

    def test_times_tables_adapt(self):
        t = ar.TimesTables([7], rng=random.Random(2))
        a, b = t.next()
        ok, right = t.answer("-1", 3)
        self.assertFalse(ok)
        self.assertEqual(right, a * b)
        self.assertGreater(t.weights[t._key(a, b)], 1.0)
        self.assertTrue(t.weakest())


class TestTasbih(unittest.TestCase):
    def test_after_prayer_sequence(self):
        c = tasbih.Counter()
        msgs = [c.tap() for _ in range(100)]
        self.assertTrue(c.finished)
        self.assertTrue(any("الحمد لله" in m for m in msgs))
        self.assertIn("تقبّل الله", msgs[-1])
        self.assertEqual(c.today_total(), 100)

    def test_undo_reset_and_store(self):
        class S(dict):
            def get_setting(self, k, d=None):
                return self.get(k, d)

            def set_setting(self, k, v):
                self[k] = v
        st = S()
        c = tasbih.Counter("istighfar")
        for _ in range(5):
            c.tap()
        c.undo()
        self.assertEqual(c.count, 4)
        tasbih.save(st, c)
        d = tasbih.load(st)
        self.assertEqual((d.sequence, d.count), ("istighfar", 4))
        d.reset("free")
        for _ in range(250):
            d.tap()
        self.assertFalse(d.finished)
        with self.assertRaises(ValueError):
            d.reset("nope")


if __name__ == "__main__":
    unittest.main()
