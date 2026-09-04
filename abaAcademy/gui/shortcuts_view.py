# -*- coding: utf-8 -*-
"""
abaAcademy.gui.shortcuts_view
=============================

Two things in one screen: an **explorer** for keyboard shortcuts (browse by app
or search across all), and a **quiz** ("اختبر معرفتي") that asks the shortcut for
a described action and checks the answer. Built on ``tools.shortcuts_data``.
"""

from __future__ import annotations

import random

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..tools import shortcuts_data as sd


class ShortcutsDialog(AccessibleDialog):
    TITLE = "مستكشف اختصارات لوحة المفاتيح"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(720, 560))
        self.academy = academy
        self._quiz_answer = None
        self._score = 0
        self._asked = 0

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "تصفّح الاختصارات حسب البرنامج أو ابحث عنها، أو اختبر معرفتك بها.")),
            0, wx.ALL, 6)

        crow = wx.BoxSizer(wx.HORIZONTAL)
        crow.Add(wx.StaticText(panel, label="البرنامج:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.catChoice = wx.Choice(panel, choices=["الكل"] + sd.all_categories())
        self.catChoice.SetSelection(0)
        self.bind_choice(self.catChoice, lambda e: self._refresh())
        crow.Add(self.catChoice, 0, wx.RIGHT, 12)
        crow.Add(wx.StaticText(panel, label="بحث:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.searchEntry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.searchEntry.SetName("بحث في الاختصارات")
        self.searchEntry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._refresh())
        crow.Add(self.searchEntry, 1)
        s.Add(crow, 0, wx.EXPAND | wx.ALL, 6)

        self.listbox = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.listbox.SetName("قائمة الاختصارات")
        s.Add(self.listbox, 1, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(680)
        s.Add(self.status, 0, wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "اختبر معرفتي", lambda e: self._new_quiz()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "أظهر الجواب", lambda e: self._reveal()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.catChoice)
        self._refresh()

    def _refresh(self):
        q = self.searchEntry.GetValue().strip()
        cat = self.catChoice.GetStringSelection()
        if q:
            rows = sd.search(q)
        elif cat and cat != "الكل":
            rows = [(cat, k, d) for k, d in sd.shortcuts_for(cat)]
        else:
            rows = sd.all_shortcuts()
        self.listbox.Set([f"{d} — {k}" for _, k, d in rows])
        if rows:
            self.select_index(self.listbox, 0)
        self._say(f"{len(rows)} اختصاراً.")

    def _new_quiz(self):
        rows = sd.all_shortcuts()
        cat, keys, desc = random.choice(rows)
        self._quiz_answer = keys
        self._asked += 1
        self._say(f"ما اختصار: {desc}؟ (في {cat}). "
                  f"فكّر ثم اضغط «أظهر الجواب».")

    def _reveal(self):
        if not self._quiz_answer:
            self._say("اضغط «اختبر معرفتي» أولاً.")
            return
        self._say(f"الجواب: {self._quiz_answer}. "
                  f"إن عرفته فأحسنت! لسؤال آخر اضغط «اختبر معرفتي».")
        self._quiz_answer = None

    def _say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    def instructions(self):
        return ("مستكشف الاختصارات: اختر البرنامج (ويندوز، وورد، إكسل، المتصفّح، NVDA) "
                "لتصفّح اختصاراته، أو ابحث بكلمة عبر جميع البرامج. «اختبر معرفتي» يسألك عن "
                "اختصار فعلٍ معيّن، و«أظهر الجواب» يكشفه. Escape للإغلاق.")
