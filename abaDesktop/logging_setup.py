# -*- coding: utf-8 -*-
"""
abaDesktop.logging_setup
========================

Error logging for the packaged application.

A frozen, windowed program has no console: if something raises, the traceback
goes nowhere and the user sees a silent failure or a bare error box with nothing
useful in it. This module writes everything to a log file next to the learner's
data, so a problem can actually be diagnosed from a report.

What is captured
----------------
* every uncaught exception on the main thread (``sys.excepthook``),
* every uncaught exception in a worker thread (``threading.excepthook``),
* anything the application logs through ``logging`` at INFO or above,
* a short header identifying the version, platform, Python build and speech
  engine, so a log is self-describing.

The log rotates at a modest size and keeps a couple of old copies, so it can
never grow without bound on a machine that is used for years.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import platform
import sys
import threading
import traceback

LOG_NAME = "academy.log"
_MAX_BYTES = 512 * 1024
_BACKUPS = 2

_configured = False


def log_path(data_dir=None):
    if data_dir is None:
        from .paths import user_data_dir
        data_dir = user_data_dir()
    return os.path.join(data_dir, LOG_NAME)


def setup(data_dir=None, level=logging.INFO):
    """Install file logging and the exception hooks. Safe to call twice."""
    global _configured
    if _configured:
        return logging.getLogger("aba")
    path = log_path(data_dir)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except Exception:
        pass

    logger = logging.getLogger()
    logger.setLevel(level)
    try:
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
        logger.addHandler(handler)
    except Exception:
        # never let logging failure stop the application starting
        pass

    _install_hooks()
    _configured = True
    log = logging.getLogger("aba")
    log.info("--- session start ---")
    log.info("platform: %s | python: %s (%d-bit)", platform.platform(),
             platform.python_version(), 64 if sys.maxsize > 2 ** 32 else 32)
    log.info("frozen: %s | log: %s", bool(getattr(sys, "frozen", False)), path)
    return log


def note_environment(speech_engine=None, version=None):
    """Record the bits worth knowing when reading a later error."""
    log = logging.getLogger("aba")
    if version:
        log.info("version: %s", version)
    if speech_engine:
        log.info("speech engine: %s", speech_engine)


def _install_hooks():
    prev_hook = sys.excepthook

    def hook(exc_type, exc, tb):
        try:
            logging.getLogger("aba").critical(
                "uncaught exception:\n%s",
                "".join(traceback.format_exception(exc_type, exc, tb)))
        except Exception:
            pass
        if not _is_benign(exc_type, exc):
            try:
                _show_error_dialog(exc_type, exc)
            except Exception:
                pass
        if prev_hook:
            prev_hook(exc_type, exc, tb)

    sys.excepthook = hook

    # worker threads (Python 3.8+): their exceptions are otherwise invisible
    if hasattr(threading, "excepthook"):
        def thread_hook(args):
            try:
                logging.getLogger("aba").error(
                    "uncaught exception in thread %s:\n%s",
                    getattr(args.thread, "name", "?"),
                    "".join(traceback.format_exception(
                        args.exc_type, args.exc_value, args.exc_traceback)))
            except Exception:
                pass
        threading.excepthook = thread_hook


def _is_benign(exc_type, exc):
    """A late callback reaching a window the learner already closed.

    wx raises ``RuntimeError: wrapped C/C++ object ... has been deleted`` in
    that case. Nothing is lost, so it is logged but never put in front of the
    learner as an error box."""
    try:
        return (issubclass(exc_type, RuntimeError)
                and "has been deleted" in str(exc))
    except Exception:
        return False


# Repeated identical errors (e.g. from a timer) open one box, not a cascade.
_shown_errors = set()


def _show_error_dialog(exc_type, exc):
    """Tell the learner where the log is, in Arabic, rather than failing mutely."""
    try:
        import wx
        if not wx.GetApp():
            return
        sig = (exc_type.__name__, str(exc)[:200])
        if sig in _shown_errors:
            return
        _shown_errors.add(sig)
        msg = (f"حدث خطأ غير متوقّع:\n{exc_type.__name__}: {exc}\n\n"
               f"سُجّلت التفاصيل في:\n{log_path()}\n\n"
               f"يمكنك إرسال هذا الملفّ للمطوّر لتشخيص المشكلة.")
        wx.MessageBox(msg, "خطأ", wx.OK | wx.ICON_ERROR)
    except Exception:
        pass
