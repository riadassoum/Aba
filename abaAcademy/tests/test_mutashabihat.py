# -*- coding: utf-8 -*-
"""Tests for the mutashabihat finder. The key guarantee is *correctness*: every
pair must be two verses that really exist in the bundled text, and the reported
difference must match their actual words. We validate against a few well-known
mutashabihat and check the diff alignment precisely."""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.quran_engine.mutashabihat import (
    MutashabihatFinder, _diff_words, _normalise,
)

_RES = os.path.abspath(os.path.join(_HERE, "..", "resources"))


class TestDiffAlignment(unittest.TestCase):
    def test_insertion_detected_once(self):
        # B has an extra word "هم" -> exactly one 'ins', not a cascade
        a = "وهم بالاخره كافرون".split()
        b = "وهم بالاخره هم كافرون".split()
        diffs = _diff_words(a, b)
        ins = [d for d in diffs if d[0] == "ins"]
        self.assertEqual(len(ins), 1)
        self.assertEqual(ins[0][2], "هم")

    def test_substitution(self):
        a = "لا يهدي القوم الكافرين".split()
        b = "لا يهدي القوم الظالمين".split()
        diffs = _diff_words(a, b)
        subs = [d for d in diffs if d[0] == "sub"]
        self.assertEqual(len(subs), 1)
        self.assertEqual((subs[0][1], subs[0][2]), ("الكافرين", "الظالمين"))

    def test_identical_no_diff(self):
        self.assertEqual(_diff_words(["a", "b"], ["a", "b"]), [])


class TestFinder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mf = MutashabihatFinder(_RES)
        cls.pairs = cls.mf.pairs(limit=5000)

    def test_finds_pairs(self):
        self.assertGreater(self.mf.count(), 20)

    def test_all_pairs_are_real_and_nonidentical(self):
        # every pair: two distinct locations, similarity < 1, at least one diff
        for p in self.pairs[:200]:
            self.assertNotEqual((p["a"]["surah"], p["a"]["ayah"]),
                                (p["b"]["surah"], p["b"]["ayah"]))
            self.assertLess(p["similarity"], 1.0)
            self.assertTrue(p["diffs"])

    def test_diff_matches_actual_text(self):
        # the reported diff must be reproducible from the two verses' own words
        for p in self.pairs[:100]:
            wa = _normalise(p["a"]["text"]).split()
            wb = _normalise(p["b"]["text"]).split()
            self.assertEqual(_diff_words(wa, wb), p["diffs"])

    def test_known_araf_hud_pair(self):
        # الأعراف 45 and هود 19 differ only by an inserted هم — a classic case.
        found = None
        for p in self.pairs:
            locs = {(p["a"]["surah"], p["a"]["ayah"]),
                    (p["b"]["surah"], p["b"]["ayah"])}
            if {(7, 45), (11, 19)} == locs:
                found = p
                break
        self.assertIsNotNone(found, "known الأعراف/هود mutashabihat not found")

    def test_description_is_arabic(self):
        if self.pairs:
            desc = self.mf.describe_difference(self.pairs[0])
            self.assertIn("الفرق", desc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
