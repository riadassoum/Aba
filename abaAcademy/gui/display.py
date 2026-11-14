# -*- coding: utf-8 -*-
"""
abaAcademy.gui.display
======================

Applies the learner's display preferences (``display_prefs``) to a screen:
every control gets the chosen text size, weight and colours, and the control
that has the keyboard focus is painted in the theme's highlight colours so a
low-vision learner, or a sighted helper beside a blind learner, can follow
where the keyboard is.

Each control remembers its original font size, so applying a new size never
compounds on the previous one.
"""

from __future__ import annotations

try:
    import wx
except Exception:  # pragma: no cover - wx missing in headless test envs
    wx = None

from ..display_prefs import DisplayPrefs

_BASE_ATTR = "_aba_base_points"
_ORIG_ATTR = "_aba_orig_colours"


def _walk(win):
    yield win
    try:
        children = win.GetChildren()
    except Exception:
        return
    for c in children:
        yield from _walk(c)


def _rgb(c):
    return wx.Colour(*c) if c is not None else None


def apply(window, prefs: DisplayPrefs) -> int:
    """Apply ``prefs`` to ``window`` and all its children. Returns the number
    of controls styled."""
    if wx is None or not window:
        return 0
    bg, fg = prefs.colours()
    count = 0
    windows = list(_walk(window))
    # Record every control's original size and colours before changing any:
    # wx passes a parent's new font down to its children, so recording while
    # restyling would capture an already-enlarged size.
    for w in windows:
        try:
            if not hasattr(w, _BASE_ATTR):
                font = w.GetFont()
                if font.IsOk():
                    setattr(w, _BASE_ATTR, font.GetPointSize())
            if not hasattr(w, _ORIG_ATTR):
                setattr(w, _ORIG_ATTR, (w.GetBackgroundColour(), w.GetForegroundColour()))
        except Exception:
            continue
    window.Freeze()
    try:
        for w in windows:
            try:
                font = w.GetFont()
                if not font.IsOk() or not hasattr(w, _BASE_ATTR):
                    continue
                base = getattr(w, _BASE_ATTR)
                f = wx.Font(font)
                f.SetPointSize(prefs.scaled(base))
                f.SetWeight(wx.FONTWEIGHT_BOLD if prefs.bold else wx.FONTWEIGHT_NORMAL)
                w.SetFont(f)
                if bg is not None and fg is not None:
                    w.SetBackgroundColour(_rgb(bg))
                    w.SetForegroundColour(_rgb(fg))
                else:
                    obg, ofg = getattr(w, _ORIG_ATTR)
                    w.SetBackgroundColour(obg)
                    w.SetForegroundColour(ofg)
                count += 1
            except Exception:
                continue
    finally:
        window.Thaw()
    try:
        window.Layout()
        _grow_to_fit(window, prefs)
        window.Refresh()
    except Exception:
        pass
    return count


def _grow_to_fit(window, prefs: DisplayPrefs) -> None:
    """Larger text needs a larger window: grow (never shrink) up to 90% of
    the display."""
    if prefs.font_scale <= 100 or not isinstance(window, wx.TopLevelWindow):
        return
    try:
        best = window.GetBestSize()
        cur = window.GetSize()
        disp = wx.Display(wx.Display.GetFromWindow(window) if wx.Display.GetFromWindow(window) >= 0 else 0)
        area = disp.GetClientArea()
        w = min(max(cur.width, best.width), int(area.width * 0.9))
        h = min(max(cur.height, best.height), int(area.height * 0.9))
        if (w, h) != (cur.width, cur.height):
            window.SetSize((w, h))
    except Exception:
        pass


class FocusHighlighter:
    """Paints the focused control in the theme's highlight colours."""

    def __init__(self, window, prefs: DisplayPrefs):
        self.window = window
        self.prefs = prefs
        self.current = None
        window.Bind(wx.EVT_CHILD_FOCUS, self._on_focus)

    def update(self, prefs: DisplayPrefs) -> None:
        self.prefs = prefs
        if self.current:
            self._restore(self.current)
            self.current = None

    def _restore(self, w):
        try:
            if not w:
                return
            bg, fg = self.prefs.colours()
            if bg is not None and fg is not None:
                w.SetBackgroundColour(_rgb(bg))
                w.SetForegroundColour(_rgb(fg))
            elif hasattr(w, _ORIG_ATTR):
                obg, ofg = getattr(w, _ORIG_ATTR)
                w.SetBackgroundColour(obg)
                w.SetForegroundColour(ofg)
            w.Refresh()
        except Exception:
            pass

    def _on_focus(self, evt):
        evt.Skip()
        try:
            w = evt.GetWindow()
        except Exception:
            return
        if self.current is not None and self.current is not w:
            self._restore(self.current)
            self.current = None
        if not self.prefs.focus_highlight or w is None or isinstance(w, (wx.Panel, wx.ScrolledWindow, wx.Dialog)):
            return
        try:
            if not hasattr(w, _ORIG_ATTR):
                setattr(w, _ORIG_ATTR, (w.GetBackgroundColour(), w.GetForegroundColour()))
            fbg, ffg = self.prefs.focus_colours()
            w.SetBackgroundColour(_rgb(fbg))
            w.SetForegroundColour(_rgb(ffg))
            w.Refresh()
            self.current = w
        except Exception:
            pass


def install(window, store) -> DisplayPrefs:
    """Load the saved preferences, apply them, and start highlighting focus.
    Safe to call more than once on the same window."""
    prefs = DisplayPrefs.load(store)
    if not prefs.is_default() or prefs.focus_highlight:
        if not prefs.is_default():
            apply(window, prefs)
        hl = getattr(window, "_aba_highlighter", None)
        if hl is None:
            window._aba_highlighter = FocusHighlighter(window, prefs)
        else:
            hl.update(prefs)
    return prefs


def reapply_everywhere(windows, store) -> int:
    """After the settings change: restyle every open screen."""
    prefs = DisplayPrefs.load(store)
    n = 0
    for w in list(windows):
        try:
            if w:
                apply(w, prefs)
                hl = getattr(w, "_aba_highlighter", None)
                if hl is None:
                    w._aba_highlighter = FocusHighlighter(w, prefs)
                else:
                    hl.update(prefs)
                n += 1
        except Exception:
            continue
    return n


def describe_control(w) -> str:
    """Spoken form of one control: its name or label and its current value."""
    try:
        if isinstance(w, wx.StaticText):
            return w.GetLabel().replace("\n", " ").strip()
        name = (w.GetName() or "").strip()
        label = (w.GetLabel() or "").strip() if hasattr(w, "GetLabel") else ""
        if isinstance(w, wx.Button):
            return f"زرّ {label or name}"
        if isinstance(w, wx.CheckBox):
            return f"{label or name}: {'محدّد' if w.GetValue() else 'غير محدّد'}"
        if isinstance(w, (wx.Choice, wx.ComboBox)):
            sel = w.GetStringSelection()
            return f"{name}: {sel}" if sel else name
        if isinstance(w, wx.ListBox):
            sel = w.GetStringSelection()
            return f"{name}، {w.GetCount()} عناصر" + (f"، المحدّد: {sel}" if sel else "")
        if isinstance(w, wx.TextCtrl):
            v = w.GetValue().replace("\n", " ").strip()
            if len(v) > 300:
                v = v[:300] + "…"
            return f"{name}: {v}" if v else f"{name}: فارغ"
        if isinstance(w, wx.SpinCtrl):
            return f"{name}: {w.GetValue()}"
        if isinstance(w, wx.Notebook):
            i = w.GetSelection()
            return f"القسم: {w.GetPageText(i)}" if i >= 0 else ""
    except Exception:
        return ""
    return ""


def screen_text(window) -> str:
    """Everything visible on a screen, in reading order, as one text."""
    parts = []
    try:
        parts.append(window.GetTitle())
    except Exception:
        pass
    notebook_pages = set()
    for w in _walk(window):
        if w is window:
            continue
        try:
            if not w.IsShown():
                continue
            parent = w.GetParent()
            # inside a notebook, only the selected page is "visible"
            if isinstance(parent, wx.Notebook):
                if parent.GetCurrentPage() is not w:
                    notebook_pages.add(id(w))
                    continue
            if any(id(a) in notebook_pages for a in _ancestors(w)):
                continue
        except Exception:
            continue
        t = describe_control(w)
        if t and t not in parts:
            parts.append(t)
    return "، ".join(p for p in parts if p)


def _ancestors(w):
    p = w.GetParent()
    while p is not None:
        yield p
        p = p.GetParent()
