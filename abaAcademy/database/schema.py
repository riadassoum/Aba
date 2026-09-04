# -*- coding: utf-8 -*-
"""
abaAcademy.database.schema
==========================

The SQLite schema for all persistent state: sessions, per-question attempts,
mistakes, spaced-repetition scheduling, mastery, achievements, and settings.

Kept as one DDL string so the migration path is trivial (create-if-missing)
and the whole shape is reviewable at a glance. All tables are keyed by stable
string ids that come from the content layer (course_id, lesson_id, qid, topic)
— the database never needs to understand what those strings mean.
"""

SCHEMA_VERSION = 1

DDL = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- One row per study session (a lesson run, a mixed session, endless practice).
CREATE TABLE IF NOT EXISTS sessions (
    session_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id    TEXT,
    level_id     TEXT,
    lesson_ids   TEXT,              -- JSON list; supports multi-lesson sessions
    mode         TEXT,              -- 'lesson' | 'mixed' | 'endless' | 'quiz'
    started_at   REAL,
    ended_at     REAL,
    total        INTEGER DEFAULT 0,
    correct      INTEGER DEFAULT 0,
    wrong        INTEGER DEFAULT 0,
    skipped      INTEGER DEFAULT 0
);

-- One row per answered question, for rich statistics and time analysis.
CREATE TABLE IF NOT EXISTS attempts (
    attempt_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER,
    qid          TEXT,
    topic        TEXT,
    course_id    TEXT,
    correct      INTEGER,           -- 1 / 0
    skipped      INTEGER DEFAULT 0,
    elapsed      REAL,
    answered_at  REAL
);

-- Aggregated mistake counts per (topic) so weak areas are cheap to query.
CREATE TABLE IF NOT EXISTS mistakes (
    topic        TEXT PRIMARY KEY,
    course_id    TEXT,
    wrong_count  INTEGER DEFAULT 0,
    right_count  INTEGER DEFAULT 0,
    last_seen    REAL
);

-- Spaced-repetition schedule, one row per tracked concept (qid).
CREATE TABLE IF NOT EXISTS srs (
    qid           TEXT PRIMARY KEY,
    topic         TEXT,
    course_id     TEXT,
    ease          REAL DEFAULT 2.5,
    interval_days REAL DEFAULT 0,
    repetitions   INTEGER DEFAULT 0,
    due_at        REAL,
    last_review   REAL
);

-- Per-lesson mastery and resume state.
CREATE TABLE IF NOT EXISTS lesson_progress (
    lesson_id    TEXT PRIMARY KEY,
    course_id    TEXT,
    level_id     TEXT,
    best_score   INTEGER DEFAULT 0, -- best quiz % achieved
    mastery      REAL DEFAULT 0.0,  -- 0..1 rolling mastery estimate
    completed    INTEGER DEFAULT 0,
    resume_phase TEXT,              -- where the learner paused
    resume_index INTEGER DEFAULT 0,
    updated_at   REAL
);

CREATE TABLE IF NOT EXISTS achievements (
    ach_id       TEXT PRIMARY KEY,
    title        TEXT,
    earned_at    REAL
);

-- Daily activity for streaks and weekly/monthly graphs.
CREATE TABLE IF NOT EXISTS daily_activity (
    day          TEXT PRIMARY KEY,  -- 'YYYY-MM-DD'
    seconds      INTEGER DEFAULT 0,
    answered     INTEGER DEFAULT 0,
    correct      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_attempts_topic ON attempts(topic);
CREATE INDEX IF NOT EXISTS idx_attempts_session ON attempts(session_id);
CREATE INDEX IF NOT EXISTS idx_srs_due ON srs(due_at);
"""
