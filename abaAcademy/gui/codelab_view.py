# -*- coding: utf-8 -*-
"""
abaAcademy.gui.codelab_view
===========================

The accessible Python code lab. A learner can write code in a multiline editor,
run it (Ctrl+Enter) and hear the output, and work through the curated challenges
with automatic Arabic feedback. Syntax and runtime errors are explained in
Arabic, with the line number, so a screen-reader user isn't stranded on an
English traceback.

Two modes:
* **تدريب حر** — free coding: write anything, run it, hear output or the Arabic
  error.
* **التحدّيات** — pick a challenge, read the task, submit, and get checked.
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..codelab.sandbox import run_code
from ..codelab.challenges import CHALLENGES, check_solution


class CodeLabDialog(AccessibleDialog):
    TITLE = "مختبر البرمجة (بايثون)"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(760, 620))
        self.academy = academy
        self._challenge = None

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "اكتب كود بايثون ثم شغّله بـ Ctrl+Enter لتسمع الناتج. الأخطاء تُشرح "
            "بالعربية مع رقم السطر. ملاحظة: التشغيل مخصّص للتعلّم على جهازك، وليس "
            "حاجزاً أمنياً ضد الأكواد الضارّة.")), 0, wx.ALL, 6)

        mrow = wx.BoxSizer(wx.HORIZONTAL)
        mrow.Add(wx.StaticText(panel, label="النمط:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.modeChoice = wx.Choice(panel, choices=["تدريب حر", "التحدّيات"])
        self.modeChoice.SetSelection(0)
        self.bind_choice(self.modeChoice, lambda e: self._on_mode())
        mrow.Add(self.modeChoice, 0, wx.RIGHT, 12)
        self.challengeChoice = wx.Choice(
            panel, choices=[f"{i+1}. {c.title}" for i, c in enumerate(CHALLENGES)])
        self.challengeChoice.SetSelection(0)
        self.challengeChoice.Disable()
        self.bind_choice(self.challengeChoice, lambda e: self._load_challenge())
        mrow.Add(wx.StaticText(panel, label="التحدّي:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        mrow.Add(self.challengeChoice, 0)
        s.Add(mrow, 0, wx.ALL, 6)

        s.Add(wx.StaticText(panel, label="الكود:"), 0, wx.LEFT | wx.TOP, 6)
        self.editor = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_DONTWRAP | wx.HSCROLL,
            size=(-1, 220))
        self.editor.SetName("محرّر الكود")
        self.editor.Bind(wx.EVT_KEY_DOWN, self._on_key)
        s.Add(self.editor, 1, wx.EXPAND | wx.ALL, 6)

        s.Add(wx.StaticText(panel, label="الناتج:"), 0, wx.LEFT, 6)
        self.output = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY,
                                  size=(-1, 120))
        self.output.SetName("ناتج التشغيل")
        s.Add(self.output, 0, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(720)
        s.Add(self.status, 0, wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "شغّل (Ctrl+Enter)", lambda e: self._run()), 0, wx.ALL, 3)
        self.submitBtn = self.button(panel, "تحقّق من الحل", lambda e: self._submit())
        self.submitBtn.Disable()
        row.Add(self.submitBtn, 0, wx.ALL, 3)
        row.Add(self.button(panel, "لمّح", lambda e: self._hint()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "اقرأ المهمة", lambda e: self._read_task()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.editor)

    # -- modes ------------------------------------------------------------
    def _on_mode(self):
        challenges = self.modeChoice.GetSelection() == 1
        self.challengeChoice.Enable(challenges)
        self.submitBtn.Enable(challenges)
        if challenges:
            self._load_challenge()
        else:
            self._challenge = None
            self._say("تدريب حر: اكتب أي كود وشغّله.")

    def _load_challenge(self):
        i = self.challengeChoice.GetSelection()
        if i < 0:
            return
        self._challenge = CHALLENGES[i]
        if self._challenge.starter:
            self.editor.SetValue(self._challenge.starter)
        self._read_task()

    def _read_task(self):
        if self._challenge:
            self._say(f"التحدّي: {self._challenge.title}. {self._challenge.prompt}")
        else:
            self._say("أنت في وضع التدريب الحر.")

    # -- running ----------------------------------------------------------
    def _on_key(self, evt):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and evt.ControlDown():
            self._run()
        else:
            evt.Skip()

    def _run(self):
        source = self.editor.GetValue()
        if not source.strip():
            self._say("اكتب بعض الكود أولاً.")
            return
        self._say("يُشغّل الكود…")
        result = run_code(source, timeout=5.0)
        if result.error:
            self.output.SetValue((result.output or "") + "\n⚠ " + result.error)
            self._say("خطأ: " + result.error)
        else:
            self.output.SetValue(result.output or "(لا مُخرجات)")
            spoken = result.output.strip() if result.output.strip() else "لا مُخرجات"
            self._say("الناتج: " + spoken)

    def _submit(self):
        if not self._challenge:
            self._say("اختر تحدّياً أولاً.")
            return
        source = self.editor.GetValue()
        passed, msg = check_solution(self._challenge, source)
        self._say(msg)
        if passed:
            # record progress in user data
            try:
                self.academy.store.set_setting(
                    f"codelab_{self._challenge.cid}", "done")
            except Exception:
                pass

    def _hint(self):
        if self._challenge and self._challenge.hint:
            self._say("تلميح: " + self._challenge.hint)
        else:
            self._say("لا يوجد تلميح لهذا الوضع.")

    def _say(self, text):
        self.status.SetLabel(text[:200])
        self.announce(text)

    def instructions(self):
        return ("مختبر البرمجة: اكتب كود بايثون في المحرّر وشغّله بـ Ctrl+Enter لتسمع الناتج. "
                "في نمط التحدّيات، اختر تحدّياً، اقرأ المهمة، اكتب الحل، ثم «تحقّق من الحل» "
                "لتُختبر إجابتك آلياً. الأخطاء تُشرح بالعربية مع رقم السطر. «لمّح» يعطيك "
                "تلميحاً. التشغيل للتعلّم على جهازك وليس حاجزاً أمنياً. Escape للإغلاق.")
