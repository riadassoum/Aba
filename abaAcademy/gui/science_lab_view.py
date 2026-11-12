# -*- coding: utf-8 -*-
"""
abaAcademy.gui.science_lab_view
===============================

Screens for the chemistry calculator, the physics formula solver, the regex
lab, text statistics and the word-search game.
"""

from __future__ import annotations

import random

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog, parse_float
from ..science import chemistry as ch
from ..science import physics as ph
from ..codelab import regex_lab as rl
from ..tools import text_stats as ts
from ..tools.ar_count import count
from ..puzzles import word_search as wsg


class ChemistryDialog(ToolDialog):
    TITLE = "حاسبة الكيمياء (الكتلة المولية وموازنة المعادلات)"
    SIZE = (780, 640)
    _UNITS = [("g", "غرامات"), ("mol", "مولات"), ("particles", "جسيمات")]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.formula = self.add_entry("الصيغة الكيميائية", "H2SO4", on_enter=self._mass,
                                      hint="مثل H2O أو Ca(OH)2 أو CuSO4·5H2O")
        self.add_buttons([("الكتلة المولية", self._mass), ("اقرأ الصيغة", self._read)], close=False)
        self.amount = self.add_entry("الكمّية", "1")
        self.unitChoice = self.add_choice("وحدة الكمّية", [l for _, l in self._UNITS])
        self.add_buttons([("حوّل الكمّية", self._convert)], close=False)
        self.equation = self.add_entry("معادلة للموازنة", "C3H8 + O2 -> CO2 + H2O", on_enter=self._balance)
        self.add_buttons([("وازن المعادلة", self._balance)])
        self.add_output("النتيجة", height=180)
        self.finish(self.formula)

    def _mass(self) -> None:
        mm, lines = ch.molar_mass(self.formula.GetValue())
        self.show_output("\n".join(lines), speak=lines[-1])

    def _read(self) -> None:
        self._say(ch.read_formula(self.formula.GetValue()))

    def _convert(self) -> None:
        try:
            v = parse_float(self.amount.GetValue())
        except ValueError:
            raise ValueError("اكتب الكمّية رقمًا (يُقبل 6.02e23).")
        unit = self._UNITS[self.choice_index(self.unitChoice)][0]
        lines = ch.convert_amount(self.formula.GetValue(), v, unit)
        self.show_output("\n".join(lines), speak=lines[-1])

    def _balance(self) -> None:
        lines = ch.balance_explained(self.equation.GetValue())
        self.show_output("\n".join(lines), speak=lines[0])

    def instructions(self) -> str:
        return ("اكتب صيغة كيميائية بالرموز اللاتينية لتعرف كتلتها المولية ونسبة كلّ عنصر، أو حوّل "
                "بين الغرامات والمولات والجسيمات. واكتب معادلة بسهم -> بين طرفيها لموازنتها.")


class PhysicsDialog(ToolDialog):
    TITLE = "حلّ مسائل الفيزياء بالقوانين"
    SIZE = (780, 640)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.lawChoice = self.add_choice("القانون", [f"{l.topic}: {l.name}" for l in ph.LAWS],
                                         on_change=self._relabel)
        self.lawText = self.add_text("")
        self.add_text("اترك الكمّية المطلوبة فارغة واكتب الباقي.")
        self.labels, self.fields = [], []
        for _ in range(4):
            row = wx.BoxSizer(wx.HORIZONTAL)
            lbl = wx.StaticText(self.panel, label="")
            ctrl = wx.TextCtrl(self.panel, style=wx.TE_PROCESS_ENTER)
            ctrl.Bind(wx.EVT_TEXT_ENTER, lambda e: self._safe(self._solve))
            row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
            row.Add(ctrl, 1, wx.EXPAND)
            self.sizer.Add(row, 0, wx.EXPAND | wx.ALL, 5)
            self.labels.append(lbl)
            self.fields.append(ctrl)
        self.add_buttons([("احسب", self._solve), ("امسح الحقول", self._clear)])
        self.add_output("الحلّ", height=140)
        self.finish(self.lawChoice)
        self._relabel()

    def _law(self):
        return ph.LAWS[self.choice_index(self.lawChoice)]

    def _relabel(self) -> None:
        law = self._law()
        self.lawText.SetLabel(law.text)
        for i, (lbl, ctrl) in enumerate(zip(self.labels, self.fields)):
            if i < len(law.variables):
                v = law.variables[i]
                lbl.SetLabel(f"{v.name} ({v.unit}):")
                ctrl.SetName(f"{v.name} بوحدة {v.unit}")
                ctrl.SetValue("")
                lbl.Show()
                ctrl.Show()
            else:
                lbl.Hide()
                ctrl.Hide()
                ctrl.SetValue("")
        self.panel.Layout()

    def _clear(self) -> None:
        for c in self.fields:
            c.SetValue("")
        self.fields[0].SetFocus()

    def _solve(self) -> None:
        law = self._law()
        known = {}
        for v, ctrl in zip(law.variables, self.fields):
            t = ctrl.GetValue().strip()
            if t:
                try:
                    known[v.key] = parse_float(t)
                except ValueError:
                    raise ValueError(f"اكتب {v.name} رقمًا.")
        _, sols, lines = ph.solve(law.key, known)
        self.show_output("\n".join(lines), speak=lines[-1])

    def instructions(self) -> str:
        return ("اختر القانون، فتتغيّر الحقول بحسب كمّياته ووحداتها. اكتب المعلوم واترك المجهول "
                "فارغًا ثم Enter. الوحدات من النظام الدولي، وتسارع الجاذبية ٩٫٨١.")


class RegexLabDialog(ToolDialog):
    TITLE = "مختبر التعابير النمطية (Regex)"
    SIZE = (800, 700)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.pattern = self.add_entry("النمط", r"\d+", on_enter=self._test)
        self.ignoreCase = self.add_check("تجاهل حالة الأحرف اللاتينية")
        self.text = self.add_entry("النصّ للاختبار", "في عام 2026 درس 35 طالبًا 12 مادّة.",
                                   multiline=True, height=70)
        self.repl = self.add_entry("الاستبدال (اختياري)")
        self.add_buttons([("اشرح النمط", self._explain), ("ابحث عن المطابقات", self._test),
                          ("استبدل", self._sub)], close=False)
        self._ex = list(rl.EXERCISES)
        self.exChoice = self.add_choice("تمرين", [e.title for e in self._ex], on_change=self._task)
        self.add_buttons([("اقرأ التمرين", self._task), ("تحقّق من نمطي", self._check),
                          ("تلميح", self._hint)])
        self.add_output("النتيجة", height=170)
        self.finish(self.pattern)

    def _explain(self) -> None:
        lines = rl.explain(self.pattern.GetValue())
        self.show_output("\n".join(lines) or "النمط فارغ.", speak="، ".join(lines))

    def _test(self) -> None:
        text = self.text.GetValue()
        ms = rl.test(self.pattern.GetValue(), text, self.ignoreCase.GetValue())
        if not ms:
            self.show_output("لا مطابقات.")
            return
        lines = rl.describe_matches(ms, text)
        self.show_output(f"{count(len(ms), 'item')} مطابقة:\n" + "\n".join(lines),
                         speak=f"المطابقات: " + "، ".join(m.text for m in ms[:12]))

    def _sub(self) -> None:
        out, n = rl.substitute(self.pattern.GetValue(), self.repl.GetValue(), self.text.GetValue(),
                               self.ignoreCase.GetValue())
        self.show_output(f"استُبدل {count(n, 'time')}:\n{out}")

    def _cur(self):
        return self._ex[self.choice_index(self.exChoice)]

    def _task(self) -> None:
        e = self._cur()
        self.show_output(f"{e.title}: {e.task}\nيجب أن يطابق: {'، '.join(e.must_match)}\n"
                         f"ولا يطابق: {'، '.join(x or '(نصّ فارغ)' for x in e.must_not)}",
                         speak=f"{e.title}: {e.task}")

    def _check(self) -> None:
        ok, problems = rl.check_exercise(self._cur(), self.pattern.GetValue())
        self.show_output("أحسنت! نمطك صحيح في كلّ الحالات." if ok else "\n".join(problems))

    def _hint(self) -> None:
        self._say(self._cur().hint)

    def instructions(self) -> str:
        return ("اكتب نمطًا لتسمع شرحه رمزًا رمزًا، واختبره على نصّ لتعرف المطابقات ومواضعها. "
                "والتمارين تتحقّق من نمطك على أمثلة يجب أن يطابقها وأخرى يجب ألّا يطابقها.")


class TextStatsDialog(ToolDialog):
    TITLE = "إحصاء النصوص (عدّاد الكلمات)"
    SIZE = (760, 600)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.text = self.add_entry("النصّ", multiline=True, height=200)
        self.add_buttons([("حلّل النصّ", self._analyse), ("الصق من الحافظة", self._paste)])
        self.add_output("الإحصاءات", height=170)
        self.finish(self.text)

    def _paste(self) -> None:
        data = wx.TextDataObject()
        ok = False
        if wx.TheClipboard.Open():
            try:
                ok = wx.TheClipboard.GetData(data)
            finally:
                wx.TheClipboard.Close()
        if not ok:
            raise ValueError("لا يوجد نصّ في الحافظة.")
        self.text.SetValue(data.GetText())
        self._analyse()

    def _analyse(self) -> None:
        lines = ts.report(self.text.GetValue())
        self.show_output("\n".join(lines), speak=" ".join(lines[:2]))

    def instructions(self) -> str:
        return ("اكتب نصًّا أو الصقه لتعرف عدد كلماته وحروفه وجمله، ووقت قراءته وإلقائه، والكلمات "
                "المتكرّرة التي يحسن تنويعها.")


class WordSearchDialog(ToolDialog):
    TITLE = "البحث عن الكلمات"
    SIZE = (760, 620)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self._rng = random.Random()
        self._levels = list(wsg.LEVELS)
        self._themes = list(wsg.THEMES)
        self.levelChoice = self.add_choice("المستوى", [wsg.LEVELS[k][0] for k in self._levels])
        self.themeChoice = self.add_choice("الموضوع", [wsg.THEMES[k][0] for k in self._themes])
        self.add_text("الأسهم للتنقّل بين الحروف، والمسافة لتحديد أوّل حرف في الكلمة ثم آخر حرف فيها. "
                      "R لقراءة الصفّ من اليمين، C لقراءة العمود، W للكلمات الباقية، H لتلميح.")
        self.cell = self.add_list("الشبكة", height=50)
        self.cell.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.add_buttons([("لعبة جديدة", self._new), ("الكلمات الباقية", self._words),
                          ("تلميح", self._hint)])
        self.add_output("ما يحدث", height=120)
        self.finish(self.cell)
        self._new(quiet=True)

    def _new(self, quiet: bool = False) -> None:
        level = self._levels[self.choice_index(self.levelChoice)]
        theme = self._themes[self.choice_index(self.themeChoice)]
        self.p = wsg.generate(level, theme, self._rng)
        self._r, self._c = 0, self.p.size - 1
        self._mark = None
        self._refresh(speak=False)
        msg = (f"شبكة {self.p.size} في {self.p.size}، موضوعها {self.p.theme}، فيها "
               f"{count(len(self.p.words), 'kalima')} مخبّأة: " + "، ".join(p.word for p in self.p.words) +
               ". التاء المربوطة مكتوبة في الشبكة هاءً، والهمزات ألفًا.")
        self.output.SetValue(msg)
        if not quiet:
            self.cell.SetFocus()
            self.announce(msg)

    def _cell_text(self) -> str:
        r, c = self._r, self._c
        mark = "، محدّد" if self._mark == (r, c) else ""
        found = "، من كلمة وُجدت" if (r, c) in self.p.found_cells else ""
        return f"{self.p.letter(r, c)}، الصفّ {r + 1} العمود {self.p.col_no(c)}{mark}{found}"

    def _refresh(self, speak: bool = True) -> None:
        t = self._cell_text()
        self.cell.Set([t])
        self.select_index(self.cell, 0)
        if speak:
            self.announce(t)

    def _on_key(self, evt) -> None:
        code = evt.GetKeyCode()
        moves = {wx.WXK_UP: (-1, 0), wx.WXK_DOWN: (1, 0), wx.WXK_LEFT: (0, -1), wx.WXK_RIGHT: (0, 1)}
        if code in moves:
            dr, dc = moves[code]
            r, c = self._r + dr, self._c + dc
            if 0 <= r < self.p.size and 0 <= c < self.p.size:
                self._r, self._c = r, c
                self._refresh()
            else:
                self.announce("حافة الشبكة.")
        elif code == wx.WXK_SPACE:
            self._space()
        elif code in (ord("R"), ord("r")):
            self.announce(f"الصفّ {self._r + 1}: {self.p.row_text(self._r)}")
        elif code in (ord("C"), ord("c")):
            self.announce(f"العمود {self.p.col_no(self._c)}: {self.p.col_text(self._c)}")
        elif code in (ord("W"), ord("w")):
            self._words()
        elif code in (ord("H"), ord("h")):
            self._hint()
        else:
            evt.Skip()

    def _space(self) -> None:
        here = (self._r, self._c)
        if self._mark is None:
            self._mark = here
            self.announce(f"بداية التحديد عند {self.p.letter(*here)}. انتقل إلى آخر حرف واضغط المسافة.")
            return
        start, self._mark = self._mark, None
        letters = self.p.letters_between(start, here)
        found = self.p.claim(start, here)
        if found:
            msg = f"وجدت {found.word}!"
            if self.p.complete:
                msg += " وجدت كلّ الكلمات. أحسنت!"
                try:
                    from .games import save_score
                    save_score(self.academy, "word_search", len(self.p.words), True)
                except Exception:
                    pass
            else:
                msg += f" بقيت {count(len(self.p.remaining()), 'kalima')}."
            self.show_output(msg)
        elif letters:
            self.announce(f"الحروف {letters} ليست كلمة من القائمة.")
        else:
            self.announce("الحرفان ليسا على خطّ واحد. ابدأ التحديد من جديد.")

    def _words(self) -> None:
        rem = self.p.remaining()
        self._say("الكلمات الباقية: " + "، ".join(rem) if rem else "وجدت كلّ الكلمات.")

    def _hint(self) -> None:
        h = self.p.hint()
        self._say(h or "لا كلمات باقية.")

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.cell:
            self._space()
            return True
        return False

    def instructions(self) -> str:
        return ("ابحث عن الكلمات المخبّأة في شبكة الحروف. الكلمات أفقية من اليمين إلى اليسار، أو "
                "عمودية من الأعلى، أو مائلة في المستوى الصعب. حدّد أوّل الكلمة وآخرها بالمسافة.")
