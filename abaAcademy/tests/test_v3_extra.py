# -*- coding: utf-8 -*-
"""Tests for the surah quiz, logic gates and data structures."""

import itertools
import os
import random
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.quran_engine import khatma, surah_quiz as sq
from abaAcademy.codelab import gates, data_structures as ds


class TestSurahQuiz(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ix = khatma.QuranIndex.load(os.path.join(_HERE, "..", "resources", "quran", "quran_data.json"))
        cls.t = sq.surah_table(ix)

    def test_table(self):
        self.assertEqual(len(self.t), 114)
        self.assertEqual(sum(s.ayat for s in self.t), 6236)
        self.assertEqual((self.t[1].ayat, self.t[1].kind), (286, "مدنية"))
        self.assertEqual(self.t[17].juz, 15)
        self.assertEqual(self.t[113].juz, 30)

    def test_questions(self):
        rng = random.Random(4)
        for kind in sq.KINDS:
            for pool in (None, sq.JUZ_AMMA):
                for _ in range(15):
                    q = sq.make_question(self.t, kind, rng, pool)
                    self.assertIn(q.answer, q.options)
                    self.assertEqual(len(set(q.options)), len(q.options))


class TestGates(unittest.TestCase):
    def test_tables(self):
        for a, b in itertools.product((0, 1), repeat=2):
            self.assertEqual(gates.evaluate("AND", a, b), a & b)
            self.assertEqual(gates.evaluate("NAND", a, b), 1 - (a & b))
            self.assertEqual(gates.evaluate("XOR", a, b), a ^ b)
        self.assertEqual(gates.evaluate("NOT", 0), 1)
        with self.assertRaises(ValueError):
            gates.evaluate("AND", 1)

    def test_adders(self):
        for a, b, c in itertools.product((0, 1), repeat=3):
            s, carry = gates.full_adder(a, b, c)
            self.assertEqual(s + 2 * carry, a + b + c)
        for x in range(0, 40, 3):
            for y in range(0, 40, 7):
                res, _ = gates.add_binary(bin(x)[2:], bin(y)[2:])
                self.assertEqual(int(res, 2), x + y)
        with self.assertRaises(ValueError):
            gates.add_binary("102", "1")

    def test_quiz(self):
        rng = random.Random(1)
        for _ in range(20):
            q = gates.make_question(rng)
            self.assertIn(q.answer, q.options)
            q = gates.identify_question(rng)
            self.assertIn(q.answer, q.options)


class TestDataStructures(unittest.TestCase):
    def test_stack_queue(self):
        s = ds.make("stack")
        for v in "ABC":
            s.do("push", v)
        self.assertIn("C", s.do("pop"))
        self.assertTrue(s.read().startswith("القمّة B"))
        q = ds.make("queue")
        for v in "ABC":
            q.do("enqueue", v)
        self.assertIn("A", q.do("dequeue"))
        self.assertIn("B، C", q.read())

    def test_linked_list(self):
        l = ds.make("list")
        for v in "123":
            l.do("append", v)
        l.do("insert", "9", 2)
        self.assertEqual(l.values(), ["1", "2", "9", "3"])
        l.do("reverse")
        self.assertEqual(l.values(), ["3", "9", "2", "1"])
        l.do("remove", "9")
        self.assertEqual(l.values(), ["3", "2", "1"])
        self.assertIn("لم أجد", l.do("find", "7"))

    def test_bst_matches_sorted(self):
        rng = random.Random(3)
        for _ in range(20):
            b = ds.make("bst")
            vals = rng.sample(range(100), 15)
            for v in vals:
                b.do("insert", str(v))
            for v in rng.sample(vals, 5):
                b.do("remove", str(v))
                vals.remove(v)
            got = b.do("inorder").split(": ")[1].split("، ")
            self.assertEqual([int(float(x)) for x in got], sorted(vals))
        with self.assertRaises(ValueError):
            ds.make("bst").do("insert", "abc")


if __name__ == "__main__":
    unittest.main()
