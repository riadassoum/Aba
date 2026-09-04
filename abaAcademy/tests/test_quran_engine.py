# -*- coding: utf-8 -*-
"""Tests for the Qur'an morphology root-search and the rule-based Tajweed
detector, run against the real bundled data."""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.quran_engine.morpho_search import MorphologySearch, _strip_diacritics
from abaAcademy.quran_engine.tajweed import analyse_ayah, rules_summary, earcon

_RES = os.path.abspath(os.path.join(_HERE, "..", "resources"))


class TestMorphology(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ms = MorphologySearch(_RES)

    def test_root_rahima_occurrences(self):
        occ = self.ms.search_root("رحم")
        # the root ر-ح-م is very frequent; sanity-bound it
        self.assertGreater(len(occ), 100)

    def test_derived_forms(self):
        forms = self.ms.derived_forms("رحم")
        self.assertGreater(len(forms), 10)
        # every form should carry a count and a first location
        for f in forms:
            self.assertIn("count", f)
            self.assertIn("first", f)

    def test_undiacritized_search(self):
        # searching without diacritics should still find the root
        self.assertEqual(len(self.ms.search_root("علم")),
                         self.ms.root_count("علم"))
        self.assertGreater(self.ms.root_count("علم"), 100)

    def test_nonexistent_root(self):
        self.assertEqual(self.ms.search_root("زقظ"), [])
        self.assertIn("لم يُعثر", self.ms.summary_for_root("زقظ"))

    def test_location_name(self):
        name = self.ms.location_name(1, 1)
        self.assertIn("الآية 1", name)

    def test_strip_diacritics(self):
        self.assertEqual(_strip_diacritics("ٱلرَّحْمَٰنِ"), _strip_diacritics("الرحمن"))


class TestTajweed(unittest.TestCase):
    def test_sun_letter_detected(self):
        # الرحمن has a sun-letter lam before ر
        hits = analyse_ayah("ٱلرَّحْمَٰنِ")
        self.assertTrue(any(h.kind == "sun" for h in hits))

    def test_divine_name_not_sun_letter(self):
        # الله must not be flagged as a sun-letter case
        hits = analyse_ayah("ٱللَّهِ")
        self.assertFalse(any(h.kind == "sun" for h in hits))

    def test_ghunnah_detected(self):
        hits = analyse_ayah("إِنَّ")     # noon with shadda
        self.assertTrue(any(h.kind == "ghunnah" for h in hits))

    def test_empty_when_no_rules(self):
        hits = analyse_ayah("هُوَ")
        self.assertIn("لا توجد", rules_summary(hits))

    def test_earcons_generate(self):
        for kind in ("qalqalah", "ghunnah", "madd", "sun"):
            self.assertGreater(len(earcon(kind)), 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
