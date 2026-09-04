# -*- coding: utf-8 -*-
"""
abaAcademy.gui.hadith_data
==========================

Loads the major hadith collections (Kutub al-Sittah + Muwatta Malik). Only the
index and one collection are bundled; the rest download once on demand from the
public-domain fawazahmed0 hadith dataset and are cached under the user's the screen reader
data folder — same offline-friendly pattern as the Qur'an editions.
"""

from __future__ import annotations

import json
import os
from .net import fetch_text

CDN = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/ara-{book}.json"


class HadithData:
    def __init__(self, res_dir, cache_dir):
        self.res_dir = res_dir
        self.cache_dir = cache_dir
        self._loaded = {}
        try:
            with open(os.path.join(res_dir, "index.json"), "r", encoding="utf-8") as f:
                self.index = json.load(f)
        except Exception:
            self.index = []

    def is_offline(self, book_id):
        if book_id in self._loaded:
            return True
        return (os.path.exists(os.path.join(self.res_dir, f"{book_id}.json"))
                or os.path.exists(os.path.join(self.cache_dir, f"{book_id}.json")))

    def get(self, book_id):
        if book_id in self._loaded:
            return self._loaded[book_id]
        for base in (self.res_dir, self.cache_dir):
            p = os.path.join(base, f"{book_id}.json")
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        d = json.load(f)
                    self._loaded[book_id] = d
                    return d
                except Exception:
                    return None
        return None

    def fetch(self, book_id):
        """Blocking download of a whole collection (call from a worker thread).
        Reformats the raw dataset to the compact shape we bundle."""
        got = self.get(book_id)
        if got is not None:
            return got
        try:
            body = fetch_text(CDN.format(book=book_id), timeout=60)
            if body is None:
                return None
            raw = json.loads(body)
            meta = raw.get("metadata", {})
            name = next((b["name"] for b in self.index if b["id"] == book_id),
                        meta.get("name", book_id))
            hs = [[h.get("hadithnumber"), (h.get("text") or "").strip(), None]
                  for h in raw.get("hadiths", [])]
            payload = {"id": book_id, "name": name,
                       "sections": meta.get("sections", {}) or {}, "hadiths": hs}
            os.makedirs(self.cache_dir, exist_ok=True)
            tmp = os.path.join(self.cache_dir, f"{book_id}.json.part")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, os.path.join(self.cache_dir, f"{book_id}.json"))
            self._loaded[book_id] = payload
            return payload
        except Exception:
            return None

    def remove_cached(self, book_id):
        p = os.path.join(self.cache_dir, f"{book_id}.json")
        if os.path.exists(p):
            try:
                os.remove(p)
                self._loaded.pop(book_id, None)
                return True
            except OSError:
                return False
        return False
