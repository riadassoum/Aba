# -*- coding: utf-8 -*-
"""
abaAcademy.gui.math_tools_view
==============================

Screens for the 3.0 maths tools, each explaining its working step by step:
matrices, statistics, equations, geometry, number bases, mental arithmetic
and propositional logic.
"""

from __future__ import annotations

import random
import time
from fractions import Fraction

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog, parse_float, parse_int
from ..math_engine import matrix_stats as ms
from ..math_engine import algebra, mental_math
from ..codelab import logic
from ..tools.ar_count import count


# ---------------------------------------------------------------------------
class MatrixDialog(ToolDialog):
    TITLE = "المصفوفات (حلّ مشروح)"
    SIZE = (800, 700)
    _OPS = [("det", "محدّد أ"), ("inv", "معكوس أ"), ("tr", "منقول أ"), ("rank", "رتبة أ"),
            ("add", "أ + ب"), ("sub", "أ − ب"), ("mul", "أ × ب"), ("scale", "عدد × أ"),
            ("solve", "حلّ نظام المعادلات: أ × س = ب")]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.add_text("اكتب كلّ صفّ في سطر، والعناصر مفصولة بمسافات. تقبل الكسور مثل 1/3. "
                      "في حلّ النظام تكتب في ب عمود الثوابت (عددًا في كلّ سطر).")
        self.aEntry = self.add_entry("المصفوفة أ", "2 1\n5 3", multiline=True, height=80)
        self.bEntry = self.add_entry("المصفوفة ب", "1 0\n0 1", multiline=True, height=80)
        self.opChoice = self.add_choice("العملية", [l for _, l in self._OPS])
        self.kEntry = self.add_entry("العدد (لضرب العدد في المصفوفة)", "2")
        self.add_buttons([("احسب", self._calc), ("اقرأ أ صفًّا صفًّا", self._read_a)])
        self.add_output("الحلّ", height=200)
        self.finish(self.aEntry)

    def _read_a(self) -> None:
        self._say(ms.speak_matrix(ms.parse_matrix(self.aEntry.GetValue())))

    def _calc(self) -> None:
        op = self._OPS[self.choice_index(self.opChoice)][0]
        a = ms.parse_matrix(self.aEntry.GetValue())
        steps = []
        result = None
        value = None
        if op == "det":
            value = ms.determinant(a, steps)
            summary = f"المحدّد = {ms.fmt(value)}"
        elif op == "inv":
            result, steps = ms.inverse(a)
            summary = "لا معكوس للمصفوفة." if result is None else "المعكوس:"
        elif op == "tr":
            result, steps = ms.transpose(a)
            summary = "المنقول:"
        elif op == "rank":
            value = ms.rank(a)
            summary = f"رتبة المصفوفة {value}."
        elif op in ("add", "sub", "mul"):
            b = ms.parse_matrix(self.bEntry.GetValue())
            if op == "mul":
                result, steps = ms.multiply(a, b)
            else:
                result, steps = ms.add(a, b, 1 if op == "add" else -1)
            summary = "الناتج:"
        elif op == "scale":
            k = ms.parse_number(self.kEntry.GetValue())
            result, steps = ms.scale(a, k)
            summary = "الناتج:"
        else:
            b = ms.parse_matrix(self.bEntry.GetValue())
            consts = [row[0] for row in b]
            sol, steps = ms.solve_system(a, consts)
            summary = steps[-1]
        text = "\n".join(steps + [summary])
        spoken = summary
        if result is not None:
            text += "\n" + ms.fmt_matrix(result)
            spoken += " " + ms.speak_matrix(result)
        self.show_output(text, speak=spoken)

    def instructions(self) -> str:
        return ("المصفوفات: اكتب المصفوفة أ (وب عند الحاجة) ثم اختر العملية واضغط احسب. "
                "الحسابات بكسور دقيقة، والخطوات مكتوبة في مربّع الحلّ.")


# ---------------------------------------------------------------------------
class StatsDialog(ToolDialog):
    TITLE = "الإحصاء الوصفي"
    SIZE = (760, 620)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.data = self.add_entry("البيانات (أرقام مفصولة بمسافات أو فواصل)",
                                   "12 15 11 18 15 20 14 15 9 17", multiline=True, height=70)
        self.add_buttons([("حلّل", self._report), ("جدول التكرار", self._freq),
                          ("استمع إلى المدرّج التكراري", self._tones)])
        self.add_output("النتائج", height=240)
        self.finish(self.data)

    def _values(self):
        return ms.parse_data(self.data.GetValue())

    def _report(self) -> None:
        v = self._values()
        rep = ms.stats_report(v)
        self.show_output(rep, speak=rep.split("\n", 3)[2] + " " + rep.split("\n")[3])

    def _freq(self) -> None:
        v = self._values()
        self.show_output(ms.histogram_text(v), speak="جدول التكرار في مربّع النتائج.", focus=True)

    def _tones(self) -> None:
        v = self._values()
        tones = ms.histogram_tones(v)
        rows = ms.frequency_table(v)
        if not self.play_tones([(f, d, 0.08) for f, d in tones]):
            self._say("الصوت غير متاح.")
        self.announce(f"{count(len(rows), 'class')} من الأصغر إلى الأكبر؛ النغمة الأعلى تعني تكرارًا أكثر.")

    def instructions(self) -> str:
        return ("الإحصاء: اكتب البيانات ثم حلّل لتسمع الوسط والوسيط والمنوال والربيعات والانحراف "
                "المعياري. استمع إلى المدرّج يعزف نغمة لكل فئة، أعلاها أكثرها تكرارًا.")


# ---------------------------------------------------------------------------
class EquationDialog(ToolDialog):
    TITLE = "حلّ المعادلات خطوة بخطوة"
    SIZE = (760, 600)
    _EXAMPLES = ["2x + 3 = 11", "x^2 - 5x + 6 = 0", "3س² = 27", "x^2 + 2x + 5 = 0",
                 "5x - 7 = 2x + 8", "2x^2 = 3x"]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.add_text("اكتب معادلة من الدرجة الأولى أو الثانية بمجهول واحد (x أو س)، مثل: "
                      "x^2 - 5x + 6 = 0. اكتب الأس بعلامة ^ أو ². لا أقواس.")
        self.eq = self.add_entry("المعادلة", on_enter=self._solve)
        self.add_buttons([("حلّ", self._solve), ("مثال", self._example),
                          ("اقرأ الخطوات واحدة واحدة", self._step)])
        self.add_output("الحلّ", height=230)
        self.finish(self.eq)
        self._steps = []
        self._pos = 0

    def _solve(self) -> None:
        text = self.eq.GetValue().strip()
        if not text:
            raise ValueError("اكتب معادلة.")
        sol = algebra.solve(text)
        self._steps = sol.steps
        self._pos = 0
        last = sol.steps[-1]
        self.show_output(sol.spoken(), speak=last)

    def _step(self) -> None:
        if not self._steps:
            self._solve()
            return
        if self._pos >= len(self._steps):
            self._pos = 0
        self._say(f"الخطوة {self._pos + 1} من {len(self._steps)}: {self._steps[self._pos]}")
        self._pos += 1

    def _example(self) -> None:
        self.eq.SetValue(random.choice(self._EXAMPLES))
        self.eq.SetFocus()
        self._solve()

    def instructions(self) -> str:
        return ("اكتب المعادلة واضغط Enter. يُعلن الحلّ، والخطوات كلّها في مربّع الحلّ، "
                "أو اسمعها واحدة واحدة بزرّ اقرأ الخطوات.")


# ---------------------------------------------------------------------------
class GeometryDialog(ToolDialog):
    TITLE = "حاسبة الهندسة"
    SIZE = (760, 620)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.shapeChoice = self.add_choice(
            "الشكل", [("مجسّم: " if s.solid else "") + s.name for s in algebra.SHAPES] +
            ["مبرهنة فيثاغورس (أدخل ضلعين)"], on_change=self._relabel)
        self.fields = []
        self.labels = []
        for i in range(3):
            row = wx.BoxSizer(wx.HORIZONTAL)
            lbl = wx.StaticText(self.panel, label="")
            ctrl = wx.TextCtrl(self.panel, style=wx.TE_PROCESS_ENTER)
            ctrl.Bind(wx.EVT_TEXT_ENTER, lambda e: self._safe(self._calc))
            row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
            row.Add(ctrl, 1, wx.EXPAND)
            self.sizer.Add(row, 0, wx.EXPAND | wx.ALL, 6)
            self.labels.append(lbl)
            self.fields.append(ctrl)
        self.add_buttons([("احسب", self._calc)])
        self.add_output("النتائج", height=200)
        self.finish(self.shapeChoice)
        self._relabel()

    def _spec(self):
        i = self.choice_index(self.shapeChoice)
        if i < len(algebra.SHAPES):
            return algebra.SHAPES[i]
        return None

    def _relabel(self) -> None:
        s = self._spec()
        params = s.params if s else (("a", "الضلع الأول (فارغ إن كان مجهولًا)"),
                                     ("b", "الضلع الثاني (فارغ إن كان مجهولًا)"),
                                     ("c", "الوتر (فارغ إن كان مجهولًا)"))
        for i, (lbl, ctrl) in enumerate(zip(self.labels, self.fields)):
            if i < len(params):
                lbl.SetLabel(params[i][1] + ":")
                ctrl.SetName(params[i][1])
                lbl.Show()
                ctrl.Show()
            else:
                lbl.Hide()
                ctrl.Hide()
                ctrl.SetValue("")
        self.panel.Layout()

    def _calc(self) -> None:
        s = self._spec()
        if s is None:
            vals = []
            for ctrl in self.fields:
                t = ctrl.GetValue().strip()
                vals.append(parse_float(t) if t else None)
            out = algebra.pythagoras(*vals)
        else:
            values = {}
            for (key, label), ctrl in zip(s.params, self.fields):
                try:
                    values[key] = parse_float(ctrl.GetValue())
                except ValueError:
                    raise ValueError(f"اكتب {label} رقمًا.")
            out = algebra.compute_shape(s.key, values)
        self.show_output("\n".join(out), speak="، ".join(out))

    def instructions(self) -> str:
        return ("اختر الشكل، فتتغيّر أسماء الحقول بحسبه. أدخل الأطوال واضغط Enter لتسمع المساحة "
                "والمحيط أو الحجم مع القانون المستخدم.")


# ---------------------------------------------------------------------------
class BasesDialog(ToolDialog):
    TITLE = "أنظمة العدّ (ثنائي، ثماني، عشري، ست عشري)"
    SIZE = (720, 560)
    _BASES = [2, 8, 10, 16]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        names = [algebra.BASES[b] for b in self._BASES]
        self.num = self.add_entry("العدد", "255", on_enter=self._convert)
        self.fromChoice = self.add_choice("من النظام", names, 2)
        self.toChoice = self.add_choice("إلى النظام", names, 0)
        self.add_buttons([("حوّل مع الخطوات", self._convert), ("في كلّ الأنظمة", self._all)])
        self.add_output("الخطوات", height=220)
        self.finish(self.num)

    def _convert(self) -> None:
        f = self._BASES[self.choice_index(self.fromChoice, 2)]
        t = self._BASES[self.choice_index(self.toChoice)]
        steps = algebra.convert_steps(self.num.GetValue(), f, t)
        self.show_output("\n".join(steps), speak=steps[-1])

    def _all(self) -> None:
        f = self._BASES[self.choice_index(self.fromChoice, 2)]
        n = algebra.parse_in_base(self.num.GetValue(), f)
        self.show_output(algebra.all_bases(n))

    def instructions(self) -> str:
        return "اكتب عددًا واختر نظامه والنظام المطلوب، ثم Enter لتسمع الناتج مع طريقة التحويل."


# ---------------------------------------------------------------------------
class MentalMathDialog(ToolDialog):
    TITLE = "الحساب الذهني (حِيَل وتدريب)"
    SIZE = (760, 620)
    SETTINGS_PREFIX = "mental_"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self._rng = random.Random()
        self.techChoice = self.add_choice("الحيلة", [t.name for t in mental_math.TECHNIQUES] + ["كلّ الحيل"],
                                          on_change=self._explain)
        self.add_buttons([("اشرح الحيلة بمثال", self._explain)], close=False)
        self.question = self.add_text("اضغط سؤال جديد.")
        self.answer = self.add_entry("إجابتك", on_enter=self._check)
        self.add_buttons([("سؤال جديد", self._new), ("تحقّق", self._check),
                          ("أرني الطريقة", self._show_steps), ("نتيجتي", self._score)])
        self.add_output("الشرح", height=170)
        self.finish(self.techChoice)
        self._p = None
        self._right = self._total = 0
        self._t0 = 0.0

    def _key(self):
        i = self.choice_index(self.techChoice)
        return mental_math.TECHNIQUES[i].key if i < len(mental_math.TECHNIQUES) else None

    def _explain(self) -> None:
        k = self._key()
        if k is None:
            self.show_output("\n".join(f"{t.name}: {t.explanation}" for t in mental_math.TECHNIQUES),
                             speak="كلّ الحيل مكتوبة في مربّع الشرح.")
            return
        t = mental_math.TECH_BY_KEY[k]
        ex = mental_math.worked_example(k)
        self.show_output(f"{t.name}: {t.explanation}\nمثال: {ex.question}\n" + "\n".join(ex.steps))

    def _new(self) -> None:
        self._p = mental_math.problem(self._key(), self._rng)
        self.question.SetLabel(self._p.question + " = ؟")
        self.answer.SetValue("")
        self.answer.SetFocus()
        self._t0 = time.monotonic()
        self.announce(self._p.question.replace("×", " ضرب ").replace("−", " ناقص ")
                      .replace("²", " تربيع").replace("٪", " بالمئة"))

    def _check(self) -> None:
        if self._p is None:
            self._new()
            return
        secs = time.monotonic() - self._t0
        self._total += 1
        if self._p.check(self.answer.GetValue()):
            self._right += 1
            self.announce(f"صحيح، في {count(round(secs), 'second')}.")
            self._new()
        else:
            self.announce(f"ليس صحيحًا. الجواب {self._p.answer}. " + " ".join(self._p.steps))
            self.show_output("\n".join([self._p.question] + self._p.steps), speak="")

    def _show_steps(self) -> None:
        if self._p:
            self.show_output("\n".join([self._p.question] + self._p.steps))

    def _score(self) -> None:
        if not self._total:
            self._say("لم تجب بعد.")
        else:
            self._say(f"{self._right} من {self._total} صحيحة.")

    def instructions(self) -> str:
        return ("الحساب الذهني: اختر حيلة واسمع شرحها بمثال، ثم تدرّب عليها. اكتب الجواب وEnter؛ "
                "الصحيح ينقلك إلى سؤال جديد، والخطأ يشرح الطريقة.")


# ---------------------------------------------------------------------------
class LogicDialog(ToolDialog):
    TITLE = "المنطق وجداول الصدق"
    SIZE = (780, 640)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.add_text("المتغيّرات كلمات مثل أ وب أو p وq. العمليات: ليس، و، أو، أو_الحصري، "
                      "يؤدي (->)، يكافئ (<->)، والأقواس للتجميع.")
        self.expr = self.add_entry("التعبير", "(أ -> ب) و أ -> ب", on_enter=self._table)
        self.expr2 = self.add_entry("تعبير ثانٍ للمقارنة (اختياري)", "", on_enter=self._compare)
        self.add_buttons([("جدول الصدق", self._table), ("هل هما متكافئان؟", self._compare),
                          ("قوانين المنطق", self._laws)])
        self.rows = self.add_list("صفوف الجدول", height=150)
        self.add_output("الخلاصة", height=90)
        self.finish(self.expr)

    def _table(self) -> None:
        tt = logic.truth_table(self.expr.GetValue())
        self.rows.Set([tt.row_text(i) for i in range(len(tt.rows))])
        self.select_index(self.rows, 0)
        true_n = len(tt.true_rows())
        self.show_output(f"{logic.to_text(logic.parse(tt.expression))}\n{tt.kind_text()}، "
                         f"صادق في {true_n} من {count(len(tt.rows), 'case')}.\n{tt.text()}",
                         speak=f"{tt.kind_text()}، صادق في {true_n} من {count(len(tt.rows), 'case')}. "
                               f"الصفوف في القائمة.")

    def _compare(self) -> None:
        b = self.expr2.GetValue().strip()
        if not b:
            raise ValueError("اكتب التعبير الثاني.")
        ok, msg = logic.equivalent(self.expr.GetValue(), b)
        self.show_output(msg)

    def _laws(self) -> None:
        lines = [f"{name}: {a}  ≡  {b}" for name, a, b in logic.LAWS]
        self.show_output("\n".join(lines), speak="قوانين المنطق في مربّع الخلاصة.", focus=True)

    def instructions(self) -> str:
        return ("اكتب تعبيرًا منطقيًّا واضغط Enter لتبني جدول صدقه، وتنقّل بين الصفوف بالأسهم. "
                "اكتب تعبيرًا ثانيًا لتعرف هل يكافئ الأول.")
