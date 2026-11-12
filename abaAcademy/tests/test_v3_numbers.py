# -*- coding: utf-8 -*-
"""Tests for the sorting/searching narrator and number theory."""

import math
import os
import random
import sys
import unittest
from fractions import Fraction

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.codelab import algorithms as al
from abaAcademy.math_engine import number_theory as nt


class TestAlgorithms(unittest.TestCase):
    def test_all_sorts_sort(self):
        rng = random.Random(1)
        for _ in range(40):
            xs = [rng.randint(-20, 20) for _ in range(rng.randint(1, 15))]
            for key, (_, fn, _) in al.SORTS.items():
                run = fn(xs)
                self.assertEqual(run.result, sorted(xs), key)
                self.assertTrue(run.summary())

    def test_known_costs(self):
        self.assertEqual(al.bubble([1, 2, 3, 4]).comparisons, 3)        # early exit
        self.assertEqual(al.selection([4, 3, 2, 1]).comparisons, 6)
        self.assertEqual(al.insertion([1, 2, 3]).moves, 0)

    def test_search(self):
        xs = [9, 4, 7, 1]
        self.assertIn("وجدته", al.linear_search(xs, 7).steps[-1])
        self.assertIn("لم أجد", al.linear_search(xs, 5).steps[-1])
        b = al.binary_search(list(range(100)), 73)
        self.assertLessEqual(b.comparisons, 7)
        self.assertIn("وجدته", b.steps[-1])

    def test_parse(self):
        self.assertEqual(al.parse_list("٣، 1 2"), [3, 1, 2])
        with self.assertRaises(ValueError):
            al.parse_list("1 x")
        with self.assertRaises(ValueError):
            al.parse_list(" ".join(["1"] * 41))


class TestNumberTheory(unittest.TestCase):
    def test_factorize(self):
        for n in range(2, 3000):
            f = nt.factorize(n)
            self.assertEqual(math.prod(p ** e for p, e in f.items()), n)
            self.assertTrue(all(nt.is_prime(p)[0] for p in f))
        self.assertEqual(nt.factor_text(nt.factorize(360)), "2³ × 3² × 5")

    def test_primes(self):
        ps = nt.primes_up_to(100)
        self.assertEqual(len(ps), 25)
        self.assertEqual([n for n in range(1, 101) if nt.is_prime(n)[0]], ps)

    def test_gcd_lcm(self):
        rng = random.Random(2)
        for _ in range(100):
            a, b = rng.randint(1, 5000), rng.randint(1, 5000)
            self.assertEqual(nt.gcd_steps(a, b)[0], math.gcd(a, b))
            self.assertEqual(nt.lcm_steps(a, b)[0], a * b // math.gcd(a, b))

    def test_divisibility_rules_agree(self):
        for n in (1716, 2520, 9999, 123456, 7):
            lines = nt.divisibility(n)
            for d, line in zip((2, 3, 4, 5, 6, 8, 9, 10, 11), lines):
                says_yes = not any(neg in line for neg in ("لا يقبل", "لا تقبل", "فلا يقبل"))
                self.assertEqual(says_yes, n % d == 0, (n, d, line))

    def test_properties(self):
        self.assertTrue(any("تامّ" in x for x in nt.properties(496)))
        self.assertTrue(any("مربّع" in x for x in nt.properties(49)))
        self.assertTrue(any("فيبوناتشي" in x for x in nt.properties(21)))
        self.assertEqual(nt.divisors(12), [1, 2, 3, 4, 6, 12])

    def test_probability(self):
        self.assertEqual(nt.dice_sum_probability(7)[0], Fraction(1, 6))
        self.assertEqual(nt.dice_sum_probability(3, 1)[0], Fraction(1, 6))
        self.assertEqual(nt.coins_probability(2, 3)[0], Fraction(3, 8))
        self.assertEqual(nt.bag_probability(3, 10, 2)[0], Fraction(1, 15))
        self.assertEqual(nt.combinations(5, 2)[0], 10)
        self.assertEqual(nt.permutations(5, 2)[0], 20)
        self.assertEqual(nt.factorial_steps(5)[0], 120)
        with self.assertRaises(ValueError):
            nt.combinations(2, 5)


if __name__ == "__main__":
    unittest.main()
