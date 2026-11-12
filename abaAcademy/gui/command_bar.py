# -*- coding: utf-8 -*-
"""
abaAcademy.gui.command_bar
==========================

Gives dialog-based reader windows a full keyboard command set plus a menu the
user can open with the Alt key (or the Applications / context-menu key), in the
spirit of a classic menu bar. Because these screens are
``wx.Dialog`` (which cannot host a native menu bar), we provide the same feel
two ways:

* an ``wx.AcceleratorTable`` so every command has a real shortcut (Ctrl+…,
  function keys, etc.) that works from anywhere in the window, and
* a popup menu built from the same command list, opened with Alt or the
  Applications key and announced by the speech engine — so commands are discoverable,
  exactly like pressing Alt on a menu bar.

A command is: (label, shortcut_text, key_tuple_or_None, handler). One source of
truth builds both the accelerators and the menu, so they never drift apart.
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None


class CommandBar:
    def __init__(self, dialog):
        self.dialog = dialog
        self._commands = []          # (label, shortcut, keytuple, handler, menu_id)
        self._by_id = {}
        self._key_index = {}

    def add(self, label, shortcut, keytuple, handler):
        """Register a command. ``keytuple`` is (flags, keycode) or None."""
        mid = wx.NewIdRef()
        self._commands.append((label, shortcut, keytuple, handler, mid))
        self._by_id[int(mid)] = handler
        return mid

    def add_separator(self):
        self._commands.append((None, None, None, None, None))

    def install(self):
        """Build the accelerator table AND a char-hook dispatcher. The char-hook
        is what makes shortcuts work even when focus is inside a multiline text
        control (which would otherwise swallow keys like Ctrl+S before the
        accelerator table sees them)."""
        entries = []
        for label, shortcut, keytuple, handler, mid in self._commands:
            if handler is None:
                continue
            self.dialog.Bind(wx.EVT_MENU, self._wrap(handler), id=mid)
            if keytuple is not None:
                flags, code = keytuple
                entries.append(wx.AcceleratorEntry(flags, code, int(mid)))
                # index for char-hook dispatch: (ctrl, shift, alt, keycode) -> handler
                self._key_index[(bool(flags & wx.ACCEL_CTRL),
                                 bool(flags & wx.ACCEL_SHIFT),
                                 bool(flags & wx.ACCEL_ALT),
                                 code)] = handler
        if entries:
            self.dialog.SetAcceleratorTable(wx.AcceleratorTable(entries))
        self.dialog.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        # A bare Alt tap opens our command menu (handled in the char hook via a
        # short armed timer, so Alt+Left/Right combos still work). EVT_KEY_DOWN
        # also watches for a key following Alt, to cancel the pending menu when
        # Alt is used as a modifier.
        self.dialog.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
        self._alt_down = False
        self._alt_used = False
        self._alt_pending = False

    def _arm_alt_menu(self):
        """Arm a very short timer to open the command menu after a bare Alt.
        If an Alt+key combo fires meanwhile (setting _alt_used) or Alt is used as
        a modifier, the pending open is cancelled. This lets a lone Alt tap open
        the menu while Alt+Left/Right still navigate."""
        self._alt_pending = True
        later = getattr(self.dialog, "call_later", None)
        if later is not None:
            later(220, self._fire_alt_menu)
        else:
            try:
                wx.CallLater(220, self._fire_alt_menu)
            except Exception:
                self._alt_pending = False

    def _fire_alt_menu(self):
        if getattr(self, "_alt_pending", False) and not self._alt_used:
            self._alt_pending = False
            self.show_menu()
        else:
            self._alt_pending = False

    def _wrap(self, handler):
        def _run(evt):
            try:
                handler()
            except Exception:
                pass
        return _run

    def _normalize_code(self, code):
        # map lowercase ASCII to uppercase so ord('s') matches ord('S')
        if ord('a') <= code <= ord('z'):
            return code - 32
        # numpad +/- and = variations
        if code in (wx.WXK_NUMPAD_ADD,):
            return ord('=')
        if code in (wx.WXK_NUMPAD_SUBTRACT,):
            return ord('-')
        return code

    def _on_char_hook(self, evt):
        code = evt.GetKeyCode()
        # F1: read out the shortcuts for THIS screen (context help)
        if code == wx.WXK_F1:
            self.speak_help()
            return
        # the Applications/menu key opens the menu immediately
        if code == wx.WXK_WINDOWS_MENU:
            self.show_menu()
            return
        # Shift+F10 is the universal "open context menu" combo — always available
        # as a reliable way to reach the commands even if the Alt menu bar does
        # not behave on a given wx build.
        if code == wx.WXK_F10 and evt.ShiftDown():
            self.show_menu()
            return
        # bare Alt: consume it fully (no Skip) so Windows never opens the window
        # system menu, then open OUR command menu. To avoid hijacking Alt+arrow
        # combos (Alt+Left/Right navigation), we don't open immediately — we arm
        # a very short timer, and if an Alt+key combo fires first it cancels the
        # timer. A lone Alt tap lets the timer fire and the menu opens.
        if code == wx.WXK_ALT and not (evt.ControlDown() or evt.ShiftDown()):
            self._alt_down = True
            self._alt_used = False
            self._arm_alt_menu()
            return   # consume -> no system menu
        if self._alt_down and code != wx.WXK_ALT:
            # a key was pressed while Alt is held -> this is a combo, not a tap;
            # cancel any pending bare-Alt menu open
            self._alt_used = True
            self._alt_pending = False
        # dispatch registered shortcuts ourselves so they fire even inside the
        # read-only text window (which would otherwise consume Ctrl/Alt+key).
        ctrl, shift, alt = evt.ControlDown(), evt.ShiftDown(), evt.AltDown()
        if ctrl or alt:
            handler = self._key_index.get((ctrl, shift, alt, self._normalize_code(code)))
            if handler is not None:
                self._alt_pending = False
                try:
                    handler()
                except Exception:
                    pass
                return
        evt.Skip()

    def _on_key_down(self, evt):
        # Track whether another key is pressed while Alt is held, so a real
        # Alt+key combo (e.g. Alt+Left) is not mistaken for a bare-Alt tap and
        # cancels the pending menu. Everything passes through.
        code = evt.GetKeyCode()
        if self._alt_down and code != wx.WXK_ALT:
            self._alt_used = True
            self._alt_pending = False
        evt.Skip()

    def help_text(self):
        """A spoken list of this screen's commands and their shortcuts."""
        parts = []
        try:
            instr = self.dialog.instructions()
            if instr:
                parts.append(instr)
        except Exception:
            pass
        parts.append("اختصارات هذه الشاشة:")
        for label, shortcut, keytuple, handler, mid in self._commands:
            if handler is None:
                continue
            parts.append(f"{shortcut}: {label}" if shortcut else label)
        parts.append("اضغط Alt أو مفتاح القائمة لعرض قائمة الأوامر.")
        return "؛ ".join(parts)

    def speak_help(self):
        try:
            self.dialog.announce(self.help_text())
        except Exception:
            pass

    def show_menu(self):
        menu = wx.Menu()
        for label, shortcut, keytuple, handler, mid in self._commands:
            if handler is None:
                menu.AppendSeparator()
                continue
            text = f"{label}\t{shortcut}" if shortcut else label
            menu.Append(mid, text)
        try:
            self.dialog.announce("القائمة")
        except Exception:
            pass
        self.dialog.PopupMenu(menu)
        menu.Destroy()


# Convenience key tuples for building commands.
def key(code, ctrl=False, shift=False, alt=False):
    flags = wx.ACCEL_NORMAL
    if ctrl:
        flags |= wx.ACCEL_CTRL
    if shift:
        flags |= wx.ACCEL_SHIFT
    if alt:
        flags |= wx.ACCEL_ALT
    return (flags, code)
