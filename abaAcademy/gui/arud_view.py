# -*- coding: utf-8 -*-
"""
abaAcademy.gui.arud_view
========================

The prosody lab (مختبر العروض). Type or paste a fully vowelled line of
poetry; the lab writes it prosodically, scans it into / and 0, names the
metre and its feet, and plays the rhythm as short and long tones so the
metre can be *heard*. A second part lists the sixteen metres with their
feet and mnemonic lines, and a listening quiz plays a metre's rhythm for
the learner to name.
"""

from __future__ import annotations

import random

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog, ChoiceQuiz
from ..arabic_lab import arud


class _MetreQuestion:
    def __init__(self, dialog, metre, options):
        self.metre = metre
        self.prompt = "استمع إلى الإيقاع: ما البحر؟"
        self.options = [m.name for m in options]
        self.answer = metre.name
        self.explanation = f"إنه {metre.name}: {metre.feet}."
        self._dialog = dialog

    def play(self):
        self._dialog.play_metre(self.metre)


class ArudDialog(ToolDialog):
    TITLE = "مختبر العروض (تقطيع الشعر ومعرفة البحر)"
    SIZE = (800, 700)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self._rng = random.Random()
        self._last = None
        self.add_text("اكتب البيت أو الشطر مضبوطًا بالشكل كاملًا (الحركات والسكون والشدّة والتنوين). "
                      "افصل بين الشطرين بنجمة * إن كتبت البيت كاملًا.")
        self.verse = self.add_entry("البيت", multiline=True, height=70)
        self.add_buttons([
            ("قطّع واعرف البحر", self._analyse),
            ("استمع إلى الإيقاع", self._play_last),
            ("اقرأ الرموز رمزًا رمزًا", self._spell_pattern),
            ("مثال", self._example),
        ], close=False)
        self.add_output("التحليل", height=150)

        self.metres = self.add_list("البحور الستة عشر (Enter لسماع إيقاع البحر)",
                                    [f"{m.name}: {m.feet}" for m in arud.METRES], height=120,
                                    on_activate=self._metre_info)
        self.quizList = self.add_list("اختبار الأذن: الخيارات", height=90)
        self.quizPrompt = self.add_text("اضغط سؤال جديد لتسمع إيقاع بحر ثم اختر اسمه.")
        self.quiz = ChoiceQuiz(self, self.quizList, self._make_question, prompt_ctrl=self.quizPrompt)
        self.add_buttons([
            ("سؤال جديد", self.quiz.next),
            ("أعد الإيقاع", self.quiz.repeat),
            ("نتيجتي", lambda: self._say(self.quiz.score_text())),
        ])
        self.finish(self.verse)

    # -- analysis --------------------------------------------------------
    def _analyse(self) -> None:
        text = self.verse.GetValue().strip()
        if not text:
            raise ValueError("اكتب بيتًا أولًا.")
        parts = arud.split_hemistichs(text)
        reports = []
        self._last = []
        for i, part in enumerate(parts):
            a = arud.analyse(part)
            self._last.append(a)
            title = ("الشطر الأول" if i == 0 else "الشطر الثاني") if len(parts) == 2 else "السطر"
            reports.append(f"{title}:\n{a.report()}")
        if len(self._last) == 2 and all(a.best for a in self._last):
            if self._last[0].best.metre.key != self._last[1].best.metre.key:
                reports.append("تنبيه: الشطران على بحرين مختلفين؛ راجع ضبط أحدهما.")
        text_out = "\n\n".join(reports)
        best = self._last[0].best
        spoken = (f"البحر {best.metre.name}. التفعيلات: {best.summary}." if best
                  else "لم يطابق أيّ بحر. التفاصيل في مربّع التحليل.")
        self.show_output(text_out, speak=spoken)
        self._play_last()

    def _play_last(self) -> None:
        if not self._last:
            self._analyse()
            return
        events = []
        for a in self._last:
            lengths = [len(f.pattern) for f in a.best.feet] if a.best else None
            events += arud.rhythm_events(a.scansion.pattern, lengths)
            events.append((0.0, 0.0, 0.5))
        if not self.play_tones(events):
            self._say("الصوت غير متاح على هذا الجهاز؛ الرموز مكتوبة في مربّع التحليل.")

    def _spell_pattern(self) -> None:
        if not self._last:
            raise ValueError("قطّع بيتًا أولًا.")
        a = self._last[0]
        if a.best:
            words = []
            for f in a.best.feet:
                syms = " ".join("متحرّك" if c == "1" else "ساكن" for c in f.pattern)
                words.append(f"{f.name}: {syms}")
            self._say(". ".join(words))
        else:
            self._say(" ".join("متحرّك" if c == "1" else "ساكن" for c in a.scansion.pattern))

    def _example(self) -> None:
        samples = ["قِفَا نَبْكِ مِنْ ذِكْرَى حَبِيبٍ وَمَنْزِلِ",
                   "الْخَيْلُ وَاللَّيْلُ وَالْبَيْدَاءُ تَعْرِفُنِي",
                   "هَلْ غَادَرَ الشُّعَرَاءُ مِنْ مُتَرَدَّمِ",
                   "أَلَا لَا يَجْهَلَنْ أَحَدٌ عَلَيْنَا"]
        self.verse.SetValue(self._rng.choice(samples))
        self.verse.SetFocus()
        self._analyse()

    # -- metres ----------------------------------------------------------
    def play_metre(self, metre) -> None:
        form = metre.forms[0]
        lengths = [len(arud.FEET[s[0]]) for s in form.slots]
        events = arud.rhythm_events(metre.canonical_pattern, lengths)
        self.play_tones(events)

    def _metre_info(self) -> None:
        i = self.metres.GetSelection()
        if i < 0:
            return
        m = arud.METRES[i]
        forms = "، ".join(f.label for f in m.forms)
        self.show_output(f"{m.name}\nالتفعيلات: {m.feet}\nالصور: {forms}\n"
                         f"الرموز: {arud.to_display(m.canonical_pattern)}\nالمفتاح: {m.miftah}",
                         speak=f"{m.name}. {m.miftah}")
        self.play_metre(m)

    def _make_question(self):
        correct, options = arud.metre_quiz(self._rng)
        return _MetreQuestion(self, correct, options)

    def on_enter_key(self) -> bool:
        focus = self.FindFocus()
        if focus is self.metres:
            self._metre_info()
            return True
        if focus is self.quizList:
            self.quiz.answer()
            return True
        return False

    def instructions(self) -> str:
        return ("مختبر العروض: اكتب بيتًا مشكولًا ثم قطّع واعرف البحر لتسمع الكتابة العروضية "
                "والرموز والتفعيلات واسم البحر، ويُعزف الإيقاع: نغمة قصيرة للمتحرّك وطويلة للساكن. "
                "قائمة البحور تعرّفك بكل بحر ومفتاحه، واختبار الأذن يعزف إيقاعًا لتعرف بحره.")
