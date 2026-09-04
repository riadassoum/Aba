# -*- coding: utf-8 -*-
"""Tests for the Python curriculum: structure, that every worked example runs and
matches its stated output, and that every challenge a unit references actually
exists and its grader accepts a correct reference solution."""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.codelab import curriculum as cur
from abaAcademy.codelab.sandbox import run_code
from abaAcademy.codelab.challenges import get_challenge, check_solution, CHALLENGES


class TestStructure(unittest.TestCase):
    def test_six_levels(self):
        self.assertEqual(len(cur.all_levels()), 6)

    def test_units_have_titles_and_bodies(self):
        for lv in cur.all_levels():
            self.assertTrue(lv.units)
            for u in lv.units:
                self.assertTrue(u.title)
                self.assertTrue(u.body)

    def test_unique_unit_ids(self):
        ids = [u.uid for lv in cur.all_levels() for u in lv.units]
        self.assertEqual(len(ids), len(set(ids)))

    def test_progression_levels_present(self):
        keys = [lv.key for lv in cur.all_levels()]
        for expected in ["beginner", "control", "data", "functions",
                         "advanced", "expert"]:
            self.assertIn(expected, keys)


class TestExamplesRun(unittest.TestCase):
    def test_every_example_runs_and_matches(self):
        for lv in cur.all_levels():
            for u in lv.units:
                if not u.example:
                    continue
                if u.example_output.startswith("("):
                    continue          # interactive/dependent output
                if u.note and "functools" in u.note:
                    continue          # intentionally read-only (needs functools)
                r = run_code(u.example, timeout=5)
                self.assertIsNone(r.error, f"{u.uid}: {r.error}")
                self.assertEqual((r.output or "").strip(),
                                 u.example_output.strip(), u.uid)


class TestChallengeLinks(unittest.TestCase):
    def test_referenced_challenges_exist(self):
        for lv in cur.all_levels():
            for u in lv.units:
                for cid in u.challenges:
                    self.assertIsNotNone(get_challenge(cid),
                                         f"{u.uid} references missing {cid}")

    def test_every_challenge_solvable(self):
        # a correct reference solution per challenge id
        refs = {
            "c01": 'print("مرحبا بالعالم")',
            "c02": 'age = 15\nprint(age)',
            "c03": 'print(7 + 8)',
            "c04": 'def is_even(n):\n    return n % 2 == 0',
            "c05": 'for i in range(1, 6):\n    print(i)',
            "c06": 'def sum_to(n):\n    return sum(range(1, n+1))',
            "c07": 'def biggest(l):\n    return max(l)',
            "c08": 'def count_char(t, c):\n    return t.count(c)',
            "c09": 'def reverse_text(t):\n    return t[::-1]',
            "c10": 'def is_prime(n):\n    if n < 2: return False\n    for i in range(2, n):\n        if n % i == 0: return False\n    return True',
            "c11": 'def capital_of(d, c):\n    return d.get(c, "غير معروف")',
            "c12": 'def unique_count(l):\n    return len(set(l))',
            "c13": 'def factorial(n):\n    return 1 if n <= 1 else n * factorial(n-1)',
            "c14": 'def squares(n):\n    return [i*i for i in range(1, n+1)]',
            "c15": 'def safe_div(a, b):\n    try:\n        return a / b\n    except ZeroDivisionError:\n        return "خطأ"',
            "c16": 'class Counter:\n    def __init__(self):\n        self.n = 0\n    def add(self):\n        self.n += 1\n    def value(self):\n        return self.n\ndef test_counter():\n    c = Counter()\n    c.add(); c.add()\n    return c.value()',
            "c17": 'def by_length(w):\n    return sorted(w, key=len)',
            "c18": 'def double_result(fn):\n    def w(*a):\n        return fn(*a) * 2\n    return w\n@double_result\ndef add(a, b):\n    return a + b',
            "c19": 'def binary_search(arr, t):\n    lo, hi = 0, len(arr)-1\n    while lo <= hi:\n        m = (lo+hi)//2\n        if arr[m] == t: return m\n        if arr[m] < t: lo = m+1\n        else: hi = m-1\n    return -1',
            "c20": 'def product(l):\n    r = 1\n    for x in l:\n        r *= x\n    return r',
        }
        for c in CHALLENGES:
            self.assertIn(c.cid, refs, f"no reference solution for {c.cid}")
            ok, msg = check_solution(c, refs[c.cid])
            self.assertTrue(ok, f"{c.cid} rejected correct solution: {msg}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
