# -*- coding: utf-8 -*-
"""
abaAcademy.study_hub.overview
=============================

نظرة عامة على المتعلّم — one page for a parent, a teacher or a caretaker who
sits with the learner, and for the learner who wants everything at a glance:

* today: questions answered against the daily goal, study time, the streak;
* every course the learner has started, with how far they are, their average
  best score, and the next lesson waiting for them;
* the topics with the most mistakes, in plain Arabic;
* a suggested next step;
* the weekly report's sections (planner, focus, khatma, adhkar, skills,
  quizzes, games).

``sections`` returns plain (title, lines) pairs that a screen reads line by
line; ``to_html`` renders the same content as a large-print page that can be
printed or sent.
"""

from __future__ import annotations

import datetime
import html
from typing import List, Optional, Tuple

from ..tools.ar_count import count

Section = Tuple[str, List[str]]


def _topic_label(topic: str) -> str:
    try:
        from ..gui.mistakes_view import _topic_label_ar
        return _topic_label_ar(topic)
    except Exception:
        return topic


def _percent(a: int, b: int) -> int:
    return round(100 * a / b) if b else 0


def course_rows(academy) -> List[dict]:
    """One row per course: progress, average best score, the next lesson."""
    rows = []
    for c in academy.courses():
        total = c.lesson_count()
        done = academy.completed_lessons(c.course_id)
        scores, next_title, started = [], None, False
        for lv in c.levels:
            for m in lv.lesson_metas:
                prog = academy.store.get_lesson_progress(m.lesson_id)
                if prog:
                    started = True
                    if prog.get("best_score") is not None:
                        scores.append(int(prog.get("best_score") or 0))
                if next_title is None and not (prog and prog.get("completed")):
                    next_title = f"{lv.title}: {m.title}"
        rows.append({"course_id": c.course_id, "title": c.title, "done": done, "total": total,
                     "percent": _percent(done, total), "started": started or done > 0,
                     "average": round(sum(scores) / len(scores)) if scores else None,
                     "next": next_title})
    return rows


def today_lines(academy) -> List[str]:
    s = academy.home_summary()
    act = academy.store.today_activity()
    lines = []
    goal, answered = s.get("daily_goal", 0), s.get("today_answered", 0)
    if goal:
        state = "تحقّق هدف اليوم" if s.get("goal_met") else f"بقي {count(max(0, goal - answered), 'question')} لهدف اليوم"
        lines.append(f"أجاب اليوم عن {count(answered, 'question')} من {goal}؛ {state}.")
    minutes = int(act.get("seconds", 0)) // 60
    lines.append(f"وقت الدراسة اليوم: {count(minutes, 'minute')}." if minutes else "لم يدرس اليوم بعد.")
    correct = int(act.get("correct", 0))
    if act.get("answered"):
        lines.append(f"الإجابات الصحيحة اليوم: {correct} من {act['answered']} ({_percent(correct, act['answered'])}٪).")
    lines.append(f"سلسلة الأيام المتتالية: {count(s['streak'], 'day')}." if s["streak"] else "لا توجد سلسلة أيام بعد.")
    return lines


def course_lines(academy) -> List[str]:
    rows = course_rows(academy)
    started = [r for r in rows if r["started"]]
    lines = []
    for r in sorted(started, key=lambda r: -r["percent"]):
        line = f"{r['title']}: أنهى {r['done']} من {r['total']} درسًا ({r['percent']}٪)"
        if r["average"] is not None:
            line += f"، ومتوسّط أفضل نتائجه {r['average']}٪"
        if r["next"] and r["done"] < r["total"]:
            line += f". التالي: {r['next']}"
        lines.append(line + ".")
    rest = len(rows) - len(started)
    if not started:
        lines.append(f"لم يبدأ أيّ دورة بعد. الدورات المتاحة: {len(rows)}.")
    elif rest:
        lines.append(f"دورات لم تبدأ بعد: {rest}.")
    return lines


def weak_lines(academy, limit: int = 6) -> List[str]:
    try:
        weak = academy.store.weakest_topics(limit=limit)
    except Exception:
        weak = []
    lines = []
    for topic, wrong, right in weak:
        total = wrong + right
        lines.append(f"{_topic_label(topic)}: {count(wrong, 'error')} من {total} محاولة "
                     f"(صحيح {_percent(right, total)}٪).")
    return lines or ["لا توجد أخطاء متكرّرة مسجّلة."]


def next_step(academy) -> str:
    s = academy.home_summary()
    try:
        weak = academy.store.weakest_topics(limit=1)
    except Exception:
        weak = []
    if not s["answered"]:
        return "ابدأ بتدريب اليوم أو بأوّل درس في الدورة التي تختارها."
    if s["daily_goal"] and not s["goal_met"]:
        return "أكمل هدف اليوم بتدريب اليوم أو بالجلسة الذكية."
    if weak and weak[0][1] >= 3:
        return f"خصّص جلسة لتدريب نقاط الضعف، وأوّلها: {_topic_label(weak[0][0])}."
    started = [r for r in course_rows(academy) if r["started"] and r["done"] < r["total"]]
    if started:
        r = max(started, key=lambda r: r["percent"])
        return f"تابع {r['title']}" + (f": {r['next']}." if r["next"] else ".")
    return "راجع المراجعة المجدولة، ثم ابدأ دورة جديدة."


def sections(academy, today: Optional[datetime.date] = None, quran_index=None) -> List[Section]:
    out: List[Section] = [
        ("اليوم", today_lines(academy)),
        ("الدورات", course_lines(academy)),
        ("نقاط الضعف", weak_lines(academy)),
        ("الخطوة التالية المقترحة", [next_step(academy)]),
    ]
    try:
        from . import weekly_report
        out += weekly_report.sections(academy.store, today, quran_index)
    except Exception:
        pass
    return [(t, ls) for t, ls in out if ls]


def text(academy, today=None, quran_index=None) -> str:
    return "\n\n".join(t + ":\n" + "\n".join(ls) for t, ls in sections(academy, today, quran_index))


def to_html(academy, student: str = "", today=None, quran_index=None) -> str:
    today = today or datetime.date.today()
    body = []
    for title, lines in sections(academy, today, quran_index):
        items = "".join(f"<li>{html.escape(l)}</li>" for l in lines)
        body.append(f"<section><h2>{html.escape(title)}</h2><ul>{items}</ul></section>")
    who = f" — {html.escape(student)}" if student else ""
    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>نظرة عامة على المتعلّم{who}</title>
<style>
body {{ font-family: Tahoma, Arial, sans-serif; font-size: 22px; line-height: 1.7; background: #fff;
       color: #000; max-width: 52em; margin: 1em auto; padding: 0 1em; }}
h1 {{ font-size: 1.6em; border-bottom: 4px solid #000; padding-bottom: .2em; }}
h2 {{ font-size: 1.25em; background: #ffe066; padding: .2em .4em; }}
li {{ margin: .4em 0; }}
@media (prefers-color-scheme: dark) {{ body {{ background: #000; color: #ff0; }} h1 {{ border-color: #ff0; }}
  h2 {{ background: #333; color: #fff; }} }}
@media print {{ body {{ font-size: 16pt; }} h2 {{ background: none; border-bottom: 2px solid #000; }} }}
</style></head>
<body><h1>نظرة عامة على المتعلّم{who}</h1>
<p>التاريخ: {today.isoformat()}. أكاديمية الكفيف العربي.</p>
{''.join(body)}
</body></html>
"""
