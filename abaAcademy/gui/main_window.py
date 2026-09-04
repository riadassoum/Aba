# -*- coding: utf-8 -*-
"""
abaAcademy.gui.main_window
==========================

The primary navigation surface: choose a course, then a level, then one or more
lessons. From here the learner can read/play a lesson, start its quiz, build a
balanced mixed session from several checked lessons, run endless practice, run a
spaced-repetition review across everything due, search the catalogue, or open
statistics.

Multi-selection is a real ``wx.ListBox`` with ``LB_EXTENDED`` so several lessons
can be checked and fed to ``academy.build_mixed_session`` — the spec's
"select lessons 5, 9, 12 -> balanced mixed session" requirement.

Everything inherits the AccessibleDialog announce-on-show and shortcut policy.
"""

from __future__ import annotations

import wx

from .accessible import AccessibleDialog
from .exercise_runner import ExerciseRunner
from .lesson_player import LessonPlayer
from .statistics_view import StatisticsView


class MainWindow(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "أكاديمية الكفيف العربي — التعلّم", speech, size=(860, 620))
        self.academy = academy
        self._courses = academy.courses()
        self._levels = []
        self._lesson_metas = []

        panel = wx.Panel(self)
        self.panel = panel
        outer = wx.BoxSizer(wx.VERTICAL)

        self.xpLabel = wx.StaticText(panel, label="")
        outer.Add(self.xpLabel, 0, wx.ALL, 6)

        cols = wx.BoxSizer(wx.HORIZONTAL)

        # courses
        cbox = wx.BoxSizer(wx.VERTICAL)
        cbox.Add(wx.StaticText(panel, label="الدورات:"), 0, wx.ALL, 3)
        self.courseList = wx.ListBox(panel, size=(230, 380))
        self.courseList.SetName("قائمة الدورات")
        for c in self._courses:
            self.courseList.Append(f"{c.title} ({c.lesson_count()} درس)")
        self.courseList.Bind(wx.EVT_LISTBOX, self._on_course)
        cbox.Add(self.courseList, 1, wx.EXPAND | wx.ALL, 3)
        cols.Add(cbox, 1, wx.EXPAND)

        # levels
        lbox = wx.BoxSizer(wx.VERTICAL)
        lbox.Add(wx.StaticText(panel, label="المستويات:"), 0, wx.ALL, 3)
        self.levelList = wx.ListBox(panel, size=(230, 380))
        self.levelList.SetName("قائمة المستويات")
        self.levelList.Bind(wx.EVT_LISTBOX, self._on_level)
        lbox.Add(self.levelList, 1, wx.EXPAND | wx.ALL, 3)
        cols.Add(lbox, 1, wx.EXPAND)

        # lessons (multi-select)
        sbox = wx.BoxSizer(wx.VERTICAL)
        sbox.Add(wx.StaticText(panel, label="الدروس (يمكن اختيار عدة دروس):"), 0, wx.ALL, 3)
        self.lessonList = wx.ListBox(panel, size=(280, 380), style=wx.LB_EXTENDED)
        self.lessonList.SetName("قائمة الدروس، يمكن تحديد أكثر من درس")
        self.lessonList.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._play_lesson())
        sbox.Add(self.lessonList, 1, wx.EXPAND | wx.ALL, 3)
        cols.Add(sbox, 1, wx.EXPAND)

        outer.Add(cols, 1, wx.EXPAND | wx.ALL, 4)

        # action buttons
        btns = wx.WrapSizer(wx.HORIZONTAL)
        btns.Add(self.button(panel, "افتح الدرس (شرح)", lambda e: self._play_lesson()), 0, wx.ALL, 4)
        btns.Add(self.button(panel, "تمارين الدرس", lambda e: self._lesson_quiz()), 0, wx.ALL, 4)
        btns.Add(self.button(panel, "جلسة مختلطة للدروس المحددة", lambda e: self._mixed()), 0, wx.ALL, 4)
        btns.Add(self.button(panel, "تدريب لا نهائي", lambda e: self._endless()), 0, wx.ALL, 4)
        btns.Add(self.button(panel, "مراجعة مجدولة", lambda e: self._review()), 0, wx.ALL, 4)
        btns.Add(self.button(panel, "بحث", lambda e: self._search()), 0, wx.ALL, 4)
        btns.Add(self.button(panel, "الإحصائيات", lambda e: self.on_statistics()), 0, wx.ALL, 4)
        btns.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        outer.Add(btns, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(outer)
        self.set_first_control(self.courseList)
        if self._courses:
            self.select_index(self.courseList, 0)
            self._on_course(None)
        self._refresh_xp()

    def instructions(self) -> str:
        return ("اختر دورة ثم مستوى ثم درساً. Ctrl+S للإحصائيات، F1 للمساعدة، Escape للرجوع.")

    # -- selection helpers -------------------------------------------------

    def _refresh_xp(self):
        parts = []
        for c in self._courses:
            done = self.academy.completed_lessons(c.course_id)
            parts.append(f"{c.title}: {done}/{c.lesson_count()}")
        streak = self.academy.store.current_streak()
        self.xpLabel.SetLabel("التقدّم — " + " | ".join(parts) + f" | سلسلة: {streak} يوم")

    def _current_course(self):
        i = self.courseList.GetSelection()
        return self._courses[i] if 0 <= i < len(self._courses) else None

    def _on_course(self, evt):
        course = self._current_course()
        self.levelList.Clear()
        self.lessonList.Clear()
        self._levels = course.levels if course else []
        for lv in self._levels:
            self.levelList.Append(f"{lv.title} ({len(lv.lesson_metas)} درس)")
        if self._levels:
            self.select_index(self.levelList, 0)
            self._on_level(None)

    def _on_level(self, evt):
        i = self.levelList.GetSelection()
        self.lessonList.Clear()
        self._lesson_metas = self._levels[i].lesson_metas if 0 <= i < len(self._levels) else []
        for m in self._lesson_metas:
            prog = self.academy.store.get_lesson_progress(m.lesson_id)
            mark = ""
            if prog and prog.get("completed"):
                mark = f" — مكتمل {prog.get('best_score',0)}٪"
            elif prog and prog.get("best_score"):
                mark = f" — أفضل {prog.get('best_score',0)}٪"
            self.lessonList.Append(f"{m.title}{mark}")

    def _selected_lessons(self):
        return [self._lesson_metas[i] for i in self.lessonList.GetSelections()
                if 0 <= i < len(self._lesson_metas)]

    def _first_selected(self):
        sels = self._selected_lessons()
        return sels[0] if sels else None

    # -- actions -----------------------------------------------------------

    def _play_lesson(self):
        meta = self._first_selected()
        if not meta:
            self.announce("اختر درساً أولاً")
            return
        lesson = self.academy.load_lesson(meta.lesson_id)
        if not lesson:
            self.announce("تعذّر تحميل الدرس")
            return
        self.show_child(LessonPlayer(self, self.academy, lesson, self.speech))
        self._on_level(None)
        self._refresh_xp()

    def _lesson_quiz(self):
        meta = self._first_selected()
        if not meta:
            self.announce("اختر درساً أولاً")
            return
        session = self.academy.build_lesson_quiz(meta.lesson_id)
        self._run(session, f"تمارين: {meta.title}", meta)

    def _mixed(self):
        metas = self._selected_lessons()
        if len(metas) < 2:
            self.announce("حدّد درسين أو أكثر لبناء جلسة مختلطة")
            return
        session = self.academy.build_mixed_session([m.lesson_id for m in metas])
        self._run(session, f"جلسة مختلطة ({len(metas)} دروس)", None)

    def _endless(self):
        metas = self._selected_lessons() or self._lesson_metas[:1]
        if not metas:
            self.announce("اختر درساً أولاً")
            return
        session = self.academy.build_endless_practice([m.lesson_id for m in metas])
        self._run(session, "تدريب لا نهائي", None, summary=False)

    def _review(self):
        session = self.academy.build_review_session(limit=20)
        if session is None:
            self.announce("لا توجد عناصر مستحقّة للمراجعة الآن. تعلّم دروساً جديدة أولاً.")
            return
        self._run(session, "مراجعة مجدولة", None)

    def _run(self, session, title, meta, summary=True):
        if session is None:
            self.announce("لا توجد أسئلة متاحة لهذه الجلسة")
            return
        runner = ExerciseRunner(
            self, self.academy, session, title, self.speech,
            lesson_id=meta.lesson_id if meta else "",
            level_id=meta.level_id if meta else "",
            course_id=meta.course_id if meta else "",
            on_finish_summary=summary)
        self.show_child(runner)
        self._on_level(None)
        self._refresh_xp()

    def _search(self):
        dlg = wx.TextEntryDialog(self, "اكتب كلمة للبحث في الدروس والقواعد:", "بحث")
        if dlg.ShowModal() == wx.ID_OK:
            query = dlg.GetValue()
            results = self.academy.search(query)
            if not results:
                self.announce("لا نتائج")
                wx.MessageBox("لا توجد نتائج مطابقة.", "بحث", wx.OK)
            else:
                names = "\n".join(f"{r['title']} — {r['course_id']}" for r in results[:40])
                self.announce(f"عدد النتائج {len(results)}")
                wx.MessageBox(f"عدد النتائج: {len(results)}\n\n{names}", "نتائج البحث", wx.OK)
        dlg.Destroy()

    def on_statistics(self):
        self.show_child(StatisticsView(self, self.academy, self.speech))
