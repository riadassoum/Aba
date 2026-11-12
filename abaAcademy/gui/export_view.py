# -*- coding: utf-8 -*-
"""
abaAcademy.gui.export_view
==========================

Export / backup of the learner's progress. A real academy lets you take your
record with you: this screen shows a full progress report (overall figures,
per-course completion, achievements, weak topics), writes it to a text file in
the learner's data folder, and lets them read or copy it. Useful for a teacher
to review, or simply to keep a personal record.
"""

from __future__ import annotations

from .accessible import AccessibleDialog

try:
    import wx
except Exception:
    wx = None


class ExportView(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "تصدير التقدّم", speech, size=(640, 560))
        self.academy = academy
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "هذا تقرير تقدّمك الكامل. يمكنك قراءته أو نسخه، وحفظ كملف يكتبه في "
            "مجلّد بياناتك لتحتفظ به أو ترسله لمعلّمك.")), 0, wx.ALL, 8)
        self._text = academy.export_progress_text()
        self.body = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY,
                                value=self._text)
        self.body.SetName("تقرير التقدّم")
        s.Add(self.body, 1, wx.EXPAND | wx.ALL, 8)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "حفظ كملف", lambda e: self._save()), 0, wx.ALL, 4)
        row.Add(self.button(panel, "نسخ", lambda e: self._copy()), 0, wx.ALL, 4)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        s.Add(row, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self.set_first_control(self.body)

    def _save(self):
        try:
            path = self.academy.write_export()
            self.announce("حُفظ التقرير في ملف باسم aba_progress.txt داخل مجلّد بياناتك.")
        except Exception:
            self.announce("تعذّر حفظ الملف.")

    def _copy(self):
        try:
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(self._text))
                wx.TheClipboard.Close()
                self.announce("نُسخ التقرير. يمكنك لصقه في أي مكان.")
        except Exception:
            self.announce("تعذّر النسخ.")

    def instructions(self):
        return ("تقرير تقدّمك الكامل. حفظ كملف يكتبه في مجلّد بياناتك، ونسخ ينسخه. "
                "Escape للإغلاق.")
