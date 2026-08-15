# -*- coding: utf-8 -*-
"""
abaAcademy.app
==============

GUI lifecycle helpers.

``show_hub(parent, academy, speech)`` shows the academy hub modally over an
*existing* service and returns when the user closes it -- it does NOT create or
close the service. The NVDA plugin owns the service lifetime (built once, reused
across opens), so showing must not dispose it.

``open_academy(parent)`` is a standalone convenience (used by tests or any
non-plugin caller) that builds a service, shows the hub, and disposes it.
"""

from __future__ import annotations


def show_hub(parent, academy, speech) -> None:
    from .gui.hub import HubDialog
    from .gui.accessible import clear_shutdown, force_close_leftovers

    # Belt and braces: clear any leftover state before showing the top-level
    # hub, and always destroy it afterwards, so a prior crash can never stop
    # the hub reopening in the same NVDA session.
    force_close_leftovers()
    clear_shutdown()
    dlg = HubDialog(parent, academy, speech)
    try:
        dlg.ShowModal()
    finally:
        try:
            dlg.Destroy()
        except Exception:
            pass
        clear_shutdown()


def open_academy(parent) -> None:
    from . import bootstrap
    academy, speech = bootstrap.create_academy()
    try:
        show_hub(parent, academy, speech)
    finally:
        academy.close()


def show_quran(parent, academy, speech) -> None:
    """Show the Qur'an Mushaf reader modally over an existing service."""
    from .gui.quran_reader import QuranReader
    from .gui.accessible import clear_shutdown, force_close_leftovers
    force_close_leftovers()
    clear_shutdown()
    dlg = QuranReader(parent, academy, speech)
    try:
        dlg.ShowModal()
    finally:
        try:
            dlg.Destroy()
        except Exception:
            pass
        clear_shutdown()
