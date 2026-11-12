# -*- coding: utf-8 -*-
"""Tests for chemistry, physics, the regex lab, text statistics and word search."""

import os
import random
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.science import chemistry as ch, physics as ph
from abaAcademy.codelab import regex_lab as rl
from abaAcademy.tools import text_stats as ts
from abaAcademy.puzzles import word_search as ws


class TestChemistry(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(ch.parse_formula("H2O"), {"H": 2, "O": 1})
        self.assertEqual(ch.parse_formula("Ca(OH)2"), {"Ca": 1, "O": 2, "H": 2})
        self.assertEqual(ch.parse_formula("CuSO4·5H2O"), {"Cu": 1, "S": 1, "O": 9, "H": 10})
        self.assertEqual(ch.parse_formula("Al2(SO4)3"), {"Al": 2, "S": 3, "O": 12})
        self.assertEqual(ch.parse_formula("H₂O"), {"H": 2, "O": 1})
        for bad in ("", "Xx", "H2O(", "h2o", "H2)O"):
            with self.assertRaises(ValueError):
                ch.parse_formula(bad)

    def test_molar_mass(self):
        self.assertAlmostEqual(ch.molar_mass("H2O")[0], 18.015, places=2)
        self.assertAlmostEqual(ch.molar_mass("NaCl")[0], 58.44, places=1)
        self.assertAlmostEqual(ch.molar_mass("C6H12O6")[0], 180.16, places=1)

    def test_balance(self):
        cases = {"H2 + O2 -> H2O": [2, 1, 2], "C3H8 + O2 -> CO2 + H2O": [1, 5, 3, 4],
                 "Fe + O2 → Fe2O3": [4, 3, 2], "Al + O2 = Al2O3": [4, 3, 2],
                 "KMnO4 + HCl -> KCl + MnCl2 + H2O + Cl2": [2, 16, 2, 2, 8, 5],
                 "N2 + H2 -> NH3": [1, 3, 2]}
        for eq, want in cases.items():
            self.assertEqual(ch.balance(eq)[0], want, eq)

    def test_balanced_is_conserved(self):
        for eq in ("C2H6 + O2 -> CO2 + H2O", "Ca(OH)2 + H3PO4 -> Ca3(PO4)2 + H2O"):
            k, lhs, rhs, _ = ch.balance(eq)
            for el in set().union(*(ch.parse_formula(x) for x in lhs)):
                l = sum(c * ch.parse_formula(x).get(el, 0) for c, x in zip(k, lhs))
                r = sum(c * ch.parse_formula(x).get(el, 0) for c, x in zip(k[len(lhs):], rhs))
                self.assertEqual(l, r)

    def test_balance_errors(self):
        with self.assertRaises(ValueError):
            ch.balance("H2 + O2 -> NaCl")
        with self.assertRaises(ValueError):
            ch.balance("H2O")

    def test_conversions(self):
        self.assertIn("1 مول", ch.convert_amount("H2O", 18.015, "g")[0])
        with self.assertRaises(ValueError):
            ch.convert_amount("H2O", -1, "g")


class TestPhysics(unittest.TestCase):
    def test_each_law_round_trips(self):
        rng = random.Random(1)
        for law in ph.LAWS:
            for target in law.variables:
                vals = {v.key: rng.uniform(1, 5) for v in law.variables}
                # make the values consistent: solve for the target from the rest
                known = {k: v for k, v in vals.items() if k != target.key}
                _, sols, _ = ph.solve(law.key, known)
                for s in sols:
                    d = dict(known)
                    d[target.key] = s
                    self.assertAlmostEqual(law.residual(d), 0, places=6, msg=(law.key, target.key))

    def test_values(self):
        self.assertEqual(ph.solve("newton2", {"m": 10, "a": 2})[1], [20.0])
        self.assertAlmostEqual(ph.solve("ohm", {"U": 12, "I": 0.5})[1][0], 24.0)
        self.assertAlmostEqual(ph.solve("s_ut", {"s": 100, "u": 0, "a": 2})[1][0], 10.0)
        t = ph.solve("s_ut", {"s": 10, "u": 20, "a": -9.81})[1]
        self.assertEqual(len(t), 2)

    def test_input_errors(self):
        with self.assertRaises(ValueError):
            ph.solve("newton2", {"m": 1})
        with self.assertRaises(ValueError):
            ph.solve("newton2", {"m": -1, "a": 1})


class TestRegexLab(unittest.TestCase):
    def test_explain(self):
        lines = rl.explain(r"^\d{3}-[a-z]+$")
        self.assertTrue(lines[0].startswith("^"))
        self.assertIn("3 مرّات بالضبط", lines[1])
        self.assertTrue(any("من a إلى z" in l for l in lines))

    def test_matches(self):
        ms = rl.test(r"(\d+)-(\d+)", "a 12-34 b 5-6")
        self.assertEqual([m.text for m in ms], ["12-34", "5-6"])
        self.assertEqual(ms[0].groups, ("12", "34"))
        self.assertEqual(rl.substitute(r"\s+", " ", "a   b")[0], "a b")

    def test_bad_pattern(self):
        with self.assertRaises(ValueError):
            rl.test("(a", "x")

    def test_exercises_are_solvable(self):
        sols = [r"\d+", r"\d{5}", "[A-Z][a-z]*", r"\d{3}-\d{4}", "(نعم|لا)",
                r"[\w.]+@\w+\.\w+", "[ء-ي]+", r"(14|20)\d{2}"]
        for ex, sol in zip(rl.EXERCISES, sols):
            self.assertTrue(rl.check_exercise(ex, sol)[0], ex.title)
            self.assertFalse(rl.check_exercise(ex, ".*")[0], ex.title)


class TestTextStats(unittest.TestCase):
    def test_counts(self):
        a = ts.analyse("الطالب يكتب. الطالب يقرأ!\n\nثم ينام.")
        self.assertEqual(a["words"], 6)
        self.assertEqual(a["sentences"], 3)
        self.assertEqual(a["paragraphs"], 2)
        self.assertEqual(ts.analyse("كَتَبَ")["diacritics"], 3)

    def test_report(self):
        self.assertTrue(ts.report("نص قصير جدا"))
        with self.assertRaises(ValueError):
            ts.report("   ")


class TestWordSearch(unittest.TestCase):
    def test_words_are_in_grid(self):
        for seed in range(25):
            for level in ws.LEVELS:
                p = ws.generate(level, random.choice(list(ws.THEMES)), random.Random(seed))
                self.assertGreaterEqual(len(p.words), 3)
                for w in p.words:
                    self.assertEqual(p.letters_between(w.start, w.end), ws._norm(w.word))

    def test_claim_and_complete(self):
        p = ws.generate("easy", "food", random.Random(4))
        self.assertIsNone(p.claim((0, 0), (0, 0)) if p.words[0].start != (0, 0) else None)
        for w in p.words:
            self.assertIsNotNone(p.claim(w.end, w.start))
        self.assertTrue(p.complete)
        self.assertIsNone(p.hint())

    def test_rtl_reading(self):
        p = ws.generate("medium", "school", random.Random(2))
        for w in p.words:
            if w.direction == (0, -1):
                self.assertIn(ws._norm(w.word), p.row_text(w.start[0]).replace(" ", ""))
        self.assertEqual(p.col_no(p.size - 1), 1)


if __name__ == "__main__":
    unittest.main()
