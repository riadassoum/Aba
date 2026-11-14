# -*- coding: utf-8 -*-
"""
abaAcademy.gui.search_view
==========================

A global search across every lesson in the academy — by title, objective, or
grammar reference. In a real academy the learner shouldn't have to remember
which course a topic lives in; they type "الفاعل" or "أرقام" or "verbs" and jump
straight into a matching lesson. The academy already had a ``search`` method
with no screen behind it; this is that screen.
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


class SearchView(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "بحث في كل الدروس", speech, size=(620, 540))
        self.academy = academy
        self._results = []
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label="اكتب كلمة للبحث في عناوين الدروس وأهدافها:"),
              0, wx.ALL, 8)
        self.query = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.query.SetName("كلمة البحث")
        self.query.Bind(wx.EVT_TEXT_ENTER, lambda e: self._do_search())
        s.Add(self.query, 0, wx.EXPAND | wx.ALL, 6)
        s.Add(self.button(panel, "بحث", lambda e: self._do_search()), 0, wx.ALL, 4)

        self.results = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.results.SetName("نتائج البحث")
        self.results.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._open())
        s.Add(self.results, 1, wx.EXPAND | wx.ALL, 6)
        s.Add(self.button(panel, "افتح الدرس المختار", lambda e: self._open()),
              0, wx.EXPAND | wx.ALL, 4)
        s.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()),
              0, wx.ALIGN_RIGHT | wx.ALL, 6)
        panel.SetSizer(s)
        self.set_first_control(self.query)

    def _course_name(self, cid):
        c = self.academy.course(cid)
        return c.title if c else cid

    def _do_search(self):
        q = self.query.GetValue().strip()
        if not q:
            self.announce("اكتب كلمة للبحث.")
            return
        self._results = self.academy.search(q)
        if not self._results:
            self.results.Set([])
            self.announce("لا نتائج. جرّب كلمة أخرى.")
            return
        items = [f"{r['title']} — دورة {self._course_name(r['course_id'])}"
                 for r in self._results]
        self.results.Set(items)
        self.select_index(self.results, 0)
        self.announce(f"{_ar(len(self._results))} نتيجة. تنقّل بالأسهم واضغط افتح الدرس.")
        self.results.SetFocus()

    def _open(self):
        i = self.results.GetSelection()
        if i == wx.NOT_FOUND or i >= len(self._results):
            return
        r = self._results[i]
        session = self.academy.build_lesson_practice(r["lesson_id"])
        if session is None:
            self.announce("تعذّر فتح هذا الدرس.")
            return
        from .exercise_runner import ExerciseRunner
        self.show_child(ExerciseRunner(self, self.academy, session, r["title"], self.speech))

    def instructions(self):
        return ("ابحث في كل دروس الأكاديمية بكلمة واحدة (عنوان أو هدف أو قاعدة). اكتب الكلمة "
                "واضغط Enter، ثم اختر نتيجة وافتح الدرس. Escape للإغلاق.")
