# -*- coding: utf-8 -*-
"""
abaDesktop.app
==============

The Arab Blind Academy application.

Launching goes straight into the academy — there is no landing window to click
through. The hub *is* the main window, so the first thing the learner hears is
the academy itself.

Speech comes from :mod:`abaDesktop.tts`. When NVDA is running the academy speaks
through it, so the learner keeps the voice, rate and Arabic settings they have
already configured; otherwise the app uses the system voice. Either way the
engine is selectable from the settings screen.
"""

from __future__ import annotations

import os
import sys

import wx

from .core import build_academy
from . import logging_setup
from .tts import Speaker
from . import migrate
from .paths import user_data_dir


class AppSpeech:
    """The speech object the academy screens talk to.

    The academy only ever needs ``announce`` / ``interrupt`` / ``speak_line``;
    everything about *how* the voice is produced lives in the Speaker.
    """

    def __init__(self, speaker):
        self._speaker = speaker
        self.enabled = True
        self.log = speaker.log

    def announce(self, text, *, interrupt=True, braille=True):
        if not text or not self.enabled:
            return
        self._speaker.speak(str(text), interrupt=interrupt)

    def interrupt(self):
        self._speaker.stop()

    def speak_line(self, text):
        self.announce(text, interrupt=False)

    # let the settings screen switch engines at runtime
    def set_engine(self, name):
        return self._speaker.set_engine(name)

    def engine_name(self):
        return self._speaker.backend.name


def _offer_import(parent, data_dir):
    """One-time offer to bring a learner's add-on data across.

    This must run *before* the academy opens its database. The imported files
    include the progress database itself, so anything that read the old empty
    one first (the hub deciding whether to show onboarding, for instance) would
    act on stale state and ask the learner to set up again.

    Returns True if data was imported.
    """
    marker = os.path.join(data_dir, ".imported")
    if os.path.exists(marker):
        return False
    info = migrate.describe()
    if not info["found"]:
        try:
            open(marker, "w").write("none")
        except Exception:
            pass
        return False
    msg = ("وجدنا بيانات إضافة NVDA على هذا الجهاز.\n\n"
           + migrate.summarise(info["source"]) +
           "\n\nهل تريد نقل كل ذلك إلى البرنامج؟ (لن يُحذف شيء من الإضافة.)")
    dlg = wx.MessageDialog(parent, msg, "نقل التقدّم",
                           wx.YES_NO | wx.ICON_QUESTION)
    imported = False
    if dlg.ShowModal() == wx.ID_YES:
        copied, skipped = migrate.import_from_addon(data_dir)
        imported = bool(copied)
        wx.MessageBox(f"تم نقل {len(copied)} عنصرًا بنجاح.",
                      "اكتمل النقل", wx.OK | wx.ICON_INFORMATION, parent)
    dlg.Destroy()
    try:
        open(marker, "w").write("done")
    except Exception:
        pass
    return imported


def main(argv=None):
    data_dir = user_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    log = logging_setup.setup(data_dir)

    # finish any update whose files were locked last time (the running .exe)
    try:
        from abaAcademy import updater as _upd
        done, failed = _upd.apply_pending()
        if done:
            log.info("applied %d pending update file(s)", len(done))
        if failed:
            log.warning("could not apply %d update file(s)", len(failed))
    except Exception:
        log.exception("applying pending update failed")

    app = wx.App(False)

    # Import first: the academy must open the *imported* database, not the
    # empty one it would otherwise create.
    try:
        _offer_import(None, data_dir)
    except Exception:
        log.exception("import offer failed")

    academy = build_academy(data_dir)

    # engine preference is a normal setting; "auto" prefers NVDA when running
    try:
        preferred = academy.store.get_setting("speech_engine", "auto") or "auto"
    except Exception:
        preferred = "auto"
    speaker = Speaker(preferred=preferred)
    speech = AppSpeech(speaker)
    logging_setup.note_environment(speech_engine=speaker.backend.name)
    log.info("academy ready; data dir: %s", data_dir)

    # the hub is the application window — no landing screen in between
    from abaAcademy.gui.hub import HubDialog
    hub = HubDialog(None, academy, speech)
    try:
        hub.SetTitle("أكاديمية الكفيف العربي")
    except Exception:
        pass

    try:
        hub.ShowModal()
    finally:
        try:
            hub.Destroy()
        except Exception:
            pass
        speaker.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
