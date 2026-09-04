# -*- coding: utf-8 -*-
"""
abaAcademy.gui.exercise_runner
==============================

The accessible exercise window. It renders one ``Question`` at a time from a
``QuestionSession`` and enforces the spec's per-question rules:

* every new question is spoken immediately when it appears (cancel-before-speak),
* the answer control receives focus automatically (no Tab needed to answer),
* the question text is carried on the focused control's accessible name, so
  moving focus to it announces the whole prompt,
* Enter submits / advances; feedback (correct/incorrect + explanation) is placed
  on the Next button's accessible name so focusing it announces the result,
* consistent shortcuts (Ctrl+R repeat, Ctrl+H explanation, Escape back) via the
  AccessibleDialog base.

The runner is a thin view: all grading/stats/SRS live in the session/academy.
"""

from __future__ import annotations

import wx

from ..engine.models import QuestionType
from .accessible import AccessibleDialog


class ExerciseRunner(AccessibleDialog):
    def __init__(self, parent, academy, session, title, speech,
                 lesson_id="", level_id="", course_id="", on_finish_summary=True):
        super().__init__(parent, title, speech, size=(760, 560))
        self.academy = academy
        self.session = session
        self.lesson_id = lesson_id
        self.level_id = level_id
        self.course_id = course_id
        self.on_finish_summary = on_finish_summary
        self._answered = False
        self._selected_tf = None
        self._last_wrong = None
        self._finalized = False

        panel = wx.Panel(self)
        self.panel = panel
        self.sizer = wx.BoxSizer(wx.VERTICAL)

        self.progressLabel = wx.StaticText(panel, label="")
        self.sizer.Add(self.progressLabel, 0, wx.ALL, 8)

        self.promptCtrl = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.promptCtrl.SetName("نص السؤال")
        self.sizer.Add(self.promptCtrl, 0, wx.EXPAND | wx.ALL, 8)

        self.bodyPanel = wx.Panel(panel)
        self.bodySizer = wx.BoxSizer(wx.VERTICAL)
        self.bodyPanel.SetSizer(self.bodySizer)
        self.sizer.Add(self.bodyPanel, 1, wx.EXPAND | wx.ALL, 8)

        btns = wx.BoxSizer(wx.HORIZONTAL)
        self.checkBtn = self.button(panel, "تحقق", self._on_check)
        self.nextBtn = self.button(panel, "التالي", self._on_next)
        self.skipBtn = self.button(panel, "تخطّي", self._on_skip)
        self.hintBtn = self.button(panel, "تلميح (Ctrl+G)", lambda e: self.on_hint())
        self.nextBtn.Disable()
        btns.Add(self.checkBtn, 0, wx.ALL, 6)
        btns.Add(self.nextBtn, 0, wx.ALL, 6)
        btns.Add(self.skipBtn, 0, wx.ALL, 6)
        btns.Add(self.hintBtn, 0, wx.ALL, 6)
        closeBtn = self.button(panel, "إنهاء", lambda e: self._finish())
        btns.Add(closeBtn, 0, wx.ALL, 6)
        self.sizer.Add(btns, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(self.sizer)
        self._advance()

    def instructions(self) -> str:
        return "أجب عن السؤال ثم اضغط إنتر للتحقق. Ctrl+R لإعادة السؤال، Escape للرجوع."

    # -- flow --------------------------------------------------------------

    def _clear_body(self):
        self.bodySizer.Clear(delete_windows=True)
        self.mcq = None
        self.typing = None
        self.tfTrue = None
        self.tfFalse = None
        self.ordering = None
        self.orderList = None
        self._order_items = []
        self._match_choices = []
        self._match_lefts = []

    def _advance(self):
        if not self.session.has_next():
            self._finish()
            return
        q = self.session.next_question()
        if q is None:
            self._finish()
            return
        self._render(q)

    def _render(self, q):
        self._clear_body()
        self._answered = False
        self._selected_tf = None
        self._last_wrong = None
        self.orderList = None
        self._order_items = []
        self._hint_level = 0
        self.checkBtn.Enable()
        self.nextBtn.Disable()
        self.nextBtn.SetName("التالي")

        st = self.session.stats
        remaining = self.session.remaining()
        self.progressLabel.SetLabel(
            f"صحيحة: {st.correct} | خطأ: {st.wrong} | المتبقّي في القائمة: {remaining}")
        self.promptCtrl.SetValue(q.prompt)

        if q.qtype is QuestionType.MCQ:
            self.mcq = wx.RadioBox(self.bodyPanel, label=q.prompt, choices=q.options,
                                   majorDimension=1, style=wx.RA_SPECIFY_COLS)
            self.mcq.SetName(q.prompt)
            self.mcq.Bind(wx.EVT_KEY_DOWN, self._enter_checks)
            self.bodySizer.Add(self.mcq, 0, wx.EXPAND | wx.ALL, 4)
            self.checkBtn.SetDefault()
            self.set_first_control(self.mcq)
            wx.CallAfter(self.mcq.SetFocus)
        elif q.qtype is QuestionType.TRUE_FALSE:
            row = wx.BoxSizer(wx.HORIZONTAL)
            self.tfTrue = wx.ToggleButton(self.bodyPanel, label="صح")
            self.tfFalse = wx.ToggleButton(self.bodyPanel, label="خطأ")
            self.tfTrue.SetName(q.prompt + " — صح")
            self.tfFalse.SetName(q.prompt + " — خطأ")
            self.tfTrue.Bind(wx.EVT_TOGGLEBUTTON, lambda e: self._pick_tf(True))
            self.tfFalse.Bind(wx.EVT_TOGGLEBUTTON, lambda e: self._pick_tf(False))
            row.Add(self.tfTrue, 0, wx.ALL, 4)
            row.Add(self.tfFalse, 0, wx.ALL, 4)
            self.bodySizer.Add(row, 0, wx.ALL, 4)
            self.set_first_control(self.tfTrue)
            wx.CallAfter(self.tfTrue.SetFocus)
        elif q.qtype is QuestionType.ORDERING:
            # An accessible reordering list: the words start shuffled, and the
            # learner moves the selected word up or down (Alt+Up / Alt+Down, or
            # the buttons) until the order is right — no typing needed. Ctrl+Up /
            # Ctrl+Down is avoided because the screen reader uses those to read by paragraph.
            import random as _r
            start = list(q.options)
            _r.Random(getattr(q, "qid", "") or str(q.prompt)).shuffle(start)
            self._order_items = start
            hint = ("رتّب الكلمات: تنقّل بالأسهم، وحرّك الكلمة المختارة بـ Alt مع سهم "
                    "أعلى أو أسفل، ثم اضغط تحقّق.")
            label = wx.StaticText(self.bodyPanel, label=q.prompt + " — " + hint)
            self.bodySizer.Add(label, 0, wx.ALL, 4)
            self.orderList = wx.ListBox(self.bodyPanel, style=wx.LB_SINGLE,
                                        choices=self._order_items)
            self.orderList.SetName(q.prompt + " — " + hint)
            self.select_index(self.orderList, 0)
            self.orderList.Bind(wx.EVT_KEY_DOWN, self._on_order_key)
            self.bodySizer.Add(self.orderList, 1, wx.EXPAND | wx.ALL, 4)
            mv = wx.BoxSizer(wx.HORIZONTAL)
            up = wx.Button(self.bodyPanel, label="أعلى (Alt+↑)")
            down = wx.Button(self.bodyPanel, label="أسفل (Alt+↓)")
            up.Bind(wx.EVT_BUTTON, lambda e: self._move_order(-1))
            down.Bind(wx.EVT_BUTTON, lambda e: self._move_order(1))
            mv.Add(up, 0, wx.ALL, 2)
            mv.Add(down, 0, wx.ALL, 2)
            self.bodySizer.Add(mv, 0, wx.ALL, 2)
            self.set_first_control(self.orderList)
            wx.CallAfter(self.orderList.SetFocus)
        elif q.qtype is QuestionType.MATCHING:
            # one dropdown per left item; choices are all right-side answers.
            self._match_lefts = list(q.correct.keys())
            rights = list(dict.fromkeys(q.correct.values()))
            import random as _r
            _r.shuffle(rights)
            self._match_choices = []
            first_choice = None
            for left in self._match_lefts:
                rowlbl = wx.StaticText(self.bodyPanel, label=left)
                self.bodySizer.Add(rowlbl, 0, wx.TOP | wx.LEFT, 4)
                ch = wx.Choice(self.bodyPanel, choices=rights)
                ch.SetName("اختر ما يطابق: " + left)
                self.bodySizer.Add(ch, 0, wx.EXPAND | wx.ALL, 4)
                self._match_choices.append((left, ch))
                if first_choice is None:
                    first_choice = ch
            self.checkBtn.SetDefault()
            if first_choice is not None:
                self.set_first_control(first_choice)
                wx.CallAfter(first_choice.SetFocus)
        else:  # TYPING -> text entry
            self.typing = wx.TextCtrl(self.bodyPanel, style=wx.TE_PROCESS_ENTER)
            self.typing.SetName(q.prompt)
            self.typing.Bind(wx.EVT_TEXT_ENTER, self._on_check)
            self.bodySizer.Add(self.typing, 0, wx.EXPAND | wx.ALL, 4)
            self.checkBtn.SetDefault()
            self.set_first_control(self.typing)
            wx.CallAfter(self.typing.SetFocus)

        self.bodyPanel.Layout()
        self.panel.Layout()
        # speak the question immediately (cancel any prior speech). For dictation
        # we voice the sentence to transcribe (q.speak) instead of the prompt.
        self.announce(q.speak or q.prompt)

    def _enter_checks(self, evt):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and not self._answered:
            self._on_check(evt)
        else:
            evt.Skip()

    def _pick_tf(self, value):
        self._selected_tf = value
        (self.tfFalse if value else self.tfTrue).SetValue(False)
        if not self._answered:
            self._on_check(None)

    def _current_answer(self, q):
        if q.qtype is QuestionType.MCQ:
            return self.mcq.GetSelection() if self.mcq else -1
        if q.qtype is QuestionType.TRUE_FALSE:
            return self._selected_tf
        if q.qtype is QuestionType.ORDERING:
            return list(getattr(self, "_order_items", []))
        if q.qtype is QuestionType.MATCHING:
            return {left: ch.GetStringSelection() for left, ch in
                    getattr(self, "_match_choices", [])}
        return self.typing.GetValue() if self.typing else ""

    def on_enter_key(self) -> bool:
        # Single key drives the whole loop: if the current question is answered,
        # Enter moves to the next one; otherwise Enter checks the answer. This is
        # what removes the need to Tab to a button between questions.
        if self._answered:
            self._advance()
        else:
            self._on_check(None)
        return True

    def _on_check(self, evt):
        if self._answered:
            return
        q = self.session.current
        if q is None:
            return
        if q.qtype is QuestionType.TRUE_FALSE and self._selected_tf is None:
            self.announce("اختر صح أو خطأ أولاً")
            return
        given = self._current_answer(q)
        result = self.session.submit(given)
        self._answered = True
        self.checkBtn.Disable()
        self.nextBtn.Enable()
        self.nextBtn.SetDefault()
        import random as _r
        if result.correct:
            verdict = _r.choice(["أحسنت! ", "ممتاز! ", "رائع! ", "إجابة صحيحة. ",
                                 "بالضبط! ", "أجل، صحيح! "])
            feedback = verdict + (q.explanation or "")
        else:
            verdict = _r.choice(["لا بأس. ", "إجابة غير صحيحة. ",
                                 "ليست صحيحة، لكن لا تيأس. ", "قريب، لكن ليس تماماً. "])
            # Tell the learner *what* the right answer was and, for typing, what
            # they wrote — so a mistake teaches instead of just failing.
            correction = self._correction_text(q, given)
            parts = [verdict.strip(), correction]
            if q.explanation:
                parts.append("توضيح: " + q.explanation)
            feedback = " ".join(p for p in parts if p) + " "
            # remember a typed mistake so Ctrl+R can spell out the correct word
            # against what the learner wrote, letter by letter
            if q.qtype is QuestionType.TYPING:
                self._last_wrong = (str(q.correct), (given or "").strip())
                feedback += "اضغط Ctrl+R لتهجئة الإجابة الصحيحة ومقارنتها بما كتبت. "
        # place feedback on Next's accessible name so focusing it announces it
        self.nextBtn.SetName(feedback + " اضغط للانتقال إلى السؤال التالي")
        wx.CallAfter(self.nextBtn.SetFocus)
        self.announce(feedback)

    def _correction_text(self, q, given) -> str:
        """A clear, spoken correction for a wrong answer."""
        qt = q.qtype
        if qt is QuestionType.MCQ:
            try:
                return "الإجابة الصحيحة هي: " + q.options[q.correct] + "."
            except (IndexError, TypeError):
                return ""
        if qt is QuestionType.TRUE_FALSE:
            return "الصواب هو: " + ("صح" if q.correct else "خطأ") + "."
        if qt is QuestionType.ORDERING:
            try:
                return "الترتيب الصحيح: " + " ".join(q.correct) + "."
            except TypeError:
                return ""
        if qt is QuestionType.MATCHING:
            pairs = "، ".join(f"{k} ← {v}" for k, v in (q.correct or {}).items())
            return "المطابقات الصحيحة: " + pairs + "."
        # TYPING
        typed = (given or "").strip()
        msg = "الإجابة الصحيحة: " + str(q.correct) + "."
        if q.accepted:
            msg += " ويُقبل أيضاً: " + "، ".join(str(a) for a in q.accepted) + "."
        if typed:
            msg += " أنت كتبت: " + typed + "."
        return msg

    def _on_next(self, evt):
        self._advance()

    def _on_skip(self, evt):
        if self.session.current is not None and not self._answered:
            self.session.skip()
        self._advance()

    def _on_order_key(self, evt):
        # Alt+Up / Alt+Down move the selected word (Ctrl+arrows are left to the screen reader)
        if evt.AltDown() and evt.GetKeyCode() == wx.WXK_UP:
            self._move_order(-1)
        elif evt.AltDown() and evt.GetKeyCode() == wx.WXK_DOWN:
            self._move_order(1)
        else:
            evt.Skip()

    def _move_order(self, delta):
        lb = getattr(self, "orderList", None)
        if lb is None:
            return
        i = lb.GetSelection()
        if i == wx.NOT_FOUND:
            return
        j = i + delta
        if j < 0 or j >= len(self._order_items):
            return
        self._order_items[i], self._order_items[j] = \
            self._order_items[j], self._order_items[i]
        lb.Set(self._order_items)
        self.select_index(lb, j)
        # announce the moved word and its new position for eyes-free feedback
        self.announce(f"{self._order_items[j]}، الموضع {j + 1} من {len(self._order_items)}")

    def on_repeat(self):
        # After a typed mistake, Ctrl+R spells out the correct answer letter by
        # letter and then what the learner wrote, so they can hear exactly where
        # the spelling differed. Otherwise it just re-reads the question.
        lw = getattr(self, "_last_wrong", None)
        if self._answered and lw:
            correct, typed = lw
            msg = "الإجابة الصحيحة: " + correct + "؛ تهجئتها: " + self._spell(correct) + "."
            if typed:
                msg += " وأنت كتبت: " + typed + "؛ تهجئته: " + self._spell(typed) + "."
            self.announce(msg)
            return
        q = self.session.current
        if q is not None:
            self.announce(q.speak or q.prompt)

    @staticmethod
    def _spell(text):
        # space out the letters so the screen reader pronounces each one; keep
        # spaces between words as an explicit word so it's clear where they fall
        out = []
        for ch in str(text):
            out.append("مسافة" if ch == " " else ch)
        return " ".join(out)

    def on_hear_explanation(self):
        q = self.session.current
        if q is not None and q.explanation:
            self.announce(q.explanation)

    def on_hint(self):
        """Reveal a graded hint for the current, not-yet-answered question. Each
        press of Ctrl+G gives a stronger clue: first a nudge (the question's own
        hint, or a category/kind cue), then the first letter of the answer, then
        the number of letters. This lets a stuck learner reason toward the answer
        instead of guessing and failing — and it never simply reads the answer
        out."""
        q = self.session.current
        if q is None or self._answered:
            return
        self._hint_level = getattr(self, "_hint_level", 0) + 1
        self.announce(self._hint_text(q, self._hint_level))

    def _hint_text(self, q, level):
        from .. engine.models import QuestionType
        # a plain-text version of the answer, for letter/length hints
        if q.qtype is QuestionType.MCQ and q.options:
            answer = str(q.options[q.correct]) if isinstance(q.correct, int) else ""
        elif q.qtype is QuestionType.TYPING:
            answer = str(q.correct)
        elif q.qtype is QuestionType.TRUE_FALSE:
            # for true/false a single escalating nudge is all that's sensible
            return q.hint or "فكّر جيداً: هل العبارة تنطبق دائماً؟"
        else:
            answer = ""

        # level 1: the authored hint, or a gentle kind/category nudge
        if level <= 1:
            if q.hint:
                return "تلميح: " + q.hint
            if q.qtype is QuestionType.MCQ:
                return "تلميح: استبعد الخيارات التي تعرف أنها خطأ أولاً."
            return "تلميح: تذكّر الدرس؛ الإجابة من نفس الموضوع."
        # level 2: first letter
        if level == 2 and answer:
            return "أول حرف من الإجابة: " + answer[0]
        # level 3+: length / first two letters
        if answer:
            two = answer[:2]
            return f"الإجابة تبدأ بـ «{two}» وعدد حروفها {len(answer.replace(' ', ''))}."
        return "لا مزيد من التلميحات."

    def _finalize_once(self):
        """Record the session exactly once, whichever way the window closes."""
        if self._finalized:
            return None
        self._finalized = True
        try:
            return self.academy.finalize_session(
                self.session, self.lesson_id, self.level_id, self.course_id)
        except Exception:
            return None

    def on_closing(self):
        # Escape / Alt+F4 / the X button land here. Previously those paths
        # bypassed _finish entirely, so leaving a quiz early threw away the
        # answers already given and left an unterminated session row in the
        # database. Now partial work is always saved.
        self._finalize_once()

    def _finish(self):
        summary = self._finalize_once()
        if self.on_finish_summary and summary:
            msg = (f"انتهت الجلسة. أجبت عن {summary['total']} سؤالاً، "
                   f"منها {summary['correct']} صحيحة، بنسبة {summary['accuracy']} بالمئة.")
            earned = summary.get("achievements") or []
            if earned:
                msg += " إنجاز جديد: " + "، ".join(earned) + "."
            self.announce(msg)
            wx.MessageBox(msg, "نتيجة الجلسة", wx.OK | wx.ICON_INFORMATION)
        self.close_screen(force=True)
