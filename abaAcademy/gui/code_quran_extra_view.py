# -*- coding: utf-8 -*-
"""
abaAcademy.gui.code_quran_extra_view
====================================

Screens for the surah-facts quiz, the logic-gates lab and the
data-structures lab.
"""

from __future__ import annotations

import random

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog, ChoiceQuiz
from ..quran_engine import khatma, surah_quiz as sq
from ..codelab import gates, data_structures as dsm


class SurahQuizDialog(ToolDialog):
    TITLE = "تعرّف على سور القرآن الكريم"
    SIZE = (760, 640)
    _POOLS = [("all", "كلّ السور"), ("amma", "جزء عمّ"), ("long", "السور الطوال (البقرة إلى التوبة)")]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        from .planner_view import KhatmaDialog
        if KhatmaDialog._index is None:
            KhatmaDialog._index = khatma.QuranIndex.load(self.resource_path("quran", "quran_data.json"))
        self.table = sq.surah_table(KhatmaDialog._index)
        self._rng = random.Random()
        self.surahs = self.add_list("السور (Enter لبطاقة السورة)", [f"{t.number}. {t.name}" for t in self.table],
                                    height=150, on_activate=self._card)
        self._kinds = list(sq.KINDS)
        self.kindChoice = self.add_choice("نوع السؤال", [sq.KINDS[k] for k in self._kinds] + ["متنوّع"],
                                          len(self._kinds))
        self.poolChoice = self.add_choice("السور", [l for _, l in self._POOLS])
        self.prompt = self.add_text("اضغط سؤال جديد.")
        self.options = self.add_list("الخيارات", height=100)
        self.quiz = ChoiceQuiz(self, self.options, self._make, prompt_ctrl=self.prompt)
        self.add_buttons([("سؤال جديد", self.quiz.next), ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.add_output("البطاقة", height=70)
        self.finish(self.surahs)

    def _card(self) -> None:
        i = self.surahs.GetSelection()
        if 0 <= i < len(self.table):
            self.show_output(sq.describe(self.table[i]))

    def _make(self):
        k = self.choice_index(self.kindChoice)
        kind = self._kinds[k] if k < len(self._kinds) else self._rng.choice(self._kinds)
        pool_key = self._POOLS[self.choice_index(self.poolChoice)][0]
        pool = sq.JUZ_AMMA if pool_key == "amma" else (list(range(2, 10)) if pool_key == "long" else None)
        return sq.make_question(self.table, kind, self._rng, pool)

    def on_enter_key(self) -> bool:
        f = self.FindFocus()
        if f is self.surahs:
            self._card()
            return True
        if f is self.options:
            self.quiz.answer()
            return True
        return False

    def instructions(self) -> str:
        return ("قائمة السور بترتيب المصحف: Enter لعدد آيات السورة ونوعها والجزء والصفحة اللذين تبدأ "
                "فيهما. وفي الاختبار أسئلة عن ذلك كلّه، ويمكن حصرها في جزء عمّ.")


class GatesDialog(ToolDialog):
    TITLE = "البوّابات المنطقية والجمع الثنائي"
    SIZE = (760, 640)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self._gates = list(gates.GATES)
        self.gateChoice = self.add_choice("البوّابة", [gates.GATES[g][0] for g in self._gates],
                                          on_change=self._table)
        self.add_buttons([("جدول الصدق", self._table)], close=False)
        self.a = self.add_entry("العدد الثنائي الأول", "1011")
        self.b = self.add_entry("العدد الثنائي الثاني", "0111", on_enter=self._add)
        self.add_buttons([("اجمع بالجامع الكامل", self._add)], close=False)
        self._rng = random.Random()
        self.modeChoice = self.add_choice("التدريب", ["خرج البوّابة", "تعرّف البوّابة من جدولها"])
        self.prompt = self.add_text("اضغط سؤال جديد.")
        self.options = self.add_list("الخيارات", height=90)
        self.quiz = ChoiceQuiz(self, self.options, self._make, prompt_ctrl=self.prompt)
        self.add_buttons([("سؤال جديد", self.quiz.next), ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.add_output("الشرح", height=150)
        self.finish(self.gateChoice)

    def _table(self) -> None:
        lines = gates.truth_table(self._gates[self.choice_index(self.gateChoice)])
        self.show_output("\n".join(lines), speak="، ".join(lines))

    def _add(self) -> None:
        result, steps = gates.add_binary(self.a.GetValue(), self.b.GetValue())
        self.show_output("\n".join(steps), speak=steps[-1])

    def _make(self):
        if self.choice_index(self.modeChoice) == 0:
            return gates.make_question(self._rng)
        return gates.identify_question(self._rng)

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.options:
            self.quiz.answer()
            return True
        return False

    def instructions(self) -> str:
        return ("اختر بوّابة لتسمع جدول صدقها، واجمع عددين ثنائيين لتسمع عمل الجامع الكامل خانةً خانة "
                "مع الحمل، وتدرّب على خرج البوّابات.")


class DataStructuresDialog(ToolDialog):
    TITLE = "مختبر هياكل البيانات"
    SIZE = (760, 620)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self._kinds = list(dsm.KINDS)
        self.kindChoice = self.add_choice("الهيكل", [dsm.KINDS[k] for k in self._kinds], on_change=self._switch)
        self.opList = self.add_list("العمليات (Enter للتنفيذ)", height=130, on_activate=self._do)
        self.value = self.add_entry("القيمة", on_enter=self._do)
        self.pos = self.add_spin("الموضع (للإدراج في القائمة)", 0, 1000, 1)
        self.add_buttons([("نفّذ", self._do), ("اقرأ الهيكل", self._read), ("ابدأ من جديد", self._switch)])
        self.add_output("ما حدث", height=150)
        self.finish(self.kindChoice)
        self._switch()

    def _kind(self) -> str:
        return self._kinds[self.choice_index(self.kindChoice)]

    def _switch(self) -> None:
        self.ds = dsm.make(self._kind())
        self._ops = dsm.OPERATIONS[self._kind()]
        self.opList.Set([l for _, l in self._ops])
        self.select_index(self.opList, 0)
        if self.output is not None:
            self.output.SetValue(f"{dsm.KINDS[self._kind()]} فارغ.")

    def _do(self) -> None:
        i = self.opList.GetSelection()
        if i < 0:
            raise ValueError("اختر عملية.")
        op = self._ops[i][0]
        needs_value = op in ("push", "enqueue", "append", "prepend", "insert", "remove", "find")
        v = self.value.GetValue().strip()
        if needs_value and not v:
            self.value.SetFocus()
            raise ValueError("اكتب القيمة أوّلًا.")
        msg = self.ds.do(op, v, self.pos.GetValue())
        if needs_value and op not in ("remove", "find"):
            self.value.SetValue("")
        self.show_output(f"{msg}\n{self.ds.read()}", speak=msg)

    def _read(self) -> None:
        self._say(self.ds.read())

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.opList:
            self._safe(self._do)
            return True
        return False

    def instructions(self) -> str:
        return ("اختر هيكل بيانات، واكتب قيمة ثم نفّذ عملية من القائمة. يُشرح ما حدث وكلفته، "
                "واقرأ الهيكل يصفه كاملًا كما لو كان مرسومًا أمامك.")


class AlgorithmsDialog(ToolDialog):
    TITLE = "خوارزميات الترتيب والبحث"
    SIZE = (780, 660)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        from ..codelab import algorithms as al
        self.al = al
        self.data = self.add_entry("القائمة (أرقام مفصولة بمسافات)", "5 3 8 1 9 2", on_enter=self._sort)
        self._sorts = list(al.SORTS)
        self.sortChoice = self.add_choice("الخوارزمية", [al.SORTS[k][0] for k in self._sorts],
                                          on_change=self._about)
        self.add_buttons([("رتّب خطوة بخطوة", self._sort), ("قارن كلّ الخوارزميات", self._compare)],
                         close=False)
        self.target = self.add_entry("قيمة للبحث عنها", "8", on_enter=self._binary)
        self.add_buttons([("بحث خطّي", self._linear), ("بحث ثنائي", self._binary)])
        self.steps = self.add_list("الخطوات", height=180)
        self.add_output("الخلاصة", height=80)
        self.finish(self.data)

    def _about(self) -> None:
        self._say(self.al.SORTS[self._sorts[self.choice_index(self.sortChoice)]][2])

    def _show(self, run) -> None:
        self.steps.Set(run.steps or ["(لا خطوات)"])
        self.select_index(self.steps, 0)
        self.show_output(run.summary())
        self.steps.SetFocus()

    def _sort(self) -> None:
        xs = self.al.parse_list(self.data.GetValue())
        self._show(self.al.SORTS[self._sorts[self.choice_index(self.sortChoice)]][1](xs))

    def _compare(self) -> None:
        lines = self.al.compare_all(self.al.parse_list(self.data.GetValue()))
        self.show_output("\n".join(lines))

    def _target(self) -> float:
        try:
            return self.al.parse_list(self.target.GetValue())[0]
        except ValueError:
            raise ValueError("اكتب القيمة المبحوث عنها رقمًا.")

    def _linear(self) -> None:
        self._show(self.al.linear_search(self.al.parse_list(self.data.GetValue()), self._target()))

    def _binary(self) -> None:
        self._show(self.al.binary_search(self.al.parse_list(self.data.GetValue()), self._target()))

    def instructions(self) -> str:
        return ("اكتب قائمة أرقام واختر خوارزمية ترتيب لتسمع كلّ مقارنة وتبديل، أو قارن عدد خطوات "
                "الخوارزميات على القائمة نفسها، أو ابحث عن قيمة بحثًا خطّيًّا أو ثنائيًّا.")


class NumberTheoryDialog(ToolDialog):
    TITLE = "الأعداد والاحتمالات"
    SIZE = (780, 700)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        from ..math_engine import number_theory as nt
        from .tool_base import parse_int
        self.nt = nt
        self._int = parse_int
        self.n = self.add_entry("العدد", "360", on_enter=self._analyse)
        self.m = self.add_entry("عدد ثانٍ (للقاسم والمضاعف المشتركين)", "84")
        self.add_buttons([("حلّل العدد", self._analyse), ("التحليل إلى عوامل أوّلية", self._factor),
                          ("قواعد قابلية القسمة", self._div), ("ق.م.أ والمضاعف المشترك", self._gcd),
                          ("الأعداد الأوّلية حتى العدد", self._primes)], close=False)
        self._probs = [("perm", "التباديل ل(ن، ر)"), ("comb", "التوافيق ق(ن، ر)"), ("fact", "المضروب ن!"),
                       ("dice", "مجموع أحجار النرد (المجموع، عدد الأحجار)"),
                       ("coins", "رمي قطعة النقد (عدد الصور، عدد الرميات)"),
                       ("bag", "السحب من كيس (المطلوب، الكلّ، عدد السحبات)")]
        self.probChoice = self.add_choice("حساب الاحتمال", [l for _, l in self._probs])
        self.p1 = self.add_entry("القيمة الأولى", "7")
        self.p2 = self.add_entry("القيمة الثانية", "2")
        self.p3 = self.add_entry("القيمة الثالثة", "1")
        self.add_buttons([("احسب", self._prob)])
        self.add_output("النتيجة", height=170)
        self.finish(self.n)

    def _num(self, ctrl, label="العدد") -> int:
        try:
            return self._int(ctrl.GetValue())
        except ValueError:
            raise ValueError(f"اكتب {label} عددًا صحيحًا.")

    def _analyse(self) -> None:
        n = self._num(self.n)
        ok, why = self.nt.is_prime(n)
        lines = [why] + self.nt.properties(n)
        if n <= 10 ** 7:
            d = self.nt.divisors(n)
            lines.append("القواسم: " + "، ".join(map(str, d[:60])) + ("…" if len(d) > 60 else ""))
        self.show_output("\n".join(lines), speak=" ".join(lines[:3]))

    def _factor(self) -> None:
        steps = self.nt.factor_steps(self._num(self.n))
        self.show_output("\n".join(steps), speak=steps[-1])

    def _div(self) -> None:
        self.show_output("\n".join(self.nt.divisibility(self._num(self.n))), speak="القواعد في مربّع النتيجة.",
                         focus=True)

    def _gcd(self) -> None:
        a, b = self._num(self.n), self._num(self.m, "العدد الثاني")
        _, steps = self.nt.lcm_steps(a, b)
        self.show_output("\n".join(steps), speak=" ".join(steps[-2:]))

    def _primes(self) -> None:
        ps = self.nt.primes_up_to(self._num(self.n))
        self.show_output(f"عددها {len(ps)}: " + "، ".join(map(str, ps[:400])) + ("…" if len(ps) > 400 else ""),
                         speak=f"الأعداد الأوّلية حتى {self.n.GetValue()}: عددها {len(ps)}.")

    def _prob(self) -> None:
        kind = self._probs[self.choice_index(self.probChoice)][0]
        a = self._num(self.p1, "القيمة الأولى")
        if kind == "fact":
            _, text = self.nt.factorial_steps(a)
        else:
            b = self._num(self.p2, "القيمة الثانية")
            if kind == "perm":
                _, text = self.nt.permutations(a, b)
            elif kind == "comb":
                _, text = self.nt.combinations(a, b)
            elif kind == "dice":
                _, text = self.nt.dice_sum_probability(a, b)
            elif kind == "coins":
                _, text = self.nt.coins_probability(a, b)
            else:
                c = self._num(self.p3, "القيمة الثالثة")
                _, text = self.nt.bag_probability(a, b, c)
        self.show_output(text)

    def instructions(self) -> str:
        return ("اكتب عددًا لتعرف أهو أوّلي ولماذا، وخصائصه وقواسمه وتحليله إلى عوامل أوّلية، وقواعد "
                "قسمته، والقاسم المشترك الأكبر بخوارزمية إقليدس. وفي الأسفل حاسبة التباديل والتوافيق "
                "والاحتمالات.")
