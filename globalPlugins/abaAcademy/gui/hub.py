# -*- coding: utf-8 -*-
"""
abaAcademy.gui.hub
==================

The Academy hub — the first screen from the NVDA Tools menu. It's designed to
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
__version__ = "1.0"


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
            panel, label="اختر ما تريد. تشمل الأكاديمية: العربية والإنجليزية والفرنسية "
                        "وبرايل والحاسوب والرياضيات والعلوم والتاريخ والجغرافيا والثقافة العامة.")
        intro.Wrap(560)
        sizer.Add(intro, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # primary action: practice of the day
        self.dailyBtn = self.button(panel, "تدريب اليوم (مراجعة متنوّعة سريعة)", self._open_daily)
        self.dailyBtn.SetDefault()
        sizer.Add(self.dailyBtn, 0, wx.EXPAND | wx.ALL, 6)

        # continue last lesson (only if there is one)
        if self.academy.last_lesson():
            sizer.Add(self.button(panel, "متابعة آخر درس", self._continue_last),
                      0, wx.EXPAND | wx.ALL, 6)

        sizer.Add(self.button(panel, "المراجعة المجدولة (تكرار متباعد)", self._open_review),
                  0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.button(panel, "تدريب نقاط الضعف (الأكثر خطأً)", self._open_weak),
                  0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.button(panel, "دفتر الأخطاء (راجع وتدرّب على أخطائك)", self._open_mistakes),
                  0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.button(panel, "بحث في كل الدروس", self._open_search),
                  0, wx.EXPAND | wx.ALL, 6)
        self.learnBtn = self.button(panel, "كل الدورات والدروس", self._open_learn)
        sizer.Add(self.learnBtn, 0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.button(panel, "تحدي الكتابة السريعة والدقيقة", self._open_typing),
                  0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.button(panel, "قراءة القرآن الكريم (تنقّل واستماع)", self._open_quran),
                  0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.button(panel, "قارئ الحديث الشريف", self._open_hadith),
                  0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.button(panel, "البطاقات التعليمية (مراجعة ذكية)", self._open_flashcards),
                  0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.button(panel, "أدوات إسلامية (الأسماء الحسنى ومواقيت الصلاة)", self._open_islamic),
                  0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.button(panel, "الألعاب الذهنية (تقوية الذاكرة والحساب والمنطق)", self._open_games),
                  0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.button(panel, "القاموس الإنجليزي", self._open_dictionary),
                  0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.button(panel, "الإنجازات", self._open_achievements),
                  0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.button(panel, "الإحصائيات", self._open_stats),
                  0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.button(panel, "المساعدة والاختصارات", lambda e: self.on_help()),
                  0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()),
                  0, wx.ALIGN_RIGHT | wx.ALL, 6)

        panel.SetSizer(sizer)
        self.set_first_control(self.dailyBtn)
        # first run: greet the learner once, then never again
        try:
            if self.academy.settings._store.get_setting("onboarded", "") != "1":
                wx.CallAfter(self._open_onboarding, None)
        except Exception:
            pass
        self._maybe_welcome()

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

    def _open_weak(self, evt):
        session = self.academy.build_weak_topics_session(limit=15)
        if session is None:
            self.announce("لا توجد نقاط ضعف مسجّلة بعد. تدرّب أكثر وسيتعرّف البرنامج عليها.")
            return
        self._run_session(session, "تدريب نقاط الضعف")

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
