# -*- coding: utf-8 -*-
"""
abaAcademy.gui.tool_base
========================

Shared scaffolding for the tool and practice screens added in 3.0.

``ToolDialog`` builds on ``AccessibleDialog`` and gives every screen the same
shape: a labelled control per row (the label is both visible text and the
control's accessible name, so nothing is ever unlabelled), a read-only
results box that is spoken when it changes, a button row, persistent
per-screen settings, and tone playback that is stopped when the screen
closes.

``ChoiceQuiz`` is a small helper for multiple-choice practice inside a
screen: it shows the options in a list, answers on Enter, keeps score, and
asks the screen for the next question.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple

try:
    import wx
except Exception:      # headless tests import the module without wx
    wx = None

from .accessible import AccessibleDialog

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,")


def to_western(text: str) -> str:
    return (text or "").translate(_AR_DIGITS)


def parse_float(text: str) -> float:
    t = to_western(text).strip().replace("،", ".").replace(",", "")
    if not t:
        raise ValueError("empty")
    return float(t)


def parse_int(text: str) -> int:
    t = to_western(text).strip()
    if not t:
        raise ValueError("empty")
    return int(float(t))


class ToolDialog(AccessibleDialog):
    TITLE = ""
    SIZE = (780, 600)
    SETTINGS_PREFIX = ""

    def __init__(self, parent, academy, speech, title: Optional[str] = None,
                 size=None):
        super().__init__(parent, title or self.TITLE, speech, size=size or self.SIZE)
        self.academy = academy
        self.panel = wx.Panel(self)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self._player = None
        self.output = None

    # -- building --------------------------------------------------------
    def add_text(self, text: str, wrap: int = 720) -> "wx.StaticText":
        st = wx.StaticText(self.panel, label=text)
        try:
            st.Wrap(wrap)
        except Exception:
            pass
        self.sizer.Add(st, 0, wx.ALL, 6)
        return st

    def _row(self, label: str, ctrl, proportion: int = 1) -> None:
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(self.panel, label=label + ":"), 0,
                wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(ctrl, proportion, wx.EXPAND)
        self.sizer.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)

    def add_entry(self, label: str, value: str = "", on_enter: Optional[Callable] = None,
                  multiline: bool = False, height: int = 0, hint: str = "") -> "wx.TextCtrl":
        style = wx.TE_MULTILINE if multiline else wx.TE_PROCESS_ENTER
        ctrl = wx.TextCtrl(self.panel, value=value, style=style)
        ctrl.SetName(label)
        if hint:
            try:
                ctrl.SetHint(hint)
            except Exception:
                pass
        if height:
            ctrl.SetMinSize(wx.Size(-1, height))
        if on_enter and not multiline:
            ctrl.Bind(wx.EVT_TEXT_ENTER, lambda e: on_enter())
        if multiline:
            self.sizer.Add(wx.StaticText(self.panel, label=label + ":"), 0,
                           wx.LEFT | wx.RIGHT | wx.TOP, 6)
            self.sizer.Add(ctrl, 1 if height else 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        else:
            self._row(label, ctrl)
        return ctrl

    def add_choice(self, label: str, choices: Sequence[str], selection: int = 0,
                   on_change: Optional[Callable] = None) -> "wx.Choice":
        ctrl = wx.Choice(self.panel, choices=list(choices))
        ctrl.SetName(label)
        if choices:
            ctrl.SetSelection(max(0, min(len(choices) - 1, selection)))
        if on_change:
            self.bind_choice(ctrl, lambda e: on_change())
        self._row(label, ctrl, 0)
        return ctrl

    def add_spin(self, label: str, low: int, high: int, value: int) -> "wx.SpinCtrl":
        ctrl = wx.SpinCtrl(self.panel, min=low, max=high, initial=max(low, min(high, value)))
        ctrl.SetName(label)
        self._row(label, ctrl, 0)
        return ctrl

    def add_check(self, label: str, value: bool = False,
                  on_change: Optional[Callable] = None) -> "wx.CheckBox":
        ctrl = wx.CheckBox(self.panel, label=label)
        ctrl.SetName(label)
        ctrl.SetValue(bool(value))
        if on_change:
            ctrl.Bind(wx.EVT_CHECKBOX, lambda e: on_change())
        self.sizer.Add(ctrl, 0, wx.ALL, 6)
        return ctrl

    def add_list(self, label: str, items: Sequence[str] = (), height: int = 160,
                 on_activate: Optional[Callable] = None,
                 on_select: Optional[Callable] = None) -> "wx.ListBox":
        self.sizer.Add(wx.StaticText(self.panel, label=label + ":"), 0,
                       wx.LEFT | wx.RIGHT | wx.TOP, 6)
        ctrl = wx.ListBox(self.panel, choices=list(items), style=wx.LB_SINGLE)
        ctrl.SetName(label)
        ctrl.SetMinSize(wx.Size(-1, height))
        if on_activate:
            ctrl.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: on_activate())
        if on_select:
            ctrl.Bind(wx.EVT_LISTBOX, lambda e: on_select())
        self.sizer.Add(ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        if items:
            self.select_index(ctrl, 0)
        return ctrl

    def add_output(self, label: str = "النتيجة", height: int = 160) -> "wx.TextCtrl":
        self.sizer.Add(wx.StaticText(self.panel, label=label + ":"), 0,
                       wx.LEFT | wx.RIGHT | wx.TOP, 6)
        ctrl = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        ctrl.SetName(label)
        ctrl.SetMinSize(wx.Size(-1, height))
        self.sizer.Add(ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        self.output = ctrl
        return ctrl

    def add_buttons(self, specs: Sequence[Tuple[str, Callable]], close: bool = True) -> List["wx.Button"]:
        row = wx.WrapSizer(wx.HORIZONTAL) if hasattr(wx, "WrapSizer") else wx.BoxSizer(wx.HORIZONTAL)
        out = []
        for label, handler in specs:
            b = self.button(self.panel, label, lambda e, h=handler: self._safe(h))
            row.Add(b, 0, wx.ALL, 3)
            out.append(b)
        if close:
            row.Add(self.button(self.panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        self.sizer.Add(row, 0, wx.ALL, 4)
        return out

    def finish(self, first=None) -> None:
        self.panel.SetSizer(self.sizer)
        if first is not None:
            self.set_first_control(first)

    # -- behaviour -------------------------------------------------------
    def _safe(self, handler: Callable) -> None:
        """Run a button handler; a mistake in one action is reported to the
        learner and logged instead of escaping into the event loop."""
        try:
            handler()
        except ValueError as exc:
            self._say(str(exc) or "قيمة غير صالحة.")
        except Exception as exc:          # pragma: no cover - logged for the developer
            try:
                import logging
                logging.getLogger("aba").exception("action failed in %s", type(self).__name__)
            except Exception:
                pass
            self._say(f"تعذّر تنفيذ الأمر: {exc}")

    def _say(self, text: str) -> None:
        self.announce(text)

    def show_output(self, text: str, speak: Optional[str] = None, focus: bool = False) -> None:
        if self.output is not None:
            self.output.SetValue(text)
            self.output.SetInsertionPoint(0)
            if focus:
                self.output.SetFocus()
        self.announce(speak if speak is not None else text)

    # -- settings ------------------------------------------------------
    def setting(self, key: str, default: str = "") -> str:
        try:
            v = self.academy.store.get_setting(self.SETTINGS_PREFIX + key, default)
            return default if v is None else v
        except Exception:
            return default

    def set_setting(self, key: str, value) -> None:
        try:
            self.academy.store.set_setting(self.SETTINGS_PREFIX + key, str(value))
        except Exception:
            pass

    def resource_path(self, *parts) -> str:
        import os
        base = getattr(self.academy, "resource_dir", None)
        if not base:
            base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources")
        return os.path.join(base, *parts)

    # -- sound -----------------------------------------------------------
    def player(self):
        if self._player is None:
            from ..math_engine.sonification import TonePlayer
            self._player = TonePlayer()
        return self._player

    def play_pcm(self, pcm: bytes) -> bool:
        p = self.player()
        if not p.available:
            return False
        p.play(pcm)
        return True

    def play_tones(self, events: Sequence[Tuple[float, float, float]]) -> bool:
        """(frequency, duration, pause) triples; frequency 0 = silence."""
        from ..math_engine.sonification import _sine
        pcm = bytearray()
        silence_frame = b"\x00\x00\x00\x00"
        for freq, dur, pause in events:
            if freq > 0:
                pcm += _sine(freq, dur, amp=0.3)
            else:
                pcm += silence_frame * int(22050 * dur)
            pcm += silence_frame * int(22050 * pause)
        return self.play_pcm(bytes(pcm))

    def stop_sound(self) -> None:
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:
                pass

    def on_closing(self) -> None:
        self.stop_sound()


class ChoiceQuiz:
    """Multiple-choice practice inside a ToolDialog.

    The screen supplies ``make()`` returning an object with ``prompt``,
    ``options``, ``answer`` and ``explanation`` (and optionally a ``play``
    callable for listening questions). The options live in ``listbox``;
    Enter or double-click answers the selected one."""

    def __init__(self, dialog: ToolDialog, listbox, make: Callable,
                 on_score: Optional[Callable[[int, int], None]] = None,
                 prompt_ctrl=None):
        self.d = dialog
        self.listbox = listbox
        self.make = make
        self.on_score = on_score
        self.prompt_ctrl = prompt_ctrl
        self.q = None
        self.answered = False
        self.right = 0
        self.total = 0
        self.streak = 0
        listbox.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.answer())

    def next(self) -> None:
        q = self.make()
        if q is None:
            self.d._say("لا يمكن توليد سؤال الآن.")
            return
        self.q = q
        self.answered = False
        self.listbox.Set(list(q.options))
        self.d.select_index(self.listbox, 0)
        if self.prompt_ctrl is not None:
            self.prompt_ctrl.SetLabel(q.prompt)
        self.listbox.SetFocus()
        play = getattr(q, "play", None)
        if callable(play):
            play()
        self.d.announce(f"{q.prompt} الخيارات: " + "، ".join(q.options))

    def repeat(self) -> None:
        if self.q is None:
            self.next()
            return
        play = getattr(self.q, "play", None)
        if callable(play):
            play()
        self.d.announce(self.q.prompt)

    def answer(self) -> None:
        if self.q is None:
            self.next()
            return
        if self.answered:
            self.next()
            return
        i = self.listbox.GetSelection()
        if i is None or i < 0:
            self.d._say("اختر إجابة بالأسهم ثم اضغط Enter.")
            return
        chosen = self.listbox.GetString(i)
        self.total += 1
        ok = chosen == self.q.answer
        if ok:
            self.right += 1
            self.streak += 1
            head = "صحيح!" + (f" {self.streak} على التوالي." if self.streak >= 3 else "")
        else:
            self.streak = 0
            head = f"خطأ. الصواب: {self.q.answer}."
        self.answered = True
        if self.on_score:
            self.on_score(self.right, self.total)
        self.d.announce(f"{head} {self.q.explanation} النتيجة {self.right} من {self.total}. "
                        f"اضغط Enter للسؤال التالي.")

    def score_text(self) -> str:
        if not self.total:
            return "لم تجب عن أي سؤال بعد."
        from ..tools.ar_count import count
        return (f"أجبت عن {count(self.total, 'question')}، الصحيح منها {self.right} "
                f"({round(100 * self.right / self.total)}٪).")
