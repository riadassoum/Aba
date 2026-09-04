# -*- coding: utf-8 -*-
"""
abaAcademy.teacher.editor
=========================

A content-authoring API so teachers can create and validate lesson packs
without touching Python. It builds the same on-disk JSON layout the engine
loads, and reuses ``engine.schema`` to validate before publishing — so a
malformed lesson is caught at authoring time, not at a learner's runtime.

This module is intentionally UI-agnostic (pure functions + a small builder
class). A wx front end, a CLI, or an external tool can all drive it. The GUI
"teacher mode" screen (future) would sit on top of this.

Capabilities (mapping to the spec's teacher-mode list):
  * create a course / level / lesson skeleton on disk,
  * add theory text, examples, questions, and generated blocks to a lesson,
  * import media files into a lesson's media/ folder,
  * validate a whole course pack (returns Arabic problem strings),
  * "publish" = validate + write a pack manifest.
"""

from __future__ import annotations

import json
import os
import shutil
from typing import Any, Dict, List

from ..engine import schema


class LessonBuilder:
    """Accumulates blocks for one lesson, then writes the 5 JSON files."""

    def __init__(self, lesson_id: str, title: str, order: int = 0):
        self.meta: Dict[str, Any] = {
            "lesson_id": lesson_id, "title": title, "order": order,
            "objectives": [], "grammar_refs": [], "difficulty": 1,
        }
        self.theory: List[Dict] = []
        self.practice: List[Dict] = []
        self.review: List[Dict] = []
        self.quiz: List[Dict] = []

    def objective(self, text: str) -> "LessonBuilder":
        self.meta["objectives"].append(text)
        return self

    def text(self, phase: str, content: str) -> "LessonBuilder":
        self._phase(phase).append({"btype": "text", "text": content})
        return self

    def example(self, phase: str, content: str, note: str = "") -> "LessonBuilder":
        self._phase(phase).append({"btype": "example", "text": content, "note": note})
        return self

    def mcq(self, phase: str, prompt: str, options: List[str], correct_index: int,
            explanation: str = "", topic: str = "") -> "LessonBuilder":
        self._phase(phase).append({"btype": "question", "question": {
            "qtype": "mcq", "prompt": prompt, "options": options,
            "correct": correct_index, "explanation": explanation, "topic": topic}})
        return self

    def typing(self, phase: str, prompt: str, correct: str, accepted: List[str] = None,
               explanation: str = "", topic: str = "") -> "LessonBuilder":
        self._phase(phase).append({"btype": "question", "question": {
            "qtype": "typing", "prompt": prompt, "correct": correct,
            "accepted": accepted or [], "explanation": explanation, "topic": topic}})
        return self

    def generated(self, phase: str, generator: str, count: int = 8,
                  params: Dict = None, data: str = None) -> "LessonBuilder":
        block = {"btype": "generated", "generator": generator, "count": count,
                 "params": params or {}}
        if data:
            block["data"] = data
        self._phase(phase).append(block)
        return self

    def _phase(self, phase: str) -> List[Dict]:
        return {"theory": self.theory, "practice": self.practice,
                "review": self.review, "quiz": self.quiz}[phase]

    def validate(self) -> List[str]:
        problems = schema.validate_lesson_meta(self.meta, self.meta["lesson_id"])
        for phase, blocks in (("theory", self.theory), ("practice", self.practice),
                              ("review", self.review), ("quiz", self.quiz)):
            problems += schema.validate_block_file({"blocks": blocks},
                                                   f"{self.meta['lesson_id']}/{phase}")
        return problems

    def write(self, level_dir: str) -> List[str]:
        problems = self.validate()
        if problems:
            return problems
        lesson_dir = os.path.join(level_dir, self.meta["lesson_id"])
        os.makedirs(lesson_dir, exist_ok=True)
        payloads = {
            "lesson.json": self.meta,
            "theory.json": {"blocks": self.theory},
            "practice.json": {"blocks": self.practice},
            "review.json": {"blocks": self.review},
            "quiz.json": {"blocks": self.quiz},
        }
        for fn, payload in payloads.items():
            with open(os.path.join(lesson_dir, fn), "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=1)
        return []


class CoursePackEditor:
    """Create a course skeleton and publish it after validation."""

    def __init__(self, courses_root: str, course_id: str, title: str,
                 description: str = ""):
        self.courses_root = courses_root
        self.course_id = course_id
        self.course_path = os.path.join(courses_root, course_id)
        self.title = title
        self.description = description
        self._levels: List[Dict[str, Any]] = []

    def add_level(self, level_id: str, title: str, order: int = 0) -> str:
        level_dir = os.path.join(self.course_path, "levels", level_id)
        os.makedirs(level_dir, exist_ok=True)
        self._levels.append({"level_id": level_id, "title": title,
                             "order": order, "lessons": []})
        return level_dir

    def register_lesson(self, level_id: str, builder: LessonBuilder) -> None:
        for lv in self._levels:
            if lv["level_id"] == level_id:
                lv["lessons"].append({
                    "lesson_id": builder.meta["lesson_id"],
                    "title": builder.meta["title"],
                    "order": builder.meta["order"],
                    "objectives": builder.meta["objectives"],
                    "grammar_refs": builder.meta["grammar_refs"],
                    "difficulty": builder.meta["difficulty"],
                })

    def import_media(self, level_id: str, lesson_id: str, src_path: str) -> str:
        media_dir = os.path.join(self.course_path, "levels", level_id, lesson_id, "media")
        os.makedirs(media_dir, exist_ok=True)
        dst = os.path.join(media_dir, os.path.basename(src_path))
        shutil.copy2(src_path, dst)
        return dst

    def publish(self) -> List[str]:
        manifest = {
            "course_id": self.course_id, "title": self.title,
            "description": self.description, "order": 0, "version": "1.0.0",
            "levels": self._levels,
        }
        problems = schema.validate_course_file(manifest, "course.json")
        if problems:
            return problems
        os.makedirs(self.course_path, exist_ok=True)
        with open(os.path.join(self.course_path, "course.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        return []


def validate_pack(course_path: str) -> List[str]:
    """Validate an on-disk course pack end to end; returns Arabic problems."""
    problems: List[str] = []
    manifest_path = os.path.join(course_path, "course.json")
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError) as e:
        return [f"تعذّر قراءة course.json: {e}"]
    problems += schema.validate_course_file(manifest, "course.json")
    for lv in manifest.get("levels", []):
        for lm in lv.get("lessons", []):
            ldir = os.path.join(course_path, "levels", lv["level_id"], lm["lesson_id"])
            for phase in ("theory", "practice", "review", "quiz"):
                fp = os.path.join(ldir, f"{phase}.json")
                if os.path.isfile(fp):
                    try:
                        with open(fp, encoding="utf-8") as f:
                            problems += schema.validate_block_file(json.load(f),
                                                                   f"{lm['lesson_id']}/{phase}")
                    except (OSError, ValueError) as e:
                        problems.append(f"[{lm['lesson_id']}/{phase}] خطأ قراءة: {e}")
    return problems
