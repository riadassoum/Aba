# -*- coding: utf-8 -*-
"""Tests for the spreadsheet, execution tracer, Arabic number rules, escape
room, school calculators and Arabic count agreement."""

import datetime
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.tools import sheet as sh, school_calc as sc
from abaAcademy.tools.ar_count import count
from abaAcademy.codelab import tracer
from abaAcademy.arabic_lab import number_rules as nr
from abaAcademy.puzzles import escape_room as er


class TestSheet(unittest.TestCase):
    def setUp(self):
        self.s = sh.Sheet(30, 8)
        for i, v in enumerate([70, 45, 90, 55]):
            self.s.set(i, 0, str(v))

    def test_functions_arabic_and_english(self):
        s = self.s
        for f, want in (("=مجموع(A1:A4)", 260), ("=SUM(A1:A4)", 260), ("=متوسط(A1:A4)", 65),
                        ("=أكبر(A1:A4)", 90), ("=MIN(A1:A4)", 45), ("=عدد(A1:A4)", 4),
                        ("=وسيط(A1:A4)", 62.5), ("=عد_إذا(A1:A4، \">=50\")", 3),
                        ("=مجموع_إذا(A1:A4، \">60\")", 160), ("=تقريب(10/3، 2)", 3.33),
                        ("=جذر(16)+أس(2،3)", 12), ("=باقي(7، 3)", 1), ("=2^3*(1+1)", 16)):
            s.set(10, 1, f)
            self.assertAlmostEqual(s.value(10, 1), want, places=6, msg=f)

    def test_if_and_text(self):
        self.s.set(0, 1, '=إذا(A1>=50، "ناجح"، "راسب")')
        self.s.set(1, 1, '=IF(A2>=50, "ناجح", "راسب")')
        self.assertEqual(self.s.value(0, 1), "ناجح")
        self.assertEqual(self.s.value(1, 1), "راسب")
        self.s.set(2, 1, '="العلامة "&A3')
        self.assertEqual(self.s.value(2, 1), "العلامة 90")

    def test_recalc_and_undo(self):
        self.s.set(5, 0, "=مجموع(A1:A4)")
        self.s.set(0, 0, "100")
        self.assertEqual(self.s.value(5, 0), 290)
        self.assertEqual(self.s.dependents(0, 0), ["A6"])
        self.assertTrue(self.s.undo())
        self.assertEqual(self.s.value(5, 0), 260)

    def test_errors(self):
        for f, code in (("=A1/0", "#قسمة_على_صفر"), ("=foo(1)", "#اسم"), ("=1+", "#صيغة"),
                        ("=جذر(-1)", "#قيمة"), ('=A1+"x"', "#قيمة")):
            self.s.set(12, 2, f)
            self.assertEqual(self.s.display(12, 2), code, f)
        self.s.set(13, 2, "=C15")
        self.s.set(14, 2, "=C14")
        self.assertEqual(self.s.display(13, 2), "#دوري")

    def test_fill_down_and_csv(self):
        self.s.set(0, 3, "=A1*2")
        self.assertEqual(self.s.fill_down(0, 3, 3), 3)
        self.assertEqual(self.s.raw(3, 3), "=A4*2")
        self.assertEqual(self.s.value(3, 3), 110)
        self.s.set(0, 4, "=$A$1+A1")
        self.s.fill_down(0, 4, 1)
        self.assertEqual(self.s.raw(1, 4), "=$A$1+A2")
        other = sh.Sheet(30, 8)
        other.load_csv(self.s.to_csv())
        self.assertEqual(other.value(3, 3), 110)

    def test_addresses(self):
        self.assertEqual(sh.parse_addr("c7"), (6, 2))
        self.assertEqual(sh.addr(6, 2), "C7")
        with self.assertRaises(ValueError):
            sh.parse_addr("7C")

    def test_percent_and_arabic_digits(self):
        self.s.set(20, 0, "٥٠")
        self.s.set(21, 0, "=A21*10%")
        self.assertAlmostEqual(self.s.value(21, 0), 5)


class TestTracer(unittest.TestCase):
    def test_loop_values(self):
        t = tracer.trace(tracer.SAMPLES[0][1])
        self.assertIsNone(t.error)
        self.assertEqual(t.output.strip(), "15")
        changes = [c for s in t.steps for c in s.changes]
        self.assertIn("صار total = 15", changes)
        self.assertEqual(t.line_counts()[3], 5)

    def test_functions(self):
        t = tracer.trace(tracer.SAMPLES[1][1])
        kinds = [s.kind for s in t.steps]
        self.assertIn("call", kinds)
        self.assertIn("return", kinds)
        ret = next(s for s in t.steps if s.kind == "return")
        self.assertIn("24", ret.spoken())
        print_step = [s for s in t.steps if s.kind == "line" and s.line == 7][0]
        self.assertEqual(print_step.output.strip(), "24")

    def test_infinite_loop_stops(self):
        t = tracer.trace("while True:\n    x = 1\n", max_steps=100)
        self.assertTrue(t.stopped)
        self.assertLessEqual(len(t.steps), 100)

    def test_errors_and_sandbox(self):
        t = tracer.trace("x = 1\ny = x / 0\n")
        self.assertIsNotNone(t.error)
        self.assertEqual(t.steps[-1].kind, "exception")
        self.assertIsNotNone(tracer.trace("print('a'").error)
        t = tracer.trace("import os\n")
        self.assertIsNotNone(t.error)

    def test_input_and_samples(self):
        t = tracer.trace("name = input()\nprint(name)\n", input_lines=["سارة"])
        self.assertEqual(t.output.strip(), "سارة")
        for name, src in tracer.SAMPLES:
            self.assertIsNone(tracer.trace(src).error, name)


class TestNumberRules(unittest.TestCase):
    def setUp(self):
        self.m = next(n for n in nr.NOUNS if n.singular == "كتاب")
        self.f = next(n for n in nr.NOUNS if n.singular == "قصة")

    def test_table(self):
        expect = {
            1: ("كتاب واحد", "قصة واحدة"), 2: ("كتابان اثنان", "قصتان اثنتان"),
            3: ("ثلاثة كتب", "ثلاث قصص"), 8: ("ثمانية كتب", "ثماني قصص"),
            10: ("عشرة كتب", "عشر قصص"), 11: ("أحد عشر كتابًا", "إحدى عشرة قصةً"),
            12: ("اثنا عشر كتابًا", "اثنتا عشرة قصةً"), 15: ("خمسة عشر كتابًا", "خمس عشرة قصةً"),
            20: ("عشرون كتابًا", "عشرون قصةً"), 21: ("واحد وعشرون كتابًا", "إحدى وعشرون قصةً"),
            22: ("اثنان وعشرون كتابًا", "اثنتان وعشرون قصةً"), 37: ("سبعة وثلاثون كتابًا", "سبع وثلاثون قصةً"),
            100: ("مئة كتاب", "مئة قصة"), 200: ("مئتا كتاب", "مئتا قصة"), 1000: ("ألف كتاب", "ألف قصة"),
        }
        for n, (m, f) in expect.items():
            self.assertEqual(nr.number_phrase(n, self.m), m, n)
            self.assertEqual(nr.number_phrase(n, self.f), f, n)

    def test_questions(self):
        import random
        rng = random.Random(3)
        for band in ("all", "1-10", "11-19", "20-99", "100+"):
            for _ in range(30):
                q = nr.number_question(rng, band)
                self.assertIn(q.answer, q.options)
                self.assertEqual(len(set(q.options)), len(q.options))
                self.assertGreaterEqual(len(q.options), 3)

    def test_lam(self):
        self.assertEqual(nr.lam_kind("الشمس"), "sun")
        self.assertEqual(nr.lam_kind("القمر"), "moon")
        self.assertEqual(nr.lam_kind("والليل"), "sun")
        self.assertEqual(nr.lam_kind("بالكتاب"), "moon")
        self.assertEqual(len(nr.SUN_LETTERS), 14)
        with self.assertRaises(ValueError):
            nr.lam_kind("كتاب")
        for w in nr._WORDS_AFTER_AL:
            nr.lam_kind(w)


class TestEscapeRoom(unittest.TestCase):
    def test_solution_wins(self):
        g = er.new_game()
        for key, code in er.solution_path():
            self.assertNotEqual(g.do(key, code), "هذا غير متاح الآن.", key)
        self.assertTrue(g.won)

    def test_wrong_code_and_locked(self):
        g = er.new_game()
        self.assertEqual(g.do("to_archive"), "هذا غير متاح الآن.")
        self.assertIn("لم ينفتح", g.do("side_door", "111"))
        self.assertEqual(g.wrong_codes, 1)
        self.assertIn("ورقة", g.hint() + g.do("table"))

    def test_every_room_reachable_and_clues_present(self):
        rooms = set(er.LIBRARY.rooms)
        targets = {a.go for r in er.LIBRARY.rooms.values() for a in r.actions if a.go}
        self.assertEqual(rooms - {er.LIBRARY.start}, targets - {er.LIBRARY.start})
        hall = er.LIBRARY.rooms["hall"]
        text = " ".join(a.text for a in hall.actions)
        self.assertIn("أربعة كتب", text)        # first digit of 432
        self.assertIn("الثالثة", text)          # second digit


class TestSchoolCalc(unittest.TestCase):
    def test_average(self):
        subs = sc.parse_subjects("رياضيات 85\nعلوم، 17، 20، 2\nعربي، 72/100")
        avg, gpa, lines = sc.average_report(subs)
        self.assertAlmostEqual(avg, (85 + 85 * 2 + 72) / 4)
        self.assertEqual(sc.letter(91)[0], "A")
        self.assertEqual(sc.letter(59.9)[0], "F")
        with self.assertRaises(ValueError):
            sc.parse_subjects("رياضيات 120")

    def test_scale_20(self):
        subs = sc.parse_subjects("رياضيات، 14، 20، 4\nعربي، 11، 20، 3\nرسم، 18، 20، 1")
        avg, lines = sc.report_20(subs)
        self.assertAlmostEqual(avg, (14 * 4 + 11 * 3 + 18) / 8)
        self.assertEqual(sc.mention_20(16), "ممتاز")
        self.assertEqual(sc.mention_20(9.99), "راسب")
        low, lines = sc.report_20(sc.parse_subjects("أ، 8، 20"))
        self.assertIn("ينقصك 2.00", lines[-1])

    def test_needed(self):
        need, _ = sc.needed_mark(70, 60, 80)
        self.assertAlmostEqual(need, 95)
        self.assertIsNone(sc.needed_mark(40, 90, 80)[0])
        self.assertEqual(sc.needed_mark(95, 90, 80)[0], 0.0)

    def test_dates(self):
        t = sc.date_difference(datetime.date(2026, 1, 31), datetime.date(2026, 10, 23))
        self.assertIn("265 يومًا", t)
        self.assertIn("8 أشهر", t)
        self.assertIn("26 سنة", sc.age_text(datetime.date(2000, 5, 10), datetime.date(2026, 10, 23)))
        with self.assertRaises(ValueError):
            sc.age_text(datetime.date(2030, 1, 1), datetime.date(2026, 1, 1))


class TestCount(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(count(1, "error"), "خطأ واحد")
        self.assertEqual(count(2, "error"), "خطآن")
        self.assertEqual(count(5, "error"), "5 أخطاء")
        self.assertEqual(count(11, "error"), "11 خطأً")
        self.assertEqual(count(105, "day"), "105 أيام")
        self.assertEqual(count(0, "card"), "0 بطاقات")


if __name__ == "__main__":
    unittest.main()
