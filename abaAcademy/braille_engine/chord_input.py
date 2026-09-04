# -*- coding: utf-8 -*-
"""
abaAcademy.braille_engine.chord_input
=====================================

One implementation of Perkins-style chord capture, shared by every screen that
takes braille input.

A brailler registers all the dot keys pressed "together" as a single cell. On a
computer keyboard the fingers never land or lift at the same instant, so the
rule that actually matches how people type is:

    accumulate every dot key pressed, and commit the cell when the last
    finger lifts.

That is what :class:`ChordAccumulator` does. It is deliberately plain Python
with no wx dependency so it can be unit-tested exhaustively — the previous
versions of this logic lived inside two GUI classes and drifted apart, and the
bugs were only reproducible by hand.

Two details matter and are handled here:

* **Key auto-repeat.** Holding a key makes the OS send repeated key-down
  events. Repeats must not disturb the chord or restart anything.
* **Lost key-ups.** If the window loses focus mid-chord the key-up may never
  arrive. :meth:`tick` lets the host commit a stalled chord instead of leaving
  the learner stuck, and :meth:`reset` clears state on focus loss.
"""

from __future__ import annotations

#: keyboard keys to braille dot numbers (standard Perkins home-row layout)
KEY_TO_DOT = {"F": 1, "D": 2, "S": 3, "J": 4, "K": 5, "L": 6}

#: same mapping by key code, for handlers that see codes rather than characters
KEYCODE_TO_DOT = {ord(k): v for k, v in KEY_TO_DOT.items()}


class ChordAccumulator:
    """Collects dot keys into a cell and reports when the cell is complete.

    Usage from a key handler::

        acc.press(dot)                 # on key-down
        cell = acc.release(dot)        # on key-up; non-None means "commit this"

    The accumulator never speaks or grades; it only decides what the cell is and
    when it is finished.
    """

    def __init__(self):
        self._held = set()        # dots whose keys are currently down
        self._chord = set()       # every dot pressed since the chord began
        self._stalled = 0         # consecutive ticks with keys stuck down

    # -- state ------------------------------------------------------------
    @property
    def pending(self):
        """Dots accumulated so far (the cell in progress)."""
        return set(self._chord)

    @property
    def holding(self):
        """Dots whose keys are still physically down."""
        return set(self._held)

    @property
    def active(self):
        return bool(self._chord)

    # -- events -----------------------------------------------------------
    def press(self, dot):
        """Register a dot key going down. Auto-repeat is harmless."""
        if dot not in KEY_TO_DOT.values():
            return
        self._held.add(dot)
        self._chord.add(dot)
        self._stalled = 0

    def release(self, dot):
        """Register a dot key coming up.

        Returns the completed cell (a frozenset of dot numbers) when the last
        finger lifts, else None — the learner is still mid-chord.
        """
        if dot not in KEY_TO_DOT.values():
            return None
        self._held.discard(dot)
        self._stalled = 0
        if self._held or not self._chord:
            return None
        return self._finish()

    def tick(self, max_stalls=25):
        """Safety net for a key-up that never arrived (e.g. focus was lost).

        The host may call this on a timer. It returns the cell only after the
        state has looked stuck for ``max_stalls`` consecutive calls, so normal
        holding is never cut short.
        """
        if not self._chord:
            return None
        if not self._held:
            return self._finish()
        self._stalled += 1
        if self._stalled >= max_stalls:
            return self._finish()
        return None

    def reset(self):
        """Abandon the chord in progress (focus loss, screen change)."""
        self._held.clear()
        self._chord.clear()
        self._stalled = 0

    def _finish(self):
        cell = frozenset(self._chord)
        self.reset()
        return cell or None


class PollingChordCapture:
    """Chord capture driven by polling the physical keyboard.

    Why polling rather than key events
    ----------------------------------
    Every event-driven attempt at this had the same class of failure: a cell
    committed with only some of the dots, or nothing at all. The causes are all
    outside our control — a key-up that is never delivered, key-downs arriving
    one at a time, the focused control swallowing keys, or another handler
    consuming them before ours runs.

    Polling sidesteps all of it. A few times a second we ask the operating
    system which of the six dot keys are physically held. The rule is then
    exact and needs no cooperation from the event system:

        while any dot key is down, union everything held;
        when the last one comes up, that union is the cell.

    Holding the keys for as long as you like is fine, pressing them in any
    order is fine, and no event needs to arrive on time.

    The host still consumes the key events so the letters do not leak into text
    fields or trigger menu shortcuts, but correctness no longer depends on them.
    """

    #: how often to sample the keyboard (ms). 25ms is far below human key
    #: timing, so no press is missed, and costs nothing.
    INTERVAL_MS = 25

    def __init__(self, key_state, on_cell, is_active=None):
        """``key_state(dot) -> bool`` reports whether that dot's key is held.
        ``on_cell(frozenset)`` receives each completed cell.
        ``is_active()`` gates capture (e.g. only while the screen is focused).
        """
        self._key_state = key_state
        self._on_cell = on_cell
        self._is_active = is_active or (lambda: True)
        self._chord = set()
        self._was_down = False

    def poll(self):
        """Sample once. Call from a timer. Returns the cell if one completed."""
        if not self._is_active():
            # focus left the screen: abandon a half-typed cell rather than
            # letting it merge into whatever is typed next
            self._chord.clear()
            self._was_down = False
            return None
        held = {d for d in KEY_TO_DOT.values() if self._key_state(d)}
        if held:
            self._chord |= held
            self._was_down = True
            return None
        if self._was_down and self._chord:
            cell = frozenset(self._chord)
            self._chord.clear()
            self._was_down = False
            self._on_cell(cell)
            return cell
        self._was_down = False
        return None

    def reset(self):
        self._chord.clear()
        self._was_down = False

    @property
    def pending(self):
        return set(self._chord)


class ChordPadMixin:
    """Wires a :class:`ChordAccumulator` to a wx control.

    The host screen supplies ``self.pad`` (the control that receives typing) and
    implements ``on_cell(cell)``; the mixin handles the key plumbing, ignores
    auto-repeat, clears the chord when focus leaves, and runs the stall timer.
    """

    CHORD_TICK_MS = 60

    def init_chord_pad(self, pad, on_space=None):
        import wx
        self._acc = ChordAccumulator()
        self._on_space = on_space
        self.pad = pad
        pad.Bind(wx.EVT_KEY_DOWN, self._chord_key_down)
        pad.Bind(wx.EVT_KEY_UP, self._chord_key_up)
        pad.Bind(wx.EVT_KILL_FOCUS, lambda e: (self._acc.reset(), e.Skip()))
        self._chord_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._chord_tick, self._chord_timer)
        self._chord_timer.Start(self.CHORD_TICK_MS)

    def stop_chord_pad(self):
        try:
            self._chord_timer.Stop()
        except Exception:
            pass

    def _chord_key_down(self, evt):
        import wx
        code = evt.GetKeyCode()
        if code in KEYCODE_TO_DOT:
            self._acc.press(KEYCODE_TO_DOT[code])
            return                      # consume; no Skip
        if code == wx.WXK_SPACE and self._on_space:
            self._on_space()
            return
        evt.Skip()

    def _chord_key_up(self, evt):
        code = evt.GetKeyCode()
        if code in KEYCODE_TO_DOT:
            cell = self._acc.release(KEYCODE_TO_DOT[code])
            if cell is not None:
                self.on_cell(cell)
            return
        evt.Skip()

    def _chord_tick(self, evt):
        cell = self._acc.tick()
        if cell is not None:
            self.on_cell(cell)

    def on_cell(self, cell):            # pragma: no cover - host implements
        raise NotImplementedError
