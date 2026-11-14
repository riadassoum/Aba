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
__version__ = "3.0"


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
            panel, label="Ctrl+Tab ينقلك بين الأقسام، والأسهم بين الميزات داخل القسم، وEnter يفتح الميزة. "
                        "أو اكتب اسم ميزة في الانتقال السريع.")
        intro.Wrap(640)
        sizer.Add(intro, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # a quick-jump search box above the tabs lets a learner reach any
        # feature by name without hunting through sections.
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

        # Each tab is a list of features (one Tab stop instead of a dozen
        # buttons), a large description of the selected feature for sighted
        # helpers and low-vision learners, and an Open button for the mouse.
        from .hub_catalog import CATALOG
        conditions = {
            "has_last": bool(self.academy.last_lesson()),
            "has_profiles": bool(getattr(self.academy, "profiles_root", "")),
        }
        self._tab_lists = []
        self._features = []          # (label, handler, description) for quick-jump
        self._describe_timer = None
        for tab_info in CATALOG:
            items = [f for f in tab_info.features if not f.when or conditions.get(f.when, False)]
            items = [f for f in items if not f.handler.startswith("course:")
                     or self.academy.course(f.handler.split(":", 1)[1]) is not None]
            page = wx.Panel(self.notebook)
            ps = wx.BoxSizer(wx.VERTICAL)
            summary = wx.StaticText(page, label=tab_info.summary)
            ps.Add(summary, 0, wx.ALL, 6)
            lst = wx.ListBox(page, choices=[f.label for f in items], style=wx.LB_SINGLE)
            lst.SetName(f"{tab_info.title}: {tab_info.summary}")
            if items:
                lst.SetSelection(0)
            ps.Add(lst, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
            desc = wx.StaticText(page, label=items[0].description if items else "")
            dfont = desc.GetFont()
            dfont.SetPointSize(dfont.GetPointSize() + 2)
            desc.SetFont(dfont)
            desc.Wrap(600)
            ps.Add(desc, 0, wx.EXPAND | wx.ALL, 8)
            open_btn = self.button(page, "افتح", lambda e, L=lst, I=items: self._open_selected(L, I))
            ps.Add(open_btn, 0, wx.ALIGN_LEFT | wx.LEFT | wx.BOTTOM, 6)
            page.SetSizer(ps)
            lst.Bind(wx.EVT_LISTBOX, lambda e, L=lst, I=items, D=desc: self._on_feature_selected(L, I, D))
            lst.Bind(wx.EVT_LISTBOX_DCLICK, lambda e, L=lst, I=items: self._open_selected(L, I))
            lst.Bind(wx.EVT_KEY_DOWN, lambda e, L=lst, I=items: self._on_list_key(e, L, I))
            self.notebook.AddPage(page, tab_info.title)
            self._tab_lists.append((lst, items, desc))
            for f in items:
                self._features.append((f.label, self._resolve(f.handler), f.description))
        self._home_base = list(self._tab_lists[0][1]) if self._tab_lists else []
        self._refresh_recent()
        self.dailyBtn = self._tab_lists[0][0] if self._tab_lists else None
        self.learnBtn = self.dailyBtn

        # a persistent close button below the tabs
        sizer.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()),
                  0, wx.ALIGN_RIGHT | wx.ALL, 6)

        panel.SetSizer(sizer)
        # focus the quick-jump box so a learner can reach any feature instantly;
        # Tab moves into the sections.
        self.set_first_control(self.jumpEntry)
        # Ctrl+Tab / Ctrl+Shift+Tab move between sections and speak the new one
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_tab_changed)
        # first run: greet the learner once, then never again
        try:
            if self.academy.settings._store.get_setting("onboarded", "") != "1":
                self.call_after(self._open_onboarding, None)
        except Exception:
            pass
        self._maybe_welcome()

    def _quick_jump(self):
        """Open the feature whose name best matches the typed text, and name
        the next-best matches so the learner knows what else was found."""
        query = self.jumpEntry.GetValue().strip()
        if not query:
            return
        from ..tools.feature_search import search
        labels = [label for label, _, _ in self._features]
        hits = search(query, labels)
        if not hits:
            hits = search(query, [f"{label} {desc}" for label, _, desc in self._features])
        if not hits:
            self.announce("لم أجد ميزة بهذا الاسم. جرّب كلمة أخرى.")
            return
        _, best = hits[0]
        label, handler, _ = self._features[best]
        try:
            from .hub_catalog import all_features
            feat = next((f for f in all_features() if f.label == label), None)
            if feat is not None:
                self._remember(feat)
        except Exception:
            pass
        others = [labels[i] for _, i in hits[1:3]]
        self.jumpEntry.SetValue("")
        msg = f"فتح: {label}"
        if others:
            msg += ". ووجدت أيضًا: " + "، ".join(others)
        self.announce(msg)
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

    # -- feature lists -------------------------------------------------------

    def _resolve(self, name):
        if name.startswith("course:"):
            cid = name.split(":", 1)[1]
            return lambda evt, c=cid: self._open_course(c)
        return getattr(self, name)

    RECENT_KEY = "hub_recent_features"

    def _recent_labels(self):
        import json
        try:
            data = json.loads(self.academy.store.get_setting(self.RECENT_KEY, "[]") or "[]")
            return [x for x in data if isinstance(x, str)][:5]
        except Exception:
            return []

    def _remember(self, feature):
        import json
        labels = [l for l in self._recent_labels() if l != feature.label]
        labels.insert(0, feature.label)
        try:
            self.academy.store.set_setting(self.RECENT_KEY, json.dumps(labels[:5], ensure_ascii=False))
        except Exception:
            return
        self._refresh_recent()

    def _refresh_recent(self):
        """Put the last features used (from any tab) at the top of the home tab."""
        if not self._tab_lists:
            return
        lst, items, desc = self._tab_lists[0]
        from .hub_catalog import all_features
        by_label = {f.label: f for f in all_features()}
        home_labels = {f.label for f in self._home_base}
        recent = [by_label[l] for l in self._recent_labels() if l in by_label and l not in home_labels]
        recent = [f._replace(description="استعملتها مؤخرًا. " + f.description) for f in recent]
        sel = lst.GetSelection()
        items[:] = recent + self._home_base
        lst.Set([f.label for f in items])
        if items:
            lst.SetSelection(sel if 0 <= sel < len(items) else 0)

    def _open_selected(self, lst, items):
        i = lst.GetSelection()
        if 0 <= i < len(items):
            feature = items[i]
            self._remember(feature)
            self._resolve(feature.handler)(None)

    def _on_list_key(self, evt, lst, items):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._open_selected(lst, items)
            return
        evt.Skip()

    def _on_feature_selected(self, lst, items, desc):
        i = lst.GetSelection()
        if not (0 <= i < len(items)):
            return
        desc.SetLabel(items[i].description)
        desc.Wrap(max(300, desc.GetParent().GetClientSize().width - 20))
        desc.GetParent().Layout()
        try:
            from ..display_prefs import DisplayPrefs
            describe = DisplayPrefs.load(self.academy.store).describe_features
        except Exception:
            describe = True
        if not describe:
            return
        if self._describe_timer is not None:
            try:
                self._describe_timer.Stop()
            except Exception:
                pass
        text = items[i].description

        def speak(L=lst, idx=i, t=text):
            if self and L and L.GetSelection() == idx and L.HasFocus():
                self.speech.speak_line(t) if hasattr(self.speech, "speak_line") else self.speech.announce(t)
        self._describe_timer = wx.CallLater(900, speak)

    def _open_placement(self, evt):
        from .placement_view import PlacementDialog
        self.show_child(PlacementDialog(self, self.academy, self.speech))

    def _open_overview(self, evt):
        from .overview_view import OverviewDialog
        self.show_child(OverviewDialog(self, self.academy, self.speech))

    def _open_course(self, course_id):
        self.show_child(MainWindow(self, self.academy, self.speech, course_id=course_id))
        self._refresh_progress()

    def _open_display(self, evt):
        from .display_view import DisplayDialog
        self.show_child(DisplayDialog(self, self.academy, self.speech))

    def _open_help(self, evt):
        self.on_help()

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
                "أهلاً بك في أكاديمية الكفيف العربي. ابدأ بـتدريب اليوم لمراجعة سريعة، "
                "أو ادخل كل الدورات والدروس لتختار مجالك. اضغط F1 في أي وقت لمعرفة الاختصارات.")

    def _run_session(self, session, title):
        if session is None:
            self.announce("لا توجد أسئلة متاحة الآن. جرّب درساً من كل الدورات والدروس أولاً.")
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

    # -- 3.0 screens -------------------------------------------------------
    def _open_khatma(self, evt):
        from .planner_view import KhatmaDialog
        self.show_child(KhatmaDialog(self, self.academy, self.speech))

    def _open_prayer(self, evt):
        from .prayer_view import PrayerTimesDialog
        self.show_child(PrayerTimesDialog(self, self.academy, self.speech))

    def _open_calendar(self, evt):
        from .calendar_view import CalendarDialog
        self.show_child(CalendarDialog(self, self.academy, self.speech))

    def _open_zakat(self, evt):
        from .skills_view import ZakatDialog
        self.show_child(ZakatDialog(self, self.academy, self.speech))

    def _open_roots(self, evt):
        from .roots_view import RootsDialog
        self.show_child(RootsDialog(self, self.academy, self.speech))

    def _open_arud(self, evt):
        from .arud_view import ArudDialog
        self.show_child(ArudDialog(self, self.academy, self.speech))

    def _open_periodic(self, evt):
        from .periodic_view import PeriodicTableDialog
        self.show_child(PeriodicTableDialog(self, self.academy, self.speech))

    def _open_equations(self, evt):
        from .math_tools_view import EquationDialog
        self.show_child(EquationDialog(self, self.academy, self.speech))

    def _open_geometry(self, evt):
        from .math_tools_view import GeometryDialog
        self.show_child(GeometryDialog(self, self.academy, self.speech))

    def _open_matrices(self, evt):
        from .math_tools_view import MatrixDialog
        self.show_child(MatrixDialog(self, self.academy, self.speech))

    def _open_stats_tool(self, evt):
        from .math_tools_view import StatsDialog
        self.show_child(StatsDialog(self, self.academy, self.speech))

    def _open_bases(self, evt):
        from .math_tools_view import BasesDialog
        self.show_child(BasesDialog(self, self.academy, self.speech))

    def _open_mental_math(self, evt):
        from .math_tools_view import MentalMathDialog
        self.show_child(MentalMathDialog(self, self.academy, self.speech))

    def _open_logic(self, evt):
        from .math_tools_view import LogicDialog
        self.show_child(LogicDialog(self, self.academy, self.speech))

    def _open_web_lab(self, evt):
        from .web_lab_view import WebLabDialog
        self.show_child(WebLabDialog(self, self.academy, self.speech))

    def _open_morse(self, evt):
        from .morse_view import MorseDialog
        self.show_child(MorseDialog(self, self.academy, self.speech))

    def _open_planner(self, evt):
        from .planner_view import PlannerDialog
        self.show_child(PlannerDialog(self, self.academy, self.speech))

    def _open_deck_import(self, evt):
        from .deck_import_view import DeckImportDialog
        self.show_child(DeckImportDialog(self, self.academy, self.speech))

    def _open_number_rules(self, evt):
        from .study_tools_view import NumberRulesDialog
        self.show_child(NumberRulesDialog(self, self.academy, self.speech))

    def _open_tracer(self, evt):
        from .study_tools_view import TracerDialog
        self.show_child(TracerDialog(self, self.academy, self.speech))

    def _open_sheet(self, evt):
        from .study_tools_view import SheetDialog
        self.show_child(SheetDialog(self, self.academy, self.speech))

    def _open_school_calc(self, evt):
        from .study_tools_view import SchoolCalcDialog
        self.show_child(SchoolCalcDialog(self, self.academy, self.speech))

    def _open_chemistry(self, evt):
        from .science_lab_view import ChemistryDialog
        self.show_child(ChemistryDialog(self, self.academy, self.speech))

    def _open_physics(self, evt):
        from .science_lab_view import PhysicsDialog
        self.show_child(PhysicsDialog(self, self.academy, self.speech))

    def _open_regex(self, evt):
        from .science_lab_view import RegexLabDialog
        self.show_child(RegexLabDialog(self, self.academy, self.speech))

    def _open_text_stats(self, evt):
        from .science_lab_view import TextStatsDialog
        self.show_child(TextStatsDialog(self, self.academy, self.speech))

    def _open_tasbih(self, evt):
        from .daily_tools_view import TasbihDialog
        self.show_child(TasbihDialog(self, self.academy, self.speech))

    def _open_arithmetic(self, evt):
        from .daily_tools_view import ArithmeticDialog
        self.show_child(ArithmeticDialog(self, self.academy, self.speech))

    def _open_countries(self, evt):
        from .daily_tools_view import CountriesDialog
        self.show_child(CountriesDialog(self, self.academy, self.speech))

    def _open_times(self, evt):
        from .daily_tools_view import TimesTablesDialog
        self.show_child(TimesTablesDialog(self, self.academy, self.speech))

    def _open_weekly(self, evt):
        from .quiz_builder_view import WeeklyReportDialog
        self.show_child(WeeklyReportDialog(self, self.academy, self.speech))

    def _open_quiz_builder(self, evt):
        from .quiz_builder_view import QuizBuilderDialog
        self.show_child(QuizBuilderDialog(self, self.academy, self.speech))

    def _open_surah_quiz(self, evt):
        from .code_quran_extra_view import SurahQuizDialog
        self.show_child(SurahQuizDialog(self, self.academy, self.speech))

    def _open_gates(self, evt):
        from .code_quran_extra_view import GatesDialog
        self.show_child(GatesDialog(self, self.academy, self.speech))

    def _open_ds(self, evt):
        from .code_quran_extra_view import DataStructuresDialog
        self.show_child(DataStructuresDialog(self, self.academy, self.speech))

    def _open_algorithms(self, evt):
        from .code_quran_extra_view import AlgorithmsDialog
        self.show_child(AlgorithmsDialog(self, self.academy, self.speech))

    def _open_number_theory(self, evt):
        from .code_quran_extra_view import NumberTheoryDialog
        self.show_child(NumberTheoryDialog(self, self.academy, self.speech))

    def _open_clock(self, evt):
        from .daily_tools_view import ClockDialog
        self.show_child(ClockDialog(self, self.academy, self.speech))

    def _open_resistors(self, evt):
        from .daily_tools_view import ResistorsDialog
        self.show_child(ResistorsDialog(self, self.academy, self.speech))

    def _open_profiles(self, evt):
        from .profiles_view import ProfilesDialog
        self.show_child(ProfilesDialog(self, self.academy, self.speech))

    def _open_dictionary(self, evt):
        self.show_child(DictionaryDialog(self, self.academy, self.speech))

    def _open_achievements(self, evt):
        self.show_child(AchievementsView(self, self.academy, self.speech))

    def _open_stats(self, evt):
        self.show_child(StatisticsView(self, self.academy, self.speech))

    def instructions(self) -> str:
        base = ("الشاشة الرئيسية. اكتب اسم ميزة في الانتقال السريع، أو اضغط Tab للأقسام. "
                "Ctrl+Tab بين الأقسام، والأسهم بين الميزات، وEnter للفتح، وF2 لقراءة الشاشة كلها، "
                "وF1 للمساعدة، وEscape للإغلاق.")
        reminder = self._study_reminder()
        return f"{reminder} {base}" if reminder else base

    def _study_reminder(self) -> str:
        """Mentioned once when the academy opens: anything due today or
        tomorrow, and exams in the next three days, from the study planner."""
        if getattr(self, "_reminded", False):
            return ""
        self._reminded = True
        try:
            from ..study_hub.planner import Planner
            p = Planner(self.academy.store)
            soon = [i for i in p.items() if 0 <= i.days_left() <= (3 if i.kind == "exam" else 1)]
            late = [i for i in p.items() if i.days_left() < 0]
        except Exception:
            return ""
        parts = []
        for i in soon[:3]:
            d = i.days_left()
            when = "اليوم" if d == 0 else ("غدًا" if d == 1 else f"بعد {d} أيام")
            parts.append(f"{i.title} {when}")
        if late:
            parts.append(f"وعندك {len(late)} من المهامّ فات موعدها")
        return ("تذكير من مخطّط المذاكرة: " + "، ".join(parts) + ".") if parts else ""

    def on_closing(self):
        clear_shutdown()
