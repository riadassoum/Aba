# -*- coding: utf-8 -*-
"""Open the real main screen and every feature it offers, with real wx.

Each catalogue entry's handler is called the way a learner would trigger it.
The child screen is shown, the event loop runs, the display settings and the
focus highlight are applied, and the screen is closed. Any exception, and any
screen that fails to appear, is a failure.

Skipped when wx or a display is not available (run under xvfb-run).
"""

import os
import sys
import tempfile
import time
import traceback
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

try:
    import wx
    _app = wx.App(False) if wx.GetApp() is None else wx.GetApp()
    HAVE_WX = bool(wx.Display.GetCount())
except Exception:
    HAVE_WX = False


def pump(n=6):
    for _ in range(n):
        wx.Yield()
        time.sleep(0.005)


class _Speech:
    def __init__(self):
        self.lines = []

    def announce(self, text, **_):
        self.lines.append(str(text))

    def speak_line(self, text):
        self.lines.append(str(text))

    def interrupt(self):
        pass


@unittest.skipUnless(HAVE_WX, "wx with a display is required")
class TestEveryHubFeatureOpens(unittest.TestCase):
    def test_every_feature(self):
        from abaDesktop.core import build_academy
        from abaAcademy.gui import hub as hub_mod
        from abaAcademy.gui.hub_catalog import CATALOG
        from abaAcademy.display_prefs import DisplayPrefs

        academy = build_academy(tempfile.mkdtemp())
        academy.settings._store.set_setting("onboarded", "1")
        # exercise the display path on every screen: big text, high contrast
        DisplayPrefs(font_scale=150, theme="yellow_on_black", bold=True).save(academy.store)

        opened, failures = [], []

        def fake_show_child(self, dlg):
            try:
                dlg.Show()
                pump()
                opened.append(type(dlg).__name__)
                # a focusable control should exist and the highlight should not break
                if hasattr(dlg, "_first_control") and dlg._first_control:
                    dlg._first_control.SetFocus()
                    pump(2)
            except Exception:
                failures.append(f"{type(dlg).__name__}: {traceback.format_exc(limit=3)}")
            finally:
                try:
                    dlg.close_screen(force=True) if hasattr(dlg, "close_screen") else None
                    dlg.Destroy()
                except Exception:
                    pass
            return wx.ID_CANCEL

        patches = [
            (hub_mod.AccessibleDialog, "show_child", fake_show_child),
            (wx.Dialog, "ShowModal", lambda self: wx.ID_CANCEL),
            (wx.SingleChoiceDialog, "ShowModal", lambda self: wx.ID_CANCEL),
            (wx.TextEntryDialog, "ShowModal", lambda self: wx.ID_CANCEL),
            (wx.MessageDialog, "ShowModal", lambda self: wx.ID_CANCEL),
            (wx.FileDialog, "ShowModal", lambda self: wx.ID_CANCEL),
            (wx.DirDialog, "ShowModal", lambda self: wx.ID_CANCEL),
            (wx, "MessageBox", lambda *a, **k: wx.ID_CANCEL),
        ]
        saved = [(o, n, getattr(o, n)) for o, n, _ in patches]
        for o, n, f in patches:
            setattr(o, n, f)
        speech = _Speech()
        frame = wx.Frame(None)
        try:
            hub = hub_mod.HubDialog(frame, academy, speech)
            hub.Show()
            pump(10)
            self.assertEqual(hub.notebook.GetPageCount(), len(CATALOG))
            total = 0
            for page, (lst, items, desc) in enumerate(hub._tab_lists):
                hub.notebook.SetSelection(page)
                pump(2)
                for i, feat in enumerate(items):
                    lst.SetSelection(i)
                    hub._on_feature_selected(lst, items, desc)
                    self.assertEqual(" ".join(desc.GetLabel().split()), " ".join(feat.description.split()))
                    before = len(opened) + len(failures)
                    spoken = len(speech.lines)
                    if os.environ.get("ABA_TRACE"):
                        print("OPEN", feat.handler, flush=True)
                    try:
                        hub._open_selected(lst, items)
                        pump(3)
                    except Exception:
                        failures.append(f"{feat.label} ({feat.handler}): {traceback.format_exc(limit=4)}")
                    total += 1
                    if feat.handler not in ("_open_help", "_open_typing", "_continue_last") \
                            and len(opened) + len(failures) == before and len(speech.lines) == spoken:
                        failures.append(f"{feat.label} ({feat.handler}): nothing opened")
            # quick jump by name and by description
            hub.jumpEntry.SetValue("القبلة")
            hub._quick_jump()
            pump(3)
            hub.jumpEntry.SetValue("الحالات الأربع")
            hub._quick_jump()
            pump(3)
            self.assertGreater(total, 80)
            hub.close_screen(force=True)
            hub.Destroy()
        finally:
            for o, n, f in saved:
                setattr(o, n, f)
            frame.Destroy()
            academy.close()
        self.assertEqual(failures, [], "\n".join(failures))
        self.assertIn("MainWindow", opened)
        self.assertIn("DisplayDialog", opened)


@unittest.skipUnless(HAVE_WX, "wx with a display is required")
class TestNewScreens(unittest.TestCase):
    def setUp(self):
        from abaDesktop.core import build_academy
        self.academy = build_academy(tempfile.mkdtemp())
        self.academy.settings._store.set_setting("onboarded", "1")
        self.speech = _Speech()
        self.frame = wx.Frame(None)

    def tearDown(self):
        self.frame.Destroy()
        self.academy.close()

    def test_placement_runs_to_a_result(self):
        from abaAcademy.gui.placement_view import PlacementDialog
        from abaAcademy.engine.placement import saved_level
        d = PlacementDialog(self.frame, self.academy, self.speech, course_id="italian")
        d.Show(); pump()
        d._start(); pump()
        n = 0
        while d._p and not d._p.finished and n < 60:
            q = d._p.current
            d.options.SetSelection(q.correct if n < 4 else (q.correct + 1) % len(q.options))
            d._answer(); pump(1)
            n += 1
        self.assertTrue(d.openBtn.IsEnabled())
        self.assertTrue(saved_level(self.academy.store, "italian").startswith("stage"))
        d.close_screen(force=True); d.Destroy()

    def test_display_settings_change_other_screens(self):
        from abaAcademy.gui.display_view import DisplayDialog
        from abaAcademy.gui.overview_view import OverviewDialog
        from abaAcademy.display_prefs import FONT_SCALES, THEMES
        other = OverviewDialog(self.frame, self.academy, self.speech)
        other.Show(); pump()
        before = other.sectionList.GetFont().GetPointSize()
        d = DisplayDialog(self.frame, self.academy, self.speech)
        d.Show(); pump()
        d.scaleChoice.SetSelection(FONT_SCALES.index(200))
        d.themeChoice.SetSelection(list(THEMES).index("yellow_on_black"))
        d._preview(); d._save(); pump()
        self.assertGreaterEqual(other.sectionList.GetFont().GetPointSize(), before * 2 - 1)
        self.assertEqual(other.sectionList.GetForegroundColour().Get()[:3], (255, 255, 0))
        d._reset(); d._save(); pump()
        self.assertEqual(other.sectionList.GetFont().GetPointSize(), before)
        # F2 reads the screen: title, labels and values
        from abaAcademy.gui.display import screen_text
        text = screen_text(other)
        self.assertIn("نظرة عامة على المتعلّم", text)
        self.assertIn("الأقسام", text)
        other.read_screen()
        self.assertIn("زرّ", self.speech.lines[-1])
        for w in (d, other):
            w.close_screen(force=True); w.Destroy()

    def test_hub_remembers_recent_features(self):
        from abaAcademy.gui import hub as hub_mod
        opened = []
        orig = hub_mod.AccessibleDialog.show_child

        def fake(self_, dlg):
            opened.append(type(dlg).__name__)
            dlg.Destroy()
            return wx.ID_CANCEL
        hub_mod.AccessibleDialog.show_child = fake
        try:
            h = hub_mod.HubDialog(self.frame, self.academy, self.speech)
            h.Show(); pump()
            page = next(i for i, (_, items, _) in enumerate(h._tab_lists) if any(f.handler == "_open_periodic" for f in items))
            lst, items, desc = h._tab_lists[page]
            lst.SetSelection(next(i for i, f in enumerate(items) if f.handler == "_open_periodic"))
            h._open_selected(lst, items); pump()
            home_list, home_items, _ = h._tab_lists[0]
            self.assertEqual(home_items[0].handler, "_open_periodic")
            self.assertEqual(home_list.GetString(0), "الجدول الدوري")
            h2 = hub_mod.HubDialog(self.frame, self.academy, self.speech)   # remembered across sessions
            self.assertEqual(h2._tab_lists[0][1][0].handler, "_open_periodic")
            for w in (h, h2):
                w.close_screen(force=True); w.Destroy()
        finally:
            hub_mod.AccessibleDialog.show_child = orig
        self.assertIn("PeriodicTableDialog", opened)
