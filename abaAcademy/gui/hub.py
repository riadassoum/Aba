# -*- coding: utf-8 -*-
"""
abaAcademy.gui.hub
==================

The Academy hub — the first screen from the the screen reader Tools menu. It's designed to
feel like a real academy home: a live progress line at the top (streak, lessons
completed, accuracy, study time), a one-tap "practice of the day", a way to jump
straight back into the last lesson, spaced-repetition review, the full course
navigator, the typing challenge, achievements, and statistics. It owns the
singleton Academy service for the session and closes it on exit.

Everything here is wired to real data and real sessions — no placeholders.
"""

from __future__ import annotations

import wx

from .accessible import AccessibleDialog, clear_shutdown
from .achievements_view import AchievementsView
from .exercise_runner import ExerciseRunner
from .main_window import MainWindow
from .statistics_view import StatisticsView
from .keyboard_trainer import KeyboardTrainer, TIERS
from .quran_reader import QuranReader
from .hadith_reader import HadithReader
from .flashcards_view import FlashcardsHome
from .islamic_tools import IslamicToolsHome
from .games import GamesHome
from .settings_view import SettingsView
from .mistakes_view import MistakesView
from .search_view import SearchView
from .certificates_view import CertificatesView
from .export_view import ExportView
from .onboarding_view import OnboardingView
from .dictionary import DictionaryDialog

# Kept in sync with manifest.ini.
__version__ = "2.0"


class HubDialog(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(
            parent, f"أكاديمية الكفيف العربي (ABA) — الإصدار {__version__}",
            speech, size=(600, 560))
        self.academy = academy

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # live progress line
        self.progressLabel = wx.StaticText(panel, label=self._progress_text())
        self.progressLabel.Wrap(560)
        sizer.Add(self.progressLabel, 0, wx.ALL, 10)

        intro = wx.StaticText(
            panel, label="تنقّل بين الأقسام بـ Ctrl+Tab، وداخل كل قسم بالأسهم. "
                        "الأقسام: الرئيسية، الدورات، القرآن والإسلاميات، اللغة العربية، "
                        "البرمجة، الأدوات، الألعاب والمزيد.")
        intro.Wrap(560)
        sizer.Add(intro, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # tabbed sections keep the many features tidy; Ctrl+Tab moves between them
        # a quick-jump search box above the tabs lets a learner reach any feature
        # by name without hunting through sections.
        jump_row = wx.BoxSizer(wx.HORIZONTAL)
        jump_row.Add(wx.StaticText(panel, label="انتقال سريع:"), 0,
                     wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.jumpEntry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.jumpEntry.SetName("انتقال سريع إلى ميزة")
        self.jumpEntry.SetHint("اكتب اسم ميزة ثم Enter")
        self.jumpEntry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._quick_jump())
        jump_row.Add(self.jumpEntry, 1)
        sizer.Add(jump_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.notebook = wx.Notebook(panel)
        sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 4)

        # each section is (tab title, [(label, handler, optional_condition), ...])
        # condition, when present and False, skips that button.
        has_last = bool(self.academy.last_lesson())
        sections = [
            ("الرئيسية", [
                ("تدريب اليوم (مراجعة متنوّعة سريعة)", self._open_daily, True, True),
                ("متابعة آخر درس", self._continue_last, has_last, False),
                ("ابدأ جلسة المعلّم الذكي (متكيّفة مع مستواك)", self._open_adaptive, True, False),
                ("المُعلّم الذكي (رفيقك الذي يوصيك بما تدرس)", self._open_tutor, True, False),
                ("لوحة تقدّمي (سلسلتك وإتقانك وإنجازاتك)", self._open_progress, True, False),
                ("المراجعة المجدولة (تكرار متباعد)", self._open_review, True, False),
                ("تدريب نقاط الضعف (الأكثر خطأً)", self._open_weak, True, False),
                ("دفتر الأخطاء (راجع وتدرّب على أخطائك)", self._open_mistakes, True, False),
            ]),
            ("الدورات", [
                ("كل الدورات والدروس", self._open_learn, True, False),
                ("بحث في كل الدروس", self._open_search, True, False),
                ("البطاقات التعليمية (مراجعة ذكية)", self._open_flashcards, True, False),
                ("تحدي الكتابة السريعة والدقيقة", self._open_typing, True, False),
                ("حزم الدورات (استورد أو صدّر دورة)", self._open_packs, True, False),
            ]),
            ("القرآن والإسلاميات", [
                ("قراءة القرآن الكريم (تنقّل واستماع)", self._open_quran, True, False),
                ("اختبار الحفظ (أكمل الآية والمتشابهات)", self._open_hifz_tester, True, False),
                ("مقارنة التفاسير (تنقّل بين المصادر لنفس الآية)", self._open_tafsir_compare, True, False),
                ("دراسة القرآن (بحث بالجذور وأحكام التجويد)", self._open_quran_study, True, False),
                ("قارئ الحديث الشريف", self._open_hadith, True, False),
                ("أدوات إسلامية (الأسماء الحسنى ومواقيت الصلاة)", self._open_islamic, True, False),
            ]),
            ("اللغة العربية", [
                ("مصرّف الأفعال", self._open_conjugator, True, False),
                ("مختبر الإملاء والهمزات", self._open_spelling, True, False),
                ("معلّم برايل التفاعلي (محاكي بيركنز بست نقاط)", self._open_perkins, True, False),
                ("دروس برايل التفاعلية (تعلّم الاختصارات باختبارات مؤقّتة)", self._open_braille_lessons, True, False),
                ("القاموس الإنجليزي", self._open_dictionary, True, False),
                ("محرّر الواجبات والملاحظات (تصدير وورد وHTML)", self._open_docstudio, True, False),
            ]),
            ("البرمجة", [
                ("دورة البرمجة (دروس من المبتدئ إلى المتقدّم)", self._open_curriculum, True, False),
                ("مختبر البرمجة (تعلّم بايثون بالعربية)", self._open_codelab, True, False),
            ]),
            ("الأدوات", [
                ("أدوات الطالب (تفقيط ومحوّل التاريخ الهجري)", self._open_student_tools, True, False),
                ("الآلة الحاسبة الناطقة", self._open_calculator, True, False),
                ("محوّل الوحدات (طول، وزن، حرارة، وغيرها)", self._open_converter, True, False),
                ("الآلة الحاسبة البيانية الصوتية (ارسم الدوال بالصوت)", self._open_grapher, True, False),
                ("مؤقّت الدراسة (بومودورو)", self._open_pomodoro, True, False),
                ("دفتر الملاحظات", self._open_notebook, True, False),
                ("منسّق النصوص العربية", self._open_clipboard, True, False),
                ("مستكشف اختصارات لوحة المفاتيح", self._open_shortcuts, True, False),
            ]),
            ("الألعاب والمزيد", [
                ("الألعاب الذهنية (تقوية الذاكرة والحساب والمنطق)", self._open_games, True, False),
                ("شهاداتي (الدورات المكتملة)", self._open_certificates, True, False),
                ("الإنجازات", self._open_achievements, True, False),
                ("الإحصائيات", self._open_stats, True, False),
                ("الإعدادات", self._open_settings, True, False),
                ("التحقّق من التحديثات", self._open_updates, True, False),
                ("المساعدة والاختصارات", lambda e: self.on_help(), True, False),
            ]),
        ]

        self._first_btn = None
        self._features = []          # (label, handler) for quick-jump
        for title, buttons in sections:
            tab = wx.ScrolledWindow(self.notebook)
            tab.SetScrollRate(0, 12)
            tsizer = wx.BoxSizer(wx.VERTICAL)
            for label, handler, cond, is_default in buttons:
                if not cond:
                    continue
                btn = self.button(tab, label, handler)
                tsizer.Add(btn, 0, wx.EXPAND | wx.ALL, 5)
                self._features.append((label, handler))
                if self._first_btn is None:
                    self._first_btn = btn
                    self.dailyBtn = btn
                if is_default:
                    btn.SetDefault()
                if handler == self._open_learn:
                    self.learnBtn = btn
            tab.SetSizer(tsizer)
            self.notebook.AddPage(tab, title)

        # a persistent close button below the tabs
        sizer.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()),
                  0, wx.ALIGN_RIGHT | wx.ALL, 6)

        panel.SetSizer(sizer)
        if self._first_btn is not None:
            self.dailyBtn = self.dailyBtn if hasattr(self, "dailyBtn") else self._first_btn
        # focus the quick-jump box so a learner can reach any feature instantly;
        # Tab moves into the sections.
        self.set_first_control(self.jumpEntry)
        # Ctrl+Tab / Ctrl+Shift+Tab move between sections and speak the new one
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_tab_changed)
        # first run: greet the learner once, then never again
        try:
            if self.academy.settings._store.get_setting("onboarded", "") != "1":
                wx.CallAfter(self._open_onboarding, None)
        except Exception:
            pass
        self._maybe_welcome()

    def _quick_jump(self):
        """Open the feature whose name best matches the typed text."""
        query = self.jumpEntry.GetValue().strip()
        if not query:
            return
        q = query.casefold()
        # exact-ish contains match first, then word-overlap
        best = None
        for label, handler in self._features:
            if q in label.casefold():
                best = (label, handler)
                break
        if best is None:
            # fall back to any word overlap
            qwords = set(q.split())
            for label, handler in self._features:
                if qwords & set(label.casefold().split()):
                    best = (label, handler)
                    break
        if best is None:
            self.announce("لم أجد ميزة بهذا الاسم. جرّب كلمة أخرى.")
            return
        label, handler = best
        self.jumpEntry.SetValue("")
        self.announce(f"فتح: {label}")
        handler(None)

    def _on_tab_changed(self, evt):
        # Announce the section name but DO NOT move focus into the page. If we
        # grabbed focus here, arrowing left/right along the tab headers would
        # jerk the user into the page content and they couldn't keep browsing
        # tabs. Standard behaviour: stay on the tab bar; the user presses Tab to
        # enter the section when ready.
        try:
            idx = evt.GetSelection()
            title = self.notebook.GetPageText(idx)
            self.announce(f"قسم {title}")
        except Exception:
            pass
        evt.Skip()

    def on_tab_key(self):
        """Ctrl+Tab handled by the notebook natively; this is a no-op hook kept
        for clarity."""
        return False

    # -- helpers ----------------------------------------------------------

    def _progress_text(self) -> str:
        s = self.academy.home_summary()
        parts = [f"سلسلتك: {s['streak']} يوماً"]
        # daily goal — front and centre so the learner has a target each day
        goal, today = s.get("daily_goal", 0), s.get("today_answered", 0)
        if goal:
            if s.get("goal_met"):
                parts.append(f"هدف اليوم: تحقّق! ({today} من {goal})")
            else:
                parts.append(f"هدف اليوم: {today} من {goal} سؤالاً")
        parts.append(f"الدروس المكتملة: {s['lessons_done']} من {s['lessons_total']}")
        if s["answered"]:
            parts.append(f"الدقة: {s['accuracy']} بالمئة")
        if s["minutes"]:
            parts.append(f"وقت الدراسة: {s['minutes']} دقيقة")
        parts.append(f"الإنجازات: {s['earned_achievements']} من {s['total_achievements']}")
        return " | ".join(parts)

    def _refresh_progress(self):
        try:
            self.progressLabel.SetLabel(self._progress_text())
            self.panel_layout()
        except Exception:
            pass

    def panel_layout(self):
        if self.progressLabel and self.progressLabel.GetParent():
            self.progressLabel.GetParent().Layout()

    def _maybe_welcome(self):
        if self.academy.store.get_setting("welcomed", "0") != "1":
            self.academy.store.set_setting("welcomed", "1")
            self.announce(
                "أهلاً بك في أكاديمية الكفيف العربي. ابدأ بـ«تدريب اليوم» لمراجعة سريعة، "
                "أو ادخل «كل الدورات والدروس» لتختار مجالك. اضغط F1 في أي وقت لمعرفة الاختصارات.")

    def _run_session(self, session, title):
        if session is None:
            self.announce("لا توجد أسئلة متاحة الآن. جرّب درساً من «كل الدورات والدروس» أولاً.")
            return
        runner = ExerciseRunner(self, self.academy, session, title, self.speech)
        self.show_child(runner)
        self._refresh_progress()

    # -- actions ----------------------------------------------------------

    def _open_daily(self, evt):
        self._run_session(self.academy.build_daily_session(), "تدريب اليوم")

    def _continue_last(self, evt):
        lid = self.academy.last_lesson()
        if not lid:
            self.announce("لا يوجد درس سابق بعد.")
            return
        self._run_session(self.academy.build_lesson_practice(lid), "متابعة آخر درس")

    def _open_review(self, evt):
        session = self.academy.build_review_session(limit=20)
        if session is None:
            self.announce("لا توجد عناصر مستحقّة للمراجعة الآن. تدرّب أكثر وستظهر لاحقاً.")
            return
        self._run_session(session, "المراجعة المجدولة")

    def _open_certificates(self, evt):
        self.show_child(CertificatesView(self, self.academy, self.speech))

    def _open_updates(self, evt):
        from .update_view import UpdateDialog
        self.show_child(UpdateDialog(self, self.academy, self.speech))

    def _open_export(self, evt):
        self.show_child(ExportView(self, self.academy, self.speech))

    def _open_onboarding(self, evt):
        self.show_child(OnboardingView(self, self.academy, self.speech))

    def _open_settings(self, evt):
        self.show_child(SettingsView(self, self.academy, self.speech))

    def _open_mistakes(self, evt):
        self.show_child(MistakesView(self, self.academy, self.speech))

    def _open_search(self, evt):
        self.show_child(SearchView(self, self.academy, self.speech))

    def _open_tutor(self, evt):
        from .tutor_view import TutorDialog
        self.show_child(TutorDialog(self, self.academy, self.speech))

    def _open_progress(self, evt):
        from .progress_view import ProgressDialog
        self.show_child(ProgressDialog(self, self.academy, self.speech))

    def _build_session_async(self, builder, title, empty_msg):
        """Run a potentially slow session builder off the UI thread so the screen reader never
        freezes. Announces a short wait message, builds in a background thread,
        then launches the session (or reports emptiness) back on the UI thread."""
        import threading
        self.announce("يُجهّز التدريب، لحظة من فضلك…")

        def work():
            try:
                session = builder()
            except Exception:
                session = None
            wx.CallAfter(finish, session)

        def finish(session):
            if session is None:
                self.announce(empty_msg)
                return
            self._run_session(session, title)

        threading.Thread(target=work, daemon=True).start()

    def _open_weak(self, evt):
        self._build_session_async(
            lambda: self.academy.build_weak_topics_session(limit=15),
            "تدريب نقاط الضعف",
            "لا توجد نقاط ضعف مسجّلة بعد. تدرّب أكثر وسيتعرّف البرنامج عليها.")

    def _open_adaptive(self, evt):
        self._build_session_async(
            lambda: self.academy.build_adaptive_session(limit=12),
            "جلسة المعلّم الذكي",
            "ابدأ بأيّ درس أولًا، وبعد تدريبٍ قليل سيبني لك المعلّم الذكي "
            "جلسة متكيّفة مع مستواك.")

    def _open_learn(self, evt):
        self.show_child(MainWindow(self, self.academy, self.speech))
        self._refresh_progress()

    def _open_typing(self, evt):
        keys = list(TIERS.keys())
        labels = [TIERS[k][0] for k in keys]
        choice = wx.SingleChoiceDialog(self, "اختر مستوى التحدي:", "تحدي الكتابة", labels)
        if choice.ShowModal() == wx.ID_OK:
            tier = keys[choice.GetSelection()]
            self.show_child(KeyboardTrainer(self, self.academy, tier, self.speech))
        choice.Destroy()

    def _open_quran(self, evt):
        self.show_child(QuranReader(self, self.academy, self.speech))

    def _open_hadith(self, evt):
        self.show_child(HadithReader(self, self.academy, self.speech))

    def _open_flashcards(self, evt):
        self.show_child(FlashcardsHome(self, self.academy, self.speech))

    def _open_islamic(self, evt):
        self.show_child(IslamicToolsHome(self, self.academy, self.speech))

    def _open_games(self, evt):
        self.show_child(GamesHome(self, self.academy, self.speech))

    def _open_grapher(self, evt):
        from .grapher import GrapherDialog
        self.show_child(GrapherDialog(self, self.academy, self.speech))

    def _open_calculator(self, evt):
        from .calculator import CalculatorDialog
        self.show_child(CalculatorDialog(self, self.academy, self.speech))

    def _open_codelab(self, evt):
        from .codelab_view import CodeLabDialog
        self.show_child(CodeLabDialog(self, self.academy, self.speech))

    def _open_curriculum(self, evt):
        from .curriculum_view import CurriculumDialog
        self.show_child(CurriculumDialog(self, self.academy, self.speech))

    def _open_pomodoro(self, evt):
        from .pomodoro_view import PomodoroDialog
        self.show_child(PomodoroDialog(self, self.academy, self.speech))

    def _open_notebook(self, evt):
        from .notebook_view import NotebookDialog
        self.show_child(NotebookDialog(self, self.academy, self.speech))

    def _open_shortcuts(self, evt):
        from .shortcuts_view import ShortcutsDialog
        self.show_child(ShortcutsDialog(self, self.academy, self.speech))

    def _open_clipboard(self, evt):
        from .clipboard_view import ClipboardDialog
        self.show_child(ClipboardDialog(self, self.academy, self.speech))

    def _open_converter(self, evt):
        from .converter import ConverterDialog
        self.show_child(ConverterDialog(self, self.academy, self.speech))

    def _open_perkins(self, evt):
        from .perkins_tutor import PerkinsTutorDialog
        self.show_child(PerkinsTutorDialog(self, self.academy, self.speech))

    def _open_braille_lessons(self, evt):
        from .braille_lessons_view import BrailleLessonsDialog
        self.show_child(BrailleLessonsDialog(self, self.academy, self.speech))

    def _open_packs(self, evt):
        from .pack_manager import PackManagerDialog
        self.show_child(PackManagerDialog(self, self.academy, self.speech))

    def _open_quran_study(self, evt):
        from .quran_study import QuranStudyDialog
        self.show_child(QuranStudyDialog(self, self.academy, self.speech))

    def _open_tafsir_compare(self, evt):
        from .tafsir_compare import TafsirCompareDialog
        self.show_child(TafsirCompareDialog(self, self.academy, self.speech))

    def _open_hifz_tester(self, evt):
        from .hifz_tester import HifzTesterDialog
        self.show_child(HifzTesterDialog(self, self.academy, self.speech))

    def _open_spelling(self, evt):
        from .spelling_view import SpellingDialog
        self.show_child(SpellingDialog(self, self.academy, self.speech))

    def _open_conjugator(self, evt):
        from .conjugator_view import ConjugatorDialog
        self.show_child(ConjugatorDialog(self, self.academy, self.speech))

    def _open_docstudio(self, evt):
        from .docstudio_view import DocStudioDialog
        self.show_child(DocStudioDialog(self, self.academy, self.speech))

    def _open_student_tools(self, evt):
        from .student_tools_view import StudentToolsDialog
        self.show_child(StudentToolsDialog(self, self.academy, self.speech))

    def _open_dictionary(self, evt):
        self.show_child(DictionaryDialog(self, self.academy, self.speech))

    def _open_achievements(self, evt):
        self.show_child(AchievementsView(self, self.academy, self.speech))

    def _open_stats(self, evt):
        self.show_child(StatisticsView(self, self.academy, self.speech))

    def instructions(self) -> str:
        return ("استخدم Tab للتنقل بين الأزرار وEnter للاختيار. "
                "Escape للإغلاق، وF1 لعرض كل الاختصارات.")

    def on_closing(self):
        clear_shutdown()
