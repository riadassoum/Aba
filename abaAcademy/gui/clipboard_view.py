# -*- coding: utf-8 -*-
"""
abaAcademy.gui.clipboard_view
=============================

A screen for the smart Arabic text cleaner: paste or type text, choose which
fixes to apply (digit conversion, tatweel removal, punctuation spacing, …), and
get the cleaned text back to copy. Built on ``tools.clipboard_formatter``.
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..tools import clipboard_formatter as cf


class ClipboardDialog(AccessibleDialog):
    TITLE = "منسّق النصوص العربية"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(720, 580))
        self.academy = academy

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "ألصق نصاً في الحقل، اختر التنظيفات المطلوبة، ثم «نظّف». "
            "انسخ الناتج من الحقل السفلي.")), 0, wx.ALL, 6)

        s.Add(wx.StaticText(panel, label="النص الأصلي:"), 0, wx.LEFT | wx.TOP, 6)
        self.input = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 150))
        self.input.SetName("النص الأصلي")
        s.Add(self.input, 1, wx.EXPAND | wx.ALL, 6)

        # options
        orow = wx.BoxSizer(wx.HORIZONTAL)
        orow.Add(wx.StaticText(panel, label="الأرقام:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.digitChoice = wx.Choice(panel, choices=["دون تغيير", "إلى عربية (٠-٩)", "إلى لاتينية (0-9)"])
        self.digitChoice.SetSelection(0)
        self.bind_choice(self.digitChoice, lambda e: None)
        orow.Add(self.digitChoice, 0, wx.RIGHT, 12)
        s.Add(orow, 0, wx.ALL, 6)

        self.cbTatweel = wx.CheckBox(panel, label="إزالة التطويل (ـــ)")
        self.cbTatweel.SetValue(True)
        self.cbPunct = wx.CheckBox(panel, label="ضبط مسافات الترقيم")
        self.cbPunct.SetValue(True)
        self.cbInvis = wx.CheckBox(panel, label="إزالة المحارف الخفية")
        self.cbInvis.SetValue(True)
        self.cbBlanks = wx.CheckBox(panel, label="دمج الأسطر الفارغة الزائدة")
        self.cbBlanks.SetValue(True)
        for cb in (self.cbTatweel, self.cbPunct, self.cbInvis, self.cbBlanks):
            s.Add(cb, 0, wx.LEFT, 10)

        s.Add(wx.StaticText(panel, label="الناتج:"), 0, wx.LEFT | wx.TOP, 6)
        self.output = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 150))
        self.output.SetName("النص المنظّف")
        s.Add(self.output, 1, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        s.Add(self.status, 0, wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "نظّف", lambda e: self._clean()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "انسخ الناتج", lambda e: self._copy()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.input)

    def _clean(self):
        text = self.input.GetValue()
        if not text.strip():
            self._say("ألصق نصاً أولاً.")
            return
        digits = {0: "none", 1: "arabic", 2: "western"}[self.choice_index(self.digitChoice)]
        cleaned = cf.clean_text(
            text, digits=digits, tatweel=self.cbTatweel.GetValue(),
            invisibles=self.cbInvis.GetValue(), punctuation=self.cbPunct.GetValue(),
            blank_lines=self.cbBlanks.GetValue(), spaces=True)
        self.output.SetValue(cleaned)
        self._say(cf.describe_changes(text, cleaned) + " الناتج في الحقل السفلي.")

    def _copy(self):
        text = self.output.GetValue()
        if not text:
            self._say("لا يوجد ناتج لنسخه.")
            return
        try:
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(text))
                wx.TheClipboard.Close()
                self._say("نُسخ الناتج إلى الحافظة.")
        except Exception:
            self._say("تعذّر النسخ؛ يمكنك تحديد الناتج ونسخه يدوياً.")

    def _say(self, text):
        self.status.SetLabel(text[:150])
        self.announce(text)

    def instructions(self):
        return ("منسّق النصوص العربية: ألصق نصاً في الحقل العلوي، اختر تحويل الأرقام "
                "والتنظيفات (إزالة التطويل، ضبط الترقيم، إزالة المحارف الخفية، دمج الأسطر "
                "الفارغة)، ثم «نظّف». انسخ الناتج بـ«انسخ الناتج». Escape للإغلاق.")
