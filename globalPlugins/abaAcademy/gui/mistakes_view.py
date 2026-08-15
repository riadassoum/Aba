# -*- coding: utf-8 -*-
"""
abaAcademy.gui.mistakes_view
============================

A "mistake notebook" (دفتر الأخطاء): the topics the learner gets wrong most,
listed with how often, so they can see their weak spots and drill them straight
away. Reviewing one's own errors is one of the most effective study habits, and
until now the data was tracked but never shown. The "تدرّب على هذا" button turns
the selected weak topic into a fresh practice session on the spot.
"""

from __future__ import annotations

from .accessible import AccessibleDialog

try:
    import wx
except Exception:
    wx = None

AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def _ar(n):
    return str(n).translate(AR)


class MistakesView(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "دفتر الأخطاء", speech, size=(600, 520))
        self.academy = academy
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        try:
            self._weak = academy.store.weakest_topics(limit=40)
        except Exception:
            self._weak = []

        if not self._weak:
            s.Add(wx.StaticText(panel, label=(
                "لا أخطاء مسجّلة بعد. عندما تخطئ في أسئلة، ستُجمع مواضيعها هنا "
                "لتتدرّب عليها. تدرّب قليلاً ثم عُد.")), 0, wx.ALL, 10)
        else:
            s.Add(wx.StaticText(panel, label=(
                "أكثر المواضيع التي تخطئ فيها. اختر موضوعاً ثم «تدرّب على هذا» "
                "لجلسة تركّز عليه:")), 0, wx.ALL, 8)
            self.listbox = wx.ListBox(panel, style=wx.LB_SINGLE)
            items = []
            for topic, wrong, right in self._weak:
                total = wrong + right
                rate = round(wrong * 100 / total) if total else 0
                items.append(f"{self._topic_label(topic)} — أخطأت {_ar(wrong)} من {_ar(total)} "
                             f"({_ar(rate)}٪)")
            self.listbox.Set(items)
            self.listbox.SetSelection(0)
            self.listbox.SetName("قائمة المواضيع الأكثر خطأً")
            s.Add(self.listbox, 1, wx.EXPAND | wx.ALL, 6)
            s.Add(self.button(panel, "تدرّب على هذا الموضوع", lambda e: self._drill()),
                  0, wx.EXPAND | wx.ALL, 4)
            s.Add(self.button(panel, "تدرّب على كل نقاط ضعفي", lambda e: self._drill_all()),
                  0, wx.EXPAND | wx.ALL, 4)
        s.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()),
              0, wx.ALIGN_RIGHT | wx.ALL, 6)
        panel.SetSizer(s)
        first = getattr(self, "listbox", None) or panel.GetChildren()[0]
        self.set_first_control(first)

    def _topic_label(self, topic):
        # topics look like "geography:capital" or "en:confusable"; make readable
        if ":" in topic:
            a, b = topic.split(":", 1)
            names = {"en": "الإنجليزية", "fr": "الفرنسية", "confusable": "كلمات متشابهة",
                     "matching": "مطابقة", "listen": "استماع"}
            return f"{names.get(a, a)} — {names.get(b, b)}"
        return topic

    def _drill(self):
        if not getattr(self, "listbox", None):
            return
        i = self.listbox.GetSelection()
        if i == wx.NOT_FOUND:
            return
        topic = self._weak[i][0]
        session = None
        # regenerate questions for this one topic via the academy's refill path
        for course in self.academy.courses():
            refill = self.academy._make_refill(
                course.course_id, self.academy._lessons_for_course(course.course_id))
            qs = refill(topic, 12)
            if qs:
                from ..engine.session import QuestionSession
                sid = self.academy.store.start_session("", "", [], "mistakes")
                session = QuestionSession(qs, keep_diacritics=self.academy.settings.strict_tashkeel,
                                          store=self.academy.store, session_id=sid)
                break
        if session is None:
            self.announce("تعذّر توليد أسئلة لهذا الموضوع الآن.")
            return
        self._run(session, "تدريب على " + self._topic_label(topic))

    def _drill_all(self):
        session = self.academy.build_weak_topics_session(limit=15)
        if session is None:
            self.announce("لا توجد نقاط ضعف كافية بعد.")
            return
        self._run(session, "تدريب نقاط الضعف")

    def _run(self, session, title):
        from .exercise_runner import ExerciseRunner
        self.show_child(ExerciseRunner(self, self.academy, session, title, self.speech))

    def instructions(self):
        return ("دفتر أخطائك: المواضيع التي تخطئ فيها أكثر مع نسبة الخطأ. اختر موضوعاً "
                "و«تدرّب على هذا» لجلسة تركّز عليه، أو تدرّب على كل نقاط ضعفك. Escape للإغلاق.")
