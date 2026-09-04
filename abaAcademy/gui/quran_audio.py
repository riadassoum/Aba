# -*- coding: utf-8 -*-
"""
abaAcademy.gui.quran_audio
==========================

On-device audio cache for the Qur'an reader. It makes navigation fast and
listening possible offline by pulling recitation files into the add-on's own
data folder:

  * ``cached()``   -> is this ayah already on disk?
  * ``fetch()``    -> download one ayah (blocking) and return its path
  * ``prefetch()`` -> quietly download upcoming ayat in the background so the
                      next "play" is instant
  * ``download_range()`` -> bulk-download a whole surah / juz for offline use

Files live under ``<user data>/quran_audio/<reciter>/<globalAyah>.mp3`` and are
reused across sessions, so each ayah is fetched at most once per reciter.
"""

from __future__ import annotations

import os
import threading
from .net import download_to

AUDIO_URL = "https://cdn.islamic.network/quran/audio/{bitrate}/{reciter}/{num}.mp3"


def verse_url(base, surah, ayah):
    """everyayah verse scheme: <base><surah:03d><ayah:03d>.mp3 (e.g. .../001002.mp3)."""
    return f"{base}{surah:03d}{ayah:03d}.mp3"


class QuranAudio:
    def __init__(self, cache_root):
        self.cache_root = cache_root
        self._prefetching = set()
        self._lock = threading.Lock()

    def _path(self, reciter, num):
        return os.path.join(self.cache_root, reciter, f"{num}.mp3")

    def cached(self, reciter, num):
        p = self._path(reciter, num)
        try:
            if os.path.exists(p) and os.path.getsize(p) > 0:
                return p
        except OSError:
            pass
        return None

    def fetch(self, reciter, bitrate, num, url=None):
        """Blocking download of one ayah; returns the cached path or None.
        ``reciter`` is used as the cache tag; ``url`` overrides the default
        alquran.cloud CDN scheme (used for mp3quran verse-style reciters)."""
        hit = self.cached(reciter, num)
        if hit:
            return hit
        p = self._path(reciter, num)
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            url = url or AUDIO_URL.format(bitrate=bitrate, reciter=reciter, num=num)
            if download_to(url, p, timeout=25) and os.path.getsize(p) > 0:
                return p
        except Exception:
            try:
                if os.path.exists(p + ".part"):
                    os.remove(p + ".part")
            except OSError:
                pass
        return None

    def prefetch(self, reciter, bitrate, numbers, url_for=None):
        """Background-download a list of ayah numbers, skipping cached ones.
        ``url_for(num)`` optionally supplies a custom URL per ayah."""
        todo = []
        with self._lock:
            for n in numbers:
                key = (reciter, n)
                if n and not self.cached(reciter, n) and key not in self._prefetching:
                    self._prefetching.add(key)
                    todo.append(n)
        if not todo:
            return

        def _run():
            for n in todo:
                self.fetch(reciter, bitrate, n, url=(url_for(n) if url_for else None))
                with self._lock:
                    self._prefetching.discard((reciter, n))

        threading.Thread(target=_run, daemon=True).start()

    def download_range(self, reciter, bitrate, numbers, progress=None, should_stop=None, url_for=None):
        """Bulk download (blocking — call from a worker thread). Calls
        ``progress(done, total)`` periodically; stops early if ``should_stop()``
        returns True. Already-cached ayat are counted as done immediately, so a
        partly-downloaded surah only fetches the missing ayat."""
        numbers = list(numbers)
        total = len(numbers)
        done = 0
        for n in numbers:
            if should_stop and should_stop():
                break
            if self.cached(reciter, n) is None:
                self.fetch(reciter, bitrate, n, url=(url_for(n) if url_for else None))
            done += 1
            if progress and (done % 3 == 0 or done == total):
                progress(done, total)
        if progress:
            progress(done, total)
        return done

    def missing_numbers(self, reciter, numbers):
        """Return the subset of ``numbers`` not yet cached for this reciter."""
        return [n for n in numbers if self.cached(reciter, n) is None]

    def all_cached(self, reciter, numbers):
        """True if every number is already downloaded for this reciter."""
        return all(self.cached(reciter, n) is not None for n in numbers)
