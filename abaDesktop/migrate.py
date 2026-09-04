# -*- coding: utf-8 -*-
"""
abaDesktop.migrate
==================

Find an existing NVDA installation of the academy add-on and copy the learner's
data into the standalone application, so nobody loses their streak, mistakes
notebook, flashcard scheduling, certificates or settings when they switch.

What moves across
-----------------
Everything the add-on stored under NVDA's configuration directory:

* ``aba_academy.db`` — progress, attempt history, spaced-repetition state,
  achievements, settings.
* ``notebook.json``, ``flashcards`` decks, installed course packs, and any other
  files the add-on wrote into its user-data folder.

Where it looks
--------------
NVDA keeps user config in ``%APPDATA%\\nvda`` for an installed copy, or in a
``userConfig`` folder beside ``nvda.exe`` for a portable copy. Both layouts are
searched, plus any path the user points at manually. Nothing is deleted from the
add-on: this is a copy, so NVDA keeps working exactly as before.
"""

from __future__ import annotations

import os
import shutil
import sys

# files/folders the add-on writes into its user-data directory
KNOWN_ITEMS = [
    "aba_academy.db",
    "aba_academy.json",
    "notebook.json",
    "flashcards",
    "courses",
    "quran_editions",
    "certificates",
]


def candidate_nvda_dirs():
    """Plausible NVDA user-config directories on this machine."""
    out = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        out.append(os.path.join(appdata, "nvda"))
    # portable copies keep a userConfig folder next to the executable
    for base in (os.environ.get("PROGRAMFILES"),
                 os.environ.get("PROGRAMFILES(X86)"),
                 os.path.expanduser("~")):
        if not base:
            continue
        out.append(os.path.join(base, "NVDA", "userConfig"))
    if sys.platform != "win32":
        # developer/testing layout
        out.append(os.path.expanduser("~/.config/nvda"))
    return [p for p in out if p]


def find_addon_data():
    """Return the add-on's user-data directory, or None if not found.

    The add-on stores its data in ``<nvda config>/abaAcademy``.
    """
    for base in candidate_nvda_dirs():
        candidate = os.path.join(base, "abaAcademy")
        if os.path.isdir(candidate):
            return candidate
    return None


def describe(source=None):
    """A human summary of what would be imported, for showing before copying."""
    source = source or find_addon_data()
    if not source or not os.path.isdir(source):
        return {"found": False, "source": None, "items": [], "bytes": 0}
    items, total = [], 0
    for name in KNOWN_ITEMS:
        path = os.path.join(source, name)
        if os.path.isfile(path):
            size = os.path.getsize(path)
            items.append((name, size))
            total += size
        elif os.path.isdir(path):
            size = 0
            for dirpath, _dirs, files in os.walk(path):
                for f in files:
                    try:
                        size += os.path.getsize(os.path.join(dirpath, f))
                    except OSError:
                        pass
            items.append((name + os.sep, size))
            total += size
    return {"found": True, "source": source, "items": items, "bytes": total}


def import_from_addon(dest_dir, source=None, overwrite=False):
    """Copy the add-on's data into ``dest_dir``.

    Returns (copied_names, skipped_names). Existing files are left alone unless
    ``overwrite`` is set, so re-running the import can't clobber newer progress
    made in the desktop app by accident.
    """
    source = source or find_addon_data()
    if not source or not os.path.isdir(source):
        return [], []
    os.makedirs(dest_dir, exist_ok=True)
    copied, skipped = [], []
    # Sweep the whole add-on folder, not a fixed list: whatever the add-on ever
    # wrote (progress database, notebook, decks, packs, certificates, records,
    # game scores, settings) comes across, including files added by later
    # versions that this code has never heard of.
    names = sorted(set(KNOWN_ITEMS) | set(os.listdir(source)))
    for name in names:
        src = os.path.join(source, name)
        dst = os.path.join(dest_dir, name)
        if not os.path.exists(src):
            continue
        if os.path.exists(dst) and not overwrite:
            skipped.append(name)
            continue
        try:
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            copied.append(name)
        except Exception:
            skipped.append(name)
    return copied, skipped


def export_to_folder(user_data_dir, dest_dir):
    """Export the desktop app's own data to a folder (backup / move machines)."""
    os.makedirs(dest_dir, exist_ok=True)
    copied = []
    for name in os.listdir(user_data_dir):
        src = os.path.join(user_data_dir, name)
        dst = os.path.join(dest_dir, name)
        try:
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            copied.append(name)
        except Exception:
            pass
    return copied


def summarise(source=None):
    """A readable Arabic summary of what the add-on holds, for the import prompt.

    Reads the progress database directly so the learner sees real numbers —
    lessons completed, attempts answered, strengths and weaknesses, streak,
    game records — rather than a bare list of filenames.
    """
    source = source or find_addon_data()
    if not source or not os.path.isdir(source):
        return "لا توجد بيانات."
    lines = []
    # some installations store progress as JSON rather than SQLite
    js = os.path.join(source, "aba_academy.json")
    if os.path.isfile(js):
        try:
            import json as _json
            with open(js, encoding="utf-8") as f:
                doc = _json.load(f)
            lessons = sum(1 for v in (doc.get("lesson_progress") or {}).values()
                          if v.get("completed"))
            attempts = len(doc.get("attempts") or [])
            correct = sum(1 for a in (doc.get("attempts") or [])
                          if a.get("correct"))
            cards = len(doc.get("srs") or {})
            days = len(doc.get("daily_activity") or {})
            secs = sum(int(v.get("seconds") or 0)
                       for v in (doc.get("daily_activity") or {}).values())
            if lessons:
                lines.append(f"الدروس المكتملة: {lessons}")
            if attempts:
                pct = int(round(100 * correct / attempts))
                lines.append(f"الأسئلة المُجابة: {attempts} (دقّتك {pct}٪)")
            if cards:
                lines.append(f"بطاقات المراجعة المتباعدة: {cards}")
            if days:
                hours = secs // 3600
                lines.append(f"أيّام الدراسة المسجّلة: {days}"
                             + (f"، بمجموع {hours} ساعة" if hours else ""))
        except Exception:
            lines.append("قاعدة تقدّمك (ستُنقل كاملة)")

    db = os.path.join(source, "aba_academy.db")
    if os.path.isfile(db):
        try:
            import sqlite3
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row

            def scalar(sql, default=0):
                try:
                    row = con.execute(sql).fetchone()
                    return (row[0] if row and row[0] is not None else default)
                except Exception:
                    return default

            lessons = scalar("SELECT COUNT(*) FROM lesson_progress "
                             "WHERE completed = 1")
            attempts = scalar("SELECT COUNT(*) FROM attempts")
            correct = scalar("SELECT COUNT(*) FROM attempts WHERE correct = 1")
            topics = scalar("SELECT COUNT(DISTINCT topic) FROM attempts")
            seconds = scalar("SELECT SUM(seconds) FROM daily_activity")
            days = scalar("SELECT COUNT(*) FROM daily_activity")
            settings = scalar("SELECT COUNT(*) FROM settings")
            cards = scalar("SELECT COUNT(*) FROM srs_cards")

            if lessons:
                lines.append(f"الدروس المكتملة: {lessons}")
            if attempts:
                pct = int(round(100 * correct / attempts)) if attempts else 0
                lines.append(f"الأسئلة المُجابة: {attempts} (دقّتك {pct}٪)")
            if topics:
                lines.append(f"الموضوعات التي تدرّبت عليها: {topics}")
            if cards:
                lines.append(f"بطاقات المراجعة المتباعدة: {cards}")
            if days:
                hours = int(seconds or 0) // 3600
                lines.append(f"أيّام الدراسة المسجّلة: {days}"
                             + (f"، بمجموع {hours} ساعة" if hours else ""))
            if settings:
                lines.append(f"الإعدادات والأرقام القياسية المحفوظة: {settings}")
            con.close()
        except Exception:
            lines.append("قاعدة تقدّمك (ستُنقل كاملة)")
    # other files
    extras = []
    for name in sorted(os.listdir(source)):
        if name in ("aba_academy.db",) or name.startswith("."):
            continue
        extras.append(name)
    if extras:
        lines.append("ملفّات أخرى: " + "، ".join(extras[:8])
                     + ("…" if len(extras) > 8 else ""))
    return "\n".join(f"• {l}" for l in lines) if lines else "بيانات التقدّم."
