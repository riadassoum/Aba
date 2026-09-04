#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_app.py — launcher for the Arab Blind Academy desktop application.

With no arguments it opens the graphical application. With arguments it runs the
command-line interface instead (``--stats``, ``--report``, ``--backup``,
``--import-nvda``), which is handy for teachers scripting reports or for
restoring a learner's data without opening the interface.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Make the bundled pure-Python libraries importable before anything else runs.
try:
    from abaDesktop.vendored import install as _install_vendor
    _install_vendor()
except Exception:
    pass


def main():
    args = sys.argv[1:]
    if args:
        from abaDesktop.extras import run_cli
        return run_cli(args)
    from abaDesktop.app import main as app_main
    return app_main()


if __name__ == "__main__":
    sys.exit(main())
