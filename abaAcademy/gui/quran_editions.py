# -*- coding: utf-8 -*-
"""
abaAcademy.gui.quran_editions
=============================

Gives the reader access to the whole Tanzil / alquran.cloud edition catalogue:
14 Arabic scripts (not only Uthmani), 6 tafsirs, 124 translations, and
transliterations. A handful are bundled for instant offline use
(resources/quran/ed_*.json); every other edition is fetched once on demand and
cached on disk, so all of them become available without shipping hundreds of
megabytes inside the add-on.

Lookup order for an edition's text: already-loaded in memory -> bundled file ->
on-disk cache -> download the whole edition, cache it, then serve.
"""

from __future__ import annotations

import json
import os
from .net import fetch_text

EDITION_API = "https://api.alquran.cloud/v1/quran/{edition}"


class QuranEditions:
    def __init__(self, res_dir, cache_dir, uthmani=None):
        self.res_dir = res_dir
        self.cache_dir = cache_dir
        self._loaded = {}          # id -> [6236 strings]
        if uthmani is not None:
            self._loaded["quran-uthmani"] = uthmani
        try:
            with open(os.path.join(res_dir, "editions.json"), "r", encoding="utf-8") as f:
                self.catalog = json.load(f)
        except Exception:
            self.catalog = []

    # -- catalogue ---------------------------------------------------------

    def by_type(self, etype):
        return [e for e in self.catalog if e.get("type") == etype]

    def label(self, e):
        name = e.get("name") or e.get("id", "")
        lang = e.get("lang", "")
        return f"{lang} — {name}" if lang and e.get("type") != "quran" else name

    def find_index(self, editions, edition_id):
        for i, e in enumerate(editions):
            if e.get("id") == edition_id:
                return i
        return 0

    # -- text access -------------------------------------------------------

    def is_offline(self, edition_id):
        if edition_id in self._loaded:
            return True
        return (os.path.exists(os.path.join(self.res_dir, f"ed_{edition_id}.json"))
                or os.path.exists(os.path.join(self.cache_dir, f"ed_{edition_id}.json")))

    def get_edition(self, edition_id):
        """Return the full 6236-item list if available offline, else None."""
        if edition_id in self._loaded:
            return self._loaded[edition_id]
        for base in (self.res_dir, self.cache_dir):
            p = os.path.join(base, f"ed_{edition_id}.json")
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        arr = json.load(f)
                    self._loaded[edition_id] = arr
                    return arr
                except Exception:
                    return None
        return None

    def fetch_edition(self, edition_id):
        """Blocking: download a whole edition, cache it, return the list (or None).
        Call from a worker thread."""
        arr = self.get_edition(edition_id)
        if arr is not None:
            return arr
        try:
            url = EDITION_API.format(edition=edition_id)
            raw = fetch_text(url, timeout=40)
            if raw is None:
                return None
            d = json.loads(raw)
            if d.get("code") != 200:
                return None
            out = [None] * 6236
            for s in d["data"]["surahs"]:
                for ay in s["ayahs"]:
                    out[ay["number"] - 1] = (ay["text"] or "").replace("\ufeff", "").strip()
            os.makedirs(self.cache_dir, exist_ok=True)
            tmp = os.path.join(self.cache_dir, f"ed_{edition_id}.json.part")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, os.path.join(self.cache_dir, f"ed_{edition_id}.json"))
            self._loaded[edition_id] = out
            return out
        except Exception:
            return None

    def text(self, edition_id, global_num):
        """One ayah's text if the edition is already available offline, else None."""
        arr = self.get_edition(edition_id)
        if arr and 1 <= global_num <= len(arr):
            return arr[global_num - 1]
        return None
