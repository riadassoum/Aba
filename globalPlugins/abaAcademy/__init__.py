# -*- coding: utf-8 -*-
"""
ABA Academy - أكاديمية الكفيف العربي.

This package *is* the NVDA global plugin (NVDA scans modules directly under
``globalPlugins/``; ``abaAcademy/__init__.py`` therefore defines the
``GlobalPlugin``). The class is a thin shim: it registers one Tools-menu item
and delegates the GUI to :mod:`abaAcademy.app`.

Lifecycle: the heavy :class:`abaAcademy.academy.Academy` service (course
discovery + SQLite) is built **once, lazily**, and kept alive for the plugin's
lifetime -- not rebuilt on every menu click. Rebuilding on every open was
wasteful (re-reading every course pack, reopening the database) and, worse, any
failure on a later construction would silently kill the menu action so the
window "wouldn't re-open". Now:

Re-opening after closing
------------------------
The reported fault was that the academy opened once and then the Tools-menu
item did nothing for the rest of the NVDA session. Four separate things could
cause that, and all four are addressed here:

1. **A failed service build.** Building the ``Academy`` touches storage. If
   that raised -- and on runtimes without ``sqlite3`` it *always* raised, see
   ``database/store.py`` -- the exception escaped, the menu item appeared
   dead, and there was no message explaining why. The service is now built
   defensively, the storage layer no longer has a hard dependency, and any
   failure is both logged and reported to the learner in Arabic.

2. **A wedged re-entrancy guard.** ``_opening`` was set before work that could
   fail; it is now cleared in a ``finally`` on every path.

3. **An orphaned modal window.** A dialog surviving its owner leaves a hidden
   modal parented to NVDA's main frame, after which wx refuses to start a new
   modal loop and the menu item is dead until NVDA restarts. Leftovers are now
   hunted down and destroyed before each open.

4. **Unbalanced prePopup/postPopup.** If ``prePopup`` succeeded but the code
   raised before ``postPopup``, NVDA was left believing a dialog was still up.
   The pairing is now exception-safe.

On any failure the service is dropped so the *next* open rebuilds cleanly --
a bad state can never permanently wedge reopening.
"""

try:
    import globalPluginHandler
    # NOTE: this add-on has its own ``gui`` *subpackage*
    # (abaAcademy.gui). A bare ``import gui`` here is ambiguous: depending on
    # how NVDA sets up ``sys.path`` for global plugins, the name can bind to
    # our local ``abaAcademy.gui`` instead of NVDA's top-level ``gui`` module,
    # after which ``gui.mainFrame`` raises AttributeError and the academy never
    # opens. Importing it under an explicit alias removes the ambiguity: this
    # always refers to NVDA's own gui module.
    import gui as nvda_gui
    import wx
    _IN_NVDA = True
except Exception:
    _IN_NVDA = False


if _IN_NVDA:

    try:
        from scriptHandler import script as _script
    except Exception:
        def _script(**kwargs):
            def _wrap(f): return f
            return _wrap

    class GlobalPlugin(globalPluginHandler.GlobalPlugin):

        scriptCategory = "أكاديمية الكفيف العربي"

        def __init__(self):
            super(GlobalPlugin, self).__init__()
            self._item = None
            self._tools_menu = None
            self._academy = None
            self._speech = None
            self._opening = False
            try:
                self._tools_menu = nvda_gui.mainFrame.sysTrayIcon.toolsMenu
                self._item = self._tools_menu.Append(
                    wx.ID_ANY,
                    "أكاديمية الكفيف العربي (ABA)...",
                    "افتح أكاديمية الكفيف العربي: دروس اللغة والحاسوب وتمارين تفاعلية",
                )
                nvda_gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self._on_open, self._item)
            except Exception:
                self._log_error("ABA Academy: failed to add Tools menu item")
                self._tools_menu = None

        # -- service lifecycle ------------------------------------------

        def _ensure_service(self):
            if self._academy is None:
                from .bootstrap import create_academy
                self._academy, self._speech = create_academy()
            return self._academy, self._speech

        def _reset_service(self):
            try:
                if self._academy is not None:
                    self._academy.close()
            except Exception:
                pass
            self._academy = None
            self._speech = None

        # -- open flow --------------------------------------------------

        def _on_open(self, evt):
            # Run off the menu event and never allow two opens to stack. If a
            # previous open is (or got) stuck, the guard is cleared in the
            # finally of _open_now, so the menu can always be used again.
            if self._opening:
                return
            wx.CallAfter(self._open_now)

        def _open_now(self):
            if self._opening:
                return
            self._opening = True
            popped = False
            try:
                # Destroy anything a previous session may have left behind
                # before asking wx for a new modal loop.
                try:
                    from .gui.accessible import force_close_leftovers
                    force_close_leftovers()
                except Exception:
                    pass

                try:
                    nvda_gui.mainFrame.prePopup()
                    popped = True
                except Exception:
                    popped = False

                academy, speech = self._ensure_service()
                from .app import show_hub
                show_hub(nvda_gui.mainFrame, academy, speech)
            except Exception:
                self._log_error("ABA Academy: failed to open the academy window")
                # Drop possibly-broken state so the next attempt rebuilds fresh.
                self._reset_service()
                self._report_failure()
            finally:
                if popped:
                    try:
                        nvda_gui.mainFrame.postPopup()
                    except Exception:
                        pass
                self._opening = False

        def _open_mushaf(self):
            if self._opening:
                return
            wx.CallAfter(self._open_mushaf_now)

        def _open_generic(self, which):
            if self._opening:
                return
            def _run():
                if self._opening:
                    return
                self._opening = True
                popped = False
                try:
                    try:
                        from .gui.accessible import force_close_leftovers
                        force_close_leftovers()
                    except Exception:
                        pass
                    try:
                        nvda_gui.mainFrame.prePopup(); popped = True
                    except Exception:
                        popped = False
                    academy, speech = self._ensure_service()
                    if which == "hadith":
                        from .gui.hadith_reader import HadithReader
                        from .gui.accessible import clear_shutdown
                        clear_shutdown()
                        dlg = HadithReader(nvda_gui.mainFrame, academy, speech)
                        try:
                            dlg.ShowModal()
                        finally:
                            try: dlg.Destroy()
                            except Exception: pass
                            clear_shutdown()
                except Exception:
                    self._log_error("ABA Academy: failed to open " + which)
                    self._reset_service(); self._report_failure()
                finally:
                    if popped:
                        try: nvda_gui.mainFrame.postPopup()
                        except Exception: pass
                    self._opening = False
            wx.CallAfter(_run)

        def _open_mushaf_now(self):
            if self._opening:
                return
            self._opening = True
            popped = False
            try:
                try:
                    from .gui.accessible import force_close_leftovers
                    force_close_leftovers()
                except Exception:
                    pass
                try:
                    nvda_gui.mainFrame.prePopup(); popped = True
                except Exception:
                    popped = False
                academy, speech = self._ensure_service()
                from .app import show_quran
                show_quran(nvda_gui.mainFrame, academy, speech)
            except Exception:
                self._log_error("ABA Academy: failed to open the Mushaf")
                self._reset_service(); self._report_failure()
            finally:
                if popped:
                    try: nvda_gui.mainFrame.postPopup()
                    except Exception: pass
                self._opening = False

        # No default gesture: the shortcut is unassigned so it never clashes with
        # other add-ons. The user assigns it from NVDA > Preferences > Input
        # Gestures, category "أكاديمية الكفيف العربي".
        @_script(description="فتح المصحف لقراءة القرآن الكريم")
        def script_openMushaf(self, gesture):
            self._open_mushaf()

        @_script(description="فتح أكاديمية الكفيف العربي")
        def script_openAcademy(self, gesture):
            self._on_open(None)

        @_script(description="فتح قارئ الحديث الشريف")
        def script_openHadith(self, gesture):
            self._open_generic("hadith")

        def _report_failure(self):
            """Tell the learner, in Arabic, that opening failed.

            A silently dead menu item is the worst failure mode: it looks like
            the add-on is broken for good, when in fact the state has just
            been reset and the next attempt will very likely succeed.
            """
            try:
                wx.CallAfter(
                    nvda_gui.messageBox,
                    "تعذّر فتح الأكاديمية هذه المرة، وقد أُعيد ضبط حالتها. "
                    "جرّب فتحها مرة أخرى من قائمة الأدوات. "
                    "إن تكرّر الأمر فراجع سجل NVDA لمعرفة السبب.",
                    "أكاديمية الكفيف العربي",
                    wx.OK | wx.ICON_ERROR,
                )
            except Exception:
                pass

        # -- misc -------------------------------------------------------

        def _log_error(self, message):
            try:
                from logHandler import log
                log.error(message, exc_info=True)
            except Exception:
                pass

        def terminate(self):
            try:
                from .gui.accessible import close_all_screens, force_close_leftovers
                close_all_screens()
                force_close_leftovers()
            except Exception:
                pass
            self._reset_service()
            try:
                if self._item is not None and self._tools_menu is not None:
                    self._tools_menu.Remove(self._item)
            except Exception:
                pass
