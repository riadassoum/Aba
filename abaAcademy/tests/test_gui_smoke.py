# -*- coding: utf-8 -*-
"""Smoke test for every 3.0 screen: each is opened for real and its main
actions are driven, failing on any exception. Runs wherever wxPython and a
display are available (the Windows build machine; a virtual display on
Linux) and is skipped otherwise."""

import os
import sys
import tempfile
import time
import traceback
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, _ROOT)

try:
    import wx
    _HAVE_WX = True
except Exception:
    _HAVE_WX = False

_HAVE_DISPLAY = sys.platform.startswith("win") or sys.platform == "darwin" or bool(os.environ.get("DISPLAY"))


@unittest.skipUnless(_HAVE_WX and _HAVE_DISPLAY, "wxPython and a display are needed")
class TestScreensSmoke(unittest.TestCase):
    def test_all_screens(self):
        from abaDesktop.core import build_academy
        LOG = []

        class Speech:
            def announce(self, text, **k):
                LOG.append(str(text))

            def interrupt(self):
                pass

            def speak_line(self, t):
                LOG.append(str(t))

        app = wx.GetApp() or wx.App(False)
        data = tempfile.mkdtemp()
        academy = build_academy(data)
        academy.profiles_root = data
        speech = Speech()
        frame = wx.Frame(None)
        failures = []

        def pump(n=5):
            for _ in range(n):
                wx.Yield()
                time.sleep(0.005)

        def run(name, factory, actions):
            LOG.clear()
            try:
                dlg = factory(frame, academy, speech)
                dlg.Show()
                pump(8)
                for label, fn in actions:
                    try:
                        fn(dlg)
                        pump(2)
                    except Exception:
                        failures.append(f"{name} / {label}:\n{traceback.format_exc()}")
                dlg.close_screen(force=True)
                pump(4)
            except Exception:
                failures.append(f"{name} (open):\n{traceback.format_exc()}")

        from abaAcademy.gui import (calendar_view, prayer_view, arud_view, roots_view, morse_view,
                                    periodic_view, puzzles_view, math_tools_view, web_lab_view,
                                    deck_import_view, planner_view, skills_view, profiles_view, hub)

        run("Calendar", calendar_view.CalendarDialog, [
            ("next", lambda d: d._shift(1)), ("prev", lambda d: d._shift(-2)), ("today", lambda d: d._go_today()),
            ("occ", lambda d: d._occasions()),
            ("conv h->g", lambda d: (d.dayEntry.SetValue("1"), d.monthEntry.SetValue("9"), d.yearEntry.SetValue("1447"), d._convert())),
            ("conv g->h", lambda d: (d.direction.SetSelection(1), d.dayEntry.SetValue("18"), d.monthEntry.SetValue("10"), d.yearEntry.SetValue("2026"), d._convert(), d._open_converted())),
            ("bad", lambda d: (d.dayEntry.SetValue("x"), d._safe(d._convert))),
        ])
        run("Prayer", prayer_view.PrayerTimesDialog, [
            ("calc", lambda d: d._calc()), ("next", lambda d: d._next()), ("qibla", lambda d: d._qibla()),
            ("month", lambda d: d._month_table()),
            ("city beirut", lambda d: (d.cityChoice.SetSelection(15), d._on_city())),
            ("custom", lambda d: (d.cityChoice.SetSelection(len(d._city_keys) - 1), d._on_city(),
                                  d.latEntry.SetValue("40"), d.lonEntry.SetValue("-3.7"), d._calc())),
            ("date", lambda d: (d.dateEntry.SetValue("2026-12-21"), d._calc())),
            ("bad", lambda d: (d.latEntry.SetValue("abc"), d._safe(d._qibla))),
        ])
        run("Arud", arud_view.ArudDialog, [
            ("example", lambda d: d._example()),
            ("verse", lambda d: (d.verse.SetValue("قِفَا نَبْكِ مِنْ ذِكْرَى حَبِيبٍ وَمَنْزِلِ * بِسِقْطِ اللِّوَى بَيْنَ الدَّخُولِ فَحَوْمَلِ"), d._analyse())),
            ("spell", lambda d: d._spell_pattern()), ("play", lambda d: d._play_last()),
            ("metre", lambda d: (d.metres.SetSelection(3), d._metre_info())),
            ("quiz", lambda d: (d.quiz.next(), d.quiz.answer(), d.quiz.answer())),
            ("empty", lambda d: (d.verse.SetValue(""), d._safe(d._analyse))),
        ])
        run("Roots", roots_view.RootsDialog, [
            ("analyse", lambda d: (d.wordEntry.SetValue("المكتبة"), d._analyse())),
            ("family", lambda d: (roots_view.RootsDialog._index.wait(30), d._family())),
            ("quiz", lambda d: (d.quiz.next(), d.quiz.answer(), d.quiz.next())),
            ("kind", lambda d: (d.kindChoice.SetSelection(2), d.quiz.next())),
        ])
        run("Morse", morse_view.MorseDialog, [
            ("translate", lambda d: (d.textEntry.SetValue("سلام"), d._translate())),
            ("decode", lambda d: (d.textEntry.SetValue("... --- ..."), d.alphaChoice.SetSelection(1), d._on_alpha(), d._translate())),
            ("table", lambda d: d._table()), ("lesson", lambda d: d._lesson_letters()),
            ("group", lambda d: (d._new_group(), d.answerEntry.SetValue(d._group), d._check_group())),
            ("quiz", lambda d: (d.quiz.next(), d.quiz.answer())),
            ("keyer", lambda d: (d._clear_keyer(), d._read_keyer())),
        ])
        run("Periodic", periodic_view.PeriodicTableDialog, [
            ("card", lambda d: d._card()), ("right", lambda d: d._move_h(1)), ("down", lambda d: d._move_v(1)),
            ("search", lambda d: (d.searchEntry.SetValue("ذهب"), d._search())),
            ("family", lambda d: d._family()), ("period", lambda d: d._period()), ("group", lambda d: d._group()),
            ("lanth", lambda d: (d.searchEntry.SetValue("60"), d._search(), d._group(), d._period(), d._move_v(-1))),
        ])
        run("ElementQuiz", periodic_view.ElementQuizDialog, [
            ("q", lambda d: [(d.quiz.next(), d.quiz.answer()) for _ in range(12)]),
        ])
        run("Sudoku", puzzles_view.SudokuDialog, [
            ("hint", lambda d: d._hint()), ("put", lambda d: d._put(5)), ("undo", lambda d: d._undo()),
            ("check", lambda d: d._check()), ("4x4", lambda d: (d.sizeChoice.SetSelection(1), d._new())),
            ("solve4", lambda d: [(lambda h: (d.set_cursor(h.row, h.col), d._put(h.value)))(d.game.hint()) for _ in range(d.game.empty_count())]),
        ])
        run("Mines", puzzles_view.MinesweeperDialog, [
            ("open", lambda d: d.activate(4, 4)), ("hint", lambda d: d._hint()), ("rem", lambda d: d._remaining()),
            ("expert", lambda d: (d.levelChoice.SetSelection(3), d._new(), d.activate(6, 6))),
        ])
        run("2048", puzzles_view.Game2048Dialog, [
            ("moves", lambda d: [d._move(x) for x in ("left", "up", "right", "down") * 5]), ("undo", lambda d: d._undo()),
        ])
        run("Sliding", puzzles_view.SlidingPuzzleDialog, [
            ("solve", lambda d: [d._move(d.p.suggest()) for _ in range(40) if not d.p.solved()]),
            ("hint", lambda d: d._hint()), ("4x4", lambda d: (d.sizeChoice.SetSelection(1), d._new(), d._hint())),
        ])
        run("Matrix", math_tools_view.MatrixDialog, [
            ("ops", lambda d: [(d.opChoice.SetSelection(i), d._safe(d._calc)) for i in range(len(d._OPS))]),
            ("read", lambda d: d._read_a()),
            ("solve", lambda d: (d.aEntry.SetValue("2 1\n1 -1"), d.bEntry.SetValue("5\n1"), d.opChoice.SetSelection(8), d._calc())),
        ])
        run("Stats", math_tools_view.StatsDialog, [
            ("report", lambda d: d._report()), ("freq", lambda d: d._freq()), ("tones", lambda d: d._tones()),
        ])
        run("Equation", math_tools_view.EquationDialog, [
            ("ex", lambda d: d._example()), ("steps", lambda d: [d._step() for _ in range(4)]),
            ("bad", lambda d: (d.eq.SetValue("x^3=1"), d._safe(d._solve))),
        ])
        run("Geometry", math_tools_view.GeometryDialog, [
            ("all", lambda d: [(d.shapeChoice.SetSelection(i), d._relabel(),
                                [f.SetValue("5") for f in d.fields], d._safe(d._calc)) for i in range(len(math_tools_view.algebra.SHAPES) + 1)]),
            ("pyth", lambda d: (d.fields[2].SetValue(""), d._calc())),
        ])
        run("Bases", math_tools_view.BasesDialog, [("conv", lambda d: d._convert()), ("all", lambda d: d._all())])
        run("Mental", math_tools_view.MentalMathDialog, [
            ("explain", lambda d: d._explain()), ("q", lambda d: (d._new(), d.answer.SetValue(str(d._p.answer)), d._check())),
            ("wrong", lambda d: (d.answer.SetValue("-1"), d._check(), d._score())),
            ("all", lambda d: (d.techChoice.SetSelection(len(math_tools_view.mental_math.TECHNIQUES)), d._explain(), d._new())),
        ])
        run("Logic", math_tools_view.LogicDialog, [
            ("table", lambda d: d._table()), ("cmp", lambda d: (d.expr2.SetValue("ليس أ أو ب"), d._compare())),
            ("laws", lambda d: d._laws()), ("bad", lambda d: (d.expr.SetValue("p and"), d._safe(d._table))),
        ])
        run("WebLab", web_lab_view.WebLabDialog, [
            ("audit", lambda d: d._audit()), ("views", lambda d: [(d.viewChoice.SetSelection(i), d._preview()) for i in range(5)]),
            ("lessons", lambda d: d._lessons()), ("bad", lambda d: (d.editor.SetValue("<img src=x>"), d._audit())),
            ("starter", lambda d: d._starter()),
        ])
        run("DeckImport", deck_import_view.DeckImportDialog, [
            ("gen", lambda d: [(d.genChoice.SetSelection(i), d._generated()) for i in range(len(d._gen_keys))]),
            ("parse", lambda d: (setattr(d, "_parsed", deck_import_view.deck_import.parse_text("a\tb\nc\td")), d._import())),
        ])
        run("Planner", planner_view.PlannerDialog, [
            ("add", lambda d: (d.titleEntry.SetValue("امتحان"), d.dueEntry.SetValue("7"), d.subjectEntry.SetValue("رياضيات"), d._add())),
            ("details", lambda d: d._details()), ("log", lambda d: d._log()), ("today", lambda d: d._today()),
            ("week", lambda d: d._week()), ("done", lambda d: (d._done(), d._toggle_done(), d._done())),
            ("baddate", lambda d: (d.titleEntry.SetValue("x"), d.dueEntry.SetValue("زمان"), d._safe(d._add))),
        ])
        run("Khatma", planner_view.KhatmaDialog, [
            ("status none", lambda d: d._status()),
            ("create", lambda d: (wx.MessageBox.__call__ if False else None, d.ks.create("juz", 30), d._render(), d._status())),
            ("finish", lambda d: d._finish_today()),
            ("mark", lambda d: (d.surahChoice.SetSelection(1), d.ayahEntry.SetValue("200"), d._mark())),
            ("badmark", lambda d: (d.ayahEntry.SetValue("999"), d._safe(d._mark))),
        ])
        run("Zakat", skills_view.ZakatDialog, [
            ("calc", lambda d: (d.fields["cash"].SetValue("10000"), d.goldPrice.SetValue("100"), d._calc())),
            ("noprice", lambda d: (d.goldPrice.SetValue(""), d._safe(d._calc))),
        ])
        run("Profiles", profiles_view.ProfilesDialog, [
            ("create", lambda d: (d.nameEntry.SetValue("سارة"), d._create())),
            ("rename", lambda d: (d.nameEntry.SetValue("سارة أحمد"), d._rename())),
            ("ask", lambda d: (d.askCheck.SetValue(True), d._ask_changed())),
        ])

        from abaAcademy.gui import study_tools_view as stv
        run("Sheet", stv.SheetDialog, [
            ("type", lambda d: [(d.editor.SetValue(v), d._commit()) for v in ("10", "20", "=مجموع(A1:A2)", "=A1/0")]),
            ("move", lambda d: (d._move(-1, 0), d._move(0, 1), d._move(0, -5))),
            ("goto", lambda d: (d.gotoEntry.SetValue("A3"), d._goto())),
            ("funcs", lambda d: d._functions()),
            ("undo", lambda d: d.sheet.undo()),
        ])
        run("Tracer", stv.TracerDialog, [
            ("run", lambda d: [(d.sampleChoice.SetSelection(i), d._load_sample(), d._run()) for i in range(5)]),
            ("counts", lambda d: d._counts()),
            ("bad", lambda d: (d.code.SetValue("while True: pass"), d._run())),
        ])
        run("NumberRules", stv.NumberRulesDialog, [
            ("quiz", lambda d: [(d.modeChoice.SetSelection(i % 2), d.quiz.next(), d.quiz.answer()) for i in range(6)]),
            ("write", lambda d: (d.numEntry.SetValue("١٣"), d.nounChoice.SetSelection(20), d._write())),
            ("rules", lambda d: d._rules()), ("bad", lambda d: (d.numEntry.SetValue("150"), d._safe(d._write))),
        ])
        run("Escape", stv.EscapeRoomDialog, [
            ("play", lambda d: [(d.actions.SetSelection(0), d._safe(d._do)) for _ in range(3)]),
            ("bag", lambda d: (d._bag(), d._hint(), d._where())),
            ("restart", lambda d: d._restart()),
        ])
        run("SchoolCalc", stv.SchoolCalcDialog, [
            ("avg", lambda d: d._average()),
            ("need", lambda d: (d.curEntry.SetValue("70"), d._needed())),
            ("diff", lambda d: (d.fromEntry.SetValue("2000-05-10"), d._diff(), d._age())),
        ])

        from abaAcademy.gui import science_lab_view as slv
        run("Chem", slv.ChemistryDialog, [("mass", lambda d: d._mass()), ("read", lambda d: d._read()),
            ("conv", lambda d: [(d.unitChoice.SetSelection(i), d._convert()) for i in range(3)]), ("bal", lambda d: d._balance()),
            ("bad", lambda d: (d.formula.SetValue("Qq"), d._safe(d._mass)))])
        run("Phys", slv.PhysicsDialog, [("laws", lambda d: [(d.lawChoice.SetSelection(i), d._relabel(),
            [f.SetValue("2") for f in d.fields[1:len(d._law().variables)]], d._safe(d._solve)) for i in range(len(slv.ph.LAWS))])])
        run("Regex", slv.RegexLabDialog, [("ex", lambda d: d._explain()), ("test", lambda d: d._test()),
            ("sub", lambda d: (d.repl.SetValue("#"), d._sub())), ("task", lambda d: (d._task(), d._check(), d._hint())),
            ("bad", lambda d: (d.pattern.SetValue("(a"), d._safe(d._test)))])
        run("TextStats", slv.TextStatsDialog, [("an", lambda d: (d.text.SetValue("مرحبا بكم. هذا نص."), d._analyse()))])
        run("WordSearch", slv.WordSearchDialog, [("play", lambda d: (setattr(d, "_r", d.p.words[0].start[0]), setattr(d, "_c", d.p.words[0].start[1]),
            d._space(), setattr(d, "_r", d.p.words[0].end[0]), setattr(d, "_c", d.p.words[0].end[1]), d._space())),
            ("words", lambda d: (d._words(), d._hint())), ("new", lambda d: (d.levelChoice.SetSelection(2), d._new()))])

        from abaAcademy.gui import daily_tools_view as dtv
        run("Countries", dtv.CountriesDialog, [("card", lambda d: d._card()), ("region", lambda d: (d.regionChoice.SetSelection(2), d._fill(), d._card())),
            ("search", lambda d: (d.searchEntry.SetValue("موروني"), d._search())), ("quiz", lambda d: [(d.quiz.next(), d.quiz.answer()) for _ in range(5)])])
        run("Arith", dtv.ArithmeticDialog, [("frac", lambda d: [(d.opChoice.SetSelection(i), d._fraction()) for i in range(4)]),
            ("pct", lambda d: [(d.pctChoice.SetSelection(i), d._percent()) for i in range(6)]),
            ("roman", lambda d: (d._roman(), d.numEntry.SetValue("XIV"), d._roman(), d.numEntry.SetValue("1205"), d._english()))])
        run("Times", dtv.TimesTablesDialog, [("q", lambda d: [(d._next(), d.answer.SetValue("1"), d._check()) for _ in range(3)]), ("weak", lambda d: d._weak())])
        run("Tasbih", dtv.TasbihDialog, [("tap", lambda d: [d._tap() for _ in range(35)]), ("undo", lambda d: d._undo()), ("today", lambda d: d._today()),
            ("change", lambda d: (d.seqChoice.SetSelection(2), d._change(), d._restart()))])
        from abaAcademy.gui import games, pomodoro_view
        run("GamesHome", games.GamesHome, [])
        run("HighScores", games.HighScores, [])


        from abaAcademy.gui import quiz_builder_view as qbv
        run("QuizBuilder", qbv.QuizBuilderDialog, [("sample", lambda d: d._sample()),
            ("new", lambda d: (d.titleEntry.SetValue("اختبار"), d._new_quiz())),
            ("addq", lambda d: [(d.kindChoice.SetSelection(k), d.prompt.SetValue("سؤال؟"), d.optionsEntry.SetValue("أ\nب"), d._add_question()) for k in range(3)]),
            ("delq", lambda d: d._delete_question()), ("results", lambda d: d._results())])
        run("QuizTake", lambda p, a, s: qbv.QuizTakeDialog(p, a, s, qbv.qb.sample_quiz()), [
            ("start", lambda d: (d.nameEntry.SetValue("سارة"), d._start())),
            ("answer", lambda d: [(d.answer.SetValue("كتب"), d.select_index(d.options, 0), d.runner.answer(0 if d.runner.question.kind != "short" else "كتب")) for _ in range(4)]),
            ("finish", lambda d: d._finish()), ("time", lambda d: d._time())])
        run("Weekly", qbv.WeeklyReportDialog, [("build", lambda d: d._build())])

        from abaAcademy.gui import code_quran_extra_view as cqv
        run("SurahQuiz", cqv.SurahQuizDialog, [("card", lambda d: d._card()),
            ("quiz", lambda d: [(d.poolChoice.SetSelection(i % 3), d.quiz.next(), d.quiz.answer()) for i in range(8)])])
        run("Gates", cqv.GatesDialog, [("table", lambda d: [(d.gateChoice.SetSelection(i), d._table()) for i in range(7)]),
            ("add", lambda d: d._add()), ("quiz", lambda d: [(d.modeChoice.SetSelection(i % 2), d.quiz.next(), d.quiz.answer()) for i in range(4)])])
        run("DataStructures", cqv.DataStructuresDialog, [("all", lambda d: [(d.kindChoice.SetSelection(k), d._switch(),
            [(d.value.SetValue(v), d.opList.SetSelection(0), d._do()) for v in ("5", "3", "8")],
            [(d.value.SetValue("3"), d.opList.SetSelection(i), d._safe(d._do)) for i in range(d.opList.GetCount())], d._read())
            for k in range(4)])])

        run("Algorithms", cqv.AlgorithmsDialog, [("sorts", lambda d: [(d.sortChoice.SetSelection(i), d._sort(), d._about()) for i in range(5)]),
            ("compare", lambda d: d._compare()), ("search", lambda d: (d._linear(), d._binary())),
            ("bad", lambda d: (d.data.SetValue("x"), d._safe(d._sort)))])
        run("NumberTheory", cqv.NumberTheoryDialog, [("all", lambda d: (d._analyse(), d._factor(), d._div(), d._gcd(), d._primes())),
            ("prob", lambda d: [(d.probChoice.SetSelection(i), d._safe(d._prob)) for i in range(6)])])

        from abaAcademy.gui import daily_tools_view as dtv2
        run("Clock", dtv2.ClockDialog, [("say", lambda d: (d._time(), d._date(), d._world())),
            ("sw", lambda d: (d._sw_toggle(), pump(3), d._lap(), d._sw_say(), d._sw_toggle(), d._sw_reset())),
            ("cd", lambda d: (d.cdEntry.SetValue("0:02"), d._cd_start(), d._cd_say(), d._cd_pause()))])
        run("Resistors", dtv2.ResistorsDialog, [("calc", lambda d: [(d.arrChoice.SetSelection(i), d._calc()) for i in range(2)]),
            ("bad", lambda d: (d.rs.SetValue("5"), d._safe(d._calc)))])

        from abaAcademy.gui import codelab_view, flashcards_view

        def codelab_walk(d):
            d.modeChoice.SetSelection(1)
            d._on_mode()
            for t in range(d.trackChoice.GetCount()):
                d.trackChoice.SetSelection(t)
                d._on_track()
            d.trackChoice.SetSelection(1)
            d._on_track()
            d.challengeChoice.SetSelection(0)
            d._load_challenge()
            d.editor.SetValue('print("أنا أتعلّم بايثون")')
            d._submit()
            assert "(منجز)" in d.challengeChoice.GetString(0), d.challengeChoice.GetString(0)
            d._next_challenge()
            d._hint()

        run("CodeLab", codelab_view.CodeLabDialog, [("tracks and submit", codelab_walk),
                                                   ("free run", lambda d: (d.modeChoice.SetSelection(0), d._on_mode(),
                                                                           d.editor.SetValue("print(2 + 2)"), d._run()))])

        def lib_walk(d):
            labels = [d.courseChoice.GetString(i) for i in range(d.courseChoice.GetCount())]
            assert "التركية" in labels and "الإسبانية" in labels, labels
            d.courseChoice.SetSelection(labels.index("التركية"))
            d._add_selected_course()

        run("FlashcardLibrary", flashcards_view.StarterLibraryDialog if hasattr(flashcards_view, "StarterLibraryDialog")
            else [v for k, v in vars(flashcards_view).items() if isinstance(v, type) and hasattr(v, "_add_selected_course")][0],
            [("languages", lib_walk)])

        from abaAcademy.gui.lesson_player import LessonPlayer
        from abaAcademy.gui.exercise_runner import ExerciseRunner
        for lid in ("spanish.intro", "spanish.g050", "turkish.cj01", "german.gr02", "italian.exam01",
                    "english_graded.r010", "french_graded.g200"):
            lesson = academy.load_lesson(lid)
            if lesson is None:
                failures.append(f"lesson {lid} missing")
                continue

            def walk(d):
                for _ in range(len(d._steps) + 2):
                    if d._index < len(d._steps) and d.nextBtn.IsEnabled():
                        d._on_next(None)
                assert d._steps, "no theory steps"

            run(f"LessonPlayer {lid}", lambda p, a, sp, L=lesson: LessonPlayer(p, a, L, sp), [("walk", walk)])
            run(f"Runner {lid}", lambda p, a, sp, L=lid: ExerciseRunner(p, a, a.build_lesson_quiz(L, seed=1), "quiz", sp,
                                                                         lesson_id=L), [])
        frame.Destroy()
        self.assertEqual(failures, [], "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
