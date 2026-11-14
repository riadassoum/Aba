# -*- coding: utf-8 -*-
"""
abaAcademy.study_hub.weekly_report
==================================

تقرير أسبوعي: one spoken summary of the learner's week across the tools
that keep their own records — study planner minutes and upcoming exams,
pomodoro focus time, the khatma plan, tasbih totals, times-table weak
facts, Morse lessons reached, quiz results and best game scores — exported
as an RTL HTML page a parent or teacher can open.
"""

from __future__ import annotations

import datetime
import html
import json
from typing import List, Optional, Tuple

from ..tools.ar_count import count


def _get(store, key, default=""):
    try:
        v = store.get_setting(key, default)
        return default if v is None else v
    except Exception:
        return default


def _pomodoro_week(store, today: datetime.date) -> int:
    total = 0
    for k in range(7):
        d = (today - datetime.timedelta(days=k)).isoformat()
        try:
            total += int(_get(store, f"pomodoro_{d}", "0") or 0)
        except ValueError:
            pass
    return total // 60


def sections(store, today: Optional[datetime.date] = None,
             quran_index=None) -> List[Tuple[str, List[str]]]:
    today = today or datetime.date.today()
    out: List[Tuple[str, List[str]]] = []

    # study planner
    from .planner import Planner
    p = Planner(store)
    week = p.week_minutes(today)
    lines = [f"ذاكرت هذا الأسبوع {count(sum(week.values()), 'minute')} مسجّلة في المخطّط."]
    soon = p.upcoming(7, today)
    for i in soon[:5]:
        lines.append(p.describe(i, today))
    late = [i for i in p.items() if i.days_left(today) < 0]
    if late:
        lines.append(f"مهامّ فات موعدها: {'، '.join(i.title for i in late[:5])}.")
    out.append(("المذاكرة", lines))

    focus = _pomodoro_week(store, today)
    if focus:
        out.append(("التركيز", [f"جلسات بومودورو هذا الأسبوع: {count(focus, 'minute')}."]))

    # khatma
    if quran_index is not None:
        from ..quran_engine import khatma
        plan = khatma.KhatmaStore(store).load()
        if plan is not None:
            out.append(("ختمة القرآن", khatma.status(quran_index, plan, today)[1:]))

    # tasbih
    try:
        from ..tools import tasbih
        c = tasbih.load(store)
        days = [(today - datetime.timedelta(days=k)).isoformat() for k in range(7)]
        wk = sum(c.daily.get(d, 0) for d in days)
        if wk:
            out.append(("الأذكار", [f"سبّحت هذا الأسبوع {count(wk, 'time')}، واليوم {count(c.daily.get(today.isoformat(), 0), 'time')}."]))
    except Exception:
        pass

    # skills
    skills = []
    try:
        weights = json.loads(_get(store, "times_weights", "{}") or "{}")
        weak = [k.replace("x", " × ") for k, v in sorted(weights.items(), key=lambda kv: -kv[1]) if v > 1.0][:5]
        if weak:
            skills.append("حقائق جدول الضرب التي تحتاج تدريبًا: " + "، ".join(weak) + ".")
    except Exception:
        pass
    for alpha, name in (("ar", "العربية"), ("en", "اللاتينية")):
        lesson = _get(store, f"morse_lesson_{alpha}", "")
        if lesson and lesson != "1":
            skills.append(f"وصلت في مورس بالحروف {name} إلى الدرس {lesson}.")
    if skills:
        out.append(("المهارات", skills))

    # quizzes
    try:
        from ..teacher.quiz_builder import QuizStore
        res = QuizStore(store).results()
        recent = [a for a in res if a.started >= (datetime.datetime.combine(
            today - datetime.timedelta(days=6), datetime.time()).timestamp())]
        if recent:
            avg = sum(a.percent for a in recent) / len(recent)
            out.append(("الاختبارات", [f"حللت هذا الأسبوع {count(len(recent), 'case')} من الاختبارات، "
                                         f"بمتوسّط {avg:.0f}٪."]))
    except Exception:
        pass

    # games
    try:
        scores = json.loads(_get(store, "game_scores", "{}") or "{}")
        if scores:
            from ..gui.games import HighScores
            names = HighScores.NAMES
        else:
            names = {}
    except Exception:
        scores, names = {}, {}
    if scores:
        best = [f"{names.get(k, k)}: {v}" for k, v in list(scores.items())[:8]]
        out.append(("أفضل النتائج في الألعاب", best))
    return out


def text(store, today=None, quran_index=None) -> str:
    parts = []
    for title, lines in sections(store, today, quran_index):
        parts.append(title + ":\n" + "\n".join(lines))
    return "\n\n".join(parts)


def to_html(store, student: str = "", today=None, quran_index=None) -> str:
    today = today or datetime.date.today()
    rows = []
    for title, lines in sections(store, today, quran_index):
        items = "".join(f"<li>{html.escape(l)}</li>" for l in lines)
        rows.append(f"<h2>{html.escape(title)}</h2><ul>{items}</ul>")
    who = f" — {html.escape(student)}" if student else ""
    return (f'<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
            f"<title>التقرير الأسبوعي{who}</title>"
            "<style>body{font-family:'Traditional Arabic',Amiri,serif;font-size:18px;max-width:48em;"
            "margin:2em auto;line-height:1.7}h1{color:#14532d}h2{color:#1e3a8a;border-bottom:1px solid #ccc}"
            "</style></head><body>"
            f"<h1>التقرير الأسبوعي{who}</h1><p>حتى {today.isoformat()}</p>"
            + "".join(rows) + "</body></html>")
