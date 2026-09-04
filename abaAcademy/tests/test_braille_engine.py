# -*- coding: utf-8 -*-
"""Tests for the Arabic braille engine. The dot patterns are checked against the
authoritative Unified Arabic Braille standard (via liblouis), because a wrong
cell taught to a blind learner is actively harmful."""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.braille_engine.arabic_braille import (
    ArabicBraille, ARABIC_LETTERS, NUMBER_SIGN, dots_to_unicode, cell,
)


class TestArabicBraille(unittest.TestCase):
    def setUp(self):
        self.ab = ArabicBraille()

    def test_core_letters(self):
        # spot-check against the Unified Arabic Braille standard
        self.assertEqual(ARABIC_LETTERS["ا"], cell(1))
        self.assertEqual(ARABIC_LETTERS["ب"], cell(1, 2))
        self.assertEqual(ARABIC_LETTERS["ث"], cell(1, 4, 5, 6))
        self.assertEqual(ARABIC_LETTERS["ص"], cell(1, 2, 3, 4, 6))
        self.assertEqual(ARABIC_LETTERS["ظ"], cell(1, 2, 3, 4, 5, 6))
        self.assertEqual(ARABIC_LETTERS["ق"], cell(1, 2, 3, 4, 5))
        self.assertEqual(ARABIC_LETTERS["ي"], cell(2, 4))

    def test_all_28_letters_present(self):
        for ch in "ابتثجحخدذرزسشصضطظعغفقكلمنهوي":
            self.assertIn(ch, ARABIC_LETTERS, f"missing letter {ch}")

    def test_no_letter_collisions(self):
        # every base letter should have a distinct cell (the 28 core letters)
        core = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"
        patterns = [ARABIC_LETTERS[c] for c in core]
        self.assertEqual(len(patterns), len(set(patterns)),
                         "two core letters share a braille cell")

    def test_roundtrip_letter(self):
        for ch in "ابتثجحxخدذرزسشصضطظعغفقكلمنهوي":
            if ch in ARABIC_LETTERS:
                back = self.ab.cell_to_letter(ARABIC_LETTERS[ch])
                self.assertEqual(back, ch)

    def test_word_to_cells(self):
        cells = self.ab.text_to_cells("باب")
        flat = [c for _, cs in cells for c in cs]
        self.assertEqual(flat, [cell(1, 2), cell(1), cell(1, 2)])

    def test_digit_needs_number_sign(self):
        cells = self.ab._char_cells("5")
        self.assertEqual(cells[0], NUMBER_SIGN)
        self.assertEqual(cells[1], cell(1, 5))

    def test_unicode_glyph(self):
        # dot 1 -> U+2801
        self.assertEqual(dots_to_unicode(cell(1)), "\u2801")
        self.assertEqual(dots_to_unicode(cell(1, 2)), "\u2803")

    def test_name_for_cell(self):
        self.assertEqual(self.ab.name_for_cell(cell(1)), "حرف ا")
        self.assertEqual(self.ab.name_for_cell(NUMBER_SIGN), "علامة الرقم")
        self.assertEqual(self.ab.name_for_cell(cell()), "خلية فارغة")

    def test_grade2_wordsign(self):
        cells = self.ab.text_to_cells("من", grade2=True)
        # "من" should become a single contracted cell
        flat = [c for _, cs in cells for c in cs]
        self.assertEqual(len(flat), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
