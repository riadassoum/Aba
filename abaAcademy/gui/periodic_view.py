# -*- coding: utf-8 -*-
"""
abaAcademy.gui.periodic_view
============================

The periodic table, explored by ear. The table is a grid: Left/Right move
along a period from element to element (the gaps are skipped), Up/Down move
within a group, Home/End go to the ends of the period, and Enter reads the
element's full card. A search box finds any element by name, symbol or
number, and a quiz drills symbols, names, numbers, families and positions.
"""

from __future__ import annotations

import random

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog, ChoiceQuiz
from ..science import periodic
from ..tools.ar_count import count


class PeriodicTableDialog(ToolDialog):
    TITLE = "الجدول الدوري للعناصر"
    SIZE = (800, 680)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self._grid = periodic.grid()
        self._r, self._c = 0, 0
        self.add_text("الأسهم: يمين ويسار داخل الدورة، أعلى وأسفل داخل المجموعة. "
                      "Enter لبطاقة العنصر كاملة، وCtrl مع السهمين للقفز بين العائلات.")
        self.cells = self.add_list("الجدول", height=60)
        self.cells.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.searchEntry = self.add_entry("ابحث عن عنصر (الاسم أو الرمز أو العدد الذري)",
                                          on_enter=self._search)
        self._families = list(periodic.CATEGORY_NAMES)
        self.familyChoice = self.add_choice("عرض عائلة",
                                            [periodic.CATEGORY_NAMES[k] for k in self._families])
        self.add_buttons([("ابحث", self._search), ("اعرض العائلة", self._family),
                          ("عناصر الدورة الحالية", self._period),
                          ("عناصر المجموعة الحالية", self._group),
                          ("اختبر نفسك", self._quiz)])
        self.add_output("بطاقة العنصر", height=190)
        self.finish(self.cells)
        self._refresh(speak=False)

    # -- cursor ----------------------------------------------------------
    def _el(self, r=None, c=None):
        r = self._r if r is None else r
        c = self._c if c is None else c
        return self._grid[r][c]

    def _short(self, e) -> str:
        pos = periodic.row_label(self._r)
        g = e.group
        where = f"{pos}، المجموعة {g}" if g else pos
        return f"{e.name}، {e.symbol}، العدد الذري {e.number}، {where}"

    def _refresh(self, speak: bool = True) -> None:
        e = self._el()
        text = self._short(e) if e else "فراغ"
        self.cells.Set([text])
        self.select_index(self.cells, 0)
        if speak:
            self.announce(text)

    def _move_h(self, step: int, family_jump: bool = False) -> None:
        row = self._grid[self._r]
        cur = self._el()
        c = self._c + step
        while 0 <= c < 18:
            e = row[c]
            if e and (not family_jump or not cur or e.category != cur.category):
                self._c = c
                self._refresh()
                return
            c += step
        self.announce("نهاية الدورة. " + (self._short(cur) if cur else ""))

    def _move_v(self, step: int) -> None:
        r = self._r + step
        while 0 <= r < len(self._grid):
            if self._grid[r][self._c]:
                self._r = r
                self._refresh()
                return
            r += step
        self.announce("نهاية المجموعة. " + (self._short(self._el()) if self._el() else ""))

    def _on_key(self, evt) -> None:
        code = evt.GetKeyCode()
        ctrl = evt.ControlDown()
        if code == wx.WXK_LEFT:
            self._move_h(-1, ctrl)
        elif code == wx.WXK_RIGHT:
            self._move_h(1, ctrl)
        elif code == wx.WXK_UP:
            self._move_v(-1)
        elif code == wx.WXK_DOWN:
            self._move_v(1)
        elif code == wx.WXK_HOME:
            self._c = next(i for i, e in enumerate(self._grid[self._r]) if e)
            self._refresh()
        elif code == wx.WXK_END:
            self._c = max(i for i, e in enumerate(self._grid[self._r]) if e)
            self._refresh()
        elif code == wx.WXK_SPACE:
            self._card()
        else:
            evt.Skip()

    def _goto(self, e) -> None:
        for r, row in enumerate(self._grid):
            for c, x in enumerate(row):
                if x is e:
                    self._r, self._c = r, c
                    self._refresh(speak=False)
                    return

    # -- actions ---------------------------------------------------------
    def _card(self) -> None:
        e = self._el()
        if e is None:
            self._say("فراغ.")
            return
        self.show_output(e.describe(), speak=e.describe().replace("\n", " "))

    def _search(self) -> None:
        q = self.searchEntry.GetValue().strip()
        if not q:
            raise ValueError("اكتب اسم عنصر أو رمزه أو عدده الذري.")
        e = periodic.find(q)
        if e is None:
            self._say(f"لم أجد عنصرًا باسم {q}.")
            return
        self._goto(e)
        self.cells.SetFocus()
        self.show_output(e.describe(), speak=self._short(e))

    def _list(self, title: str, items) -> None:
        lines = [f"{e.number}. {e.name} ({e.symbol})" for e in items]
        self.show_output(f"{title}: {count(len(lines), 'element')}\n" + "\n".join(lines),
                         speak=f"{title}: " + "، ".join(e.name for e in items[:20])
                         + ("…" if len(items) > 20 else ""))

    def _family(self) -> None:
        k = self._families[self.choice_index(self.familyChoice)]
        self._list(periodic.CATEGORY_NAMES[k], periodic.members(k))

    def _period(self) -> None:
        e = self._el()
        if e is None:
            return
        if e.group is None:
            self._list(periodic.CATEGORY_NAMES[e.category], periodic.members(e.category))
        else:
            self._list(f"الدورة {e.period}", periodic.in_period(e.period))

    def _group(self) -> None:
        e = self._el()
        if e is None or e.group is None:
            self._say("عناصر هذه السلسلة لا تُرقّم ضمن مجموعة.")
            return
        self._list(f"المجموعة {e.group}", periodic.in_group(e.group))

    def _quiz(self) -> None:
        self.show_child(ElementQuizDialog(self, self.academy, self.speech))

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.cells:
            self._card()
            return True
        return False

    def instructions(self) -> str:
        return ("الجدول الدوري: تنقّل بالأسهم بين العناصر، واضغط Enter لبطاقة العنصر: كتلته "
                "وموقعه وعائلته وحالته وتوزيعه الإلكتروني. وابحث بالاسم أو الرمز أو العدد.")


class _Q:
    def __init__(self, q):
        self.prompt = q.prompt
        self.options = q.options
        self.answer = q.answer
        self.explanation = q.explanation


class ElementQuizDialog(ToolDialog):
    TITLE = "اختبار الجدول الدوري"
    SIZE = (680, 520)
    _RANGES = [(20, "أول ٢٠ عنصرًا"), (36, "أول ٣٦ عنصرًا (حتى الكريبتون)"),
               (54, "أول ٥٤ عنصرًا"), (118, "كلّ العناصر")]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self._rng = random.Random()
        self._kinds = list(periodic.QUIZ_KINDS)
        self.kindChoice = self.add_choice("نوع الأسئلة",
                                          [periodic.QUIZ_KINDS[k] for k in self._kinds] + ["متنوّع"],
                                          len(self._kinds))
        self.rangeChoice = self.add_choice("العناصر", [l for _, l in self._RANGES], 1)
        self.prompt = self.add_text("اضغط سؤال جديد.")
        self.options = self.add_list("الخيارات", height=130)
        self.quiz = ChoiceQuiz(self, self.options, self._make, prompt_ctrl=self.prompt,
                               on_score=self._record)
        self.add_buttons([("سؤال جديد", self.quiz.next), ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.finish(self.kindChoice)

    def _make(self):
        k = self.choice_index(self.kindChoice)
        kind = self._kinds[k] if k < len(self._kinds) else self._rng.choice(self._kinds)
        limit = self._RANGES[self.choice_index(self.rangeChoice, 1)][0]
        return _Q(periodic.make_question(kind, self._rng, limit))

    def _record(self, right, total) -> None:
        if total and total % 10 == 0:
            try:
                from .games import save_score
                save_score(self.academy, "periodic_quiz", right, True)
            except Exception:
                pass

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.options:
            self.quiz.answer()
            return True
        return False

    def instructions(self) -> str:
        return "اختر نوع الأسئلة ومدى العناصر، ثم سؤال جديد. الأسهم للخيارات وEnter للإجابة."
