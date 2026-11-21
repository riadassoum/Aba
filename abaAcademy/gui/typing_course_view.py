# -*- coding: utf-8 -*-
"""
abaAcademy.gui.typing_course_view
=================================

دورة الكتابة باللمس — choose a keyboard course and a lesson, hear the new
keys described by touch, then type each line and hear your accuracy, speed
and every mistake. A line passes at 95% accuracy. Lessons from KTouch (KDE).
"""

from __future__ import annotations

import wx

from .. import typing_course as tc
from .tool_base import ToolDialog


class TypingCourseDialog(ToolDialog):
    TITLE = "دورة الكتابة باللمس"
    SIZE = (820, 620)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self._index = tc.available()
        self.course = None
        self.session = None
        self.add_text("تعلّم الكتابة باللمس دون النظر إلى اللوحة: لكل حرف جديد تسمع أيّ إصبع يضغطه وأين مكانه، "
                      "ثم تكتب الأسطر وتسمع دقّتك وسرعتك وأخطاءك.")
        self.courseChoice = self.add_choice("اللوحة واللغة", [c["title"] for c in self._index], 0,
                                            on_change=self._load_course)
        self.lessonList = self.add_list("الدروس", [], height=150, on_activate=self._start)
        self.add_buttons([("ابدأ الدرس", self._start), ("اشرح المفاتيح الجديدة", self._explain),
                          ("تمرين المفاتيح الجديدة", self._drill), ("وضع اليدين", self._home)], close=False)
        self.lineOut = self.add_output("السطر المطلوب", height=60)
        f = self.lineOut.GetFont()
        f.SetPointSize(f.GetPointSize() + 4)
        self.lineOut.SetFont(f)
        self.entry = self.add_entry("اكتب السطر ثم Enter (F5 لسماعه مرّة أخرى، وF6 لسماعه حرفًا حرفًا)",
                                    on_enter=self._submit)
        self.entry.Bind(wx.EVT_TEXT, self._on_text)
        self.entry.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.status = self.add_text("")
        self.add_buttons([("الملخّص", self._summary), ("مصدر الدروس", self._credit)])
        self.finish(self.courseChoice)
        if self._index:
            self._load_course()

    def instructions(self) -> str:
        return ("اختر اللوحة ثم الدرس واضغط ابدأ. تسمع السطر، فاكتبه واضغط Enter. F5 يعيد السطر، "
                "وF6 يقرؤه حرفًا حرفًا، وزرّ اشرح المفاتيح الجديدة يصف مكان كل حرف جديد.")

    # -- course and lessons -------------------------------------------------

    def _load_course(self, evt=None):
        i = self.courseChoice.GetSelection()
        if not (0 <= i < len(self._index)):
            return
        self.course = tc.Course.load(self._index[i]["id"])
        prog = tc.load_progress(self.academy.store, self.course.id).get("lessons", {})
        items = []
        for k, les in enumerate(self.course.lessons):
            p = prog.get(str(k))
            mark = f" (الدقّة {p['accuracy']}٪، {p['wpm']} كلمة في الدقيقة)" if p else ""
            new = "، ".join(tc.char_name(c) for c in dict.fromkeys(les.new) if not c.isspace())
            items.append(f"{les.title}: {new}{mark}" if new else f"{les.title}{mark}")
        self.lessonList.Set(items)
        last = tc.load_progress(self.academy.store, self.course.id).get("last", 0)
        if items:
            self.lessonList.SetSelection(min(last, len(items) - 1))

    def _lesson_index(self):
        return self.lessonList.GetSelection()

    def _explain(self):
        if self.course and self._lesson_index() >= 0:
            self._say(self.course.lesson_intro(self._lesson_index()))

    def _home(self):
        if self.course:
            self._say(self.course.home_position())

    def _start(self, lines=None):
        i = self._lesson_index()
        if not self.course or i < 0:
            return
        self.session = tc.Session(self.course, i, lines=list(lines) if lines else [])
        self._show_line(intro=self.course.lesson_intro(i) + "\n" if not lines else "تمرين: ")

    def _drill(self):
        i = self._lesson_index()
        if not self.course or i < 0:
            return
        known = "".join(l.new for l in self.course.lessons[:i])
        lines = tc.drill_lines(self.course.lessons[i].new, known)
        if lines:
            self._start(lines)

    # -- typing ----------------------------------------------------------------

    def _show_line(self, intro: str = ""):
        s = self.session
        if s is None:
            return
        if s.finished:
            acc, wpm = s.stats()
            tc.save_lesson_result(self.academy.store, self.course.id, s.lesson_index, acc, wpm)
            self.lineOut.SetValue("")
            self._say("أنهيت الدرس. " + s.summary())
            self._load_course()
            return
        self.lineOut.SetValue(s.current)
        self.entry.SetValue("")
        self.entry.SetFocus()
        self.status.SetLabel(f"السطر {s.position + 1} من {len(s.lines)}")
        self._say(f"{intro}السطر {s.position + 1}: {s.current}")

    def _on_text(self, evt):
        evt.Skip()
        if self.session and self.session.started is None and self.entry.GetValue():
            self.session.start_line()

    def _on_key(self, evt):
        key = evt.GetKeyCode()
        if key == wx.WXK_F5 and self.session and self.session.current:
            self._say(self.session.current)
            return
        if key == wx.WXK_F6 and self.session and self.session.current:
            self._say("، ".join(tc.char_name(c) for c in self.session.current))
            return
        evt.Skip()

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.entry:
            self._submit()
            return True
        return False

    def _submit(self):
        s = self.session
        if s is None or s.finished:
            return
        if s.started is None:
            s.start_line()
        res = s.submit(self.entry.GetValue())
        if res.passed:
            self._show_line(intro=res.feedback() + " ")
        else:
            self.entry.SetValue("")
            self._say(res.feedback() + f" أعد السطر: {s.current}")

    def _summary(self):
        self._say(self.session.summary() if self.session else "ابدأ درسًا أوّلًا.")

    def _credit(self):
        if self.course:
            who = self.course.credit.replace("\n", "، ") if self.course.credit else ""
            self._say(f"الدروس من برنامج KTouch من مشروع KDE، برخصة GPL. {who}")
