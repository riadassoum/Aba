# -*- coding: utf-8 -*-
"""
abaDesktop.paths
================

Where the standalone application keeps things.

The add-on stored user data inside NVDA's configuration folder. Standalone we
use the platform's normal per-user location, so uninstalling or reinstalling the
program never touches the learner's progress:

**Portable by default.** Everything the learner accumulates — imported progress,
downloaded recitations, course packs, backups — is written to a ``userdata``
folder beside the program itself. The application and its data therefore travel
together: copy the folder to a USB stick or another machine and nothing is left
behind, no matter how large the data grows.

If that folder cannot be created (the program was installed somewhere the user
cannot write to, such as *Program Files*), it falls back to the platform's
per-user location:

* Windows: ``%APPDATA%\\ArabBlindAcademy``
* macOS:   ``~/Library/Application Support/ArabBlindAcademy``
* Linux:   ``$XDG_DATA_HOME/ArabBlindAcademy`` (or ``~/.local/share/...``)
"""

from __future__ import annotations

import os
import sys

APP_DIR_NAME = "ArabBlindAcademy"


def _exe_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def portable_dir():
    """The ``userdata`` folder beside the program, if it is usable.

    Unlike the earlier behaviour, this does not require the folder to already
    exist: we try to create it, because keeping the learner's data next to the
    executable is the intended default rather than an opt-in.
    """
    candidate = os.path.join(_exe_dir(), "userdata")
    try:
        os.makedirs(candidate, exist_ok=True)
        # prove we can actually write there before committing to it
        probe = os.path.join(candidate, ".writable")
        with open(probe, "w") as f:
            f.write("")
        os.remove(probe)
        return candidate
    except Exception:
        return None


def user_data_dir():
    portable = portable_dir()
    if portable:
        return portable
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser(
            "~/.local/share")
    return os.path.join(base, APP_DIR_NAME)


def resource_root():
    """Where the bundled academy resources live (courses, Quran, dictionary)."""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "globalPlugins", "abaAcademy",
                            "resources")
    here = os.path.dirname(os.path.abspath(__file__))
    for c in (os.path.abspath(os.path.join(here, "..", "..", "globalPlugins",
                                           "abaAcademy", "resources")),
              os.path.abspath(os.path.join(here, "..", "globalPlugins",
                                           "abaAcademy", "resources"))):
        if os.path.isdir(c):
            return c
    return ""
