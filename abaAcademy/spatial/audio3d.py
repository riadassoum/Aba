# -*- coding: utf-8 -*-
"""
abaAcademy.spatial.audio3d
==========================

A small spatial-audio engine for the acoustic maze. It renders short sound cues
positioned in a 2D plane around the listener, using two robust, fully-synthesised
cues the ear reads well without any HRTF data files:

* **stereo pan** for left/right (azimuth) — equal-power panning;
* **inter-aural level + a subtle low-pass feel via amplitude** for distance
  (nearer = louder), plus
* **pitch** as an optional elevation/type cue (different landmarks use different
  base tones).

This is deliberately *not* a full HRTF binaural renderer (that needs impulse
data we won't bundle); it is the honest, dependable subset — left/right and
near/far — which is exactly what a learner needs to walk a grid maze by ear.
Everything is generated as raw PCM in pure Python, so there are no sound assets.
"""

from __future__ import annotations

import math
import struct

_SR = 22050


def _tone(freq, dur, amp, pan, sr=_SR, harmonics=(1.0, 0.3, 0.15)):
    """A short panned tone with a few harmonics for a fuller, more locatable
    timbre. pan 0=left .. 1=right (equal-power). Returns stereo 16-bit PCM."""
    n = max(1, int(sr * dur))
    lg = math.cos(pan * math.pi / 2)
    rg = math.sin(pan * math.pi / 2)
    fade = max(1, int(sr * 0.008))
    out = bytearray()
    for i in range(n):
        env = 1.0
        if i < fade:
            env = i / fade
        elif i > n - fade:
            env = max(0.0, (n - i) / fade)
        s = 0.0
        for k, h in enumerate(harmonics, start=1):
            s += h * math.sin(2 * math.pi * freq * k * i / sr)
        s *= amp * env / sum(harmonics)
        out += struct.pack("<hh",
                            int(max(-1, min(1, s * lg)) * 32767),
                            int(max(-1, min(1, s * rg)) * 32767))
    return bytes(out)


class SpatialScene:
    """Places the listener at (lx, ly) facing +y and renders a cue for a source
    at (sx, sy). Azimuth -> stereo pan; distance -> loudness. The maze uses this
    for the goal beacon, walls, and footstep feedback."""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.max_dist = math.hypot(width, height) or 1.0

    def cue(self, listener, source, base_freq=440.0, dur=0.25, kind="beacon"):
        """Return PCM for hearing ``source`` from ``listener``. ``kind`` picks a
        timbre so different objects sound different."""
        lx, ly = listener
        sx, sy = source
        dx = sx - lx
        dy = sy - ly
        dist = math.hypot(dx, dy)
        # azimuth: angle left(-)/right(+). We treat +x as right, +y as forward.
        # pan from the x-offset relative to distance.
        if dist < 1e-6:
            pan = 0.5
        else:
            # x component normalised to -1..1, mapped to 0..1
            pan = 0.5 + 0.5 * max(-1.0, min(1.0, dx / (abs(dx) + abs(dy) + 1e-9)))
        # loudness from distance: near = 1.0, far -> ~0.25
        amp = 0.9 * (1.0 - 0.75 * min(1.0, dist / self.max_dist))
        freq = base_freq
        harm = (1.0, 0.3, 0.15)
        if kind == "wall":
            freq = 180.0
            harm = (1.0, 0.6, 0.4)     # rougher, lower for a wall thud
            dur = 0.12
        elif kind == "goal":
            freq = 660.0
            harm = (1.0, 0.5, 0.25, 0.12)
        elif kind == "step":
            freq = 320.0
            harm = (1.0,)
            dur = 0.06
        return _tone(freq, dur, amp, pan, harmonics=harm)

    def direction_word(self, listener, source):
        """A spoken Arabic bearing to the source — a fallback and a complement to
        the audio, so the maze is playable even with sound off.

        The vertical sense must match the arrow keys: the up arrow moves to a
        SMALLER y, so a source at a smaller y is "أمامك" (ahead) and a larger y
        is "خلفك" (behind). If the goal is two steps ahead, pressing up twice
        gets you there."""
        lx, ly = listener
        dx = source[0] - lx
        dy = source[1] - ly
        parts = []
        if dy < 0:
            parts.append("أمامك")
        elif dy > 0:
            parts.append("خلفك")
        if dx > 0:
            parts.append("يمينك")
        elif dx < 0:
            parts.append("يسارك")
        where = " و".join(parts) if parts else "عندك"
        dist = int(round(math.hypot(dx, dy)))
        return f"الهدف {where}، على بُعد {dist}."
