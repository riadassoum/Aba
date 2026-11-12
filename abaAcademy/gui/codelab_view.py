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
* **التحدّيات** — pick a track and a challenge, read the task, submit, and get
  checked. 150 challenges in ten tracks: the original beginner set, original
  tracks on loops, functions, Arabic text and classes, and four tracks adapted
  into Arabic from Exercism's problem specifications (MIT).
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..codelab.sandbox import run_code
from ..codelab.challenges import check_solution, tracks as challenge_tracks


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
        self._tracks = challenge_tracks()
        self.trackChoice = wx.Choice(panel, choices=[self._track_label(i) for i in range(len(self._tracks))])
        self.trackChoice.SetName("المسار")
        self.trackChoice.SetSelection(0)
        self.trackChoice.Disable()
        self.bind_choice(self.trackChoice, lambda e: self._on_track())
        mrow.Add(wx.StaticText(panel, label="المسار:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        mrow.Add(self.trackChoice, 0, wx.RIGHT, 12)
        self.challengeChoice = wx.Choice(panel, choices=[])
        self.challengeChoice.SetName("التحدّي")
        self.challengeChoice.Disable()
        self.bind_choice(self.challengeChoice, lambda e: self._load_challenge())
        mrow.Add(wx.StaticText(panel, label="التحدّي:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        mrow.Add(self.challengeChoice, 1)
        s.Add(mrow, 0, wx.EXPAND | wx.ALL, 6)
        self._fill_challenges()

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
        self.nextBtn = self.button(panel, "التحدّي التالي", lambda e: self._next_challenge())
        self.nextBtn.Disable()
        row.Add(self.nextBtn, 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.editor)

    # -- modes ------------------------------------------------------------
    def _done(self, cid):
        try:
            return self.academy.store.get_setting(f"codelab_{cid}", "") == "done"
        except Exception:
            return False

    def _track_label(self, i):
        tid, title, items = self._tracks[i]
        done = sum(1 for c in items if self._done(c.cid))
        return f"{title} ({done} من {len(items)})"

    def _items(self):
        i = self.trackChoice.GetSelection()
        return self._tracks[i][2] if 0 <= i < len(self._tracks) else []

    def _fill_challenges(self, keep=0):
        items = self._items()
        self.challengeChoice.Set([f"{k + 1}. {c.title}" + (" (منجز)" if self._done(c.cid) else "")
                                  for k, c in enumerate(items)])
        if items:
            self.challengeChoice.SetSelection(min(keep, len(items) - 1))

    def _on_track(self):
        items = self._items()
        first_open = next((k for k, c in enumerate(items) if not self._done(c.cid)), 0)
        self._fill_challenges(first_open)
        self._load_challenge()

    def _next_challenge(self):
        i = self.challengeChoice.GetSelection()
        items = self._items()
        if i + 1 < len(items):
            self.challengeChoice.SetSelection(i + 1)
            self._load_challenge()
        else:
            t = self.trackChoice.GetSelection()
            if t + 1 < len(self._tracks):
                self.trackChoice.SetSelection(t + 1)
                self._on_track()
            else:
                self._say("أنهيت آخر تحدٍّ في آخر مسار. أحسنت!")

    def _on_mode(self):
        challenges = self.modeChoice.GetSelection() == 1
        self.trackChoice.Enable(challenges)
        self.challengeChoice.Enable(challenges)
        self.submitBtn.Enable(challenges)
        self.nextBtn.Enable(challenges)
        if challenges:
            self._load_challenge()
        else:
            self._challenge = None
            self._say("تدريب حر: اكتب أي كود وشغّله.")

    def _load_challenge(self):
        i = self.challengeChoice.GetSelection()
        if i < 0:
            return
        items = self._items()
        if i >= len(items):
            return
        self._challenge = items[i]
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
        if not passed:
            self._say(msg)
        else:
            # record progress in user data
            try:
                self.academy.store.set_setting(
                    f"codelab_{self._challenge.cid}", "done")
            except Exception:
                pass
            i = self.challengeChoice.GetSelection()
            t = self.trackChoice.GetSelection()
            self.trackChoice.SetString(t, self._track_label(t))
            self._fill_challenges(i)
            self._say(msg + " اضغط التحدّي التالي للمتابعة.")

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
                "في نمط التحدّيات، اختر مسارًا ثم تحدّيًا (١٥٠ تحدّيًا في عشرة مسارات)، اقرأ المهمة، اكتب الحل، ثم تحقّق من الحل "
                "لتُختبر إجابتك آلياً. الأخطاء تُشرح بالعربية مع رقم السطر. لمّح يعطيك "
                "تلميحاً. التشغيل للتعلّم على جهازك وليس حاجزاً أمنياً. Escape للإغلاق.")
