# -*- coding: utf-8 -*-
"""
abaAcademy.engine.schema
========================

The JSON contract for course packs, plus a dependency-free validator.

A course pack on disk looks like::

    courses/<course_id>/
        course.json                 # course + levels + lesson index
        levels/<level_id>/<lesson_id>/
            lesson.json             # metadata (objectives, refs, order)
            theory.json             # ordered teaching blocks
            practice.json           # ordered practice blocks
            review.json             # ordered review blocks
            quiz.json               # ordered quiz blocks
            media/                  # optional audio/other assets

Every ``*.json`` block file is simply ``{"blocks": [ <block>, ... ]}``.

A ``<block>`` is ``{"btype": "<BlockType>", ... type-specific fields ...}``.
For ``btype == "question"`` the block carries a ``question`` object; for
``btype == "generated"`` it carries ``generator`` (an id) and ``count``.

The validator returns a list of human-readable problems (in Arabic) so the
teacher/editor tool can surface them. An empty list means the file is valid.
This is intentionally hand-rolled rather than jsonschema so the add-on has
zero third-party dependencies inside NVDA.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .models import BlockType, QuestionType

BLOCK_TYPES = {b.value for b in BlockType}
QUESTION_TYPES = {q.value for q in QuestionType}


def _err(problems: List[str], where: str, msg: str) -> None:
    problems.append(f"[{where}] {msg}")


def validate_question(obj: Dict[str, Any], where: str, problems: List[str]) -> None:
    qt = obj.get("qtype")
    if qt not in QUESTION_TYPES:
        _err(problems, where, f"نوع سؤال غير معروف: {qt!r}")
        return
    if "prompt" not in obj or not str(obj.get("prompt", "")).strip():
        _err(problems, where, "السؤال بلا نص (prompt).")
    if "correct" not in obj:
        _err(problems, where, "السؤال بلا إجابة صحيحة (correct).")
    if qt in {"mcq", "multi_select", "ordering"}:
        opts = obj.get("options")
        if not isinstance(opts, list) or len(opts) < 2:
            _err(problems, where, "يحتاج هذا النوع إلى قائمة خيارات من عنصرين على الأقل.")
        if qt == "mcq" and isinstance(obj.get("correct"), int):
            if opts and not (0 <= obj["correct"] < len(opts)):
                _err(problems, where, "قيمة correct خارج نطاق الخيارات.")


def validate_block(obj: Dict[str, Any], where: str, problems: List[str]) -> None:
    bt = obj.get("btype")
    if bt not in BLOCK_TYPES:
        _err(problems, where, f"نوع كتلة غير معروف: {bt!r}")
        return
    if bt == "question":
        q = obj.get("question")
        if not isinstance(q, dict):
            _err(problems, where, "كتلة سؤال بلا كائن question.")
        else:
            validate_question(q, where + ".question", problems)
    elif bt == "exam":
        qs = obj.get("questions")
        if not isinstance(qs, list) or not qs:
            _err(problems, where, "كتلة امتحان بلا أسئلة.")
        else:
            for i, q in enumerate(qs):
                validate_question(q, f"{where}.questions[{i}]", problems)
    elif bt == "generated":
        if not obj.get("generator"):
            _err(problems, where, "كتلة مولّدة بلا معرّف generator.")
    elif bt in {"text", "example", "reading", "dialogue"}:
        if not str(obj.get("text", obj.get("passage", ""))).strip() and bt != "dialogue":
            _err(problems, where, "كتلة نصية بلا محتوى.")


def validate_block_file(obj: Dict[str, Any], filename: str) -> List[str]:
    problems: List[str] = []
    blocks = obj.get("blocks")
    if not isinstance(blocks, list):
        _err(problems, filename, "الملف يجب أن يحتوي على مفتاح blocks كقائمة.")
        return problems
    for i, b in enumerate(blocks):
        if not isinstance(b, dict):
            _err(problems, f"{filename}.blocks[{i}]", "الكتلة ليست كائناً.")
            continue
        validate_block(b, f"{filename}.blocks[{i}]", problems)
    return problems


def validate_lesson_meta(obj: Dict[str, Any], filename: str) -> List[str]:
    problems: List[str] = []
    for key in ("lesson_id", "title"):
        if not str(obj.get(key, "")).strip():
            _err(problems, filename, f"حقل مطلوب مفقود: {key}")
    if "objectives" in obj and not isinstance(obj["objectives"], list):
        _err(problems, filename, "objectives يجب أن تكون قائمة.")
    return problems


def validate_course_file(obj: Dict[str, Any], filename: str) -> List[str]:
    problems: List[str] = []
    for key in ("course_id", "title"):
        if not str(obj.get(key, "")).strip():
            _err(problems, filename, f"حقل مطلوب مفقود: {key}")
    levels = obj.get("levels")
    if not isinstance(levels, list) or not levels:
        _err(problems, filename, "الدورة بلا مستويات (levels).")
    return problems
