# -*- coding: utf-8 -*-
"""
abaAcademy.gui.diacritizer_view
===============================

المشكِّل الآلي — paste or type Arabic text and get it back with its short
vowels, from Mishkal. The vowelled text can be heard (speech synthesizers
pronounce it far better), copied, or sent back to the homework editor.
"""

from __future__ import annotations

import threading

import wx

from ..arabic_lab import diacritizer as dz
from .tool_base import ToolDialog


class DiacritizerDialog(ToolDialog):
    TITLE = "المشكِّل الآلي"
    SIZE = (800, 600)

    def __init__(self, parent, academy, speech, target: "wx.TextCtrl" = None):
        super().__init__(parent, academy, speech)
        self.target = target
        self.add_text("اكتب نصًّا عربيًّا أو الصقه، فيُشكَّل آليًّا بمشروع مِشكال المفتوح لطه زروقي. التشكيل الآلي "
                      "صحيح في أغلب النثر العادي لكنه قد يخطئ، فلا تعتمد عليه في القرآن والحديث والشعر، وراجعه "
                      "عند معلّمك فيما يهمّ.")
        self.source = self.add_entry("النصّ", multiline=True, height=140,
                                     value=target.GetStringSelection() or target.GetValue() if target else "")
        self.add_buttons([("شكِّل", self._run), ("اقرأ النصّ المشكول", self._read)], close=False)
        self.out = self.add_output("النصّ المشكول", height=160)
        f = self.out.GetFont()
        f.SetPointSize(f.GetPointSize() + 4)
        self.out.SetFont(f)
        buttons = [("انسخ", self._copy)]
        if target is not None:
            buttons.append(("ضعه في المحرّر", self._apply))
        self.add_buttons(buttons)
        self.busy = False
        self.finish(self.source)
        dz.preload()

    def instructions(self) -> str:
        return ("اكتب النصّ أو الصقه ثم اضغط شكِّل. يُحمَّل المشكِّل في ثانيتين أوّل مرّة. "
                "النتيجة في مربّع النصّ المشكول، تقرؤها حرفًا حرفًا بالأسهم أو تنسخها.")

    def _run(self):
        text = self.source.GetValue().strip()
        if not text:
            self._say("اكتب نصًّا أوّلًا.")
            return
        if self.busy:
            return
        self.busy = True
        self._say("جارٍ التشكيل.")

        def work():
            try:
                res = dz.diacritize(text)
                err = None
            except Exception as e:
                res, err = "", str(e)
            wx.CallAfter(self._done, res, err)
        threading.Thread(target=work, daemon=True).start()

    def _done(self, res, err):
        self.busy = False
        if not self:
            return
        if err:
            self._say(err)
            return
        self.out.SetValue(res)
        self.out.SetFocus()
        self._say("تمّ التشكيل. " + res[:300])

    def _read(self):
        self._say(self.out.GetValue() or "شكِّل نصًّا أوّلًا.")

    def _copy(self):
        text = self.out.GetValue()
        if text and wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(text))
                self._say("نُسخ النصّ المشكول.")
            finally:
                wx.TheClipboard.Close()

    def _apply(self):
        text = self.out.GetValue()
        if not text or self.target is None:
            return
        a, b = self.target.GetSelection()
        if a != b:
            self.target.Replace(a, b, text)
        else:
            self.target.SetValue(text)
        self._say("وُضع النصّ المشكول في المحرّر.")
        self.close_screen()
