# -*- coding: utf-8 -*-
"""
abaAcademy.gui.placement_view
=============================

اختبار تحديد المستوى — choose a graded language course, answer a short
series of questions that climbs its stages, and open the course at the stage
that fits (see ``engine.placement``).
"""

from __future__ import annotations

import wx

from ..engine.placement import Placement, has_placement
from .tool_base import ToolDialog


class PlacementDialog(ToolDialog):
    TITLE = "اختبار تحديد المستوى في اللغات"
    SIZE = (760, 560)

    def __init__(self, parent, academy, speech, course_id=None):
        super().__init__(parent, academy, speech)
        self._courses = [c for c in academy.courses() if has_placement(c)]
        start = next((i for i, c in enumerate(self._courses) if c.course_id == course_id), 0)
        self.add_text("إذا كنت تعرف شيئًا من اللغة فلا تبدأ من الصفر: أجب عن أسئلة قصيرة تصعد مراحل الدورة، "
                      "وتُفتح لك الدورة من المرحلة المناسبة. لا يُحتسب هذا الاختبار في إحصائياتك.")
        self.courseChoice = self.add_choice("الدورة", [c.title for c in self._courses], start)
        self.add_buttons([("ابدأ الاختبار", self._start)], close=False)
        self.status = self.add_text("")
        self.prompt = self.add_output("السؤال", height=80)
        self.options = self.add_list("الخيارات (Enter للإجابة)", [], height=150, on_activate=self._answer)
        self.options.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.openBtn = self.add_buttons([("افتح الدورة من المرحلة المقترحة", self._open_course)], close=True)[0]
        self.openBtn.Disable()
        self._p = None
        self._result = None
        self.finish(self.courseChoice)

    def instructions(self) -> str:
        return ("اختر الدورة ثم ابدأ الاختبار. لكل سؤال أربعة خيارات: تنقّل بالأسهم واضغط Enter. "
                "في النهاية تسمع المرحلة المقترحة، ويمكنك فتح الدورة منها.")

    def _on_key(self, evt):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._answer()
            return
        evt.Skip()

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.options:
            self._answer()
            return True
        return False

    def _course(self):
        i = self.courseChoice.GetSelection()
        return self._courses[i] if 0 <= i < len(self._courses) else None

    def _start(self):
        c = self._course()
        if c is None:
            return
        try:
            self._p = Placement(self.academy, c.course_id)
        except ValueError as e:
            self._say(str(e))
            return
        self._result = None
        self.openBtn.Disable()
        self._next(intro=f"بدأ اختبار {c.title}. ")

    def _next(self, intro: str = ""):
        p = self._p
        q = p.next_question() if p and not p.finished else None
        if q is None:
            self._finish()
            return
        self.status.SetLabel(p.progress_text())
        self.prompt.SetValue(q.prompt)
        self.options.Set(list(q.options))
        self.options.SetSelection(0)
        self.options.SetFocus()
        self._say(f"{intro}{p.progress_text()} {q.prompt}")

    def _answer(self):
        p = self._p
        if p is None or p.current is None:
            return
        i = self.options.GetSelection()
        if i < 0:
            return
        q = p.current
        ok = p.answer(i)
        verdict = "صحيح." if ok else f"خطأ. الصحيح: {q.options[q.correct]}."
        if p.finished:
            self._finish(prefix=verdict + " ")
        else:
            self._next(intro=verdict + " ")

    def _finish(self, prefix: str = ""):
        if self._p is None:
            return
        self._result = self._p.save()
        text = self._result.summary()
        self.status.SetLabel("انتهى الاختبار.")
        self.prompt.SetValue(text)
        self.options.Set([])
        self.openBtn.Enable()
        self.openBtn.SetFocus()
        self._say(prefix + text + " اضغط زرّ فتح الدورة للبدء.")

    def _open_course(self):
        c = self._course()
        if c is None or self._result is None:
            return
        from .main_window import MainWindow
        self.show_child(MainWindow(self, self.academy, self.speech, course_id=c.course_id))
