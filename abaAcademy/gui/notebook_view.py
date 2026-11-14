# -*- coding: utf-8 -*-
"""
abaAcademy.gui.notebook_view
============================

The screen for the central quick-note hub: add a note (with an optional tag),
search notes, delete one, and export all notes to a text or Markdown file. Built
on ``study_hub.notebook``.
"""

from __future__ import annotations

import os

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..study_hub.notebook import Notebook


class NotebookDialog(AccessibleDialog):
    TITLE = "دفتر الملاحظات"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(700, 560))
        self.academy = academy
        self.nb = Notebook(academy.user_data_dir)

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label="اكتب ملاحظة جديدة وصنّفها إن أردت، ثم أضِفها."),
              0, wx.ALL, 6)

        arow = wx.BoxSizer(wx.HORIZONTAL)
        self.noteEntry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.noteEntry.SetName("نص الملاحظة")
        self.noteEntry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._add())
        arow.Add(self.noteEntry, 1, wx.RIGHT, 6)
        self.tagEntry = wx.TextCtrl(panel)
        self.tagEntry.SetName("التصنيف")
        self.tagEntry.SetHint("تصنيف")
        arow.Add(self.tagEntry, 0, wx.RIGHT, 6)
        arow.Add(self.button(panel, "أضِف", lambda e: self._add()), 0)
        s.Add(arow, 0, wx.EXPAND | wx.ALL, 6)

        srow = wx.BoxSizer(wx.HORIZONTAL)
        srow.Add(wx.StaticText(panel, label="بحث:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.searchEntry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.searchEntry.SetName("بحث في الملاحظات")
        self.searchEntry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._refresh())
        srow.Add(self.searchEntry, 1)
        srow.Add(self.button(panel, "ابحث", lambda e: self._refresh()), 0, wx.LEFT, 4)
        s.Add(srow, 0, wx.EXPAND | wx.ALL, 6)

        self.listbox = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.listbox.SetName("قائمة الملاحظات")
        s.Add(self.listbox, 1, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(660)
        s.Add(self.status, 0, wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "احذف المحدّدة", lambda e: self._delete()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "صدّر إلى نص", lambda e: self._export("txt")), 0, wx.ALL, 3)
        row.Add(self.button(panel, "صدّر إلى ماركداون", lambda e: self._export("md")), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.noteEntry)
        self._refresh()

    def _add(self):
        text = self.noteEntry.GetValue().strip()
        if not text:
            self._say("اكتب نص الملاحظة أولاً.")
            return
        self.nb.add(text, self.tagEntry.GetValue())
        self.noteEntry.SetValue("")
        self.tagEntry.SetValue("")
        self._refresh()
        self._say("أُضيفت الملاحظة.")
        self.noteEntry.SetFocus()

    def _refresh(self):
        q = self.searchEntry.GetValue().strip()
        self._current = self.nb.search(q) if q else self.nb.all()
        items = []
        for n in self._current:
            tag = f"[{n['tag']}] " if n.get("tag") else ""
            items.append(f"{tag}{n['text']}")
        self.listbox.Set(items)
        if items:
            self.select_index(self.listbox, 0)
        self._say(f"{len(items)} ملاحظة.")

    def _delete(self):
        i = self.listbox.GetSelection()
        if i == wx.NOT_FOUND or i >= len(self._current):
            self._say("اختر ملاحظة لحذفها.")
            return
        note = self._current[i]
        self.nb.delete(note["id"])
        self._refresh()
        self._say("حُذفت الملاحظة.")

    def _export(self, kind):
        wildcard = ("ملف نصي (*.txt)|*.txt" if kind == "txt"
                    else "ماركداون (*.md)|*.md")
        default = "notes." + kind
        with wx.FileDialog(self, "احفظ الملاحظات", defaultFile=default,
                           wildcard=wildcard,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        try:
            if kind == "txt":
                self.nb.export_text(path)
            else:
                self.nb.export_markdown(path)
            self._say("تم تصدير الملاحظات.")
        except Exception as exc:
            self._say(f"تعذّر التصدير: {exc}")

    def _say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    def instructions(self):
        return ("دفتر الملاحظات: اكتب ملاحظة وصنّفها ثم أضِف. ابحث في ملاحظاتك بالكلمة أو "
                "التصنيف. اختر ملاحظة من القائمة واحذف المحدّدة لحذفها. يمكنك تصدير كل "
                "ملاحظاتك إلى ملف نصي أو ماركداون. Escape للإغلاق.")
