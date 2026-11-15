# -*- coding: utf-8 -*-
"""
abaAcademy.gui.braille_translator_view
======================================

محوّل برايل العربي — Arabic text to grade 1 or grade 2 braille and back,
using the liblouis Arabic tables (see braille_engine.louis). The result can
be read as dot numbers, copied to a braille display or document, or saved as
a .brf file for a braille embosser. A drill shows grade-2 contractions as
dots and asks for the word.
"""

from __future__ import annotations

import io
import random

import wx

from ..braille_engine import louis
from .tool_base import ToolDialog

DRILL_WORDS = ["برنامج", "التعليم", "جديد", "بعد", "تحت", "ذلك", "حياة", "خارج", "داخل", "رئيس", "زمان", "في",
               "من", "الذي", "كان", "هذا", "قبل", "عند", "كل", "لكن", "مع", "على", "إلى", "عن", "الله", "حول",
               "دائم", "خاصة", "جميع", "ثاني", "ثالث", "رسول", "روح", "زواج", "حقيق", "دقيق", "تدريب", "جانب"]


class BrailleTranslatorDialog(ToolDialog):
    TITLE = "محوّل برايل العربي"
    SIZE = (820, 640)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.add_text("اكتب نصًّا عربيًّا وحوّله إلى برايل بالدرجة الأولى (حرفًا حرفًا) أو الثانية (المختصرة)، "
                      "أو الصق برايل وحوّله إلى نصّ. الجداول من مشروع liblouis، وهي التي تستعملها قارئات الشاشة.")
        self.gradeChoice = self.add_choice("الدرجة", ["الدرجة الأولى (غير مختصرة)", "الدرجة الثانية (مختصرة)"], 0)
        self.source = self.add_entry("النصّ (أو برايل للتحويل العكسي)", multiline=True, height=110)
        self.add_buttons([("إلى برايل", self._to_braille), ("من برايل إلى نصّ", self._to_text),
                          ("اقرأ الخلايا بالنقاط", self._read_dots)], close=False)
        self.result = self.add_output("النتيجة", height=110)
        f = self.result.GetFont()
        f.SetPointSize(f.GetPointSize() + 6)
        self.result.SetFont(f)
        self.add_buttons([("انسخ النتيجة", self._copy), ("احفظ ملفّ طباعة برايل (BRF)", self._save_brf),
                          ("تمرين قراءة المختصرات", self._drill_next)], close=False)
        self.drillOut = self.add_output("التمرين", height=60)
        self.drillEntry = self.add_entry("ما الكلمة؟ اكتبها ثم Enter", on_enter=self._drill_check)
        self.add_buttons([])
        self._drill_word = None
        self.finish(self.source)
        if not louis.available():
            self._say("جداول برايل غير موجودة في هذه النسخة.")

    def instructions(self) -> str:
        return ("اكتب النصّ واختر الدرجة ثم إلى برايل. النتيجة خلايا برايل تُقرأ على السطر الإلكتروني، "
                "وزرّ اقرأ الخلايا يقرؤها بأرقام النقاط. يمكنك حفظها ملفًّا للطابعة البارزة. "
                "في التحويل العكسي للدرجة الثانية قد تلتبس الأقواس ببعض المختصرات كما في برايل نفسه.")

    def _grade(self) -> int:
        return 2 if self.gradeChoice.GetSelection() == 1 else 1

    def _to_braille(self):
        text = self.source.GetValue().strip()
        if not text:
            self._say("اكتب نصًّا أوّلًا.")
            return
        out = louis.translate(text, self._grade())
        self.result.SetValue(out)
        cells = sum(1 for c in out if 0x2800 < ord(c) <= 0x28FF)
        saved = len(louis.translate(text, 1)) - len(out) if self._grade() == 2 else 0
        msg = f"حُوّل النصّ إلى {cells} خلية برايل."
        if saved > 0:
            msg += f" وفّرت الدرجة الثانية {saved} خلية."
        self._say(msg)

    def _to_text(self):
        braille = self.source.GetValue().strip()
        if not braille or not any(0x2800 <= ord(c) <= 0x28FF for c in braille):
            self._say("الصق نصًّا بخلايا برايل في المربّع أوّلًا.")
            return
        text = louis.back_translate(braille, self._grade())
        self.result.SetValue(text)
        self._say(text)

    def _read_dots(self):
        out = self.result.GetValue()
        if not any(0x2800 <= ord(c) <= 0x28FF for c in out):
            self._say("لا توجد خلايا برايل في النتيجة.")
            return
        self._say(louis.describe_cells(out))

    def _copy(self):
        text = self.result.GetValue()
        if text and wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(text))
                self._say("نُسخت النتيجة.")
            finally:
                wx.TheClipboard.Close()

    def _save_brf(self):
        out = self.result.GetValue()
        if not any(0x2800 <= ord(c) <= 0x28FF for c in out):
            self._say("حوّل نصًّا إلى برايل أوّلًا.")
            return
        with wx.FileDialog(self, "احفظ ملفّ برايل للطابعة", wildcard="BRF (*.brf)|*.brf",
                           defaultFile="برايل.brf", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        with io.open(path, "w", encoding="ascii", newline="") as f:
            f.write(louis.to_brf(out))
        self._say("حُفظ الملفّ. افتحه ببرنامج الطابعة البارزة لطباعته.")

    # -- drill -------------------------------------------------------------

    def _drill_next(self):
        self._drill_word = random.choice(DRILL_WORDS)
        cells = louis.translate(self._drill_word, 2)
        self.drillOut.SetValue(cells)
        self.drillEntry.SetValue("")
        self.drillEntry.SetFocus()
        self._say("ما الكلمة المكتوبة بالدرجة الثانية: " + louis.describe_cells(cells))

    def _drill_check(self):
        if not self._drill_word:
            return
        ans = self.drillEntry.GetValue().strip()
        if ans == self._drill_word:
            self._say(f"صحيح: {self._drill_word}. اضغط تمرين لكلمة أخرى.")
        else:
            self._say(f"الكلمة هي {self._drill_word}.")
        self._drill_word = None

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.drillEntry:
            self._drill_check()
            return True
        return False
