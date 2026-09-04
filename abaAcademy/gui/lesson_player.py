# -*- coding: utf-8 -*-
"""
abaAcademy.gui.lesson_player
============================

Plays a lesson's teaching blocks in order, the way the spec describes a lesson:
"explain a concept, ask a small question, give feedback, explain again, ask
another". It walks the ``theory`` blocks — speaking text/example blocks and, for
embedded question blocks, dropping into a one-question accessible prompt — then
offers to continue into practice/quiz via the ExerciseRunner.

It reuses the AccessibleDialog announce-on-show policy, so opening the player
immediately speaks the lesson title, the first objective, and the first block.
Blocks are executed from a freshly loaded, isolated ``Lesson`` object.
"""

from __future__ import annotations

import wx

from ..engine.models import BlockType, QuestionType
from .accessible import AccessibleDialog
from .exercise_runner import ExerciseRunner


def _block_to_text(block) -> str:
    d = block.data
    if block.btype is BlockType.TEXT:
        return d.get("text", "")
    if block.btype is BlockType.EXAMPLE:
        note = d.get("note", "")
        text = f"مثال: {d.get('text','')}"
        # a worked example may include ordered steps that show *how* the answer
        # is reached (method, not just the fact) — spoken one step at a time so
        # the learner follows the reasoning
        steps = d.get("steps", [])
        if steps:
            body = "؛ ".join(f"الخطوة {i}: {s}" for i, s in enumerate(steps, 1))
            text += " — كيف نصل إلى الحل: " + body
        if note:
            text += f" — {note}"
        return text
    if block.btype is BlockType.DIALOGUE:
        return " ".join(d.get("lines", []))
    if block.btype is BlockType.READING:
        return d.get("passage", d.get("text", ""))
    return d.get("text", "")


class LessonPlayer(AccessibleDialog):
    def __init__(self, parent, academy, lesson, speech):
        super().__init__(parent, f"درس: {lesson.meta.title}", speech, size=(760, 560))
        self.academy = academy
        self.lesson = lesson
        # Flatten theory into a display sequence: text blocks and inline questions.
        self._steps = []
        for b in lesson.theory:
            if b.btype is BlockType.QUESTION and b.questions:
                self._steps.append(("question", b.questions[0]))
            else:
                self._steps.append(("text", _block_to_text(b)))
        if not self._steps:
            # No theory loaded. This should never happen for an authored lesson
            # -- every lesson ships a theory.json with content -- so landing here
            # means the file failed to read on this machine (encoding, a partial
            # install, permissions). Log it for diagnosis and give the learner a
            # useful screen: the exercises are ready, Enter jumps straight to them.
            try:
                import logging as _logging; log = _logging.getLogger("abaAcademy")
                log.warning(
                    "abaAcademy: lesson %r loaded with empty theory; the theory "
                    "file may have failed to read.",
                    getattr(lesson.meta, "lesson_id", "?"))
            except Exception:
                pass
            self._steps.append((
                "text",
                "لم يُعثر على الشرح النصي لهذا الدرس، لكنّ التمارين جاهزة. "
                "اضغط زر «الانتقال إلى التمارين» للبدء مباشرة."))
        self._index = 0
        self._answered = False

        panel = wx.Panel(self)
        self.panel = panel
        self.sizer = wx.BoxSizer(wx.VERTICAL)

        self.statusLabel = wx.StaticText(panel, label="")
        self.sizer.Add(self.statusLabel, 0, wx.ALL, 8)

        self.textCtrl = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.textCtrl.SetName("محتوى الدرس")
        self.sizer.Add(self.textCtrl, 1, wx.EXPAND | wx.ALL, 8)

        self.answerPanel = wx.Panel(panel)
        self.answerSizer = wx.BoxSizer(wx.VERTICAL)
        self.answerPanel.SetSizer(self.answerSizer)
        self.sizer.Add(self.answerPanel, 0, wx.EXPAND | wx.ALL, 8)

        btns = wx.BoxSizer(wx.HORIZONTAL)
        self.nextBtn = self.button(panel, "متابعة", self._on_next)
        self.practiceBtn = self.button(panel, "الانتقال إلى التمارين", self._on_practice)
        btns.Add(self.nextBtn, 0, wx.ALL, 6)
        btns.Add(self.practiceBtn, 0, wx.ALL, 6)
        closeBtn = self.button(panel, "إغلاق", lambda e: self.close_screen())
        btns.Add(closeBtn, 0, wx.ALL, 6)
        self.sizer.Add(btns, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(self.sizer)
        self._render()

    def instructions(self) -> str:
        objs = "؛ ".join(self.lesson.meta.objectives)
        base = "اضغط متابعة للتنقل في الدرس، أو انتقل إلى التمارين في أي وقت."
        return (f"أهداف الدرس: {objs}. {base}") if objs else base

    def _clear_answer(self):
        self.answerSizer.Clear(delete_windows=True)
        self.mcq = None

    def _render(self):
        self._clear_answer()
        total = len(self._steps)
        if self._index >= total:
            self.statusLabel.SetLabel("انتهى الشرح.")
            self.textCtrl.SetValue("انتهى شرح الدرس. انتقل إلى التمارين لتثبيت ما تعلمته.")
            self.nextBtn.Disable()
            self.set_first_control(self.practiceBtn)
            wx.CallAfter(self.practiceBtn.SetFocus)
            self.announce("انتهى الشرح. انتقل إلى التمارين.")
            return
        kind, payload = self._steps[self._index]
        self.statusLabel.SetLabel(f"الخطوة {self._index + 1} من {total}")
        if kind == "text":
            self.textCtrl.SetValue(payload)
            self.nextBtn.Enable()
            self.nextBtn.SetDefault()
            self.set_first_control(self.textCtrl)
            wx.CallAfter(self.textCtrl.SetFocus)
            self.announce(payload)
        else:  # inline question
            q = payload
            self._answered = False
            self.textCtrl.SetValue("سؤال سريع: " + q.prompt)
            self.mcq = wx.RadioBox(self.answerPanel, label=q.prompt, choices=q.options,
                                   majorDimension=1, style=wx.RA_SPECIFY_COLS)
            self.mcq.SetName(q.prompt)
            self.answerSizer.Add(self.mcq, 0, wx.EXPAND | wx.ALL, 4)
            checkBtn = self.button(self.answerPanel, "تحقق", lambda e: self._check_inline(q))
            self.answerSizer.Add(checkBtn, 0, wx.ALL, 4)
            self.nextBtn.Disable()
            self.set_first_control(self.mcq)
            self.answerPanel.Layout()
            self.panel.Layout()
            wx.CallAfter(self.mcq.SetFocus)
            self.announce(q.prompt)

    def _check_inline(self, q):
        if self.mcq is None:
            return
        correct = self.mcq.GetSelection() == q.correct
        fb = ("أحسنت، إجابة صحيحة. " if correct else "إجابة غير صحيحة. ") + (q.explanation or "")
        self.announce(fb)
        self.nextBtn.Enable()
        self.nextBtn.SetDefault()
        wx.CallAfter(self.nextBtn.SetFocus)

    def _on_next(self, evt):
        self._index += 1
        self._render()

    def on_enter_key(self) -> bool:
        # One key walks the lesson: advance to the next teaching step, and when
        # the explanation is finished, Enter starts the practice exercises.
        if self._index >= len(self._steps):
            self._on_practice(None)
        elif self.nextBtn.IsEnabled():
            self._on_next(None)
        else:
            # inline question not yet answered: Enter checks it via its button
            return False
        return True

    def on_previous(self):
        if self._index > 0:
            self._index -= 1
            self._render()

    def _on_practice(self, evt):
        session = self.academy.build_lesson_practice(self.lesson.meta.lesson_id)
        if session is None:
            self.announce("لا توجد تمارين متاحة لهذا الدرس.")
            return
        runner = ExerciseRunner(
            self, self.academy, session, f"تمارين: {self.lesson.meta.title}",
            self.speech, lesson_id=self.lesson.meta.lesson_id,
            level_id=self.lesson.meta.level_id, course_id=self.lesson.meta.course_id)
        self.show_child(runner)
