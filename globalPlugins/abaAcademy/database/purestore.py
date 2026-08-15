# -*- coding: utf-8 -*-
"""
abaAcademy.database.purestore
=============================

A **pure-Python, dependency-free** implementation of the exact same public API
as :class:`abaAcademy.database.store.SQLiteStore`.

Why this exists
---------------
``sqlite3`` is nominally part of the Python standard library, but it is *not*
pure Python: it is a C extension (``_sqlite3.pyd``) that links against
``sqlite3.dll``. Embedded / trimmed Python runtimes -- which is exactly what a
screen reader ships -- do not always include those two binaries, and when they
don't, ``import sqlite3`` raises ``ImportError`` deep inside module import.
In the previous build that import sat at the top of ``store.py``, so on such a
machine the whole service failed to construct and the Tools-menu item silently
did nothing.

Shipping the binaries is not a real fix: ``_sqlite3.pyd`` is compiled against
one specific CPython minor version and one specific CPU architecture, so a
bundled copy that works on one NVDA release breaks on the next.

So instead of depending on a binary, the add-on now carries its own storage
engine. This module is that engine: plain Python, no imports outside the
standard pure-Python core, no compiled extension, no external file format.
It is selected automatically when ``sqlite3`` is unavailable, and the learner
never sees a difference.

Design
------
* All state lives in a handful of in-memory dicts/lists that mirror the SQL
  tables one-for-one.
* Persistence is a single JSON document written **atomically** (write to a
  temp file in the same directory, ``os.replace`` over the target), so a crash
  or a power cut can never leave a half-written progress file.
* Writes are debounced: mutating calls mark the document dirty and flush on a
  short interval (and always on ``close()``), so answering a question does not
  cost a full file write every time.
* A corrupt or unreadable file is backed up aside and treated as empty rather
  than raising -- progress loss is bad, but a learner locked out of the whole
  academy is worse.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_VERSION = 2

# Flush at most this often while the app is running (seconds).
_FLUSH_INTERVAL = 2.0


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _empty_doc() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "next_session_id": 1,
        "sessions": {},          # str(session_id) -> row dict
        "attempts": [],          # list of row dicts (append-only)
        "mistakes": {},          # topic -> row dict
        "srs": {},               # qid -> row dict
        "lesson_progress": {},   # lesson_id -> row dict
        "achievements": {},      # ach_id -> row dict
        "daily_activity": {},    # 'YYYY-MM-DD' -> row dict
        "settings": {},          # key -> value (str)
    }


class PureStore:
    """Pure-Python progress store. Mirrors the SQLite store's public API 1:1."""

    # Attempts are the only unbounded table; keep the most recent N so the
    # progress file cannot grow without limit over years of daily study.
    MAX_ATTEMPTS = 20000

    def __init__(self, db_path: str):
        # Same path the SQLite store would use, with a different suffix so the
        # two backends never fight over one file.
        base, _ = os.path.splitext(db_path)
        self.db_path = base + ".json"
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._doc = self._load()
        self._dirty = False
        self._last_flush = time.time()

    # -- persistence -------------------------------------------------------

    def _load(self) -> Dict[str, Any]:
        if not os.path.isfile(self.db_path):
            return _empty_doc()
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            if not isinstance(doc, dict):
                raise ValueError("root is not an object")
        except Exception:
            # Preserve whatever is there for forensics, then start clean.
            try:
                shutil.copyfile(self.db_path, self.db_path + ".corrupt")
            except OSError:
                pass
            return _empty_doc()
        base = _empty_doc()
        base.update({k: v for k, v in doc.items() if k in base})
        base["schema_version"] = SCHEMA_VERSION
        return base

    def _touch(self, force: bool = False) -> None:
        self._dirty = True
        if force or (time.time() - self._last_flush) >= _FLUSH_INTERVAL:
            self.flush()

    def flush(self) -> None:
        if not self._dirty:
            return
        directory = os.path.dirname(self.db_path) or "."
        tmp_name = None
        try:
            fd, tmp_name = tempfile.mkstemp(dir=directory, prefix=".aba", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._doc, f, ensure_ascii=False)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
            os.replace(tmp_name, self.db_path)
            tmp_name = None
            self._dirty = False
            self._last_flush = time.time()
        except Exception:
            # Never let a storage failure break a lesson in progress.
            pass
        finally:
            if tmp_name and os.path.exists(tmp_name):
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass

    def close(self) -> None:
        self.flush()

    # -- sessions ----------------------------------------------------------

    def start_session(self, course_id: str, level_id: str, lesson_ids: List[str],
                      mode: str) -> int:
        sid = int(self._doc.get("next_session_id", 1))
        self._doc["next_session_id"] = sid + 1
        self._doc["sessions"][str(sid)] = {
            "session_id": sid, "course_id": course_id, "level_id": level_id,
            "lesson_ids": list(lesson_ids), "mode": mode,
            "started_at": time.time(), "ended_at": None,
            "total": 0, "correct": 0, "wrong": 0, "skipped": 0,
        }
        self._touch()
        return sid

    def end_session(self, session_id: int, total: int, correct: int,
                    wrong: int, skipped: int) -> None:
        row = self._doc["sessions"].get(str(session_id))
        if row is None:
            return
        row.update({"ended_at": time.time(), "total": total, "correct": correct,
                    "wrong": wrong, "skipped": skipped})
        self._touch(force=True)

    # -- attempts + mistakes + daily activity ------------------------------

    def log_attempt(self, session_id: int, qid: str, topic: str, course_id: str,
                    correct: bool, skipped: bool, elapsed: float) -> None:
        now = time.time()
        attempts = self._doc["attempts"]
        attempts.append({
            "session_id": session_id, "qid": qid, "topic": topic,
            "course_id": course_id, "correct": int(bool(correct)),
            "skipped": int(bool(skipped)), "elapsed": float(elapsed),
            "answered_at": now,
        })
        if len(attempts) > self.MAX_ATTEMPTS:
            del attempts[: len(attempts) - self.MAX_ATTEMPTS]
        if not skipped:
            self._bump_mistake(topic, course_id, bool(correct), now)
            self._bump_daily(elapsed, bool(correct))
        self._touch()

    def _bump_mistake(self, topic: str, course_id: str, correct: bool, now: float) -> None:
        row = self._doc["mistakes"].setdefault(
            topic, {"topic": topic, "course_id": course_id,
                    "wrong_count": 0, "right_count": 0, "last_seen": now})
        row["right_count" if correct else "wrong_count"] += 1
        row["last_seen"] = now
        row["course_id"] = course_id or row.get("course_id", "")

    def _bump_daily(self, elapsed: float, correct: bool) -> None:
        day = _today_str()
        row = self._doc["daily_activity"].setdefault(
            day, {"day": day, "seconds": 0, "answered": 0, "correct": 0})
        row["seconds"] += int(elapsed)
        row["answered"] += 1
        if correct:
            row["correct"] += 1

    # -- lesson mastery + resume ------------------------------------------

    def update_lesson_progress(self, lesson_id: str, course_id: str, level_id: str,
                               score: int, mastery: float, completed: bool) -> None:
        row = self._doc["lesson_progress"].setdefault(
            lesson_id, {"lesson_id": lesson_id, "course_id": course_id,
                        "level_id": level_id, "best_score": 0, "mastery": 0.0,
                        "completed": 0, "resume_phase": None, "resume_index": 0,
                        "updated_at": 0.0})
        row["course_id"] = course_id or row.get("course_id", "")
        row["level_id"] = level_id or row.get("level_id", "")
        row["best_score"] = max(int(row.get("best_score", 0)), int(score))
        row["mastery"] = float(mastery)
        row["completed"] = max(int(row.get("completed", 0)), int(bool(completed)))
        row["updated_at"] = time.time()
        self._touch(force=True)

    def set_resume(self, lesson_id: str, phase: str, index: int) -> None:
        row = self._doc["lesson_progress"].get(lesson_id)
        if row is None:
            return
        row["resume_phase"] = phase
        row["resume_index"] = int(index)
        self._touch()

    def get_lesson_progress(self, lesson_id: str) -> Optional[Dict[str, Any]]:
        row = self._doc["lesson_progress"].get(lesson_id)
        return dict(row) if row else None

    def completed_lessons(self, course_id: str) -> int:
        return sum(1 for r in self._doc["lesson_progress"].values()
                   if r.get("course_id") == course_id and r.get("completed"))

    # -- statistics --------------------------------------------------------

    def overall_stats(self) -> Dict[str, Any]:
        rows = [a for a in self._doc["attempts"] if not a.get("skipped")]
        answered = len(rows)
        correct = sum(1 for a in rows if a.get("correct"))
        avg = (sum(float(a.get("elapsed") or 0.0) for a in rows) / answered) if answered else 0.0
        return {
            "answered": answered,
            "correct": correct,
            "accuracy": (correct / answered * 100.0) if answered else 0.0,
            "avg_time": avg,
        }

    def weakest_topics(self, limit: int = 5) -> List[Tuple[str, int, int]]:
        rows = [r for r in self._doc["mistakes"].values() if r.get("wrong_count", 0) > 0]
        rows.sort(key=lambda r: (
            -r.get("wrong_count", 0),
            -(r.get("wrong_count", 0) / (r.get("wrong_count", 0) + r.get("right_count", 0) + 1)),
        ))
        return [(r["topic"], r.get("wrong_count", 0), r.get("right_count", 0))
                for r in rows[:limit]]

    def strongest_topics(self, limit: int = 5) -> List[Tuple[str, int, int]]:
        rows = [r for r in self._doc["mistakes"].values() if r.get("right_count", 0) > 0]
        rows.sort(key=lambda r: (
            -(r.get("right_count", 0) / (r.get("wrong_count", 0) + r.get("right_count", 0) + 1)),
            -r.get("right_count", 0),
        ))
        return [(r["topic"], r.get("wrong_count", 0), r.get("right_count", 0))
                for r in rows[:limit]]

    def total_study_seconds(self) -> int:
        return int(sum(r.get("seconds", 0) for r in self._doc["daily_activity"].values()))

    def daily_activity(self, days: int = 30) -> List[Dict[str, Any]]:
        rows = sorted(self._doc["daily_activity"].values(),
                      key=lambda r: r.get("day", ""), reverse=True)
        return [dict(r) for r in rows[:days]]

    def current_streak(self) -> int:
        days = set(self._doc["daily_activity"].keys())
        streak = 0
        cursor = datetime.now(timezone.utc)
        while cursor.strftime("%Y-%m-%d") in days:
            streak += 1
            cursor = cursor.fromordinal(cursor.toordinal() - 1)
        return streak

    # -- achievements ------------------------------------------------------

    def grant_achievement(self, ach_id: str, title: str) -> bool:
        if ach_id in self._doc["achievements"]:
            return False
        self._doc["achievements"][ach_id] = {
            "ach_id": ach_id, "title": title, "earned_at": time.time()}
        self._touch(force=True)
        return True

    def achievements(self) -> List[Dict[str, Any]]:
        rows = sorted(self._doc["achievements"].values(),
                      key=lambda r: r.get("earned_at", 0.0), reverse=True)
        return [dict(r) for r in rows]

    # -- settings ----------------------------------------------------------

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        value = self._doc["settings"].get(key)
        return value if value is not None else default

    def set_setting(self, key: str, value: str) -> None:
        self._doc["settings"][key] = str(value)
        self._touch(force=True)

    # -- srs ---------------------------------------------------------------

    def srs_upsert(self, qid: str, topic: str, course_id: str, ease: float,
                   interval_days: float, repetitions: int, due_at: float,
                   stability: float = None, last_review: float = None) -> None:
        self._doc["srs"][qid] = {
            "qid": qid, "topic": topic, "course_id": course_id,
            "ease": float(ease), "interval_days": float(interval_days),
            "repetitions": int(repetitions), "due_at": float(due_at),
            "stability": float(stability) if stability is not None else float(interval_days),
            "last_review": float(last_review) if last_review is not None else time.time(),
        }
        self._touch()

    def srs_due(self, now: Optional[float] = None, limit: int = 50) -> List[Dict[str, Any]]:
        now = now if now is not None else time.time()
        rows = [r for r in self._doc["srs"].values() if float(r.get("due_at", 0)) <= now]
        rows.sort(key=lambda r: float(r.get("due_at", 0)))
        return [dict(r) for r in rows[:limit]]

    def srs_get(self, qid: str) -> Optional[Dict[str, Any]]:
        row = self._doc["srs"].get(qid)
        return dict(row) if row else None
