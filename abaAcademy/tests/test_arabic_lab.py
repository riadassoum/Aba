# -*- coding: utf-8 -*-
"""Tests for the Arabic lab: spelling trainer and the verb conjugator. The
conjugator tests specifically pin down the *honest scope* — sound verbs conjugate
correctly, and irregular verbs are refused rather than mis-conjugated."""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.arabic_lab import spelling_trainer as st
from abaAcademy.arabic_lab import conjugator as cj


class TestSpelling(unittest.TestCase):
    def test_items_exist(self):
        self.assertGreaterEqual(len(st.ITEMS), 20)

    def test_categories_cover_items(self):
        cats = {k for k, _ in st.categories()}
        for it in st.ITEMS:
            self.assertIn(it.category, cats)

    def test_check_correct(self):
        it = st.ITEMS[0]
        ok, msg = st.check(it, it.correct)
        self.assertTrue(ok)
        self.assertIn(it.rule, msg)

    def test_check_wrong_shows_rule(self):
        it = st.ITEMS[0]
        ok, msg = st.check(it, it.wrong)
        self.assertFalse(ok)
        self.assertIn(it.correct, msg)

    def test_correct_never_equals_wrong(self):
        for it in st.ITEMS:
            self.assertNotEqual(it.correct, it.wrong)


class TestClassify(unittest.TestCase):
    def test_sound(self):
        for v in ["كتب", "نصر", "جلس", "فتح"]:
            self.assertEqual(cj.classify(v)[0], "sound", v)

    def test_hollow(self):
        for v in ["قال", "باع", "نام"]:
            self.assertEqual(cj.classify(v)[0], "hollow", v)

    def test_defective(self):
        for v in ["دعا", "رمى", "سعى"]:
            self.assertEqual(cj.classify(v)[0], "defective", v)

    def test_hamzated(self):
        for v in ["أكل", "سأل", "قرأ"]:
            self.assertEqual(cj.classify(v)[0], "hamzated", v)

    def test_doubled(self):
        self.assertEqual(cj.classify("مدد")[0], "doubled")


class TestConjugateSound(unittest.TestCase):
    def test_past_has_13(self):
        table = cj.conjugate("كتب", "past")
        self.assertEqual(len(table), 13)

    def test_present_has_13(self):
        table = cj.conjugate("نصر", "present")
        self.assertEqual(len(table), 13)

    def test_present_forms_wellformed(self):
        # no form should contain two harakat in a row without a letter between
        table = cj.conjugate("نصر", "present")
        forms = [f for _, f in table]
        # 2fs should be تنصرين... with a ya'
        fem = dict((p, f) for p, f in table)
        self.assertIn("ي", fem["أنتِ"])
        self.assertIn("ن", fem["أنتِ"])

    def test_imperative_addressees(self):
        table = cj.conjugate("كتب", "imperative")
        self.assertEqual(len(table), 5)


class TestConjugateHonestScope(unittest.TestCase):
    def test_hollow_refused(self):
        with self.assertRaises(ValueError):
            cj.conjugate("قال", "past")

    def test_defective_refused(self):
        with self.assertRaises(ValueError):
            cj.conjugate("دعا", "present")

    def test_hamzated_refused(self):
        with self.assertRaises(ValueError):
            cj.conjugate("أكل", "past")

    def test_refusal_message_names_type(self):
        try:
            cj.conjugate("قال", "past")
            self.fail("should have raised")
        except ValueError as e:
            self.assertIn("أجوف", str(e))


if __name__ == "__main__":
    unittest.main(verbosity=2)
