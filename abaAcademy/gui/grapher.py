# -*- coding: utf-8 -*-
"""
abaAcademy.gui.grapher
======================

The accessible auditory graphing calculator screen. The learner types a function
of x, then:

* presses **استمع للمنحنى** (or Ctrl+P) to hear the whole curve as one glide —
  pitch = y, stereo position = x, with earcons at roots and extrema;
* arrows **Left/Right** through sample points to explore the curve point by
  point — each point plays its tone and its coordinates are announced;
* presses **ملخص** (or S) for a spoken overview (range, roots, extrema);
* jumps to the next/previous feature with **Ctrl+Right / Ctrl+Left**.

The whole thing is offline and asset-free (tones are synthesised). If the audio
device is unavailable the coordinate exploration and descriptions still work.
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..math_engine.sonification import FunctionSonifier, TonePlayer
from ..math_engine.latex_arabic import latex_to_arabic


_RANGES = [
    ("من -10 إلى 10", -10.0, 10.0),
    ("من -5 إلى 5", -5.0, 5.0),
    ("من -2π إلى 2π", -6.2832, 6.2832),
    ("من -20 إلى 20", -20.0, 20.0),
    ("من 0 إلى 10", 0.0, 10.0),
]


class GrapherDialog(AccessibleDialog):
    TITLE = "الآلة الحاسبة البيانية الصوتية"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(720, 560))
        self.academy = academy
        self._player = TonePlayer()
        self._son = None
        self._index = 0

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)

        s.Add(wx.StaticText(panel, label="اكتب دالة بدلالة إكس، مثل: x^2 - 4 أو sin(x)/x"),
              0, wx.ALL, 6)
        self.entry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.entry.SetName("الدالة")
        self.entry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._plot())
        s.Add(self.entry, 0, wx.EXPAND | wx.ALL, 6)

        rrow = wx.BoxSizer(wx.HORIZONTAL)
        rrow.Add(wx.StaticText(panel, label="المجال:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.rangeChoice = wx.Choice(panel, choices=[r[0] for r in _RANGES])
        self.rangeChoice.SetSelection(0)
        self.bind_choice(self.rangeChoice, lambda e: self._plot() if self._son else None)
        rrow.Add(self.rangeChoice, 0)
        s.Add(rrow, 0, wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(680)
        s.Add(self.status, 0, wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "ارسم واستمع (Enter)", lambda e: self._plot()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "استمع للمنحنى", lambda e: self._sweep()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "ملخص", lambda e: self._say_summary()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "نطق الدالة", lambda e: self._speak_expr()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.entry)
        self.entry.Bind(wx.EVT_KEY_DOWN, self._on_key)

    # -- plotting ---------------------------------------------------------
    def _plot(self):
        expr = self.entry.GetValue().strip()
        if not expr:
            self._say("اكتب دالة أولاً.")
            return
        label, xmin, xmax = _RANGES[self.choice_index(self.rangeChoice)]
        try:
            self._son = FunctionSonifier(expr, x_min=xmin, x_max=xmax, points=240)
            self._son.analyse()
        except ValueError as exc:
            self._son = None
            self._say(str(exc))
            return
        self._index = 0
        self._say(self._son.summary() + " استخدم الأسهم يمين ويسار للتنقّل، "
                  "والزرّ «استمع للمنحنى» لسماعه كاملاً.")
        self._sweep()

    def _sweep(self):
        if not self._son:
            self._say("ارسم دالة أولاً.")
            return
        if not self._player.available:
            self._say("تعذّر تشغيل الصوت على هذا الجهاز، لكن يمكنك استكشاف النقاط بالأسهم.")
            return
        pcm = self._son.render_sweep(duration=3.0)
        self._player.play(pcm)

    def _say_summary(self):
        if self._son:
            self._say(self._son.summary())
        else:
            self._say("ارسم دالة أولاً.")

    def _speak_expr(self):
        expr = self.entry.GetValue().strip()
        if expr:
            self._say("الدالة: " + latex_to_arabic(expr.replace("*", " في ")))

    # -- cursor exploration ----------------------------------------------
    def _on_key(self, evt):
        if not self._son:
            evt.Skip()
            return
        code = evt.GetKeyCode()
        ctrl = evt.ControlDown()
        if code == wx.WXK_RIGHT and ctrl:
            self._jump_feature(+1)
        elif code == wx.WXK_LEFT and ctrl:
            self._jump_feature(-1)
        elif code == wx.WXK_RIGHT:
            self._move(+1)
        elif code == wx.WXK_LEFT:
            self._move(-1)
        else:
            evt.Skip()

    def _move(self, delta):
        n = len(self._son.samples)
        self._index = max(0, min(n - 1, self._index + delta))
        self._play_point()

    def _jump_feature(self, direction):
        s = self._son.samples
        i = self._index + direction
        while 0 <= i < len(s):
            if s[i].feature in ("zero", "max", "min", "break"):
                self._index = i
                self._play_point()
                return
            i += direction
        self._say("لا مزيد من المعالم في هذا الاتجاه.")

    def _play_point(self):
        if self._player.available:
            self._player.play(self._son.point_tone(self._index))
        self._say(self._son.describe_point(self._index))

    # -- helpers ----------------------------------------------------------
    def _say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    def on_closing(self):
        try:
            self._player.stop()
        except Exception:
            pass

    def instructions(self):
        return ("الآلة الحاسبة البيانية الصوتية: اكتب دالة بدلالة إكس ثم اضغط Enter لتسمع "
                "شكلها صوتياً — طبقة الصوت تمثّل قيمة واي، والموضع بين الأذنين يمثّل موقع "
                "إكس، مع نغمات مميّزة عند التقاطع مع المحور وعند القمم والقيعان. تنقّل بين "
                "النقاط بالسهمين يمين ويسار، واقفز بين المعالم بـ Ctrl مع السهم. زرّ «ملخص» "
                "يعطيك نظرة عامة. Escape للإغلاق.")
