# -*- coding: utf-8 -*-
"""
abaAcademy.gui.display_view
===========================

العرض وسهولة القراءة — text size, colour theme, bold text, the focus
highlight, and whether the main screen reads a feature's description. Each
change is previewed on this screen at once; Save applies it to every open
screen and keeps it for next time.
"""

from __future__ import annotations

import wx

from ..display_prefs import DisplayPrefs, FONT_SCALES, THEMES, contrast_ratio
from .tool_base import ToolDialog
from . import display
from .accessible import open_screens


class DisplayDialog(ToolDialog):
    TITLE = "العرض وسهولة القراءة"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech, title=self.TITLE, size=(720, 560))
        self.prefs = DisplayPrefs.load(academy.store)
        self._theme_keys = list(THEMES)
        self.add_text("لضعاف البصر ولمن يرافق المتعلّم: اختر حجم الخطّ والألوان. تُعرض التغييرات هنا فورًا، "
                      "واضغط احفظ لتطبيقها على كل الشاشات.")
        self.scaleChoice = self.add_choice("حجم الخطّ", [f"{s}٪" for s in FONT_SCALES],
                                           FONT_SCALES.index(self.prefs.font_scale), on_change=self._preview)
        self.themeChoice = self.add_choice("الألوان", [THEMES[k][0] for k in self._theme_keys],
                                           self._theme_keys.index(self.prefs.theme), on_change=self._preview)
        self.boldCheck = self.add_check("خطّ عريض", self.prefs.bold, on_change=self._preview)
        self.focusCheck = self.add_check("إبراز العنصر المحدّد بلون مختلف", self.prefs.focus_highlight,
                                         on_change=self._preview)
        self.describeCheck = self.add_check("قراءة وصف الميزة في الشاشة الرئيسية بعد لحظة",
                                            self.prefs.describe_features, on_change=self._preview)
        self.sample = self.add_output("معاينة", height=110)
        self.sample.SetValue("بسم الله الرحمن الرحيم. هذا نصّ تجريبي لترى حجم الخطّ والألوان. "
                             "Sample text 123.")
        self.add_buttons([("احفظ وطبّق على كل الشاشات", self._save), ("استعد الإعدادات الافتراضية", self._reset)])
        self.finish(self.scaleChoice)

    def instructions(self):
        return ("اختر حجم الخطّ والألوان والإبراز، ثم احفظ. تُطبّق الإعدادات على كل الشاشات، "
                "ويقرأ قارئ الشاشة كل شيء كما هو.")

    def _current(self) -> DisplayPrefs:
        return DisplayPrefs(FONT_SCALES[self.scaleChoice.GetSelection()],
                            self._theme_keys[self.themeChoice.GetSelection()],
                            self.boldCheck.GetValue(), self.focusCheck.GetValue(),
                            self.describeCheck.GetValue())

    def _preview(self, evt=None):
        p = self._current()
        display.apply(self, p)
        hl = getattr(self, "_aba_highlighter", None)
        if hl is not None:
            hl.update(p)
        bg, fg = p.colours()
        extra = ""
        if bg and fg:
            extra = f" نسبة التباين {contrast_ratio(bg, fg):.1f} إلى ١."
        self._say(p.describe() + extra)

    def _save(self):
        p = self._current()
        p.save(self.academy.store)
        n = display.reapply_everywhere(open_screens(), self.academy.store)
        self._say(f"حُفظت إعدادات العرض وطُبّقت على الشاشات المفتوحة ({n}).")

    def _reset(self):
        d = DisplayPrefs()
        self.scaleChoice.SetSelection(FONT_SCALES.index(d.font_scale))
        self.themeChoice.SetSelection(self._theme_keys.index(d.theme))
        self.boldCheck.SetValue(d.bold)
        self.focusCheck.SetValue(d.focus_highlight)
        self.describeCheck.SetValue(d.describe_features)
        self._preview()
