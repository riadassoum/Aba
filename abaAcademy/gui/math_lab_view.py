# -*- coding: utf-8 -*-
"""
abaAcademy.gui.math_lab_view
============================

المختبر الرياضي الرمزي — type an expression or equation, choose what to do
(calculate, simplify, expand, factor, solve, differentiate, integrate, take
a limit) and hear the answer read in Arabic mathematical language, with the
written form in a box for the braille display. Powered by SymPy.
"""

from __future__ import annotations

from .. import math_lab as ml
from .tool_base import ToolDialog


class MathLabDialog(ToolDialog):
    TITLE = "المختبر الرياضي الرمزي"
    SIZE = (800, 600)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.add_text("اكتب تعبيرًا أو معادلة واختر العملية. المتغيّرات س ص ع، و^ للأس، و2س تعني 2 في س، "
                      "والدوال جا جتا ظا لو جذر. لنظام معادلتين افصل بينهما بفاصلة، مثل س+ص=5، س-ص=1. "
                      "الحساب بمكتبة SymPy المفتوحة.")
        self.expr = self.add_entry("التعبير أو المعادلة (Enter للحلّ أو الحساب)", on_enter=self._auto)
        self.opChoice = self.add_choice("العملية", [n for n, _ in ml.OPERATIONS] + ["النهاية", "متسلسلة تايلور", "المجموع (سيغما)"], 0)
        self.point = self.add_entry("للنهاية: القيمة التي يقترب منها المتغيّر (رقم أو ∞). لتايلور: النقطة والرتبة "
                                    "مثل 0، 5. للمجموع: من وإلى مثل 1، ن أو 1، ∞ (متغيّر الجمع ك)")
        self.add_buttons([("نفّذ", self._run), ("اقرأ التعبير كما فهمته", self._read_input)], close=False)
        self.out = self.add_output("الناتج مكتوبًا", height=90)
        self.spoken = self.add_output("الناتج مقروءًا", height=90)
        self.history = self.add_list("السجلّ", [], height=110)
        self.add_buttons([])
        self.finish(self.expr)
        if not ml.AVAILABLE:
            self._say("مكتبة SymPy غير موجودة في هذه النسخة، فالمختبر لا يعمل.")

    def instructions(self) -> str:
        return ("اكتب التعبير، واختر العملية، واضغط نفّذ. Enter في حقل التعبير يحلّ المعادلة إن كان فيها علامة يساوي، "
                "وإلا يبسّط التعبير أو يحسبه. ادرس الدالة يعطي المجال والأصفار والنهايات العظمى والصغرى والاطّراد "
                "ونقاط الانعطاف وخطوط التقارب.  زرّ اقرأ التعبير يقرأ ما فهمه البرنامج لتتأكّد من كتابتك.")

    def _auto(self):
        t = self.expr.GetValue()
        names = [n for n, _ in ml.OPERATIONS]
        if "=" in t:
            self.opChoice.SetSelection(names.index("حلّ المعادلة"))
        elif not any(ch in ml.normalise(t) for ch in "xyznktlm"):
            self.opChoice.SetSelection(names.index("احسب"))
        else:
            self.opChoice.SetSelection(names.index("بسّط"))
        self._run()

    def _run(self):
        t = self.expr.GetValue().strip()
        if not t:
            self._say("اكتب تعبيرًا أوّلًا.")
            return
        i = self.opChoice.GetSelection()
        try:
            extra = [p.strip() for p in self.point.GetValue().replace("،", ",").split(",")]
            if i == len(ml.OPERATIONS):
                w, s = ml.limit(t, self.point.GetValue() or "0")
            elif i == len(ml.OPERATIONS) + 1:
                order = int(ml.normalise(extra[1])) if len(extra) > 1 and extra[1] else 5
                w, s = ml.taylor(t, extra[0] or "0", max(1, min(order, 12)))
            elif i == len(ml.OPERATIONS) + 2:
                w, s = ml.summation(t, extra[0] or "1", extra[1] if len(extra) > 1 else "n")
            else:
                w, s = ml.OPERATIONS[i][1](t)
        except ml.MathError as e:
            self._say(str(e))
            return
        except Exception:
            self._say("تعذّرت هذه العملية على هذا التعبير.")
            return
        self.out.SetValue(w)
        self.spoken.SetValue(s)
        self.history.Insert(f"{t} ← {w}", 0)
        self._say(s)

    def _read_input(self):
        try:
            self._say(ml.speak(ml.parse(self.expr.GetValue())))
        except ml.MathError as e:
            self._say(str(e))

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.expr:
            self._auto()
            return True
        return False
