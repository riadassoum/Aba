# -*- coding: utf-8 -*-
"""
abaAcademy.study_hub.notebook
=============================

A central quick-note store. The learner captures short notes (a Hadith number, an
Ayah reference, a dictionary word, a study reminder) into one searchable place,
and can export them to a plain-text or Markdown file. Notes live in a single JSON
file under the user's data directory, so they persist across sessions and are
easy to back up.

Pure standard library — ``json``, ``time``, ``os``. No network.
"""

from __future__ import annotations

import json
import os
import time


class Notebook:
    """A simple, persistent list of notes. Each note is a dict with ``id``,
    ``text``, ``tag``, and ``created`` (epoch seconds)."""

    def __init__(self, user_data_dir):
        self.path = os.path.join(user_data_dir, "notebook.json")
        self._notes = []
        self._next_id = 1
        self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self._notes = data.get("notes", [])
            self._next_id = data.get("next_id", len(self._notes) + 1)
        except Exception:
            self._notes = []
            self._next_id = 1

    def _save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"notes": self._notes, "next_id": self._next_id},
                          f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
            return True
        except Exception:
            return False

    # -- operations -------------------------------------------------------
    def add(self, text, tag=""):
        text = (text or "").strip()
        if not text:
            return None
        note = {"id": self._next_id, "text": text, "tag": tag.strip(),
                "created": time.time()}
        self._notes.append(note)
        self._next_id += 1
        self._save()
        return note

    def delete(self, note_id):
        before = len(self._notes)
        self._notes = [n for n in self._notes if n["id"] != note_id]
        if len(self._notes) != before:
            self._save()
            return True
        return False

    def all(self):
        return list(reversed(self._notes))     # newest first

    def search(self, query):
        q = (query or "").strip()
        if not q:
            return self.all()
        return [n for n in reversed(self._notes)
                if q in n["text"] or q in n.get("tag", "")]

    def tags(self):
        return sorted({n["tag"] for n in self._notes if n.get("tag")})

    # -- export -----------------------------------------------------------
    def export_text(self, path):
        lines = ["ملاحظاتي", "=" * 8, ""]
        for n in reversed(self._notes):
            when = time.strftime("%Y-%m-%d", time.localtime(n["created"]))
            tag = f" [{n['tag']}]" if n.get("tag") else ""
            lines.append(f"- ({when}){tag} {n['text']}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path

    def export_markdown(self, path):
        lines = ["# ملاحظاتي", ""]
        by_tag = {}
        for n in reversed(self._notes):
            by_tag.setdefault(n.get("tag") or "بدون تصنيف", []).append(n)
        for tag, notes in by_tag.items():
            lines.append(f"## {tag}")
            lines.append("")
            for n in notes:
                when = time.strftime("%Y-%m-%d", time.localtime(n["created"]))
                lines.append(f"- ({when}) {n['text']}")
            lines.append("")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path
