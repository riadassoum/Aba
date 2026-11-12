# -*- coding: utf-8 -*-
"""
abaAcademy.gui.morse_view
=========================

The Morse trainer (مدرّب شيفرة مورس), Arabic and Latin:

* **Translate**: text to Morse (spoken as dot/dash and played as tones) and
  Morse back to text.
* **Listening lessons** (Koch method): groups of letters are played at full
  character speed; the learner types what they heard and moves to the next
  lesson — one more letter — at 90% accuracy.
* **Recognise the letter**: hear one letter, choose it from look-alikes.
* **Keying**: hold and release Space to send; the screen decodes the dots
  and dashes and adapts to the learner's speed.
"""

from __future__ import annotations

import random
import time

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog, ChoiceQuiz
from ..tools import morse

_SPEEDS = [(5, "بطيئة جدًّا (٥ كلمات في الدقيقة)"), (8, "بطيئة (٨)"), (12, "متوسّطة (١٢)"),
           (15, "عادية (١٥)"), (20, "سريعة (٢٠)"), (25, "سريعة جدًّا (٢٥)")]
_SPACING = [(0, "بلا مسافات إضافية"), (8, "مسافات واسعة (فارنسوورث ٨)"),
            (5, "مسافات واسعة جدًّا (فارنسوورث ٥)")]


class _LetterQuestion:
    def __init__(self, dialog, target, options):
        alpha = dialog.alphabet()
        self.target = target
        self.prompt = "أيّ حرف سمعت؟"
        self.options = [f"{c} ({morse.letter_name(c, alpha)})" if alpha == "ar" else c for c in options]
        self.answer = self.options[options.index(target)]
        code = morse.table(alpha)[target]
        self.explanation = f"{self.answer}: {morse.rhythm_word(code)}."
        self._dialog = dialog

    def play(self):
        self._dialog.play_text(self.target)


class MorseDialog(ToolDialog):
    TITLE = "مدرّب شيفرة مورس"
    SIZE = (800, 720)
    SETTINGS_PREFIX = "morse_"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self._rng = random.Random()
        self._group = ""
        self._key_down_at = None
        self._sidetone = None
        alpha_i = 1 if self.setting("alphabet", "ar") == "en" else 0
        self.alphaChoice = self.add_choice("الحروف", ["العربية", "اللاتينية والأرقام"], alpha_i,
                                           on_change=self._on_alpha)
        sp = int(self.setting("wpm", "12") or 12)
        self.speedChoice = self.add_choice("سرعة الحروف", [l for _, l in _SPEEDS],
                                           next((i for i, (w, _) in enumerate(_SPEEDS) if w == sp), 2),
                                           on_change=self._save_prefs)
        fw = int(self.setting("farnsworth", "8") or 0)
        self.spacingChoice = self.add_choice("المسافات بين الحروف", [l for _, l in _SPACING],
                                             next((i for i, (w, _) in enumerate(_SPACING) if w == fw), 1),
                                             on_change=self._save_prefs)

        # translate
        self.textEntry = self.add_entry("نصّ أو شيفرة", on_enter=self._translate,
                                        hint="اكتب نصًّا، أو شيفرة بالنقاط والشرطات مفصولة بمسافات")
        self.add_buttons([("ترجم واستمع", self._translate), ("استمع فقط", self._play_entry),
                          ("جدول الحروف", self._table)], close=False)

        # lessons
        self.lessonSpin = self.add_spin("الدرس (عدد الحروف = الدرس + ١)", 1,
                                        morse.lesson_count("ar"),
                                        int(self.setting(f"lesson_{self.alphabet()}", "1") or 1))
        self.answerEntry = self.add_entry("ما سمعته", on_enter=self._check_group)
        self.add_buttons([("مجموعة جديدة", self._new_group), ("أعد", self._replay_group),
                          ("تحقّق", self._check_group), ("حروف الدرس", self._lesson_letters)],
                         close=False)

        # recognise
        self.quizPrompt = self.add_text("التعرّف على الحرف: اضغط حرف جديد.")
        self.options = self.add_list("الخيارات", height=90)
        self.quiz = ChoiceQuiz(self, self.options, self._make_letter, prompt_ctrl=self.quizPrompt)
        self.add_buttons([("حرف جديد", self.quiz.next), ("أعد الحرف", self.quiz.repeat)], close=False)

        # keying
        self.keyer = self.add_entry("لوحة الإرسال: اضغط المسافة مطوّلة أو قصيرة لترسل", "")
        self.keyer.SetEditable(False)
        self.keyer.Bind(wx.EVT_KEY_UP, self._on_key_up)
        self.add_buttons([("امسح الإرسال", self._clear_keyer), ("اقرأ ما أرسلت", self._read_keyer)])
        self.add_output("النتيجة", height=110)
        self.finish(self.textEntry)

        self._decoder = morse.KeyDecoder(self.wpm(), self.alphabet())
        self._idle = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_idle, self._idle)
        self._idle.Start(120)

    # -- preferences ------------------------------------------------------
    def alphabet(self) -> str:
        return "en" if self.choice_index(self.alphaChoice) == 1 else "ar"

    def wpm(self) -> int:
        return _SPEEDS[self.choice_index(self.speedChoice, 2)][0]

    def timing(self) -> morse.Timing:
        fw = _SPACING[self.choice_index(self.spacingChoice, 1)][0]
        w = self.wpm()
        return morse.Timing(w, fw if fw and fw < w else 0)

    def _save_prefs(self) -> None:
        self.set_setting("alphabet", self.alphabet())
        self.set_setting("wpm", self.wpm())
        self.set_setting("farnsworth", _SPACING[self.choice_index(self.spacingChoice, 1)][0])
        self._decoder = morse.KeyDecoder(self.wpm(), self.alphabet())

    def _on_alpha(self) -> None:
        self._save_prefs()
        self.lessonSpin.SetRange(1, morse.lesson_count(self.alphabet()))
        self.lessonSpin.SetValue(int(self.setting(f"lesson_{self.alphabet()}", "1") or 1))

    # -- sound -----------------------------------------------------------
    def play_text(self, text: str) -> None:
        code = morse.encode(text, self.alphabet())
        if code and not self.play_pcm(morse.render_pcm(code, self.timing())):
            self._say("الصوت غير متاح على هذا الجهاز.")

    def _play_code(self, code: str) -> None:
        if not self.play_pcm(morse.render_pcm(code, self.timing())):
            self._say("الصوت غير متاح على هذا الجهاز.")

    # -- translate -------------------------------------------------------
    def _is_code(self, text: str) -> bool:
        return bool(text) and all(ch in ".-/ _•" for ch in text)

    def _translate(self) -> None:
        text = self.textEntry.GetValue().strip()
        if not text:
            raise ValueError("اكتب نصًّا أو شيفرة.")
        a = self.alphabet()
        if self._is_code(text):
            plain = morse.decode(text, a)
            self.show_output(f"الشيفرة: {text}\nالنصّ: {plain}", speak=f"النصّ: {plain}")
            self._play_code(text)
            return
        code = morse.encode(text, a)
        if not code:
            raise ValueError("لا توجد في النصّ حروف لها شيفرة في الأبجدية المختارة.")
        words = []
        tab = morse.table(a)
        for ch in morse.normalise(text, a):
            if ch in tab:
                words.append(f"{morse.letter_name(ch, a)}: {morse.rhythm_word(tab[ch])}")
        self.show_output(f"الشيفرة: {code}\n" + "\n".join(words),
                         speak=f"الشيفرة: {code}")
        self._play_code(code)

    def _play_entry(self) -> None:
        text = self.textEntry.GetValue().strip()
        if not text:
            raise ValueError("اكتب نصًّا أو شيفرة.")
        if self._is_code(text):
            self._play_code(text)
        else:
            self.play_text(text)

    def _table(self) -> None:
        a = self.alphabet()
        src = morse.ARABIC if a == "ar" else dict(list(morse.LATIN.items()) + list(morse.DIGITS.items()))
        lines = [f"{ch} ({morse.letter_name(ch, a)}): {code}   {morse.rhythm_word(code)}"
                 for ch, code in src.items()]
        self.show_output("\n".join(lines), speak="جدول الحروف في مربّع النتيجة.", focus=True)

    # -- lessons ---------------------------------------------------------
    def _lesson(self) -> int:
        return int(self.lessonSpin.GetValue())

    def _lesson_letters(self) -> None:
        a = self.alphabet()
        letters = morse.lesson_letters(a, self._lesson())
        self._say("حروف هذا الدرس: " + "، ".join(morse.letter_name(c, a) for c in letters)
                  + f". الحرف الجديد: {morse.letter_name(letters[-1], a)}.")
        self.play_text(letters[-1] * 3)

    def _new_group(self) -> None:
        self._group = morse.practice_group(self.alphabet(), self._lesson(), self._rng, 5)
        self.answerEntry.SetValue("")
        self.answerEntry.SetFocus()
        self.play_text(self._group)

    def _replay_group(self) -> None:
        if not self._group:
            self._new_group()
        else:
            self.play_text(self._group)
            self.answerEntry.SetFocus()

    def _check_group(self) -> None:
        if not self._group:
            self._new_group()
            return
        got = self.answerEntry.GetValue()
        right, total = morse.score(self._group, got, self.alphabet())
        pct = round(100 * right / total) if total else 0
        a = self.alphabet()
        spoken = "، ".join(morse.letter_name(c, a) for c in self._group)
        msg = f"{right} من {total} ({pct}٪). المجموعة كانت: {spoken}."
        if pct >= 90:
            lesson = self._lesson()
            if lesson < morse.lesson_count(a):
                lesson += 1
                self.lessonSpin.SetValue(lesson)
                self.set_setting(f"lesson_{a}", lesson)
                new = morse.lesson_letters(a, lesson)[-1]
                msg += f" أحسنت! انتقلت إلى الدرس {lesson} وأُضيف حرف {morse.letter_name(new, a)}."
            else:
                msg += " أتقنت كلّ الحروف!"
        self.show_output(msg)
        self._group = ""

    # -- recognition -----------------------------------------------------
    def _make_letter(self):
        target, opts = morse.multiple_choice(self.alphabet(), self._lesson(), self._rng)
        return _LetterQuestion(self, target, opts)

    # -- keying ----------------------------------------------------------
    def on_raw_key_down(self, evt) -> bool:
        if self.FindFocus() is self.keyer and evt.GetKeyCode() == wx.WXK_SPACE:
            if self._key_down_at is None:
                self._key_down_at = time.monotonic()
                self._decoder.press(self._key_down_at)
                if getattr(self, "_sidetone", None) is None:
                    # one long tone rendered once; key-up cuts it off
                    self._sidetone = morse.render_pcm("-", morse.Timing(1), lead_in=0.0)
                self.play_pcm(self._sidetone)
            return True
        return False

    def _on_key_up(self, evt) -> None:
        if evt.GetKeyCode() == wx.WXK_SPACE and self._key_down_at is not None:
            self.stop_sound()
            self._decoder.release(time.monotonic())
            self._key_down_at = None
            self.keyer.SetValue(self._decoder.text() + "  " + self._decoder.pending)
            return
        evt.Skip()

    def _on_idle(self, evt) -> None:
        if self._key_down_at is None:
            before = self._decoder.text()
            self._decoder.idle(time.monotonic())
            after = self._decoder.text()
            if after != before:
                self.keyer.SetValue(after)
                new = after[len(before):].strip() if after.startswith(before) else after[-1:]
                if new:
                    self.announce(new)

    def _clear_keyer(self) -> None:
        self._decoder.clear()
        self.keyer.SetValue("")
        self.keyer.SetFocus()
        self._say("مُسح الإرسال.")

    def _read_keyer(self) -> None:
        t = self._decoder.text()
        self._say(f"أرسلت: {t}" if t else "لم ترسل شيئًا بعد.")

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.options:
            self.quiz.answer()
            return True
        return False

    def on_closing(self) -> None:
        try:
            self._idle.Stop()
        except Exception:
            pass
        super().on_closing()

    def instructions(self) -> str:
        return ("مدرّب مورس: اختر الحروف والسرعة. للترجمة اكتب نصًّا أو شيفرة ثم Enter. "
                "في الدروس اضغط مجموعة جديدة واكتب ما سمعت؛ عند ٩٠٪ تنتقل للدرس التالي. "
                "وفي لوحة الإرسال اضغط المسافة قصيرة للنقطة وطويلة للشرطة.")
