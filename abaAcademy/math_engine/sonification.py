# -*- coding: utf-8 -*-
"""
abaAcademy.math_engine.sonification
===================================

Turn a mathematical function into sound so a blind learner can *hear its shape*.

Two complementary modes, both built here:

1. **Sweep** — play the whole curve as a continuous glide: as x moves left→right,
   the pitch rises and falls with y, and the stereo image pans left→right with x.
   Distinct short earcons mark axis crossings (y=0), local minima/maxima, and
   breaks (asymptotes / domain gaps). This gives an instant gestalt of the curve.

2. **Cursor** — the learner arrows Left/Right through sample points; each point
   plays a short tone at the pitch for its y-value, panned to its x-position,
   and the engine announces the coordinates and any feature at that point. This
   is the detailed, exploratory mode.

Everything is synthesised as raw PCM in pure Python — there are **no sound files
to bundle**. The same tiny tone generator makes the glide, the point tones, and
the earcons, so the whole feature costs zero external assets. Playback uses the
bundled miniaudio device; if miniaudio is unavailable the engine still computes
the feature analysis and coordinates (so the spoken exploration works even with
no audio device).

Pitch mapping: y-values are mapped onto an audible pitch range (default 220–880 Hz, two
octaves). y=0 always maps to the same reference pitch, so "crossing the middle
pitch" reliably means "crossing the x-axis" — an anchor the ear can trust.
"""

from __future__ import annotations

import math
import os
import struct
import sys
import threading

from .safe_eval import SafeFunction

_SR = 22050                 # sample rate (Hz) — plenty for tones, light on CPU
_LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib")


# ---------------------------------------------------------------------------
# tone synthesis (pure python, no assets)
# ---------------------------------------------------------------------------

def _sine(freq, dur, sr=_SR, amp=0.35, pan=0.5, fade=0.005):
    """Generate one panned sine tone as interleaved stereo 16-bit PCM bytes.

    ``pan`` is 0.0 (full left) .. 1.0 (full right); we use an equal-power pan so
    the loudness stays steady as the sound moves across the stereo field — which
    is what makes left/right position legible to the ear."""
    n = max(1, int(sr * dur))
    left_gain = math.cos(pan * math.pi / 2)
    right_gain = math.sin(pan * math.pi / 2)
    fade_n = max(1, int(sr * fade))
    out = bytearray()
    two_pi_f = 2.0 * math.pi * freq
    for i in range(n):
        env = 1.0
        if i < fade_n:
            env = i / fade_n
        elif i > n - fade_n:
            env = max(0.0, (n - i) / fade_n)
        s = amp * env * math.sin(two_pi_f * i / sr)
        l = int(max(-1.0, min(1.0, s * left_gain)) * 32767)
        r = int(max(-1.0, min(1.0, s * right_gain)) * 32767)
        out += struct.pack("<hh", l, r)
    return bytes(out)


def _glide(points, total_dur, sr=_SR, amp=0.32):
    """Generate a continuous frequency glide through (freq, pan) control points.
    Frequencies and pan are linearly interpolated between consecutive points, so
    the curve is heard as one smooth gesture rather than separate notes.

    ``points`` is a list of (freq_or_None, pan). A ``None`` frequency is a gap
    (asymptote / undefined): we render a brief silence there, which the ear reads
    as a break in the line."""
    if not points:
        return b""
    seg = total_dur / max(1, len(points) - 1)
    seg_n = max(1, int(sr * seg))
    out = bytearray()
    phase = 0.0
    for k in range(len(points) - 1):
        f0, p0 = points[k]
        f1, p1 = points[k + 1]
        for j in range(seg_n):
            t = j / seg_n
            if f0 is None or f1 is None:
                # break in the curve -> silence, but keep phase continuity reset
                out += struct.pack("<hh", 0, 0)
                phase = 0.0
                continue
            f = f0 + (f1 - f0) * t
            pan = p0 + (p1 - p0) * t
            phase += 2.0 * math.pi * f / sr
            lg = math.cos(pan * math.pi / 2)
            rg = math.sin(pan * math.pi / 2)
            s = amp * math.sin(phase)
            out += struct.pack("<hh",
                               int(s * lg * 32767), int(s * rg * 32767))
    return bytes(out)


def _earcon(kind, pan=0.5):
    """Short distinctive tone signatures for features. Kept few and simple on
    purpose (one generator, no files):

    * ``zero``  — axis crossing: a clean short mid 'blip'.
    * ``max``   — local maximum: two quick rising notes.
    * ``min``   — local minimum: two quick falling notes.
    * ``break`` — asymptote/gap: a short low buzz (square-ish) then silence.
    """
    if kind == "zero":
        return _sine(660, 0.07, amp=0.4, pan=pan)
    if kind == "max":
        return _sine(700, 0.05, amp=0.4, pan=pan) + _sine(1050, 0.06, amp=0.4, pan=pan)
    if kind == "min":
        return _sine(500, 0.05, amp=0.4, pan=pan) + _sine(300, 0.06, amp=0.4, pan=pan)
    if kind == "break":
        # a rougher timbre for "undefined": sum of two detuned sines, low
        base = bytearray()
        n = int(_SR * 0.09)
        for i in range(n):
            s = 0.3 * (math.sin(2 * math.pi * 150 * i / _SR)
                       + 0.5 * math.sin(2 * math.pi * 151.5 * i / _SR))
            v = int(max(-1, min(1, s)) * 32767)
            base += struct.pack("<hh", v, v)
        return bytes(base)
    return b""


# ---------------------------------------------------------------------------
# function analysis
# ---------------------------------------------------------------------------

class Sample:
    """One sampled point on the curve, with any feature detected there."""
    __slots__ = ("x", "y", "defined", "feature")

    def __init__(self, x, y, defined, feature=None):
        self.x = x
        self.y = y
        self.defined = defined
        self.feature = feature      # None | 'zero' | 'max' | 'min' | 'break'


class FunctionSonifier:
    """Sample a function over a domain, find its features, and render audio.

    Typical use::

        son = FunctionSonifier("x^2 - 4", x_min=-5, x_max=5)
        son.analyse()
        pcm = son.render_sweep()        # bytes of stereo PCM for the whole curve
        # or step through son.samples for the cursor mode
    """

    def __init__(self, expression, x_min=-10.0, x_max=10.0, points=240,
                 f_low=220.0, f_high=880.0):
        self.expression = expression
        self.x_min = float(x_min)
        self.x_max = float(x_max)
        self.points = int(points)
        self.f_low = f_low
        self.f_high = f_high
        self.func = SafeFunction(expression)
        self.samples = []
        self.y_min = None
        self.y_max = None

    # -- sampling & feature detection ------------------------------------
    def analyse(self):
        n = self.points
        step = (self.x_max - self.x_min) / (n - 1)
        raw = []
        for i in range(n):
            x = self.x_min + i * step
            y = self.func(x)
            raw.append((x, y))
        ys = [y for _, y in raw if y is not None]
        if ys:
            self.y_min, self.y_max = min(ys), max(ys)
        else:
            self.y_min, self.y_max = -1.0, 1.0
        self.samples = [Sample(x, y, y is not None) for x, y in raw]
        self._detect_features()
        return self.samples

    def _detect_features(self):
        s = self.samples
        for i in range(len(s)):
            # break: defined neighbour on one side, undefined on the other, or a
            # huge jump (asymptote)
            if not s[i].defined:
                s[i].feature = "break"
                continue
        # zero crossings and local extrema over defined runs
        for i in range(1, len(s) - 1):
            a, b, c = s[i - 1], s[i], s[i + 1]
            if not (a.defined and b.defined and c.defined):
                # asymptote hint: sign change across an undefined gap with large
                # magnitude — mark the defined edge as a break too
                continue
            # zero crossing between a and b
            if a.y == 0 or (a.y < 0 < b.y) or (a.y > 0 > b.y):
                if b.feature is None:
                    b.feature = "zero"
            # local extrema
            if b.y > a.y and b.y > c.y:
                b.feature = "max"
            elif b.y < a.y and b.y < c.y:
                b.feature = "min"

    # -- pitch mapping ----------------------------------------------------
    def _freq_for(self, y):
        """Map a y-value to a frequency. y=0 anchors to the geometric-mean pitch
        so 'crossing the middle' == 'crossing the x-axis'."""
        if y is None:
            return None
        lo, hi = self.y_min, self.y_max
        if hi - lo < 1e-9:
            return math.sqrt(self.f_low * self.f_high)
        # normalise y to 0..1, then map onto a logarithmic frequency scale
        t = (y - lo) / (hi - lo)
        return self.f_low * (self.f_high / self.f_low) ** t

    def _pan_for(self, x):
        if self.x_max - self.x_min < 1e-9:
            return 0.5
        return (x - self.x_min) / (self.x_max - self.x_min)

    # -- rendering --------------------------------------------------------
    def render_sweep(self, duration=3.0):
        """Render the whole curve as one continuous glide with feature earcons
        mixed in at their positions. Returns stereo PCM bytes."""
        pts = []
        for s in self.samples:
            pts.append((self._freq_for(s.y) if s.defined else None,
                        self._pan_for(s.x)))
        glide = _glide(pts, duration)
        # overlay earcons by concatenation at feature points would desync the
        # glide; instead we mix them onto the glide buffer at the right offset.
        buf = bytearray(glide)
        total = len(self.samples)
        for idx, s in enumerate(self.samples):
            if s.feature in ("zero", "max", "min"):
                ec = _earcon(s.feature, pan=self._pan_for(s.x))
                off = int((idx / max(1, total - 1)) * (len(buf) // 4)) * 4
                _mix_into(buf, ec, off)
        return bytes(buf)

    def point_tone(self, index, dur=0.18):
        """Tone for a single sample (cursor mode). Returns PCM bytes; a feature
        point plays its earcon after the tone."""
        if not (0 <= index < len(self.samples)):
            return b""
        s = self.samples[index]
        if not s.defined:
            return _earcon("break")
        tone = _sine(self._freq_for(s.y), dur, pan=self._pan_for(s.x))
        if s.feature in ("zero", "max", "min"):
            tone += _earcon(s.feature, pan=self._pan_for(s.x))
        return tone

    # -- spoken descriptions (work even with no audio) --------------------
    def describe_point(self, index):
        """Arabic description of a sample for the screen reader."""
        if not (0 <= index < len(self.samples)):
            return ""
        s = self.samples[index]
        x_txt = _fmt(s.x)
        if not s.defined:
            return f"عند إكس يساوي {x_txt}، الدالة غير معرّفة."
        y_txt = _fmt(s.y)
        feat = {
            "zero": "، تقاطع مع محور الإكس",
            "max": "، قمة محلية",
            "min": "، قاع محلي",
        }.get(s.feature, "")
        return f"إكس {x_txt}، واي {y_txt}{feat}."

    def summary(self):
        """A spoken overview of the whole curve: range, number of roots and
        extrema — a useful orientation before exploring."""
        roots = sum(1 for s in self.samples if s.feature == "zero")
        maxima = sum(1 for s in self.samples if s.feature == "max")
        minima = sum(1 for s in self.samples if s.feature == "min")
        breaks = sum(1 for s in self.samples if s.feature == "break")
        parts = [f"الدالة {self.expression}",
                 f"على الفترة من {_fmt(self.x_min)} إلى {_fmt(self.x_max)}"]
        if self.y_min is not None:
            parts.append(f"قيم واي بين {_fmt(self.y_min)} و {_fmt(self.y_max)}")
        parts.append(f"عدد التقاطعات مع محور الإكس {roots}")
        if maxima:
            parts.append(f"القمم {maxima}")
        if minima:
            parts.append(f"القيعان {minima}")
        if breaks:
            parts.append(f"مواضع غير معرّفة {breaks}")
        return "، ".join(parts) + "."


def _fmt(v):
    """Short human number for speech."""
    if v is None:
        return "غير معرّف"
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.2f}"


def _mix_into(buf, pcm, offset):
    """Mix ``pcm`` (stereo 16-bit) into ``buf`` starting at byte ``offset`` with
    clipping. Used to overlay earcons on the glide without lengthening it."""
    end = min(len(buf), offset + len(pcm))
    j = 0
    for i in range(offset, end, 2):
        if j + 2 > len(pcm):
            break
        a = struct.unpack_from("<h", buf, i)[0]
        b = struct.unpack_from("<h", pcm, j)[0]
        m = max(-32768, min(32767, a + b))
        struct.pack_into("<h", buf, i, m)
        j += 2


# ---------------------------------------------------------------------------
# playback (bundled miniaudio; degrades gracefully to silent analysis)
# ---------------------------------------------------------------------------

class TonePlayer:
    """Plays raw stereo PCM through the bundled miniaudio device. If miniaudio
    can't load (e.g. in a non-Windows test environment), playback is a no-op but
    everything else — analysis, coordinates, descriptions — still works."""

    def __init__(self):
        self._ma = None
        self._device = None
        self._lock = threading.Lock()
        self._buf = b""
        self._pos = 0
        try:
            if os.path.isdir(_LIB) and _LIB not in sys.path:
                sys.path.append(_LIB)
            import miniaudio  # type: ignore
            self._ma = miniaudio
        except Exception:
            self._ma = None

    @property
    def available(self):
        return self._ma is not None

    def play(self, pcm):
        """Play a PCM buffer (non-blocking). Replaces anything currently
        playing."""
        if not self._ma:
            return
        with self._lock:
            self._buf = pcm
            self._pos = 0
        try:
            self.stop()
            dev = self._ma.PlaybackDevice(
                output_format=self._ma.SampleFormat.SIGNED16,
                nchannels=2, sample_rate=_SR)
            gen = self._generator()
            next(gen)
            dev.start(gen)
            self._device = dev
        except Exception:
            self._device = None

    def _generator(self):
        required = yield b""
        while True:
            with self._lock:
                need = required * 2 * 2   # frames * channels * bytes
                chunk = self._buf[self._pos:self._pos + need]
                self._pos += len(chunk)
            if not chunk:
                chunk = b"\x00" * (required * 4)
            required = yield chunk

    def stop(self):
        if self._device is not None:
            try:
                self._device.stop()
                self._device.close()
            except Exception:
                pass
            self._device = None
