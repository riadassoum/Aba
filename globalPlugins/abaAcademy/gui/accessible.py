# -*- coding: utf-8 -*-
"""
abaAcademy.gui.accessible
=========================

The accessibility framework every screen inherits from. This is where the
spec's non-negotiable rules are *enforced structurally* so individual screens
can't forget them.

``AccessibleDialog`` guarantees, on show:
  1. the dialog takes keyboard focus,
  2. its title is spoken,
  3. its instructions are spoken,
  4. its first interactive element is focused and announced,
all with a single cancel-before-speak announcement so nothing queues behind
stale speech.

It also installs a consistent global shortcut table:
  Enter → continue/submit     Backspace → previous
  Ctrl+R → repeat question     Ctrl+H → hear explanation
  Ctrl+P → pause               Ctrl+S → statistics
  Ctrl+M → main menu           Escape → back
  F1     → help

Screens override the ``on_*`` hooks they care about; unhandled shortcuts are
harmless no-ops. Controls created through the ``add_labeled`` helpers always
get an accessible name, so "never contain unlabeled controls" holds by
construction.

Outside NVDA/wx (sandbox, tests) the module still imports: it falls back to a
minimal stub base so the accessibility *logic* (what gets announced, in what
order) is unit-testable without a display.
"""

from __future__ import annotations

import weakref
from typing import Callable, List, Optional

try:
    import wx
    _WX = True
except Exception:
    _WX = False

from ..audio.speech import SpeechManager


# ---------------------------------------------------------------------------
# Open-screen registry
# ---------------------------------------------------------------------------
# Every AccessibleDialog registers itself here while it exists. Two problems
# this solves, both reported as "the window won't come back":
#
# 1. Escape must close *everything*, not just peel off one layer. A learner
#    four dialogs deep should be able to leave the academy in one keystroke.
# 2. A dialog that somehow survives its owner (an exception during teardown, a
#    stray modal loop) used to leave a hidden modal window parented to NVDA's
#    main frame. wx then refuses to start a new modal loop and the Tools-menu
#    item appears dead for the rest of the NVDA session -- the only fix being
#    a full restart. With a registry we can find and destroy those leftovers
#    before opening again, so reopening always works.
#
# Weak references, so this can never keep a destroyed dialog alive.
_OPEN_SCREENS: "weakref.WeakSet" = weakref.WeakSet()


def open_screens() -> list:
    """Currently-live academy screens, innermost (most recently shown) last."""
    return [s for s in _OPEN_SCREENS if s]


# Set while a "leave the academy entirely" request is unwinding the stack of
# nested modal dialogs. See close_all_screens() for why this is a flag rather
# than a loop over every open window.
_shutdown_requested = False


def shutdown_requested() -> bool:
    return _shutdown_requested


def close_all_screens() -> None:
    """Leave the academy entirely, however many screens deep the learner is.

    Screens are nested *modal* loops: the hub's ``ShowModal()`` has not
    returned while the learner is inside a lesson, which is inside an exercise.
    Calling ``EndModal`` on an outer dialog whose inner loop is still spinning
    is undefined behaviour in wx and is a good way to produce exactly the kind
    of wedged, un-reopenable window this add-on suffered from.

    So instead of force-closing everything at once, we raise a flag and close
    only the innermost screen. As each modal loop returns, ``show_child``
    notices the flag and closes its own screen too, unwinding the stack one
    clean layer at a time until nothing is left.
    """
    global _shutdown_requested
    screens = open_screens()
    if not screens:
        return
    _shutdown_requested = True
    try:
        screens[-1].close_screen(force=True)
    except Exception:
        pass


def clear_shutdown() -> None:
    """Reset the flag once the stack has fully unwound (called by the hub)."""
    global _shutdown_requested
    _shutdown_requested = False


def force_close_leftovers() -> None:
    """Destroy any screen still alive outside a modal loop.

    Called defensively just before opening the academy. In normal operation
    this finds nothing; it exists so that a window orphaned by an unexpected
    error in a previous session can never permanently block reopening.
    """
    clear_shutdown()
    for screen in reversed(open_screens()):
        try:
            if not screen.IsModal():
                screen.Destroy()
        except Exception:
            pass


# Shared shortcut identifiers, referenced by help text and handlers.
SHORTCUTS_HELP = [
    ("Enter", "متابعة أو تأكيد الإجابة"),
    ("Backspace", "الصفحة أو السؤال السابق"),
    ("Ctrl+R", "إعادة قراءة السؤال الحالي"),
    ("Ctrl+H", "سماع الشرح مرة أخرى"),
    ("Ctrl+P", "إيقاف مؤقت / استئناف"),
    ("Ctrl+S", "الإحصائيات"),
    ("Ctrl+M", "القائمة الرئيسية"),
    ("Escape", "إغلاق الشاشة الحالية والرجوع"),
    ("Shift+Escape", "الخروج من الأكاديمية بالكامل"),
    ("Ctrl+Q", "الخروج من الأكاديمية بالكامل"),
    ("F1", "المساعدة"),
]


if _WX:

    class AccessibleDialog(wx.Dialog):
        """Base dialog that enforces the announce-on-show accessibility policy."""

        def __init__(self, parent, title: str, speech: SpeechManager,
                     size=(720, 540)):
            super().__init__(parent, title=title,
                             style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
                             size=size)
            self.speech = speech
            self._title_text = title
            self._first_control: Optional[wx.Window] = None
            self._accel_entries: List[tuple] = []
            self._closing = False
            self._install_core_shortcuts()
            self.Bind(wx.EVT_SHOW, self._on_show)
            self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
            # EVT_CLOSE fires for the title-bar X and Alt+F4; route it through
            # the same teardown as Escape so no path can leave a live modal.
            self.Bind(wx.EVT_CLOSE, self._on_close_event)
            _OPEN_SCREENS.add(self)

        # -- shortcut plumbing --------------------------------------------

        def _install_core_shortcuts(self) -> None:
            # Escape is handled explicitly in EVT_CHAR_HOOK below rather than
            # left to wx's built-in dialog dismissal. wx only auto-dismisses on
            # Escape when the dialog owns a button with wxID_CANCEL/wxID_OK --
            # none of these screens do, they use Arabic-labelled buttons with
            # generated ids. That is why Escape used to do nothing on several
            # screens, and why a learner could end up stuck inside a modal.
            # wxID_NONE disables the (non-functioning) built-in path so there is
            # exactly one code path for closing.
            self.SetEscapeId(wx.ID_NONE)

        def _on_char_hook(self, evt: "wx.KeyEvent") -> None:
            key = evt.GetKeyCode()
            ctrl = evt.ControlDown()
            shift = evt.ShiftDown()
            if key == wx.WXK_ESCAPE:
                # Escape always closes the screen it is pressed on -- from any
                # control, including inside a text field. Shift+Escape (and
                # Ctrl+Q) leaves the academy completely, however deep you are.
                if shift:
                    close_all_screens()
                else:
                    self.close_screen()
            elif ctrl and key in (ord("Q"), ord("q")):
                close_all_screens()
            elif ctrl and key in (ord("R"), ord("r")):
                self.on_repeat()
            elif ctrl and key in (ord("H"), ord("h")):
                self.on_hear_explanation()
            elif ctrl and key in (ord("G"), ord("g")):
                self.on_hint()
            elif ctrl and key in (ord("P"), ord("p")):
                self.on_pause()
            elif ctrl and key in (ord("S"), ord("s")):
                self.on_statistics()
            elif ctrl and key in (ord("M"), ord("m")):
                self.on_main_menu()
            elif key == wx.WXK_F1:
                self.on_help()
            elif key == wx.WXK_BACK and not self._is_text_focus():
                self.on_previous()
            elif key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and not self._is_text_focus():
                # Single-key advance/confirm from anywhere that isn't an editable
                # text field (those need Enter for their own submit). Screens
                # override on_enter_key() to do the right thing.
                if not self.on_enter_key():
                    evt.Skip()
            else:
                evt.Skip()

        # -- nested screens ------------------------------------------------

        def show_child(self, dlg) -> int:
            """Show a child screen modally and dispose of it correctly.

            Every place that opens another academy screen goes through here so
            that the three easy-to-get-wrong parts are written once:

            * the child is always ``Destroy``ed, even if it raised,
            * a pending "leave the academy" request closes this screen too as
              soon as the child's modal loop returns, unwinding the whole
              nest one layer at a time,
            * a failure to construct or show a child can never leave this
              screen in a half-dead state.
            """
            result = wx.ID_CANCEL
            try:
                result = dlg.ShowModal()
            except Exception:
                pass
            finally:
                try:
                    dlg.Destroy()
                except Exception:
                    pass
            if shutdown_requested():
                self.close_screen(force=True)
            return result

        # -- closing -------------------------------------------------------

        def can_close(self) -> bool:
            """Screens override to veto/confirm a close (e.g. mid-exam)."""
            return True

        def on_closing(self) -> None:
            """Screens override to release resources (timers, etc.)."""

        def close_screen(self, force: bool = False) -> None:
            """Close this screen, whatever state it is in.

            This is the single teardown path for Escape, the Close button, the
            title-bar X and Alt+F4. It is idempotent and never raises: a
            failure here is exactly what used to leave a zombie modal behind
            and make the academy un-reopenable.
            """
            if self._closing or not self:
                return
            if not force and not self.can_close():
                return
            self._closing = True
            try:
                self.on_closing()
            except Exception:
                pass
            try:
                if self.IsModal():
                    self.EndModal(wx.ID_CANCEL)
                else:
                    self.Show(False)
                    self.Destroy()
            except Exception:
                # Last resort: get it off the screen even if the tidy path
                # failed, so it cannot block a future modal loop.
                try:
                    self.Destroy()
                except Exception:
                    pass

        def _on_close_event(self, evt) -> None:
            if not self._closing and not self.can_close():
                if evt.CanVeto():
                    evt.Veto()
                return
            self.close_screen(force=True)

        def _is_text_focus(self) -> bool:
            focus = wx.Window.FindFocus()
            # Only *editable* text controls should capture Enter/Backspace;
            # a read-only display field must not block single-key navigation.
            return isinstance(focus, wx.TextCtrl) and focus.IsEditable()

        # -- announce-on-show policy --------------------------------------

        def set_first_control(self, ctrl: "wx.Window") -> None:
            self._first_control = ctrl

        def instructions(self) -> str:
            """Screens override to provide their spoken instructions."""
            return ""

        def _on_show(self, evt: "wx.ShowEvent") -> None:
            if evt.IsShown():
                wx.CallAfter(self._announce_screen)
            evt.Skip()

        def _announce_screen(self) -> None:
            # This runs via wx.CallAfter, so the dialog may already have been
            # destroyed (e.g. the user closed it immediately). wx objects are
            # falsy once their C++ side is gone -- bail out rather than raise.
            if not self:
                return
            try:
                self.Raise()
                parts = [self._title_text]
                instr = self.instructions()
                if instr:
                    parts.append(instr)
                first = self._first_control
                if first:
                    first.SetFocus()
                    name = first.GetName()
                    if name and name != first.GetLabel():
                        parts.append(name)
                # single cancel-before-speak announcement
                self.speech.announce("، ".join(p for p in parts if p))
            except Exception:
                pass

        def announce(self, text: str) -> None:
            self.speech.announce(text)

        # -- labeled control helpers (no unlabeled controls) --------------

        def labeled_text(self, parent, label: str, value: str = "",
                         multiline: bool = False, readonly: bool = False) -> "wx.TextCtrl":
            style = 0
            if multiline:
                style |= wx.TE_MULTILINE
            if readonly:
                style |= wx.TE_READONLY
            else:
                style |= wx.TE_PROCESS_ENTER
            ctrl = wx.TextCtrl(parent, value=value, style=style)
            ctrl.SetName(label)
            return ctrl

        def button(self, parent, label: str, handler: Callable) -> "wx.Button":
            btn = wx.Button(parent, label=label)
            btn.SetName(label)
            btn.Bind(wx.EVT_BUTTON, handler)
            return btn

        def bind_choice(self, choice: "wx.Choice", handler: Callable) -> None:
            """Bind a combo/choice's change event so the handler runs but focus
            STAYS on the combo box. Without this, a handler that rebuilds the
            screen or speaks (calling SetFocus elsewhere) yanks the user out of
            the combo after every value change, making it impossible to cycle
            through options with the arrow keys. We re-assert focus on the choice
            after the handler (and after any CallAfter the handler queued), so
            the user only leaves the combo when they press Tab themselves."""
            def _wrapped(evt, _c=choice, _h=handler):
                try:
                    _h(evt)
                finally:
                    # run after any focus changes the handler queued
                    wx.CallAfter(self._restore_choice_focus, _c)
            choice.Bind(wx.EVT_CHOICE, _wrapped)

        def _restore_choice_focus(self, choice) -> None:
            try:
                if choice and choice.IsShown() and choice.IsEnabled():
                    choice.SetFocus()
            except Exception:
                pass

        # -- overridable shortcut hooks -----------------------------------

        def on_repeat(self) -> None:
            self.announce(self._title_text)

        def on_hear_explanation(self) -> None:
            pass

        def on_hint(self) -> None:
            pass

        def on_pause(self) -> None:
            pass

        def on_statistics(self) -> None:
            pass

        def on_main_menu(self) -> None:
            self.close_screen()

        def on_previous(self) -> None:
            pass

        def on_enter_key(self) -> bool:
            """Single-key Enter action. Return True if handled (event consumed),
            False to let wx process Enter normally. Screens override this to
            advance a step or confirm an answer without needing Tab."""
            return False

        def on_help(self) -> None:
            lines = []
            try:
                instr = self.instructions()
                if instr:
                    lines.append(instr)
            except Exception:
                pass
            lines.append("اختصارات عامة:")
            lines += [f"{k}: {d}" for k, d in SHORTCUTS_HELP]
            self.announce(". ".join(lines))

else:
    # Headless stub for tests / sandbox: mirrors the announce policy so that
    # the *sequence and content* of announcements can be asserted without wx.
    class AccessibleDialog:  # type: ignore[no-redef]
        def __init__(self, parent, title: str, speech: SpeechManager, size=None):
            self.speech = speech
            self._title_text = title
            self._first_control_name: Optional[str] = None
            self._closed = False

        def instructions(self) -> str:
            return ""

        def set_first_control_name(self, name: str) -> None:
            self._first_control_name = name

        def can_close(self) -> bool:
            return True

        def on_closing(self) -> None:
            pass

        def close_screen(self, force: bool = False) -> None:
            if self._closed:
                return
            if not force and not self.can_close():
                return
            self.on_closing()
            self._closed = True

        @property
        def closed(self) -> bool:
            return self._closed

        def simulate_show(self) -> None:
            parts = [self._title_text]
            if self.instructions():
                parts.append(self.instructions())
            if self._first_control_name:
                parts.append(self._first_control_name)
            self.speech.announce("، ".join(p for p in parts if p))

        def announce(self, text: str) -> None:
            self.speech.announce(text)
