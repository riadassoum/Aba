# -*- coding: utf-8 -*-
"""
abaAcademy.codelab.sql_lab
==========================

مختبر قواعد البيانات SQL — a private in-memory SQLite database with a few
small Arabic tables (students, subjects, grades, books, loans), a free query
box whose results are read row by row, and graded exercises from SELECT to
JOIN and GROUP BY. Each exercise is checked by comparing the learner's
result with the result of the reference query, so any correct query passes.

The database lives in memory and is rebuilt on demand; ATTACH (which could
reach files on disk) and extension loading are refused, and a runaway query
is stopped after a few million steps.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

SCHEMA = """
CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, city TEXT, age INTEGER, grade_level INTEGER);
CREATE TABLE subjects (id INTEGER PRIMARY KEY, title TEXT, hours INTEGER);
CREATE TABLE grades (student_id INTEGER REFERENCES students(id), subject_id INTEGER REFERENCES subjects(id),
                     score INTEGER);
CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, author TEXT, year INTEGER, pages INTEGER, braille INTEGER);
CREATE TABLE loans (book_id INTEGER REFERENCES books(id), student_id INTEGER REFERENCES students(id),
                    loan_date TEXT, returned INTEGER);
"""

STUDENTS = [(1, "أحمد", "القدس", 15, 10), (2, "مريم", "عمّان", 14, 9), (3, "يوسف", "القاهرة", 16, 11),
            (4, "فاطمة", "بيروت", 15, 10), (5, "عمر", "الرباط", 17, 12), (6, "سارة", "تونس", 14, 9),
            (7, "خالد", "دمشق", 16, 11), (8, "ليلى", "الجزائر", 15, 10), (9, "علي", "بغداد", 17, 12),
            (10, "هدى", "غزة", 16, 11)]
SUBJECTS = [(1, "الرياضيات", 5), (2, "اللغة العربية", 6), (3, "العلوم", 4), (4, "اللغة الإنجليزية", 4),
            (5, "البرمجة", 3)]
GRADES = [(1, 1, 88), (1, 2, 92), (1, 3, 75), (1, 5, 95), (2, 1, 70), (2, 2, 98), (2, 4, 85), (3, 1, 95),
          (3, 3, 90), (3, 5, 99), (4, 2, 80), (4, 4, 91), (5, 1, 60), (5, 2, 72), (5, 3, 68), (6, 2, 89),
          (6, 4, 94), (7, 1, 83), (7, 5, 77), (8, 3, 96), (8, 2, 87), (9, 1, 79), (9, 4, 65), (10, 1, 91),
          (10, 2, 95), (10, 5, 88)]
BOOKS = [(1, "الأيام", "طه حسين", 1929, 380, 1), (2, "رجال في الشمس", "غسان كنفاني", 1963, 110, 1),
         (3, "موسم الهجرة إلى الشمال", "الطيب صالح", 1966, 170, 0), (4, "زقاق المدق", "نجيب محفوظ", 1947, 290, 1),
         (5, "عائد إلى حيفا", "غسان كنفاني", 1969, 90, 0), (6, "الخبز الحافي", "محمد شكري", 1973, 230, 0),
         (7, "أرض البرتقال الحزين", "غسان كنفاني", 1962, 140, 1), (8, "اللص والكلاب", "نجيب محفوظ", 1961, 160, 1)]
LOANS = [(1, 1, "2026-09-01", 1), (2, 1, "2026-09-15", 0), (4, 3, "2026-09-03", 1), (2, 4, "2026-09-10", 1),
         (5, 10, "2026-10-01", 0), (8, 7, "2026-10-02", 0), (7, 2, "2026-10-05", 1), (1, 6, "2026-10-07", 0)]

TABLE_NAMES = {"students": "الطلاب", "subjects": "المواد", "grades": "الدرجات", "books": "الكتب", "loans": "الإعارات"}


class SQLError(ValueError):
    pass


def _authorizer(action, a1, a2, db, trigger):
    if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (a2 or "").lower() in ("load_extension", "readfile", "writefile"):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


class _Con(sqlite3.Connection):
    _aba_steps: list


def new_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:", check_same_thread=False, factory=_Con)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO students VALUES (?,?,?,?,?)", STUDENTS)
    con.executemany("INSERT INTO subjects VALUES (?,?,?)", SUBJECTS)
    con.executemany("INSERT INTO grades VALUES (?,?,?)", GRADES)
    con.executemany("INSERT INTO books VALUES (?,?,?,?,?,?)", BOOKS)
    con.executemany("INSERT INTO loans VALUES (?,?,?,?)", LOANS)
    con.commit()
    con.set_authorizer(_authorizer)
    steps = [0]

    def progress():
        steps[0] += 1
        return 1 if steps[0] > 5000 else 0          # 5000 × 1000 VM steps
    con.set_progress_handler(progress, 1000)
    con._aba_steps = steps
    return con


@dataclass
class Result:
    columns: List[str]
    rows: List[Tuple]
    message: str = ""

    def text(self, limit: int = 50) -> str:
        if not self.columns:
            return self.message
        lines = [" | ".join(self.columns)]
        for r in self.rows[:limit]:
            lines.append(" | ".join("فارغ" if v is None else str(v) for v in r))
        if len(self.rows) > limit:
            lines.append(f"... و{len(self.rows) - limit} صفًّا أخرى")
        return "\n".join(lines)

    def spoken_rows(self) -> List[str]:
        return ["، ".join(f"{c} {('فارغ' if v is None else v)}" for c, v in zip(self.columns, r)) for r in self.rows]


def run(con: sqlite3.Connection, sql: str) -> Result:
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        raise SQLError("اكتب استعلامًا.")
    if ";" in sql:
        raise SQLError("نفّذ استعلامًا واحدًا في كل مرّة.")
    con._aba_steps[0] = 0                             # type: ignore[attr-defined]
    try:
        cur = con.execute(sql)
    except sqlite3.OperationalError as e:
        msg = str(e)
        if "interrupted" in msg:
            raise SQLError("توقّف الاستعلام لأنه طال كثيرًا.")
        if "not authorized" in msg:
            raise SQLError("هذا الأمر غير مسموح في المختبر.")
        raise SQLError(f"خطأ في الاستعلام: {msg}")
    except sqlite3.Error as e:
        if "not authorized" in str(e):
            raise SQLError("هذا الأمر غير مسموح في المختبر.")
        raise SQLError(f"خطأ: {e}")
    if cur.description is None:
        con.commit()
        n = cur.rowcount
        return Result([], [], f"تمّ التنفيذ. عدد الصفوف المتأثّرة {n}." if n >= 0 else "تمّ التنفيذ.")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchmany(1000)
    return Result(cols, rows, f"{len(rows)} صفًّا")


def describe_tables(con: sqlite3.Connection) -> List[str]:
    out = []
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid"):
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({name})")]
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        out.append(f"{name} ({TABLE_NAMES.get(name, '')}): {n} صفًّا، الأعمدة {', '.join(cols)}")
    return out


@dataclass
class Exercise:
    title: str
    task: str
    answer: str
    hint: str
    ordered: bool = False


EXERCISES = [
    Exercise("كل الصفوف", "اعرض كل أعمدة جدول الطلاب.", "SELECT * FROM students", "SELECT * FROM اسم_الجدول"),
    Exercise("أعمدة محدّدة", "اعرض اسم كل طالب ومدينته فقط.", "SELECT name, city FROM students",
             "اكتب أسماء الأعمدة بعد SELECT مفصولة بفاصلة."),
    Exercise("الشرط WHERE", "اعرض أسماء الطلاب الذين أعمارهم أكبر من 15.", "SELECT name FROM students WHERE age > 15",
             "WHERE age > 15"),
    Exercise("النصوص", "اعرض الطالب الذي من مدينة القدس.", "SELECT * FROM students WHERE city = 'القدس'",
             "النصوص بين علامتي تنصيص مفردة: 'القدس'"),
    Exercise("الترتيب", "اعرض أسماء الكتب مرتّبة من الأقدم إلى الأحدث.", "SELECT title FROM books ORDER BY year",
             "ORDER BY year", ordered=True),
    Exercise("الترتيب التنازلي والحدّ", "اعرض عناوين أطول ثلاثة كتب عدد صفحات.",
             "SELECT title FROM books ORDER BY pages DESC LIMIT 3", "ORDER BY pages DESC LIMIT 3", ordered=True),
    Exercise("AND و OR", "اعرض كتب غسان كنفاني المتوفّرة بطريقة برايل (braille = 1).",
             "SELECT * FROM books WHERE author = 'غسان كنفاني' AND braille = 1", "اجمع شرطين بـ AND."),
    Exercise("LIKE", "اعرض الكتب التي يبدأ عنوانها بكلمة ال.", "SELECT * FROM books WHERE title LIKE 'ال%'",
             "LIKE 'ال%' تعني يبدأ بـ ال."),
    Exercise("العدّ COUNT", "كم طالبًا في الجدول؟", "SELECT COUNT(*) FROM students", "SELECT COUNT(*) FROM ..."),
    Exercise("المتوسّط AVG", "ما متوسّط الدرجات كلها؟", "SELECT AVG(score) FROM grades", "AVG(score)"),
    Exercise("التجميع GROUP BY", "اعرض كل مؤلّف وعدد كتبه.", "SELECT author, COUNT(*) FROM books GROUP BY author",
             "GROUP BY author مع COUNT(*)"),
    Exercise("HAVING", "اعرض المؤلّفين الذين لهم أكثر من كتاب واحد.",
             "SELECT author FROM books GROUP BY author HAVING COUNT(*) > 1", "HAVING بعد GROUP BY"),
    Exercise("الربط JOIN", "اعرض اسم كل طالب مع درجاته (الاسم والدرجة).",
             "SELECT students.name, grades.score FROM students JOIN grades ON students.id = grades.student_id",
             "JOIN grades ON students.id = grades.student_id"),
    Exercise("ربط ثلاثة جداول", "اعرض اسم الطالب واسم المادة والدرجة لكل درجة.",
             "SELECT s.name, j.title, g.score FROM grades g JOIN students s ON s.id = g.student_id "
             "JOIN subjects j ON j.id = g.subject_id", "اربط grades بـ students ثم بـ subjects."),
    Exercise("متوسّط كل طالب", "اعرض اسم كل طالب ومتوسّط درجاته.",
             "SELECT s.name, AVG(g.score) FROM students s JOIN grades g ON s.id = g.student_id GROUP BY s.id",
             "JOIN ثم GROUP BY s.id مع AVG"),
    Exercise("استعلام فرعي", "اعرض أسماء الطلاب الذين استعاروا كتبًا ولم يعيدوها (returned = 0).",
             "SELECT name FROM students WHERE id IN (SELECT student_id FROM loans WHERE returned = 0)",
             "WHERE id IN (SELECT ...)"),
    Exercise("LEFT JOIN", "اعرض عناوين الكتب التي لم يستعرها أحد.",
             "SELECT b.title FROM books b LEFT JOIN loans l ON b.id = l.book_id WHERE l.book_id IS NULL",
             "LEFT JOIN ثم WHERE ... IS NULL"),
    Exercise("الإدراج INSERT", "أضف مادة جديدة اسمها الفيزياء بعدد ساعات 4 ورقمها 6، ثم تُفحص المواد كلها.",
             "INSERT INTO subjects VALUES (6, 'الفيزياء', 4)", "INSERT INTO subjects VALUES (...)"),
    Exercise("التعديل UPDATE", "ارفع عمر الطالبة مريم إلى 15، ثم يُفحص جدول الطلاب.",
             "UPDATE students SET age = 15 WHERE name = 'مريم'", "UPDATE ... SET ... WHERE ..."),
    Exercise("الحذف DELETE", "احذف الإعارات التي أُعيدت (returned = 1)، ثم يُفحص جدول الإعارات.",
             "DELETE FROM loans WHERE returned = 1", "DELETE FROM ... WHERE ..."),
]
_WRITE_CHECK = {"INSERT": "SELECT * FROM subjects ORDER BY id", "UPDATE": "SELECT * FROM students ORDER BY id",
                "DELETE": "SELECT * FROM loans ORDER BY rowid"}


def _norm(rows: Sequence[Tuple], ordered: bool) -> list:
    r = [tuple(round(v, 4) if isinstance(v, float) else v for v in row) for row in rows]
    return r if ordered else sorted(r, key=repr)


def check(ex: Exercise, sql: str) -> Tuple[bool, str]:
    verb = ex.answer.split()[0].upper()
    if verb in _WRITE_CHECK:
        mine, ref = new_db(), new_db()
        run(mine, sql)
        run(ref, ex.answer)
        a = run(mine, _WRITE_CHECK[verb]).rows
        b = run(ref, _WRITE_CHECK[verb]).rows
        ok = _norm(a, True) == _norm(b, True)
        return ok, ("صحيح! الجدول صار كما يجب." if ok else "الجدول بعد استعلامك لا يطابق المطلوب.")
    mine = run(new_db(), sql)
    ref = run(new_db(), ex.answer)
    if not mine.columns:
        return False, "المطلوب استعلام يعرض نتيجة."
    if len(mine.columns) != len(ref.columns):
        return False, f"عدد الأعمدة في نتيجتك {len(mine.columns)} والمطلوب {len(ref.columns)}."
    if len(mine.rows) != len(ref.rows):
        return False, f"عدد الصفوف في نتيجتك {len(mine.rows)} والمطلوب {len(ref.rows)}."
    ok = _norm(mine.rows, ex.ordered) == _norm(ref.rows, ex.ordered)
    if ok:
        return True, "صحيح! أحسنت."
    return False, "عدد الصفوف صحيح لكن القيم أو ترتيبها مختلفة."
