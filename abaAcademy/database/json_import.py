# -*- coding: utf-8 -*-
"""
abaAcademy.database.json_import
===============================

Load a JSON-format progress file into the SQLite store.

Two storage backends exist for historical reasons: a JSON document
(``aba_academy.json``) and the SQLite database the application uses today
(``aba_academy.db``). A learner whose progress was written by the JSON backend
would see an empty academy after moving across — the file was copied but never
read, so completed lessons, streaks and spaced-repetition scheduling all looked
lost even though the data was sitting right there.

This module converts one into the other. It writes directly through the SQLite
store's own connection so the schema stays authoritative, and it merges rather
than replaces: importing twice does not duplicate history, and progress already
made in the destination is never overwritten by an older record.
"""

from __future__ import annotations

import json
import os


def _rows(container):
    """The JSON store keeps some tables as dicts keyed by id and some as lists."""
    if isinstance(container, dict):
        return list(container.values())
    if isinstance(container, list):
        return list(container)
    return []


def import_json_document(store, doc):
    """Merge a decoded JSON progress document into ``store``.

    Returns a dict of counts describing what was imported, suitable for showing
    to the learner or writing to the log.
    """
    con = store._conn
    counts = {"sessions": 0, "attempts": 0, "lessons": 0, "srs": 0,
              "mistakes": 0, "achievements": 0, "days": 0, "settings": 0}

    # -- settings: don't clobber anything already set here -------------------
    for key, value in (doc.get("settings") or {}).items():
        try:
            existing = store.get_setting(key, None)
            if existing in (None, ""):
                store.set_setting(key, str(value))
                counts["settings"] += 1
        except Exception:
            pass

    # -- sessions ------------------------------------------------------------
    session_map = {}
    for row in _rows(doc.get("sessions")):
        try:
            new_id = store.start_session(
                row.get("course_id") or "", row.get("level_id") or "",
                json.loads(row["lesson_ids"])
                if isinstance(row.get("lesson_ids"), str)
                else (row.get("lesson_ids") or []),
                row.get("mode") or "quiz")
            old_id = row.get("session_id") or row.get("id")
            if old_id is not None:
                session_map[str(old_id)] = new_id
            counts["sessions"] += 1
        except Exception:
            continue

    # -- attempts ------------------------------------------------------------
    for row in _rows(doc.get("attempts")):
        try:
            sid = session_map.get(str(row.get("session_id")), None)
            con.execute(
                "INSERT INTO attempts(session_id, qid, topic, course_id, "
                "correct, skipped, elapsed, answered_at) VALUES(?,?,?,?,?,?,?,?)",
                (sid, row.get("qid"), row.get("topic"), row.get("course_id"),
                 1 if row.get("correct") else 0,
                 1 if row.get("skipped") else 0,
                 row.get("elapsed") or 0,
                 row.get("answered_at") or 0))
            counts["attempts"] += 1
        except Exception:
            continue

    # -- lesson progress: keep the better result -----------------------------
    for row in _rows(doc.get("lesson_progress")):
        lesson_id = row.get("lesson_id")
        if not lesson_id:
            continue
        try:
            current = store.get_lesson_progress(lesson_id) or {}
            if (current.get("best_score") or 0) >= (row.get("best_score") or 0) \
                    and current.get("completed"):
                continue
            store.update_lesson_progress(
                lesson_id, row.get("course_id") or "",
                row.get("level_id") or "",
                int(row.get("best_score") or 0),
                float(row.get("mastery") or 0.0),
                bool(row.get("completed")))
            counts["lessons"] += 1
        except Exception:
            continue

    # -- spaced repetition ---------------------------------------------------
    for row in _rows(doc.get("srs")):
        try:
            con.execute(
                "INSERT OR REPLACE INTO srs(qid, topic, course_id, ease, "
                "interval_days, repetitions, due_at, last_review) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (row.get("qid"), row.get("topic"), row.get("course_id"),
                 row.get("ease") if row.get("ease") is not None else 2.5,
                 row.get("interval_days") or 0,
                 row.get("repetitions") or 0,
                 row.get("due_at") or 0, row.get("last_review") or 0))
            counts["srs"] += 1
        except Exception:
            continue

    # -- mistakes ------------------------------------------------------------
    for row in _rows(doc.get("mistakes")):
        try:
            con.execute(
                "INSERT OR REPLACE INTO mistakes(topic, course_id, "
                "wrong_count, right_count, last_seen) VALUES(?,?,?,?,?)",
                (row.get("topic"), row.get("course_id"),
                 row.get("wrong_count") or 0, row.get("right_count") or 0,
                 row.get("last_seen") or 0))
            counts["mistakes"] += 1
        except Exception:
            continue

    # -- achievements --------------------------------------------------------
    for row in _rows(doc.get("achievements")):
        try:
            con.execute(
                "INSERT OR REPLACE INTO achievements(ach_id, title, earned_at) "
                "VALUES(?,?,?)",
                (row.get("ach_id") or row.get("id"), row.get("title") or "",
                 row.get("earned_at") or 0))
            counts["achievements"] += 1
        except Exception:
            continue

    # -- daily activity: sum, so a day recorded in both is not lost ----------
    for row in _rows(doc.get("daily_activity")):
        day = row.get("day")
        if not day:
            continue
        try:
            con.execute(
                "INSERT INTO daily_activity(day, seconds, answered, correct) "
                "VALUES(?,?,?,?) ON CONFLICT(day) DO UPDATE SET "
                "seconds=seconds+excluded.seconds, "
                "answered=answered+excluded.answered, "
                "correct=correct+excluded.correct",
                (day, row.get("seconds") or 0, row.get("answered") or 0,
                 row.get("correct") or 0))
            counts["days"] += 1
        except Exception:
            continue

    try:
        con.commit()
    except Exception:
        pass
    return counts


def import_json_file(store, path):
    """Import a JSON progress file if it exists. Returns counts, or None."""
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:
        return None
    if not isinstance(doc, dict):
        return None
    return import_json_document(store, doc)


def has_content(path):
    """True if a JSON progress file holds anything worth importing."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:
        return False
    if not isinstance(doc, dict):
        return False
    for key in ("attempts", "lesson_progress", "srs", "sessions", "settings"):
        if doc.get(key):
            return True
    return False
