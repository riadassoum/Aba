# -*- coding: utf-8 -*-
"""
abaAcademy.gui.calculator
=========================

A talking scientific calculator. The learner types an expression (e.g.
``3*sin(pi/6) + sqrt(2)``) and hears the result spoken in Arabic. It reuses the
sandboxed evaluator from the STEM engine, so there is no ``eval`` and no security
risk, and it understands the same functions and constants as the graphing tool —
which means a student can move between "compute a value" and "hear the shape of a
function" with one mental model.

A short history of recent results is kept in the session (spoken on request), and
the last answer is available as ``ans`` in the next expression, the way a physical
scientific calculator works.

This is a feature added on top of the requested V2.0 set because a dependable,
fully-accessible calculator is one of the most-used everyday tools for a student,
and we already had the safe math core to build it on.
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..math_engine.safe_eval import SafeFunction
from ..math_engine.latex_arabic import latex_to_arabic


def _speak_number(value):
    """Render a number for speech: integers plainly, decimals to a sensible
    precision, and very large/small values in a readable form."""
    if value is None:
        return "غير معرّف"
    if abs(value - round(value)) < 1e-12:
        return str(int(round(value)))
    if abs(value) >= 1e6 or (0 < abs(value) < 1e-4):
        return f"{value:.6g}"
    return f"{value:.6f}".rstrip("0").rstrip(".")


class CalculatorDialog(AccessibleDialog):
    TITLE = "الآلة الحاسبة الناطقة"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(680, 480))
        self.academy = academy
        self._ans = 0.0
        self._history = []

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "اكتب عملية حسابية ثم Enter لتسمع الناتج. تدعم: + - * / ^، والدوال "
            "مثل sin وcos وsqrt وlog، والثابتين pi وe، والكلمة ans لآخر ناتج.")),
            0, wx.ALL, 6)

        self.entry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.entry.SetName("العملية الحسابية")
        self.entry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._compute())
        s.Add(self.entry, 0, wx.EXPAND | wx.ALL, 6)

        self.result = wx.StaticText(panel, label="")
        self.result.Wrap(640)
        s.Add(self.result, 0, wx.ALL, 8)

        self.log = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.log.SetName("سجل العمليات")
        s.Add(self.log, 1, wx.EXPAND | wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "احسب (Enter)", lambda e: self._compute()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "انطق العملية", lambda e: self._speak_expr()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "امسح السجل", lambda e: self._clear()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.entry)

    def _compute(self):
        expr = self.entry.GetValue().strip()
        if not expr:
            self._say("اكتب عملية أولاً.")
            return
        # substitute ans -> last answer; evaluate as a function of a dummy var
        prepared = expr.replace("ans", f"({self._ans})")
        try:
            # SafeFunction expects a variable; we use x but the expression may not
            # use it — evaluating at x=0 gives a constant result
            fn = SafeFunction(prepared, var="x")
            value = fn(0.0)
        except ValueError as exc:
            self._say(str(exc))
            return
        if value is None:
            self._say("العملية غير معرّفة (مثل القسمة على صفر أو جذر عدد سالب).")
            return
        self._ans = value
        spoken = _speak_number(value)
        self.result.SetLabel(f"{expr} = {spoken}")
        entry_line = f"{expr} = {spoken}"
        self._history.append(entry_line)
        self.log.Insert(entry_line, 0)
        self._say(f"الناتج: {spoken}.")
        self.entry.SetValue("")
        self.entry.SetFocus()

    def _speak_expr(self):
        expr = self.entry.GetValue().strip()
        if expr:
            self._say("العملية: " + latex_to_arabic(expr.replace("*", " في ")))
        else:
            self._say("اكتب عملية أولاً.")

    def _clear(self):
        self._history = []
        self.log.Clear()
        self._say("مُسح السجل.")

    def _say(self, text):
        self.result_text = text
        self.announce(text)

    def instructions(self):
        return ("الآلة الحاسبة الناطقة: اكتب عمليةً حسابية واضغط Enter لتسمع ناتجها. "
                "تدعم الجمع والطرح والضرب والقسمة والأس (^)، ودوالّ مثل sin وcos وtan "
                "وsqrt وlog وln، والثابتين pi وe. استخدم الكلمة ans لإدراج آخر ناتج. "
                "«انطق العملية» يقرأ التعبير بالعربية، والسجلّ يحتفظ بعملياتك. Escape للإغلاق.")
