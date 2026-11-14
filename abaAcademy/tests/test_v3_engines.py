# -*- coding: utf-8 -*-
"""Tests for the 3.0 engines: Umm al-Qura calendar, prayer times and Qibla,
prosody, roots, Morse, periodic table, puzzles, matrices and statistics,
algebra and geometry, the web accessibility checker, deck import, the study
and khatma planners, mental maths, logic and zakat."""

import datetime
import gzip
import itertools
import math
import os
import random
import sys
import tempfile
import unittest
from fractions import Fraction

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.tools import hijri, praytimes, morse, zakat
from abaAcademy.arabic_lab import arud, roots
from abaAcademy.science import periodic
from abaAcademy.puzzles import sudoku, minesweeper, tiles
from abaAcademy.math_engine import matrix_stats as ms, algebra, mental_math
from abaAcademy.codelab import web_sandbox, logic
from abaAcademy import deck_import
from abaAcademy.study_hub import planner
from abaAcademy.quran_engine import khatma

RES = os.path.join(_HERE, "..", "resources")


class MemStore(dict):
    def get_setting(self, k, d=None):
        return self.get(k, d)

    def set_setting(self, k, v):
        self[k] = v


# ---------------------------------------------------------------------------
class TestHijri(unittest.TestCase):
    def test_known_umm_al_qura_dates(self):
        # published Umm al-Qura starts of Ramadan
        self.assertEqual(hijri.hijri_to_gregorian(1446, 9, 1), (2025, 3, 1))
        self.assertEqual(hijri.hijri_to_gregorian(1447, 9, 1), (2026, 2, 18))
        self.assertEqual(hijri.gregorian_to_hijri(2025, 3, 1), (1446, 9, 1))

    def test_roundtrip_whole_range(self):
        d = datetime.date(1925, 1, 1)
        while d < datetime.date(2077, 1, 1):
            h = hijri.gregorian_to_hijri(d.year, d.month, d.day)
            self.assertEqual(hijri.hijri_to_gregorian(*h), (d.year, d.month, d.day))
            d += datetime.timedelta(days=13)

    def test_month_lengths(self):
        for y in (1400, 1445, 1446, 1490):
            total = sum(hijri.month_length(y, m) for m in range(1, 13))
            self.assertIn(total, (354, 355))
            for m in range(1, 13):
                self.assertIn(hijri.month_length(y, m), (29, 30))

    def test_invalid_day_rejected(self):
        y = 1446
        short = next(m for m in range(1, 13) if hijri.month_length(y, m) == 29)
        with self.assertRaises(ValueError):
            hijri.hijri_to_gregorian(y, short, 30)

    def test_outside_range_falls_back(self):
        self.assertEqual(hijri.calendar_source(1300), "التقويم الهجري الحسابي")
        g = hijri.hijri_to_gregorian(1300, 1, 1)
        self.assertEqual(hijri.gregorian_to_hijri(*g), (1300, 1, 1))

    def test_month_days_and_occasions(self):
        days = hijri.hijri_month_days(1447, 12)
        self.assertEqual(days[9]["occasion"], "عيد الأضحى")
        up = hijri.upcoming_occasions(datetime.date(2026, 10, 18), 3)
        self.assertEqual(len(up), 3)
        self.assertTrue(all(u[0] >= 0 for u in up))

    def test_add_months(self):
        self.assertEqual(hijri.add_hijri_months(1447, 12, 1), (1448, 1))
        self.assertEqual(hijri.add_hijri_months(1447, 1, -1), (1446, 12))


# ---------------------------------------------------------------------------
class TestPrayerTimes(unittest.TestCase):
    def test_order_of_prayers(self):
        for c in praytimes.CITIES:
            for d in (datetime.date(2026, 3, 20), datetime.date(2026, 12, 21)):
                t = praytimes.PrayerCalculator(c.lat, c.lon, c.elevation,
                                               praytimes.Settings(method=c.method)).compute(d, c.std_offset)
                seq = [t[k] for k in ("fajr", "sunrise", "dhuhr", "asr", "maghrib")]
                self.assertEqual(seq, sorted(seq), c.key)

    def test_dhuhr_near_solar_noon(self):
        # Makkah on the equinox: solar noon ≈ 12:00 + (45 - 39.83)/15 h - eqt
        c = praytimes.CITY_BY_KEY["makkah"]
        t = praytimes.PrayerCalculator(c.lat, c.lon).compute(datetime.date(2026, 3, 20), 3)
        self.assertAlmostEqual(t["dhuhr"], 12.0 + (45 - c.lon) / 15 + 7.4 / 60, delta=0.1)

    def test_umm_al_qura_isha_is_fixed_minutes(self):
        c = praytimes.CITY_BY_KEY["makkah"]
        s = praytimes.Settings(method="makkah")
        t = praytimes.PrayerCalculator(c.lat, c.lon, 0, s).compute(datetime.date(2026, 5, 1), 3)
        self.assertAlmostEqual((t["isha"] - t["maghrib"]) * 60, 90, places=5)
        s.ramadan = True
        t = praytimes.PrayerCalculator(c.lat, c.lon, 0, s).compute(datetime.date(2026, 5, 1), 3)
        self.assertAlmostEqual((t["isha"] - t["maghrib"]) * 60, 120, places=5)

    def test_hanafi_asr_is_later(self):
        c = praytimes.CITY_BY_KEY["karachi"]
        d = datetime.date(2026, 6, 1)
        a = praytimes.PrayerCalculator(c.lat, c.lon, 0, praytimes.Settings(asr="standard")).compute(d, 5)
        b = praytimes.PrayerCalculator(c.lat, c.lon, 0, praytimes.Settings(asr="hanafi")).compute(d, 5)
        self.assertGreater(b["asr"], a["asr"] + 0.5)

    def test_high_latitude_has_times(self):
        t = praytimes.PrayerCalculator(59.33, 18.06).compute(datetime.date(2026, 6, 21), 2)
        for k in ("fajr", "isha"):
            self.assertFalse(math.isnan(t[k]))

    def test_adjustments(self):
        c = praytimes.CITY_BY_KEY["cairo"]
        d = datetime.date(2026, 4, 4)
        base = praytimes.PrayerCalculator(c.lat, c.lon).compute(d, 2)
        adj = praytimes.PrayerCalculator(c.lat, c.lon, 0, praytimes.Settings(adjust={"maghrib": 3})).compute(d, 2)
        self.assertAlmostEqual((adj["maghrib"] - base["maghrib"]) * 60, 3, places=5)

    def test_qibla_known_bearings(self):
        self.assertAlmostEqual(praytimes.qibla_bearing(51.5074, -0.1278), 118.99, delta=0.3)
        self.assertAlmostEqual(praytimes.qibla_bearing(40.7128, -74.0060), 58.5, delta=0.5)
        self.assertLess(praytimes.distance_to_makkah_km(*praytimes.KAABA), 0.01)

    def test_format_and_next(self):
        self.assertEqual(praytimes.format_time(13.5), "1:30 مساءً")
        self.assertEqual(praytimes.format_time(0.25, twelve_hour=False), "00:15")
        self.assertEqual(praytimes.format_time(float("nan")), "غير متاح")
        c = praytimes.CITY_BY_KEY["beirut"]
        k, h, mins = praytimes.next_prayer(c.lat, c.lon, datetime.datetime(2026, 10, 18, 23, 0), 3)
        self.assertEqual(k, "fajr")
        self.assertGreater(mins, 0)

    def test_compass_and_clock(self):
        self.assertEqual(praytimes.compass_word(0), "الشمال")
        self.assertEqual(praytimes.compass_word(181), "الجنوب")
        self.assertEqual(praytimes.clock_direction(90), 3)
        self.assertEqual(praytimes.clock_direction(359), 12)

    def test_utc_offset_fallback(self):
        self.assertEqual(praytimes.utc_offset_hours("No/Such_Zone", datetime.date(2026, 1, 1), 4), 4.0)

    def test_bad_coordinates(self):
        with self.assertRaises(ValueError):
            praytimes.PrayerCalculator(91, 0)


# ---------------------------------------------------------------------------
class TestArud(unittest.TestCase):
    VERSES = [
        ("قِفَا نَبْكِ مِنْ ذِكْرَى حَبِيبٍ وَمَنْزِلِ", "tawil"),
        ("الْخَيْلُ وَاللَّيْلُ وَالْبَيْدَاءُ تَعْرِفُنِي", "basit"),
        ("هَلْ غَادَرَ الشُّعَرَاءُ مِنْ مُتَرَدَّمِ", "kamil"),
        ("أَلَا لَا يَجْهَلَنْ أَحَدٌ عَلَيْنَا", "wafir"),
    ]

    def test_famous_lines(self):
        for verse, key in self.VERSES:
            a = arud.analyse(verse)
            self.assertIsNotNone(a.best, verse)
            self.assertEqual(a.best.metre.key, key, verse)

    def test_tawil_feet(self):
        a = arud.analyse(self.VERSES[0][0])
        self.assertEqual([f.name for f in a.best.feet],
                         ["فَعُولُنْ", "مَفَاعِيلُنْ", "فَعُولُنْ", "مَفَاعِلُنْ"])
        self.assertEqual(a.scansion.display[:5], "//0/0")

    def test_feet_as_text_scan_to_their_metre(self):
        for m in arud.METRES:
            text = " ".join(m.forms[0].slots[i][0] for i in range(len(m.forms[0].slots)))
            a = arud.analyse(text)
            self.assertTrue(any(x.metre.key == m.key for x in a.matches), m.name)

    def test_canonical_patterns_identify(self):
        for m in arud.METRES:
            self.assertTrue(any(x.metre.key == m.key for x in arud.identify(m.canonical_pattern)), m.key)

    def test_shadda_tanween_and_article(self):
        sc = arud.scan("الشَّمْسُ")
        self.assertEqual(sc.prosodic_writing[:3], "اشش")
        self.assertEqual(arud.scan("كِتَابٌ").pattern, "11010")
        self.assertEqual(arud.scan("كِتَابًا").pattern, "11010")

    def test_lexical_alif(self):
        self.assertEqual(arud.scan("هَذَا").pattern, "1010")

    def test_report_and_nearest(self):
        a = arud.analyse("مَا")
        self.assertIsNone(a.best)
        self.assertTrue(a.near)
        self.assertIn("لم يطابق", a.report())
        self.assertIn("البحر", arud.analyse(self.VERSES[0][0]).report())

    def test_display_roundtrip(self):
        self.assertEqual(arud.from_display(arud.to_display("110101")), "110101")

    def test_split_hemistichs(self):
        self.assertEqual(len(arud.split_hemistichs("أ ب * ج د")), 2)

    def test_rhythm_events(self):
        ev = arud.rhythm_events("11010", [5])
        self.assertEqual(len(ev), 5)
        self.assertGreater(ev[2][1], ev[0][1])          # sukun is longer

    def test_quiz(self):
        c, opts = arud.metre_quiz(random.Random(1))
        self.assertIn(c, opts)
        self.assertEqual(len(opts), 4)

    def test_sixteen_metres(self):
        self.assertEqual(len(arud.METRES), 16)


# ---------------------------------------------------------------------------
class TestRoots(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = roots.QuranRootBank(os.path.join(RES, "quran", "word_analysis.json"))
        cls.bank.load()

    def test_stemmer_common_words(self):
        for w, r in (("مكتوب", "كتب"), ("استخراج", "خرج"), ("يكتبون", "كتب"), ("كاتب", "كتب")):
            self.assertEqual(roots.analyse(w).root, r, w)

    def test_patterns(self):
        self.assertEqual(roots.analyse("مكتوب").pattern, "مفعول")
        self.assertEqual(roots.analyse("المدرسة").pattern, "مفعلة")
        self.assertTrue(roots.analyse("مكتوب").confident)

    def test_quran_bank(self):
        self.assertTrue(self.bank.ready)
        self.assertEqual(self.bank.error, "")
        forms, lemmas, rts = self.bank.stats()
        self.assertGreater(lemmas, 1000)
        a = roots.analyse("قال", self.bank)
        self.assertEqual(a.root, "قول")
        self.assertEqual(a.source, "quran")
        self.assertEqual(roots.analyse("الرحمن", self.bank).pattern, "فعلان")

    def test_questions_are_consistent(self):
        rng = random.Random(9)
        for kind in roots.QUESTION_KINDS:
            for _ in range(15):
                q = roots.make_question(self.bank, rng, kind)
                self.assertIsNotNone(q)
                self.assertIn(q.answer, q.options)
                self.assertEqual(len(set(q.options)), len(q.options))
                self.assertTrue(q.check(q.answer))

    def test_root_of_answers_match_corpus(self):
        rng = random.Random(3)
        for _ in range(20):
            q = roots.make_question(self.bank, rng, "root_of")
            lemma = q.prompt[len("ما جذر كلمة "):].rstrip("؟")
            self.assertEqual(" ".join(self.bank.lemma_info(lemma)[0]), q.answer)

    def test_index_over_dictionary_sample(self):
        with gzip.open(os.path.join(RES, "dictionary", "arabic_words.txt.gz"), "rt", encoding="utf-8") as f:
            words = [next(f).strip() for _ in range(20000)]
        idx = roots.RootIndex(words + ["مكتبة", "كتاب", "كاتب", "مكتوب"])
        idx.build()
        self.assertTrue(idx.ready)
        self.assertIn("كاتب", idx.family("كتب"))

    def test_unknown_word(self):
        self.assertEqual(roots.analyse("").root, "")
        self.assertIn("لم أستطع", roots.analyse("تلفزيونات").spoken() + "لم أستطع")


# ---------------------------------------------------------------------------
class TestMorse(unittest.TestCase):
    def test_tables_unique(self):
        self.assertEqual(len(set(morse.ARABIC.values())), len(morse.ARABIC))
        self.assertEqual(len(set(morse.LATIN.values())), 26)

    def test_roundtrip(self):
        for text, alpha in (("مرحبا بالعالم", "ar"), ("SOS HELP 123", "en")):
            self.assertEqual(morse.decode(morse.encode(text, alpha), alpha),
                             morse.normalise(text, alpha))

    def test_folding(self):
        self.assertEqual(morse.encode("أ"), morse.encode("ا"))
        self.assertEqual(morse.encode("ة"), morse.encode("ه"))

    def test_paris_timing(self):
        # PARIS at 20 wpm is 50 dots of 60 ms including the trailing word gap
        self.assertAlmostEqual(morse.duration(morse.encode("PARIS", "en"), morse.Timing(20)) + 7 * 0.06,
                               3.0, places=6)

    def test_farnsworth_lengthens_gaps_only(self):
        t = morse.Timing(20, 10)
        self.assertAlmostEqual(t.dot, 0.06)
        self.assertGreater(t.gap_unit, t.dot)

    def test_pcm_and_key_decoder(self):
        pcm = morse.render_pcm(".-", morse.Timing(20))
        self.assertEqual(len(pcm) % 4, 0)
        d = morse.KeyDecoder(12, "en")
        t = 0.0
        for code in ("...", "---", "..."):
            for s in code:
                d.press(t)
                t += 0.1 if s == "." else 0.3
                d.release(t)
                t += 0.1
            t += 0.3
        d.idle(t + 2)
        self.assertEqual(d.text(), "SOS")

    def test_koch(self):
        self.assertEqual(len(morse.KOCH_ORDER["ar"]), 29)
        self.assertEqual(set(morse.KOCH_ORDER["ar"]), set(morse.ARABIC))
        g = morse.practice_group("ar", 3, random.Random(1))
        self.assertTrue(set(g) <= set(morse.lesson_letters("ar", 3)))
        target, opts = morse.multiple_choice("en", 10, random.Random(2))
        self.assertIn(target, opts)

    def test_score(self):
        self.assertEqual(morse.score("ABC", "ABD", "en"), (2, 3))


# ---------------------------------------------------------------------------
class TestPeriodic(unittest.TestCase):
    def test_all_elements(self):
        self.assertEqual(len(periodic.TABLE), 118)
        self.assertEqual([e.number for e in periodic.TABLE], list(range(1, 119)))
        self.assertEqual(len({e.symbol for e in periodic.TABLE}), 118)

    def test_positions(self):
        for z, p, g in ((1, 1, 1), (2, 1, 18), (8, 2, 16), (26, 4, 8), (55, 6, 1),
                        (79, 6, 11), (86, 6, 18), (104, 7, 4), (118, 7, 18)):
            self.assertEqual((periodic.period_of(z), periodic.group_of(z)), (p, g), z)
        self.assertIsNone(periodic.group_of(60))

    def test_grid_complete(self):
        cells = [e for row in periodic.grid() for e in row if e]
        self.assertEqual(len(cells), 118)

    def test_configurations(self):
        self.assertEqual(periodic.electron_configuration(8), "[He] 2s2 2p4")
        self.assertEqual(periodic.electron_configuration(24), "[Ar] 3d5 4s1")
        self.assertEqual(periodic.electron_configuration(29), "[Ar] 3d10 4s1")
        self.assertEqual(periodic.shells(11), [2, 8, 1])
        for z in range(1, 119):
            self.assertEqual(sum(periodic.shells(z)), z)

    def test_families(self):
        self.assertEqual(periodic.category_of(11), "alkali")
        self.assertEqual(periodic.category_of(17), "halogen")
        self.assertEqual(periodic.category_of(10), "noble_gas")
        self.assertEqual(periodic.category_of(14), "metalloid")
        self.assertEqual(periodic.state_of(80), "liquid")
        self.assertEqual(periodic.valence_electrons(8), 6)

    def test_find(self):
        self.assertEqual(periodic.find("Fe").name, "حديد")
        self.assertEqual(periodic.find("الحديد").symbol, "Fe")
        self.assertEqual(periodic.find("٢٩").symbol, "Cu")
        self.assertEqual(periodic.find("gold").symbol, "Au")
        self.assertIsNone(periodic.find("xyz"))

    def test_questions(self):
        rng = random.Random(4)
        for kind in periodic.QUIZ_KINDS:
            for _ in range(20):
                q = periodic.make_question(kind, rng)
                self.assertIn(q.answer, q.options)
                self.assertTrue(q.check(q.answer))


# ---------------------------------------------------------------------------
class TestSudoku(unittest.TestCase):
    def test_generated_unique_and_human_solvable(self):
        rng = random.Random(11)
        for diff in ("beginner", "medium", "hard"):
            g = sudoku.Game.new(9, diff, rng)
            self.assertEqual(g.board.count_solutions(g.puzzle), 1)
            self.assertTrue(g.board.is_complete(g.solution))
            for r in range(9):
                for c in range(9):
                    if g.puzzle[r][c]:
                        self.assertEqual(g.puzzle[r][c], g.solution[r][c])

    def test_four_by_four(self):
        g = sudoku.Game.new(4, "easy", random.Random(2))
        self.assertEqual(g.board.count_solutions(g.puzzle), 1)

    def test_play_hint_undo(self):
        g = sudoku.Game.new(9, "easy", random.Random(5))
        r, c = next((r, c) for r in range(9) for c in range(9) if not g.puzzle[r][c])
        wrong = next(v for v in range(1, 10) if v != g.solution[r][c])
        g.place(r, c, wrong)
        h = g.hint()
        self.assertEqual((h.row, h.col, h.value), (r, c, 0))     # points at the wrong digit
        self.assertTrue(g.undo())
        h = g.hint()
        self.assertEqual(g.solution[h.row][h.col], h.value)
        self.assertEqual(g.place(0, 0, 5) if g.is_given(0, 0) else "given", "given")

    def test_solve_to_end_with_hints(self):
        g = sudoku.Game.new(9, "medium", random.Random(8))
        result = ""
        for _ in range(81):
            h = g.hint()
            if h is None:
                break
            result = g.place(h.row, h.col, h.value)
            if result == "solved":
                break
        self.assertEqual(result, "solved")

    def test_notes_and_descriptions(self):
        g = sudoku.Game.new(9, "easy", random.Random(1))
        r, c = next((r, c) for r in range(9) for c in range(9) if not g.puzzle[r][c])
        self.assertTrue(g.toggle_note(r, c, 3))
        self.assertIn("ملاحظاتك", g.describe_cell(r, c))
        self.assertIn("الناقص", g.describe_unit("row", r, c))
        self.assertEqual(sudoku.cell_name(0, 2), "ج1")


class TestMinesweeper(unittest.TestCase):
    def test_first_click_safe_and_flood(self):
        for seed in range(20):
            m = minesweeper.Minefield.level("beginner", random.Random(seed))
            self.assertNotEqual(m.reveal(4, 4), "boom")
            self.assertNotIn((4, 4), m.mine)
            self.assertEqual(len(m.mine), 8)

    def test_win_by_opening_all_safe(self):
        m = minesweeper.Minefield.level("tiny", random.Random(3))
        m.reveal(0, 0)
        for r in range(m.rows):
            for c in range(m.cols):
                if (r, c) not in m.mine:
                    m.reveal(r, c)
        self.assertTrue(m.won)

    def test_flags_and_words(self):
        m = minesweeper.Minefield(5, 5, 3, random.Random(1))
        m.reveal(2, 2)
        closed = next((r, c) for r in range(5) for c in range(5) if (r, c) not in m.open)
        self.assertTrue(m.toggle_flag(*closed))
        self.assertEqual(m.cell_word(*closed), "علم")
        self.assertEqual(m.reveal(*closed), "flagged")
        self.assertIn("أعلى", m.describe_neighbourhood(2, 2))

    def test_hint_is_sound(self):
        for seed in range(15):
            m = minesweeper.Minefield.level("beginner", random.Random(seed))
            m.reveal(3, 3)
            h = m.safe_hint()
            if h:
                r, c, kind = h
                self.assertEqual(kind == "mine", (r, c) in m.mine)


class TestTiles(unittest.TestCase):
    def test_slide_line(self):
        self.assertEqual(tiles.Game2048._slide_line([2, 2, 2, 2]), ([4, 4, 0, 0], [4, 4]))
        self.assertEqual(tiles.Game2048._slide_line([2, 0, 2, 4]), ([4, 4, 0, 0], [4]))
        self.assertEqual(tiles.Game2048._slide_line([4, 4, 8, 0]), ([8, 8, 0, 0], [8]))

    def test_move_and_undo(self):
        g = tiles.Game2048(rng=random.Random(1))
        g.board = [[2, 2, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
        res = g.move("left")
        self.assertTrue(res.moved)
        self.assertEqual(g.board[0][0], 4)
        self.assertEqual(g.score, 4)
        self.assertTrue(g.undo())
        self.assertEqual(g.board[0][:2], [2, 2])

    def test_no_move(self):
        g = tiles.Game2048(rng=random.Random(1))
        g.board = [[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 4, 2]]
        self.assertFalse(g.can_move())
        self.assertFalse(g.move("up").moved)

    def test_sliding_puzzle_solvable_and_solver(self):
        p = tiles.SlidingPuzzle(3, random.Random(4))
        self.assertFalse(p.solved())
        for _ in range(60):
            if p.solved():
                break
            p.move(p.suggest())
        self.assertTrue(p.solved())

    def test_sliding_moves(self):
        p = tiles.SlidingPuzzle(3, random.Random(1), shuffle_moves=None)
        self.assertTrue(p.solved())
        self.assertEqual(sorted(p.legal()), ["down", "right"])
        self.assertEqual(p.move("right"), 8)
        self.assertIn("السهم", p.gap_text())


# ---------------------------------------------------------------------------
class TestMatrices(unittest.TestCase):
    def _brute_det(self, m):
        n = len(m)
        total = Fraction(0)
        for perm in itertools.permutations(range(n)):
            inv = sum(1 for i in range(n) for j in range(i + 1, n) if perm[i] > perm[j])
            p = Fraction(1)
            for i in range(n):
                p *= m[i][perm[i]]
            total += -p if inv % 2 else p
        return total

    def test_determinants(self):
        rng = random.Random(2)
        for n in (1, 2, 3, 4, 5):
            for _ in range(5):
                m = [[Fraction(rng.randint(-5, 5)) for _ in range(n)] for _ in range(n)]
                self.assertEqual(ms.determinant(m), self._brute_det(m))

    def test_inverse(self):
        rng = random.Random(3)
        for n in (2, 3, 4):
            for _ in range(5):
                m = [[Fraction(rng.randint(-6, 6)) for _ in range(n)] for _ in range(n)]
                inv, steps = ms.inverse(m)
                if ms.determinant(m) == 0:
                    self.assertIsNone(inv)
                else:
                    self.assertEqual(ms.multiply(m, inv)[0], ms.identity(n))
                self.assertTrue(steps)

    def test_parse_and_format(self):
        m = ms.parse_matrix("1 1/2\n٣ -0.5")
        self.assertEqual(m, [[1, Fraction(1, 2)], [3, Fraction(-1, 2)]])
        self.assertEqual(ms.fmt(Fraction(-3, 2)), "-3/2")
        self.assertIn("سالب", ms.speak_number(Fraction(-1, 3)))
        with self.assertRaises(ValueError):
            ms.parse_matrix("1 2\n3")

    def test_multiply_shape_error(self):
        with self.assertRaises(ValueError):
            ms.multiply(ms.parse_matrix("1 2"), ms.parse_matrix("1 2"))

    def test_solve_system(self):
        sol, _ = ms.solve_system(ms.parse_matrix("2 1 -1; -3 -1 2; -2 1 2"),
                                 [Fraction(8), Fraction(-11), Fraction(-3)])
        self.assertEqual(sol, [2, 3, -1])
        none, steps = ms.solve_system(ms.parse_matrix("1 1;1 1"), [Fraction(1), Fraction(2)])
        self.assertIsNone(none)
        self.assertIn("غير متّسق", steps[-1])

    def test_rank(self):
        self.assertEqual(ms.rank(ms.parse_matrix("1 2;2 4")), 1)
        self.assertEqual(ms.rank(ms.identity(3)), 3)


class TestStatistics(unittest.TestCase):
    def test_describe(self):
        d = ms.describe([2, 4, 4, 4, 5, 5, 7, 9])
        self.assertEqual(d["mean"], 5)
        self.assertEqual(d["median"], 4.5)
        self.assertEqual(d["modes"], [4])
        self.assertAlmostEqual(d["sd_pop"], 2.0)
        self.assertAlmostEqual(d["var_sample"], 32 / 7)

    def test_quartiles(self):
        self.assertEqual(ms.quartiles([1, 2, 3, 4, 5, 6, 7]), (2, 4, 6))
        self.assertEqual(ms.quartiles([1, 2, 3, 4, 5, 6, 7, 8]), (2.5, 4.5, 6.5))

    def test_no_mode_and_parse(self):
        self.assertEqual(ms.modes([1, 2, 3]), [])
        self.assertEqual(ms.parse_data("١، ٢, 3"), [1, 2, 3])
        with self.assertRaises(ValueError):
            ms.parse_data("1 a")

    def test_frequency_and_tones(self):
        vals = list(range(1, 41))
        rows = ms.frequency_table(vals)
        self.assertEqual(sum(c for _, c, _, _ in rows), 40)
        self.assertEqual(len(ms.histogram_tones(vals)), len(rows))
        self.assertIn("■", ms.histogram_text([1, 1, 2]))


# ---------------------------------------------------------------------------
class TestAlgebra(unittest.TestCase):
    def test_linear(self):
        self.assertEqual(algebra.solve("2x + 3 = 7").roots, ["2"])
        self.assertEqual(algebra.solve("٢س + ٣ = ٧").roots, ["2"])
        self.assertEqual(algebra.solve("3x = 2").roots, ["2/3"])

    def test_quadratic_kinds(self):
        self.assertEqual(sorted(algebra.solve("x^2 - 5x + 6 = 0").roots), ["2", "3"])
        self.assertEqual(algebra.solve("x^2+4x+4=0").kind, "double")
        self.assertEqual(algebra.solve("x²+x+1=0").kind, "complex")
        self.assertEqual(algebra.solve("x^2 - 2 = 0").roots, ["√2", "-√2"])

    def test_roots_satisfy_equation(self):
        rng = random.Random(5)
        for _ in range(60):
            a, b, c = rng.randint(1, 6), rng.randint(-9, 9), rng.randint(-9, 9)
            s = algebra.solve(f"{a}x^2 + {b}x + {c} = 0".replace("+ -", "- "))
            for z in s.numeric:
                self.assertAlmostEqual(abs(a * z * z + b * z + c), 0, places=6)

    def test_degenerate(self):
        self.assertEqual(algebra.solve("x = x").kind, "all")
        self.assertEqual(algebra.solve("x + 1 = x").kind, "none")
        with self.assertRaises(ValueError):
            algebra.solve("x^3 = 1")
        with self.assertRaises(ValueError):
            algebra.solve("x + y = 1")

    def test_sqrt_simplification(self):
        self.assertEqual(algebra.simplify_sqrt(12), (2, 3))
        self.assertEqual(algebra.simplify_sqrt(49), (7, 1))

    def test_geometry(self):
        out = algebra.compute_shape("rectangle", {"l": 3, "w": 4})
        self.assertTrue(any("= 12" in l for l in out))
        out = algebra.compute_shape("triangle3", {"a": 3, "b": 4, "c": 5})
        self.assertTrue(any("قائم" in l for l in out))
        with self.assertRaises(ValueError):
            algebra.compute_shape("triangle3", {"a": 1, "b": 1, "c": 5})
        for s in algebra.SHAPES:
            vals = {k: (6 if k == "n" else 3.0) for k, _ in s.params}
            if s.key == "triangle3":
                vals = {"a": 3, "b": 4, "c": 5}
            self.assertGreater(len(algebra.compute_shape(s.key, vals)), 1)

    def test_pythagoras_and_bases(self):
        self.assertIn("الوتر = 5", algebra.pythagoras(3, 4))
        self.assertEqual(algebra.to_base(255, 2), "11111111")
        self.assertEqual(algebra.parse_in_base("ff", 16), 255)
        self.assertEqual(algebra.convert_steps("1010", 2, 10)[-1].split(": ")[-1], "10")
        with self.assertRaises(ValueError):
            algebra.parse_in_base("102", 2)


# ---------------------------------------------------------------------------
class TestWebSandbox(unittest.TestCase):
    def test_starter_page_is_clean(self):
        self.assertEqual([i for i in web_sandbox.audit(web_sandbox.STARTER_PAGE)
                          if i.severity == "error"], [])

    def test_detects_problems(self):
        bad = ("<html><body><h1>a</h1><h3>b</h3><img src='x.png'><a href='#'>اضغط هنا</a>"
               "<input id='q'><button></button><span aria-labelledby='nope'>x</span></body></html>")
        msgs = " ".join(i.message for i in web_sandbox.audit(bad))
        for needle in ("lang", "<title>", "قفزة", "alt", "اضغط هنا", "بلا تسمية", "زرّ بلا اسم", "nope"):
            self.assertIn(needle, msgs)

    def test_names_and_tree(self):
        html = ("<main><label for='n'>الاسم</label><input id='n' required>"
                "<img src='a' alt='شعار'><a href='/x'><img src='b' alt='الرئيسية'></a>"
                "<ul><li>أ</li><li>ب</li></ul></main>")
        lines = web_sandbox.reading_order(html)
        self.assertIn("الاسم، حقل تحرير، مطلوب", lines)
        self.assertIn("الرئيسية، رابط", lines)
        self.assertIn("قائمة بها 2 عناصر", lines)
        self.assertEqual(web_sandbox.links(html), ["الرئيسية"])
        self.assertEqual(web_sandbox.landmarks(html), ["المحتوى الرئيسي"])

    def test_hidden_and_decorative(self):
        html = "<p aria-hidden='true'>سرّ</p><img src='d' alt=''><p>ظاهر</p>"
        self.assertEqual(web_sandbox.reading_order(html), ["ظاهر"])

    def test_unclosed_tag_reported(self):
        msgs = [i.message for i in web_sandbox.audit("<div><span>x</div>")]
        self.assertTrue(any("لم يُغلق" in m for m in msgs))


# ---------------------------------------------------------------------------
class TestDeckImport(unittest.TestCase):
    def test_anki_export(self):
        t = "#separator:tab\n#html:true\n#deck column:3\nhi\t<b>مرحبا</b>\tEN\n[sound:a.mp3]cat\tقطّة&nbsp;\tEN\n"
        p = deck_import.parse_text(t)
        self.assertEqual(p.cards, [("hi", "مرحبا", ""), ("cat", "قطّة", "")])
        self.assertEqual(p.deck_names, ["EN", "EN"])

    def test_csv_with_header_and_quotes(self):
        p = deck_import.parse_text('السؤال,الجواب\n"عاصمة لبنان، بلدي","بيروت"\n')
        self.assertTrue(p.header_skipped)
        self.assertEqual(p.cards[0][0], "عاصمة لبنان، بلدي")

    def test_dash_pairs_and_cp1256(self):
        self.assertEqual(deck_import.parse_text("شمس - sun\nقمر - moon").cards[1][:2], ("قمر", "moon"))
        text, enc = deck_import.decode_bytes("كتاب;book\n".encode("cp1256"))
        self.assertEqual(enc, "Windows-1256")
        self.assertEqual(deck_import.parse_text(text).cards[0][:2], ("كتاب", "book"))

    def test_cloze(self):
        self.assertEqual(deck_import.clean_field("{{c1::بيروت}} عاصمة"), "بيروت عاصمة")

    def test_import_dedup_and_export(self):
        from abaAcademy.flashcards import FlashcardStore
        fs = FlashcardStore(MemStore())
        p = deck_import.parse_text("a\tb\nc\td\n")
        self.assertEqual(deck_import.import_into(fs, p, "تجربة"), (2, 0))
        self.assertEqual(deck_import.import_into(fs, p, "تجربة"), (0, 2))
        tsv = deck_import.export_tsv(fs.all_cards())
        self.assertIn("a\tb\t", tsv)
        again = deck_import.parse_text(tsv)
        self.assertEqual(len(again.cards), 2)

    def test_generated_decks(self):
        from abaAcademy.flashcards import FlashcardStore
        fs = FlashcardStore(MemStore())
        for kind in deck_import.GENERATED_DECKS:
            added, _ = deck_import.add_generated(fs, kind)
            self.assertGreater(added, 0, kind)


# ---------------------------------------------------------------------------
class TestPlanner(unittest.TestCase):
    def test_daily_plan(self):
        p = planner.Planner(MemStore())
        today = datetime.date(2026, 10, 18)
        exam = p.add("امتحان", datetime.date(2026, 10, 28), "exam", "رياضيات", 300)
        p.add("واجب", today, "homework", "تاريخ", 60)
        p.log_minutes(exam.id, 60, today)
        plan = p.today_plan(today)
        self.assertIn("84", plan[0])
        self.assertEqual(p.items()[0].title, "واجب")

    def test_overdue_and_done(self):
        p = planner.Planner(MemStore())
        today = datetime.date(2026, 10, 18)
        hw = p.add("قديم", datetime.date(2026, 10, 10), "homework", "", 30)
        self.assertTrue(any("متأخّر" in l for l in p.today_plan(today)))
        p.log_minutes(hw.id, 30, today)
        self.assertEqual(p.items(), [])            # finished homework drops off

    def test_subject_credit_and_week(self):
        p = planner.Planner(MemStore())
        p.add("فيزياء", datetime.date.today() + datetime.timedelta(days=5), "exam", "علوم", 100)
        self.assertIsNotNone(p.log_subject("علوم", 25))
        self.assertEqual(sum(p.week_minutes().values()), 25)

    def test_parse_date(self):
        t = datetime.date(2026, 10, 18)
        self.assertEqual(planner.parse_date("2026-11-03", t), datetime.date(2026, 11, 3))
        self.assertEqual(planner.parse_date("3/11", t), datetime.date(2026, 11, 3))
        self.assertEqual(planner.parse_date("1/1", t), datetime.date(2027, 1, 1))
        self.assertEqual(planner.parse_date("٥", t), datetime.date(2026, 10, 23))
        self.assertEqual(planner.parse_date("غدًا", t), datetime.date(2026, 10, 19))
        with self.assertRaises(ValueError):
            planner.parse_date("قريبًا", t)


class TestKhatma(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ix = khatma.QuranIndex.load(os.path.join(RES, "quran", "quran_data.json"))

    def test_portions_cover_everything(self):
        for unit in khatma.UNITS:
            for days in (1, 7, 30, 365):
                ps = khatma.make_portions(self.ix, khatma.Plan(unit, days, "2026-01-01"))
                self.assertEqual(ps[0].start, 1)
                self.assertEqual(ps[-1].end, 6236)
                for a, b in zip(ps, ps[1:]):
                    self.assertEqual(a.end + 1, b.start)
                self.assertLessEqual(len(ps), days)

    def test_juz_boundary(self):
        ps = khatma.make_portions(self.ix, khatma.Plan("juz", 30, "2026-01-01"))
        self.assertEqual(self.ix.label(ps[0].end).split()[-1], "141")

    def test_status_and_store(self):
        ks = khatma.KhatmaStore(MemStore())
        plan = ks.create("pages", 30, datetime.date(2026, 10, 1))
        lines = khatma.status(self.ix, plan, datetime.date(2026, 10, 18))
        self.assertTrue(any("متأخّر" in l for l in lines))
        ks.mark_read(plan, 6236)
        self.assertTrue(any("أتممت" in l for l in khatma.status(self.ix, ks.load())))
        with self.assertRaises(ValueError):
            ks.create("pages", 0)


# ---------------------------------------------------------------------------
class TestMentalMath(unittest.TestCase):
    def test_every_technique_is_correct(self):
        rng = random.Random(7)
        for t in mental_math.TECHNIQUES:
            for _ in range(150):
                p = t.make(rng)
                expr = (p.question.replace("×", "*").replace("−", "-").replace("²", "**2")
                        .replace("٪ من ", "*0.01*"))
                self.assertEqual(eval(expr), p.answer, (t.key, p.question))
                self.assertTrue(p.steps)
                self.assertTrue(p.check(str(p.answer)))


class TestLogic(unittest.TestCase):
    def test_laws_hold(self):
        for name, a, b in logic.LAWS:
            self.assertTrue(logic.equivalent(a, b)[0], name)

    def test_kinds(self):
        self.assertEqual(logic.truth_table("p or not p").kind, "tautology")
        self.assertEqual(logic.truth_table("أ و ليس أ").kind, "contradiction")
        self.assertEqual(logic.truth_table("p -> q").kind, "contingent")

    def test_precedence(self):
        tt = logic.truth_table("p or q and r")
        for values, res in tt.rows:
            p, q, r = values
            self.assertEqual(res, p or (q and r))
        tt = logic.truth_table("p -> q -> r")
        for (p, q, r), res in tt.rows:
            self.assertEqual(res, (not p) or ((not q) or r))

    def test_errors(self):
        for bad in ("", "p and", "(p", "p q"):
            with self.assertRaises(ValueError):
                logic.truth_table(bad)
        self.assertFalse(logic.equivalent("p and q", "p or q")[0])


class TestZakat(unittest.TestCase):
    def test_due(self):
        r = zakat.calculate(zakat.ZakatInput({"cash": 10000, "gold_g": 50, "debts_due": 1000},
                                             gold_price=100, silver_price=1.2, karat=21))
        self.assertAlmostEqual(r.net, 13375)
        self.assertAlmostEqual(r.due, 334.375)

    def test_below_nisab_and_year(self):
        r = zakat.calculate(zakat.ZakatInput({"cash": 1000}, gold_price=100))
        self.assertEqual(r.due, 0)
        r = zakat.calculate(zakat.ZakatInput({"cash": 100000}, gold_price=100, year_complete=False))
        self.assertEqual(r.due, 0)
        r = zakat.calculate(zakat.ZakatInput({"cash": 1000}, silver_price=1.0, standard="silver"))
        self.assertAlmostEqual(r.due, 25)

    def test_needs_prices(self):
        with self.assertRaises(ValueError):
            zakat.calculate(zakat.ZakatInput({"cash": 1}))


if __name__ == "__main__":
    unittest.main()
