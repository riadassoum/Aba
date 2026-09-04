# -*- coding: utf-8 -*-
"""Tests for the V2 STEM math engine: safe evaluation, LaTeX->Arabic speech,
and function sonification/feature-detection. Runs without wx or an audio device.
"""

import os
import sys
import unittest

# allow running both as a module and directly
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.math_engine.safe_eval import SafeFunction
from abaAcademy.math_engine.latex_arabic import latex_to_arabic, mathml_to_arabic
from abaAcademy.math_engine.sonification import FunctionSonifier


class TestSafeEval(unittest.TestCase):
    def test_basic(self):
        f = SafeFunction("x^2 + 3*x - 5")
        self.assertAlmostEqual(f(2), 5.0)
        self.assertAlmostEqual(f(0), -5.0)

    def test_functions_and_constants(self):
        self.assertAlmostEqual(SafeFunction("sqrt(x)")(9), 3.0)
        self.assertAlmostEqual(SafeFunction("cos(x)")(0), 1.0)
        self.assertAlmostEqual(SafeFunction("2*pi")(0), 6.283185, places=4)

    def test_undefined_returns_none(self):
        self.assertIsNone(SafeFunction("1/x")(0))
        self.assertIsNone(SafeFunction("sqrt(x)")(-1))
        self.assertIsNone(SafeFunction("log(x)")(-1))

    def test_security_rejections(self):
        for bad in ["__import__('os')", "x.__class__", "open('f')",
                    "lambda: 1", "[i for i in x]", "x if x else 0"]:
            with self.assertRaises(ValueError):
                SafeFunction(bad)

    def test_syntax_error(self):
        with self.assertRaises(ValueError):
            SafeFunction("x +")


class TestLatexArabic(unittest.TestCase):
    def test_fraction(self):
        out = latex_to_arabic(r"\frac{1}{2}")
        self.assertIn("كسر", out)
        self.assertIn("بسطه", out)
        self.assertIn("مقامه", out)

    def test_power_squared(self):
        self.assertIn("تربيع", latex_to_arabic("x^2"))
        self.assertIn("تكعيب", latex_to_arabic("x^3"))

    def test_sqrt(self):
        self.assertIn("الجذر التربيعي", latex_to_arabic(r"\sqrt{x}"))
        self.assertIn("النوني", latex_to_arabic(r"\sqrt[3]{8}"))

    def test_integral_bounds(self):
        out = latex_to_arabic(r"\int_{0}^{1} x^2 dx")
        self.assertIn("تكامل", out)
        self.assertIn("من 0", out)
        self.assertIn("إلى 1", out)

    def test_greek_and_symbols(self):
        self.assertIn("ألفا", latex_to_arabic(r"\alpha"))
        self.assertIn("ما لا نهاية", latex_to_arabic(r"\infty"))
        self.assertIn("أصغر من أو يساوي", latex_to_arabic(r"\leq"))

    def test_never_raises(self):
        # odd input should degrade, not crash
        for junk in ["", r"\unknowncmd{", r"}}}{{", r"\frac{1}"]:
            latex_to_arabic(junk)   # must not raise

    def test_mathml(self):
        ml = "<math><mfrac><mn>1</mn><mn>2</mn></mfrac></math>"
        self.assertIn("كسر", mathml_to_arabic(ml))


class TestSonification(unittest.TestCase):
    def test_parabola_roots(self):
        son = FunctionSonifier("x^2 - 4", x_min=-5, x_max=5, points=200)
        son.analyse()
        zeros = [s.x for s in son.samples if s.feature == "zero"]
        # two roots near -2 and +2
        self.assertEqual(len(zeros), 2)
        self.assertTrue(any(abs(z + 2) < 0.3 for z in zeros))
        self.assertTrue(any(abs(z - 2) < 0.3 for z in zeros))

    def test_sine_features(self):
        son = FunctionSonifier("sin(x)", x_min=-6.2832, x_max=6.2832, points=200)
        son.analyse()
        maxima = [s for s in son.samples if s.feature == "max"]
        minima = [s for s in son.samples if s.feature == "min"]
        self.assertEqual(len(maxima), 2)
        self.assertEqual(len(minima), 2)

    def test_asymptote_break(self):
        son = FunctionSonifier("1/x", x_min=-3, x_max=3, points=61)
        son.analyse()
        breaks = [s for s in son.samples if s.feature == "break"]
        self.assertGreaterEqual(len(breaks), 1)

    def test_render_produces_audio(self):
        son = FunctionSonifier("x", x_min=-5, x_max=5, points=50)
        son.analyse()
        pcm = son.render_sweep(duration=1.0)
        self.assertGreater(len(pcm), 1000)      # real PCM bytes
        self.assertEqual(len(pcm) % 4, 0)        # stereo 16-bit alignment

    def test_describe_and_summary(self):
        son = FunctionSonifier("x^2 - 4", x_min=-5, x_max=5, points=50)
        son.analyse()
        self.assertIn("إكس", son.describe_point(0))
        self.assertIn("الدالة", son.summary())


if __name__ == "__main__":
    unittest.main(verbosity=2)
