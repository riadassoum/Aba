# -*- coding: utf-8 -*-
"""
abaAcademy.gui.keyboard_trainer
==============================

The typing speed & accuracy trainer for the computer curriculum. the screen reader announces
a target (letter / word / sentence) via the focused prompt, the learner types
it, and on Enter we score words-per-minute and character accuracy, tracking the
best result per tier in settings. This is the "the screen reader asks the student to type
words/sentences quickly, with speed and accuracy challenges" feature.

Timing starts on the first keystroke and stops on submit. Accuracy uses a
character-level ratio. All prompts and results are spoken with cancel-before-
speak, and the target is on the input's accessible name so focusing it re-reads
what to type.
"""

from __future__ import annotations

import difflib
import random
import time

import wx

from .accessible import AccessibleDialog

import os


def _load_bank(filename, split_lines=False):
    """Load a bundled typing bank (one item per line, or whitespace-split
    words). Returns [] if the resource is missing so callers can fall back."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "..", "resources", filename)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        if split_lines:
            return [ln.strip() for ln in text.splitlines() if ln.strip()]
        return [w for w in text.split() if w.strip()]
    except OSError:
        return []


# Large authentic banks (thousands of words + real sentences), loaded from the
# bundled resources/ folder. Arabic is the primary track; English and sentences
# come alongside. Falls back to a tiny inline set only if the files are missing.
_AR_WORDS = _load_bank("typing_ar.txt") or ["قلم", "كتاب", "شمس", "قمر", "بيت", "مدرسة"]
_EN_WORDS = _load_bank("typing_en.txt") or ["file", "keyboard", "internet", "screen"]
_AR_SENTENCES = _load_bank("typing_sentences_ar.txt", split_lines=True) or [
    "الممارسة اليومية تزيد السرعة والدقة."]
_EN_SENTENCES = _load_bank("typing_sentences_en.txt", split_lines=True) or [
    "Practice makes perfect every single day."]
_AR_QURAN = _load_bank("typing_ar_quran.txt")
_AR_LITERARY = _load_bank("typing_ar_literary.txt")
_AR_SCIENCE = _load_bank("typing_ar_science.txt")
_FR_WORDS = _load_bank("typing_fr.txt")
_FR_SENTENCES = _load_bank("typing_sentences_fr.txt", split_lines=True)

TIERS = {
    "letters": ("الحروف العربية", list("ابتثجحخدذرزسشصضطظعغفقكلمنهوي")),
    "letters_en": ("الحروف الإنجليزية", list("abcdefghijklmnopqrstuvwxyz")),
    "words": ("الكلمات العربية", _AR_WORDS),
    "sentences": ("الجمل العربية", _AR_SENTENCES),
    "english": ("الكلمات الإنجليزية", _EN_WORDS),
    "english_sentences": ("الجمل الإنجليزية", _EN_SENTENCES),
    "french": ("الكلمات الفرنسية", _FR_WORDS),
}
# themed Arabic sub-banks only appear if their files loaded (kept optional)
if _AR_QURAN:
    TIERS["quran"] = ("كلمات قرآنية", _AR_QURAN)
if _AR_LITERARY:
    TIERS["literary"] = ("كلمات أدبية وبلاغية", _AR_LITERARY)
if _AR_SCIENCE:
    TIERS["science"] = ("مصطلحات علمية", _AR_SCIENCE)
if _FR_SENTENCES:
    TIERS["french_sentences"] = ("الجمل الفرنسية", _FR_SENTENCES)


def score(target: str, typed: str, elapsed: float):
    elapsed = max(elapsed, 0.3)
    accuracy = difflib.SequenceMatcher(None, target, typed).ratio() * 100.0
    cpm = (len(target) / elapsed) * 60.0
    wpm = cpm / 5.0
    return round(wpm, 1), round(accuracy, 1), typed.strip() == target.strip()


class KeyboardTrainer(AccessibleDialog):
    def __init__(self, parent, academy, tier_key, speech):
        title_ar, items = TIERS.get(tier_key, TIERS["words"])
        super().__init__(parent, f"تحدي الكتابة: {title_ar}", speech, size=(680, 400))
        self.academy = academy
        self.tier_key = tier_key
        self._items = items
        self._target = ""
        self._start = None

        panel = wx.Panel(self)
        self.panel = panel
        sizer = wx.BoxSizer(wx.VERTICAL)

        best_wpm = academy.store.get_setting(f"typing_wpm_{tier_key}", "0")
        best_acc = academy.store.get_setting(f"typing_acc_{tier_key}", "0")
        self.bestLabel = wx.StaticText(
            panel, label=f"أفضل نتيجة: {best_wpm} كلمة/دقيقة، دقة {best_acc} بالمئة")
        sizer.Add(self.bestLabel, 0, wx.ALL, 8)

        self.targetCtrl = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_RICH2)
        self.targetCtrl.SetName("النص المطلوب كتابته")
        sizer.Add(self.targetCtrl, 0, wx.EXPAND | wx.ALL, 8)

        self.inputCtrl = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.inputCtrl.SetName("اكتب هنا")
        self.inputCtrl.Bind(wx.EVT_TEXT, self._on_type)
        self.inputCtrl.Bind(wx.EVT_TEXT_ENTER, self._on_submit)
        self._last_replay_t = 0.0
        sizer.Add(self.inputCtrl, 0, wx.EXPAND | wx.ALL, 8)

        btns = wx.BoxSizer(wx.HORIZONTAL)
        submitBtn = self.button(panel, "إنهاء وتحقق", self._on_submit)
        submitBtn.SetDefault()
        nextBtn = self.button(panel, "تحدٍّ جديد", lambda e: self._new())
        timedBtn = self.button(panel, "اختبار سرعة مؤقّت...", lambda e: self._open_timed())
        btns.Add(submitBtn, 0, wx.ALL, 6)
        btns.Add(nextBtn, 0, wx.ALL, 6)
        btns.Add(timedBtn, 0, wx.ALL, 6)
        closeBtn = self.button(panel, "إغلاق", lambda e: self.close_screen())
        btns.Add(closeBtn, 0, wx.ALL, 6)
        sizer.Add(btns, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(sizer)
        self.set_first_control(self.inputCtrl)
        self._new()

    def instructions(self) -> str:
        return ("سيُعرض نص، اكتبه بأسرع وأدق ما يمكن ثم اضغط إنتر. "
                "أو اختر اختبار سرعة مؤقّت لتحديد مدة (دقيقة أو أكثر) والكتابة المتواصلة.")

    def _new(self):
        self._target = random.choice(self._items)
        self.targetCtrl.SetValue(self._target)
        self.inputCtrl.SetValue("")
        self.inputCtrl.SetName("اكتب: " + self._target)
        self._start = None
        self.call_after(self.inputCtrl.SetFocus)
        self.announce("اكتب: " + self._target)

    def on_repeat(self):
        # Ctrl+R: hear the current word again; press twice quickly to spell it.
        import time as _t
        now = _t.time()
        if self._target and now - getattr(self, "_last_replay_t", 0.0) < 1.5:
            self.announce("تهجئة: " + "، ".join(list(self._target)))
        elif self._target:
            self.announce(self._target)
        self._last_replay_t = now

    def _on_type(self, evt):
        if self._start is None and self.inputCtrl.GetValue():
            self._start = time.time()
        evt.Skip()

    def _on_submit(self, evt):
        if self._start is None:
            self.announce("اكتب النص أولاً")
            return
        elapsed = time.time() - self._start
        wpm, acc, exact = score(self._target, self.inputCtrl.GetValue(), elapsed)
        prev_wpm = float(self.academy.store.get_setting(f"typing_wpm_{self.tier_key}", "0") or 0)
        prev_acc = float(self.academy.store.get_setting(f"typing_acc_{self.tier_key}", "0") or 0)
        if wpm > prev_wpm:
            self.academy.store.set_setting(f"typing_wpm_{self.tier_key}", str(wpm))
        if acc > prev_acc:
            self.academy.store.set_setting(f"typing_acc_{self.tier_key}", str(acc))
        best_wpm = max(wpm, prev_wpm)
        best_acc = max(acc, prev_acc)
        self.bestLabel.SetLabel(f"أفضل نتيجة: {best_wpm} كلمة/دقيقة، دقة {best_acc} بالمئة")
        msg = (f"السرعة {wpm} كلمة في الدقيقة، والدقة {acc} بالمئة. "
               + ("مطابقة تامة، أحسنت!" if exact else "هناك اختلاف عن النص، انتبه للدقة."))
        self.announce(msg)
        wx.MessageBox(msg, "نتيجة التحدي", wx.OK | wx.ICON_INFORMATION)
        self._new()

    def _open_timed(self):
        # let the learner choose the duration
        options = ["نصف دقيقة (30 ثانية)", "دقيقة واحدة", "دقيقتان", "ثلاث دقائق", "خمس دقائق"]
        seconds = [30, 60, 120, 180, 300]
        dlg = wx.SingleChoiceDialog(self, "اختر مدة اختبار السرعة:", "مدة الاختبار", options)
        if dlg.ShowModal() == wx.ID_OK:
            dur = seconds[dlg.GetSelection()]
            dlg.Destroy()
            self.show_child(TimedTypingRunner(
                self, self.academy, self.tier_key, self._items, dur, self.speech))
        else:
            dlg.Destroy()


class TimedTypingRunner(AccessibleDialog):
    """Continuous timed speed test. For a learner-chosen duration, it shows one
    item at a time; each time the learner types it correctly and presses Enter,
    it immediately shows the next item and counts it. When the timer runs out it
    reports how many items were completed, plus words-per-minute and accuracy
    over the whole run. This is the "give me letters/words, advance on each
    correct one, time me for a minute or two" test."""

    def __init__(self, parent, academy, tier_key, items, duration_seconds, speech):
        title_ar, _ = TIERS.get(tier_key, ("", items))
        super().__init__(parent, f"اختبار السرعة المؤقّت: {title_ar}", speech, size=(680, 420))
        self.academy = academy
        self.tier_key = tier_key
        self._items = items
        self._duration = duration_seconds
        self._target = ""
        self._started = False
        self._start_time = None
        self._completed = 0
        self._correct_chars = 0
        self._total_target_chars = 0
        self._deadline = None
        self._finished = False
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_tick, self._timer)

        panel = wx.Panel(self)
        self.panel = panel
        sizer = wx.BoxSizer(wx.VERTICAL)

        mins = duration_seconds // 60
        secs = duration_seconds % 60
        dur_text = (f"{mins} دقيقة" if mins and not secs else
                    f"{secs} ثانية" if not mins else f"{mins} دقيقة و{secs} ثانية")
        self.statusLabel = wx.StaticText(
            panel, label=f"المدة: {dur_text}. ابدأ الكتابة لبدء العدّ. المكتمل: 0")
        sizer.Add(self.statusLabel, 0, wx.ALL, 8)

        self.targetCtrl = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_RICH2)
        self.targetCtrl.SetName("النص المطلوب")
        sizer.Add(self.targetCtrl, 0, wx.EXPAND | wx.ALL, 8)

        self.inputCtrl = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.inputCtrl.SetName("اكتب هنا")
        self.inputCtrl.Bind(wx.EVT_TEXT, self._on_type)
        self.inputCtrl.Bind(wx.EVT_TEXT_ENTER, self._on_enter)
        self._last_replay_t = 0.0
        sizer.Add(self.inputCtrl, 0, wx.EXPAND | wx.ALL, 8)

        btns = wx.BoxSizer(wx.HORIZONTAL)
        stopBtn = self.button(panel, "إيقاف الآن", lambda e: self._finish())
        btns.Add(stopBtn, 0, wx.ALL, 6)
        closeBtn = self.button(panel, "إغلاق", lambda e: self._abort())
        btns.Add(closeBtn, 0, wx.ALL, 6)
        sizer.Add(btns, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(sizer)
        self.set_first_control(self.inputCtrl)
        self._next_item()

    def instructions(self) -> str:
        return ("اكتب كل نص يظهر ثم اضغط إنتر. عند كل إجابة صحيحة يظهر نص جديد فوراً "
                "ويُحسب لك. يبدأ الوقت مع أول حرف تكتبه. اضغط Ctrl+R لسماع الكلمة "
                "مرة أخرى، ومرتين متتاليتين لتهجئتها حرفاً حرفاً.")

    def _next_item(self):
        self._target = random.choice(self._items)
        self.targetCtrl.SetValue(self._target)
        self.inputCtrl.SetValue("")
        self.inputCtrl.SetName("اكتب: " + self._target)
        self.announce(self._target)

    def on_repeat(self):
        # Ctrl+R: hear the current word again; press twice quickly to spell it.
        now = time.time()
        if self._target and now - self._last_replay_t < 1.5:
            self.announce("تهجئة: " + "، ".join(list(self._target)))
        elif self._target:
            self.announce(self._target)
        self._last_replay_t = now

    def _on_type(self, evt):
        if not self._started and self.inputCtrl.GetValue():
            self._started = True
            self._start_time = time.time()
            self._deadline = self._start_time + self._duration
            self._timer.Start(500)
        evt.Skip()

    def _on_enter(self, evt):
        typed = self.inputCtrl.GetValue().strip()
        if not typed:
            return
        self._total_target_chars += len(self._target)
        # count matching characters for accuracy
        matched = sum(1 for a, b in zip(typed, self._target) if a == b)
        self._correct_chars += matched
        if typed == self._target.strip():
            self._completed += 1
            self.statusLabel.SetLabel(
                f"المكتمل: {self._completed} | الوقت المتبقّي: {self._remaining()} ثانية")
            self._next_item()
        else:
            # wrong: keep same target, let them retry, brief feedback
            self.announce("غير مطابق، حاول مرة أخرى")
            self.inputCtrl.SetValue("")

    def _remaining(self):
        if not self._deadline:
            return self._duration
        return max(0, int(round(self._deadline - time.time())))

    def _on_tick(self, evt):
        rem = self._remaining()
        if rem <= 0:
            self._finish()
        elif rem in (10, 5, 3):
            self.announce(f"باقٍ {rem} ثوانٍ")

    def on_closing(self):
        # A running wx.Timer on a destroyed window is a hard crash. Every close
        # path (Escape, Alt+F4, the X, the buttons) funnels through here, so the
        # timer can never outlive the dialog.
        try:
            if self._timer.IsRunning():
                self._timer.Stop()
        except Exception:
            pass

    def _abort(self):
        self.close_screen(force=True)

    def _finish(self):
        if self._finished:
            return
        self._finished = True
        self.on_closing()
        elapsed = (time.time() - self._start_time) if self._start_time else self._duration
        elapsed = max(elapsed, 1.0)
        # WPM over the whole run using the 5-chars-per-word convention on the
        # characters the learner typed correctly.
        wpm = round((self._correct_chars / 5.0) / (elapsed / 60.0), 1)
        accuracy = round((self._correct_chars / self._total_target_chars * 100.0)
                         if self._total_target_chars else 0.0, 1)
        # persist bests (timed bests stored under a separate key)
        prev = float(self.academy.store.get_setting(f"timed_wpm_{self.tier_key}", "0") or 0)
        if wpm > prev:
            self.academy.store.set_setting(f"timed_wpm_{self.tier_key}", str(wpm))
        msg = (f"انتهى الوقت! أكملت {self._completed} عنصراً. "
               f"السرعة {wpm} كلمة في الدقيقة، والدقة {accuracy} بالمئة.")
        self.announce(msg)
        wx.MessageBox(msg, "نتيجة اختبار السرعة", wx.OK | wx.ICON_INFORMATION)
        self.close_screen(force=True)
