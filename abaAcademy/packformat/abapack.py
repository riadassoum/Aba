# -*- coding: utf-8 -*-
"""
abaAcademy.packformat.abapack
=============================

The ``.abapack`` course-pack format: a clean, zip-based container that lets a
teacher author a custom course, quiz, or flashcard set and share it with
students, who import it in one step.

Why a new format
----------------
The academy already loads courses from ``user_data_dir/courses``. A ``.abapack``
is simply a portable, validated bundle of exactly that content plus a manifest,
so a teacher can hand a single file to a student (email, USB, chat) and the
student imports it without touching folders. Everything is plain JSON inside a
zip — open, inspectable, and forgeable by hand if desired.

Structure of a .abapack (a zip file)::

    pack.json                     # manifest (required)
    course/course.json            # the course definition (optional)
    course/levels/.../lesson.json # lesson + block files (optional)
    flashcards/<deck>.json        # flashcard decks (optional)

The manifest ``pack.json``::

    {
      "abapack_version": 1,
      "id": "teacher.geography.rivers",
      "title": "أنهار العالم",
      "author": "اسم المعلّم",
      "description": "...",
      "created": "2026-01-01",
      "contains": ["course", "flashcards"]
    }

Design goals: never overwrite a student's data silently, validate before
installing, and fail loudly with a clear Arabic message rather than corrupting
the courses folder.
"""

from __future__ import annotations

import io
import json
import os
import re
import time
import zipfile


ABAPACK_VERSION = 1
_ID_RE = re.compile(r"^[A-Za-z0-9._-]{3,64}$")


class PackError(Exception):
    """Raised with an Arabic, user-facing message when a pack is invalid."""


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------

def make_manifest(pack_id, title, author="", description="", contains=None):
    if not _ID_RE.match(pack_id or ""):
        raise PackError("معرّف الحزمة غير صالح؛ استخدم أحرفاً وأرقاماً لاتينية ونقاطاً فقط.")
    return {
        "abapack_version": ABAPACK_VERSION,
        "id": pack_id,
        "title": title or pack_id,
        "author": author,
        "description": description,
        "created": time.strftime("%Y-%m-%d"),
        "contains": contains or [],
    }


def validate_manifest(man):
    if not isinstance(man, dict):
        raise PackError("ملف الحزمة تالف: البيان غير صحيح.")
    if man.get("abapack_version") != ABAPACK_VERSION:
        raise PackError("إصدار الحزمة غير مدعوم في هذه النسخة.")
    if not _ID_RE.match(str(man.get("id", ""))):
        raise PackError("معرّف الحزمة غير صالح.")
    return True


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

class PackBuilder:
    """Assemble a .abapack in memory, then write it to disk. A teacher tool (or
    a future authoring screen) feeds it a course dict and/or flashcard decks."""

    def __init__(self, pack_id, title, author="", description=""):
        self._man = make_manifest(pack_id, title, author, description)
        self._files = {}          # arcname -> bytes
        self._contains = set()

    def add_course(self, course_dict, lessons=None):
        """Add a course.json (dict) and optional lesson files.

        ``lessons`` is a dict of ``relative_path -> lesson_dict`` where the path
        is e.g. ``levels/rivers/lesson0/quiz.json``."""
        self._put("course/course.json", course_dict)
        for rel, data in (lessons or {}).items():
            safe = _safe_relpath(rel)
            self._put(f"course/{safe}", data)
        self._contains.add("course")

    def add_flashcard_deck(self, name, deck_dict):
        safe = _safe_relpath(name if name.endswith(".json") else name + ".json")
        self._put(f"flashcards/{safe}", deck_dict)
        self._contains.add("flashcards")

    def _put(self, arcname, data):
        self._files[arcname] = json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8")

    def to_bytes(self):
        self._man["contains"] = sorted(self._contains)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("pack.json",
                       json.dumps(self._man, ensure_ascii=False, indent=1))
            for arc, data in self._files.items():
                z.writestr(arc, data)
        return buf.getvalue()

    def write(self, path):
        with open(path, "wb") as f:
            f.write(self.to_bytes())
        return path


# ---------------------------------------------------------------------------
# import / inspect
# ---------------------------------------------------------------------------

class PackReader:
    """Open and validate a .abapack, expose its manifest, and install it into the
    user's courses / flashcards folders without clobbering existing data."""

    def __init__(self, path):
        self.path = path
        if not zipfile.is_zipfile(path):
            raise PackError("الملف ليس حزمة abapack صالحة.")
        self._zip = zipfile.ZipFile(path, "r")
        try:
            self.manifest = json.loads(self._zip.read("pack.json").decode("utf-8"))
        except KeyError:
            raise PackError("الحزمة لا تحتوي على ملف البيان pack.json.")
        except Exception:
            raise PackError("تعذّر قراءة بيان الحزمة.")
        validate_manifest(self.manifest)

    # -- inspection -------------------------------------------------------
    def summary(self):
        m = self.manifest
        parts = [f"«{m.get('title', m['id'])}»"]
        if m.get("author"):
            parts.append(f"إعداد {m['author']}")
        contains = m.get("contains", [])
        labels = {"course": "دورة", "flashcards": "بطاقات تعليمية"}
        if contains:
            parts.append("تحتوي على: " + "، ".join(labels.get(c, c) for c in contains))
        if m.get("description"):
            parts.append(m["description"])
        return "، ".join(parts) + "."

    def _members(self, prefix):
        return [n for n in self._zip.namelist()
                if n.startswith(prefix) and not n.endswith("/")]

    # -- installation -----------------------------------------------------
    def install(self, user_data_dir, overwrite=False):
        """Install the pack's content under ``user_data_dir``. Returns a short
        Arabic report of what was installed. Refuses to overwrite an existing
        course of the same id unless ``overwrite=True``."""
        installed = []
        contains = self.manifest.get("contains", [])

        if "course" in contains:
            installed.append(self._install_course(user_data_dir, overwrite))
        if "flashcards" in contains:
            installed.append(self._install_flashcards(user_data_dir, overwrite))

        if not installed:
            return "لا يوجد محتوى قابل للتثبيت في هذه الحزمة."
        return "تم التثبيت: " + "، ".join(installed) + "."

    def _install_course(self, user_data_dir, overwrite):
        try:
            course = json.loads(self._zip.read("course/course.json").decode("utf-8"))
        except Exception:
            raise PackError("تعذّر قراءة الدورة داخل الحزمة.")
        course_id = course.get("course_id") or self.manifest["id"]
        if not _ID_RE.match(str(course_id)):
            raise PackError("معرّف الدورة داخل الحزمة غير صالح.")
        dest = os.path.join(user_data_dir, "courses", _safe_name(course_id))
        if os.path.isdir(dest) and not overwrite:
            raise PackError(f"توجد دورة بالمعرّف {course_id} مسبقاً. "
                            f"فعّل الاستبدال إن أردت الكتابة فوقها.")
        # extract all course/* members under dest, path-safely
        for member in self._members("course/"):
            rel = member[len("course/"):]
            target = _join_safe(dest, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(self._zip.read(member))
        return f"دورة «{course.get('title', course_id)}»"

    def _install_flashcards(self, user_data_dir, overwrite):
        dest_dir = os.path.join(user_data_dir, "flashcards")
        os.makedirs(dest_dir, exist_ok=True)
        count = 0
        for member in self._members("flashcards/"):
            name = _safe_name(os.path.basename(member))
            target = os.path.join(dest_dir, name)
            if os.path.exists(target) and not overwrite:
                continue
            with open(target, "wb") as f:
                f.write(self._zip.read(member))
            count += 1
        return f"{count} حزمة بطاقات"

    def close(self):
        try:
            self._zip.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# path safety
# ---------------------------------------------------------------------------

def _safe_name(name):
    """A single safe filename component (no separators, no traversal)."""
    name = os.path.basename(name.replace("\\", "/"))
    if name in ("", ".", "..") or not _ID_RE.match(name.rsplit(".", 1)[0] if "." in name else name):
        # allow dots for extension but keep it strict otherwise
        cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        return cleaned or "item.json"
    return name


def _safe_relpath(rel):
    """Sanitise a relative path used inside the archive (forward slashes,
    no traversal)."""
    rel = rel.replace("\\", "/")
    parts = [p for p in rel.split("/") if p not in ("", ".", "..")]
    return "/".join(parts)


def _join_safe(base, rel):
    """Join base + rel, guaranteeing the result stays inside base (prevents zip
    path-traversal attacks)."""
    target = os.path.normpath(os.path.join(base, _safe_relpath(rel)))
    base_abs = os.path.normpath(base)
    if not (target == base_abs or target.startswith(base_abs + os.sep)):
        raise PackError("مسار غير آمن داخل الحزمة.")
    return target
