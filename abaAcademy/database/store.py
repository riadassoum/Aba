# -*- coding: utf-8 -*-
"""
abaAcademy.database.store
=========================

Data-access layer for all progress/statistics, with **no external dependency
of any kind**.

Two interchangeable backends implement one identical API:

* :class:`SQLiteStore` -- used when ``sqlite3`` imports successfully. Fast,
  transactional, and what most installations will get.
* :class:`~abaAcademy.database.purestore.PureStore` -- a pure-Python engine
  bundled inside the add-on, used automatically when ``sqlite3`` is missing.

``sqlite3`` looks like a stdlib module but is really a C extension
(``_sqlite3.pyd`` + ``sqlite3.dll``). Trimmed/embedded Python runtimes -- the
kind a screen reader ships -- do not always carry those binaries, and the
import then fails. Previously that import sat at module top level, so the
failure propagated out of service construction and the Tools-menu item did
nothing at all. Bundling the binaries is not a fix either: they are compiled
per CPython minor version *and* per architecture, so a copy that works on one
the screen reader release breaks on the next.

Hence: the import is guarded, and the add-on carries its own fallback engine.
The learner needs nothing installed on their machine.

Call :func:`Store` (a factory, deliberately spelled like a class so existing
call sites are unchanged) to get whichever backend is available.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .purestore import PureStore
from .schema import DDL, SCHEMA_VERSION

try:  # C extension -- may be absent in a trimmed Python runtime.
    import sqlite3
    SQLITE_AVAILABLE = True
except Exception:  # pragma: no cover - depends on host runtime
    sqlite3 = None  # type: ignore[assignment]
    SQLITE_AVAILABLE = False


def backend_name() -> str:
    """Human-readable name of the storage engine actually in use (Arabic)."""
    return "SQLite" if SQLITE_AVAILABLE else "المحرك الداخلي (بايثون خالص)"


def Store(db_path: str):
    """Return a progress store backed by whichever engine is available.

    Spelled as a factory function rather than a class so callers keep writing
    ``Store(path)`` and stay unaware of which backend they got.
    """
    if SQLITE_AVAILABLE:
        try:
            return SQLiteStore(db_path)
        except Exception:
            # A locked, read-only or corrupt database must not block study.
            pass
    return PureStore(db_path)


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class SQLiteStore:

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self._conn.executescript(DDL)
        cur = self._conn.execute("SELECT value FROM meta WHERE key='schema_version'")
        row = cur.fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
        self._conn.commit()

    def flush(self) -> None:
        """Commit pending work. Mirrors PureStore.flush so callers can be
        backend-agnostic."""
        try:
            self._conn.commit()
        except Exception:
            pass

    def close(self) -> None:
        try:
            self._conn.commit()
            self._conn.close()
        except Exception:
            pass

    # -- sessions ----------------------------------------------------------

    def start_session(self, course_id: str, level_id: str, lesson_ids: List[str],
                      mode: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO sessions(course_id, level_id, lesson_ids, mode, started_at) "
            "VALUES(?,?,?,?,?)",
            (course_id, level_id, json.dumps(lesson_ids, ensure_ascii=False), mode, time.time()),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def end_session(self, session_id: int, total: int, correct: int,
                    wrong: int, skipped: int) -> None:
        self._conn.execute(
            "UPDATE sessions SET ended_at=?, total=?, correct=?, wrong=?, skipped=? "
            "WHERE session_id=?",
            (time.time(), total, correct, wrong, skipped, session_id),
        )
        self._conn.commit()

    # -- attempts + mistakes + daily activity ------------------------------

    def log_attempt(self, session_id: int, qid: str, topic: str, course_id: str,
                    correct: bool, skipped: bool, elapsed: float) -> None:
        now = time.time()
        try:
            self._conn.execute(
                "INSERT INTO attempts(session_id, qid, topic, course_id, correct, "
                "skipped, elapsed, answered_at) VALUES(?,?,?,?,?,?,?,?)",
                (session_id, qid, topic, course_id, int(correct), int(skipped), elapsed, now),
            )
            if not skipped:
                self._bump_mistake(topic, course_id, correct, now)
                self._bump_daily(elapsed, correct)
            self._conn.commit()
        except Exception:
            pass

    def _bump_mistake(self, topic: str, course_id: str, correct: bool, now: float) -> None:
        self._conn.execute(
            "INSERT INTO mistakes(topic, course_id, wrong_count, right_count, last_seen) "
            "VALUES(?,?,?,?,?) ON CONFLICT(topic) DO UPDATE SET "
            "wrong_count = wrong_count + ?, right_count = right_count + ?, last_seen=?",
            (topic, course_id, 0 if correct else 1, 1 if correct else 0, now,
             0 if correct else 1, 1 if correct else 0, now),
        )

    def _bump_daily(self, elapsed: float, correct: bool) -> None:
        day = _today_str()
        self._conn.execute(
            "INSERT INTO daily_activity(day, seconds, answered, correct) VALUES(?,?,1,?) "
            "ON CONFLICT(day) DO UPDATE SET seconds = seconds + ?, answered = answered + 1, "
            "correct = correct + ?",
            (day, int(elapsed), 1 if correct else 0, int(elapsed), 1 if correct else 0),
        )

    # -- lesson mastery + resume ------------------------------------------

    def update_lesson_progress(self, lesson_id: str, course_id: str, level_id: str,
                               score: int, mastery: float, completed: bool) -> None:
        self._conn.execute(
            "INSERT INTO lesson_progress(lesson_id, course_id, level_id, best_score, "
            "mastery, completed, updated_at) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(lesson_id) DO UPDATE SET "
            "best_score = MAX(best_score, ?), mastery=?, completed = MAX(completed, ?), "
            "updated_at=?",
            (lesson_id, course_id, level_id, score, mastery, int(completed), time.time(),
             score, mastery, int(completed), time.time()),
        )
        self._conn.commit()

    def set_resume(self, lesson_id: str, phase: str, index: int) -> None:
        self._conn.execute(
            "UPDATE lesson_progress SET resume_phase=?, resume_index=? WHERE lesson_id=?",
            (phase, index, lesson_id),
        )
        self._conn.commit()

    def get_lesson_progress(self, lesson_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT * FROM lesson_progress WHERE lesson_id=?", (lesson_id,)
        ).fetchone()
        return dict(row) if row else None

    def completed_lessons(self, course_id: str) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM lesson_progress WHERE course_id=? AND completed=1",
            (course_id,),
        ).fetchone()[0]

    # -- statistics --------------------------------------------------------

    def overall_stats(self) -> Dict[str, Any]:
        row = self._conn.execute(
            "SELECT COUNT(*) answered, SUM(correct) correct, "
            "AVG(elapsed) avg_time FROM attempts WHERE skipped=0"
        ).fetchone()
        answered = row["answered"] or 0
        correct = row["correct"] or 0
        return {
            "answered": answered,
            "correct": correct,
            "accuracy": (correct / answered * 100.0) if answered else 0.0,
            "avg_time": row["avg_time"] or 0.0,
        }

    def weakest_topics(self, limit: int = 5) -> List[Tuple[str, int, int]]:
        rows = self._conn.execute(
            "SELECT topic, wrong_count, right_count FROM mistakes "
            "WHERE wrong_count > 0 ORDER BY wrong_count DESC, "
            "(CAST(wrong_count AS REAL)/(wrong_count+right_count+1)) DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [(r["topic"], r["wrong_count"], r["right_count"]) for r in rows]

    def strongest_topics(self, limit: int = 5) -> List[Tuple[str, int, int]]:
        rows = self._conn.execute(
            "SELECT topic, wrong_count, right_count FROM mistakes "
            "WHERE right_count > 0 ORDER BY "
            "(CAST(right_count AS REAL)/(wrong_count+right_count+1)) DESC, "
            "right_count DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [(r["topic"], r["wrong_count"], r["right_count"]) for r in rows]

    def total_study_seconds(self) -> int:
        return self._conn.execute(
            "SELECT COALESCE(SUM(seconds),0) FROM daily_activity"
        ).fetchone()[0]

    def today_activity(self) -> Dict[str, Any]:
        """Today's activity row (answered / correct / seconds), or zeros."""
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self._conn.execute(
            "SELECT day, seconds, answered, correct FROM daily_activity "
            "WHERE day = ?", (day,)).fetchone()
        if row:
            return dict(row)
        return {"day": day, "seconds": 0, "answered": 0, "correct": 0}

    def daily_activity(self, days: int = 30) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT day, seconds, answered, correct FROM daily_activity "
            "ORDER BY day DESC LIMIT ?",
            (days,),
        ).fetchall()
        return [dict(r) for r in rows]

    def current_streak(self) -> int:
        """Consecutive days up to today with any activity."""
        rows = self._conn.execute(
            "SELECT day FROM daily_activity ORDER BY day DESC"
        ).fetchall()
        days = {r["day"] for r in rows}
        streak = 0
        cursor = datetime.now(timezone.utc)
        while cursor.strftime("%Y-%m-%d") in days:
            streak += 1
            cursor = cursor.fromordinal(cursor.toordinal() - 1)
        return streak

    # -- achievements ------------------------------------------------------

    def grant_achievement(self, ach_id: str, title: str) -> bool:
        try:
            # NOTE: ``connection.total_changes`` is cumulative for the lifetime
            # of the connection, so it is always > 0 after the first write and
            # cannot tell us whether *this* INSERT actually inserted. Use the
            # cursor's rowcount, which is per-statement.
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO achievements(ach_id, title, earned_at) VALUES(?,?,?)",
                (ach_id, title, time.time()),
            )
            self._conn.commit()
            return cur.rowcount > 0
        except Exception:
            return False

    def achievements(self) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT ach_id, title, earned_at FROM achievements ORDER BY earned_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # -- settings ----------------------------------------------------------

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO settings(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=?",
            (key, value, value),
        )
        self._conn.commit()

    # -- srs passthrough (schedule owned by srs.py) ------------------------

    def srs_upsert(self, qid: str, topic: str, course_id: str, ease: float,
                   interval_days: float, repetitions: int, due_at: float,
                   stability: float = None, last_review: float = None) -> None:
        lr = float(last_review) if last_review is not None else time.time()
        self._conn.execute(
            "INSERT INTO srs(qid, topic, course_id, ease, interval_days, repetitions, "
            "due_at, last_review) VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(qid) DO UPDATE SET ease=?, interval_days=?, repetitions=?, "
            "due_at=?, last_review=?",
            (qid, topic, course_id, ease, interval_days, repetitions, due_at, lr,
             ease, interval_days, repetitions, due_at, lr),
        )
        self._conn.commit()

    # note: FSRS 'stability' is derived from interval_days on reload, so no
    # schema change is needed; 'ease' column now carries FSRS difficulty.

    def srs_due(self, now: Optional[float] = None, limit: int = 50) -> List[Dict[str, Any]]:
        now = now if now is not None else time.time()
        rows = self._conn.execute(
            "SELECT * FROM srs WHERE due_at <= ? ORDER BY due_at ASC LIMIT ?",
            (now, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def srs_get(self, qid: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute("SELECT * FROM srs WHERE qid=?", (qid,)).fetchone()
        return dict(row) if row else None
