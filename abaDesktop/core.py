# -*- coding: utf-8 -*-
"""
abaDesktop.core
===============

Construction of the Academy, deliberately free of any GUI import so the
command-line interface works on a machine without wxPython.
"""

from __future__ import annotations

import os
import sys


def academy_root():
    """Folder containing the ``abaAcademy`` package."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(sys._MEIPASS)
    candidates.append(os.path.abspath(os.path.join(here, "..")))
    for c in candidates:
        if os.path.isdir(os.path.join(c, "abaAcademy")):
            if c not in sys.path:
                sys.path.insert(0, c)
            return c
    return None


def build_academy(data_dir=None):
    """Construct the Academy against the application's data directory."""
    from .paths import user_data_dir
    root = academy_root()
    from abaAcademy.academy import Academy
    base = os.path.join(root, "abaAcademy") if root else "abaAcademy"
    return Academy(base, data_dir or user_data_dir())
