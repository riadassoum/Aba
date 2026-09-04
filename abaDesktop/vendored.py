# -*- coding: utf-8 -*-
"""
abaDesktop.vendored
===================

Makes the libraries shipped in ``vendor/`` importable.

What is bundled, and why only these
-----------------------------------
``vendor/`` holds **pure-Python** packages only — currently ``comtypes`` and
``pyttsx3``, which together give the application a voice on Windows (SAPI5)
without the learner installing anything. Pure-Python packages are safe to ship
because they run on any interpreter and any platform.

Compiled extensions are deliberately *not* vendored. A ``.pyd``/``.so`` is built
against one exact Python version and platform, so a bundled copy silently stops
working the moment the interpreter changes — which is precisely the trap the old
add-on fell into with a Python 3.13 Windows-only audio binary. Those
dependencies (wxPython, miniaudio) are installed for the interpreter actually in
use; ``build.py --deps`` does that in one step.

The vendor directory is appended to ``sys.path``, never prepended, so a properly
installed copy always wins over the bundled one.
"""

from __future__ import annotations

import os
import sys


def vendor_dir():
    """Absolute path of the bundled-library folder, or None if absent."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(sys._MEIPASS, "vendor"))
        candidates.append(os.path.join(os.path.dirname(sys.executable), "vendor"))
    candidates.append(os.path.abspath(os.path.join(here, "..", "vendor")))
    for c in candidates:
        if os.path.isdir(c):
            return c
    return None


def install():
    """Append the vendor folder to ``sys.path``. Safe to call more than once."""
    path = vendor_dir()
    if path and path not in sys.path:
        # append, so an installed package always takes precedence
        sys.path.append(path)
    return path


def bundled_packages():
    """Names of the packages actually present in ``vendor/``."""
    path = vendor_dir()
    if not path:
        return []
    out = []
    for name in sorted(os.listdir(path)):
        full = os.path.join(path, name)
        if os.path.isdir(full) and not name.endswith(".dist-info"):
            out.append(name)
        elif name.endswith(".py"):
            out.append(name[:-3])
    return out
