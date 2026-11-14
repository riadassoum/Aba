# -*- coding: utf-8 -*-
"""
abaAcademy.gui.pomodoro_view
============================

An accessible Pomodoro study timer. The learner picks an interval scheme (25/5 or
50/10), optionally tags the study subject, and starts. The timer counts focus and
break periods, announces transitions in Arabic, and plays a gentle synthesised
earcon at each change (no sound files). Focus time is logged per subject so the
learner can see how much they studied.

The countdown uses a wx.Timer (UI-thread safe, non-blocking) so nothing freezes
the screen reader. All state is simple and the accumulated focus seconds are persisted through
the academy store.
"""

from __future__ import annotations

import time

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..math_engine.sonification import TonePlayer

# scheme -> (focus_minutes, break_minutes)
_SCHEMES = [("٢٥ / ٥", 25, 5), ("٥٠ / ١٠", 50, 10), ("١٥ / ٣ (قصير)", 15, 3)]


def _earcon_focus():
    # rising two-tone: time to focus
    from ..quran_engine.tajweed import _tone
    return _tone(440, 0.12) + _tone(660, 0.16)


def _earcon_break():
    from ..quran_engine.tajweed import _tone
    return _tone(660, 0.12) + _tone(440, 0.16)


class PomodoroDialog(AccessibleDialog):
    TITLE = "مؤقّت الدراسة (بومودورو)"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(680, 480))
        self.academy = academy
        self._player = TonePlayer()
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_tick, self._timer)
        self._remaining = 0
        self._phase = "idle"       # idle | focus | break
        self._focus_seconds = 0
        self._scheme = _SCHEMES[0]

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "اختر نظام التركيز والراحة، وسمِّ مادّة الدراسة إن أردت، ثم ابدأ. "
            "سيُعلن المؤقّت بدء كل فترة تركيز وراحة.")), 0, wx.ALL, 6)

        srow = wx.BoxSizer(wx.HORIZONTAL)
        srow.Add(wx.StaticText(panel, label="النظام:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.schemeChoice = wx.Choice(panel, choices=[n for n, _, _ in _SCHEMES])
        self.schemeChoice.SetSelection(0)
        self.bind_choice(self.schemeChoice, lambda e: None)
        srow.Add(self.schemeChoice, 0, wx.RIGHT, 12)
        srow.Add(wx.StaticText(panel, label="المادّة:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.subjectEntry = wx.TextCtrl(panel)
        self.subjectEntry.SetName("مادّة الدراسة")
        srow.Add(self.subjectEntry, 1)
        s.Add(srow, 0, wx.EXPAND | wx.ALL, 6)

        self.clock = wx.StaticText(panel, label="جاهز للبدء")
        font = self.clock.GetFont()
        font.SetPointSize(font.GetPointSize() + 6)
        self.clock.SetFont(font)
        s.Add(self.clock, 0, wx.ALL, 12)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(640)
        s.Add(self.status, 0, wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        self.startBtn = self.button(panel, "ابدأ", lambda e: self._start())
        row.Add(self.startBtn, 0, wx.ALL, 3)
        self.pauseBtn = self.button(panel, "إيقاف مؤقّت", lambda e: self._toggle_pause())
        self.pauseBtn.Disable()
        row.Add(self.pauseBtn, 0, wx.ALL, 3)
        self.stopBtn = self.button(panel, "أنهِ", lambda e: self._stop())
        self.stopBtn.Disable()
        row.Add(self.stopBtn, 0, wx.ALL, 3)
        row.Add(self.button(panel, "كم درست اليوم؟", lambda e: self._say_today()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.schemeChoice)

    # -- control ----------------------------------------------------------
    def _start(self):
        self._scheme = _SCHEMES[self.choice_index(self.schemeChoice)]
        self._begin_phase("focus")
        self.startBtn.Disable()
        self.pauseBtn.Enable()
        self.stopBtn.Enable()

    def _begin_phase(self, phase):
        self._phase = phase
        minutes = self._scheme[1] if phase == "focus" else self._scheme[2]
        self._remaining = minutes * 60
        self._update_clock()
        if phase == "focus":
            if self._player.available:
                self._player.play(_earcon_focus())
            self._say(f"ابدأ التركيز لمدة {minutes} دقيقة. بالتوفيق!")
        else:
            if self._player.available:
                self._player.play(_earcon_break())
            self._say(f"استراحة لمدة {minutes} دقيقة. أرح عينيك وذهنك.")
        self._timer.Start(1000)

    def _on_tick(self, evt):
        self._remaining -= 1
        if self._phase == "focus":
            self._focus_seconds += 1
        if self._remaining <= 0:
            self._timer.Stop()
            if self._phase == "focus":
                self._begin_phase("break")
            else:
                self._begin_phase("focus")
            return
        self._update_clock()
        # gentle spoken cue at each minute boundary and final 5 seconds
        if self._remaining % 60 == 0:
            mins = self._remaining // 60
            self.announce(f"بقي {mins} دقيقة.")
        elif self._remaining <= 5:
            self.announce(str(self._remaining))

    def _update_clock(self):
        m, s = divmod(max(0, self._remaining), 60)
        phase_ar = {"focus": "تركيز", "break": "راحة", "idle": "جاهز"}[self._phase]
        self.clock.SetLabel(f"{phase_ar} — {m:02d}:{s:02d}")

    def _toggle_pause(self):
        if self._timer.IsRunning():
            self._timer.Stop()
            self.pauseBtn.SetLabel("تابع")
            self._say("أُوقف المؤقّت مؤقّتاً.")
        else:
            self._timer.Start(1000)
            self.pauseBtn.SetLabel("إيقاف مؤقّت")
            self._say("تابع.")

    def _stop(self):
        self._timer.Stop()
        self._save_focus()
        self._phase = "idle"
        self._update_clock()
        self.startBtn.Enable()
        self.pauseBtn.Disable()
        self.stopBtn.Disable()
        mins = self._focus_seconds // 60
        self._say(f"انتهت الجلسة. ركّزت {mins} دقيقة. أحسنت!")

    def _save_focus(self):
        if self._focus_seconds <= 0:
            return
        subject = (self.subjectEntry.GetValue().strip() or "عام")
        try:
            key = f"pomodoro_{time.strftime('%Y-%m-%d')}"
            prev = self.academy.store.get_setting(key, "0")
            total = int(prev) + self._focus_seconds
            self.academy.store.set_setting(key, str(total))
            sk = f"pomodoro_subj_{subject}"
            psub = self.academy.store.get_setting(sk, "0")
            self.academy.store.set_setting(sk, str(int(psub) + self._focus_seconds))
        except Exception:
            pass
        # credit the study planner's soonest task of the same subject
        mins = self._focus_seconds // 60
        if mins and subject != "عام":
            try:
                from ..study_hub.planner import Planner
                item = Planner(self.academy.store).log_subject(subject, mins)
                if item is not None:
                    self.announce(f"أُضيفت {mins} دقيقة إلى {item.title} في مخطّط المذاكرة.")
            except Exception:
                pass
        self._focus_seconds = 0

    def _say_today(self):
        try:
            key = f"pomodoro_{time.strftime('%Y-%m-%d')}"
            secs = int(self.academy.store.get_setting(key, "0")) + self._focus_seconds
        except Exception:
            secs = self._focus_seconds
        mins = secs // 60
        self._say(f"ركّزت اليوم {mins} دقيقة حتى الآن.")

    def on_closing(self):
        self._timer.Stop()
        self._save_focus()
        try:
            self._player.stop()
        except Exception:
            pass

    def _say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    def instructions(self):
        return ("مؤقّت الدراسة بطريقة بومودورو: اختر نظام التركيز والراحة (مثل ٢٥ دقيقة "
                "تركيز و٥ راحة)، سمِّ المادّة، ثم ابدأ. يعلن المؤقّت بداية كل فترة وينبّهك "
                "في الدقائق الأخيرة. إيقاف مؤقّت يوقف ويتابع، وأنهِ يُنهي ويحفظ زمن "
                "تركيزك. كم درست اليوم؟ يخبرك بمجموع دقائق تركيزك. Escape للإغلاق.")
