# -*- coding: utf-8 -*-
"""
abaAcademy.gui.net
==================

One small, robust place for the add-on's outbound HTTP. Everything that fetches
from the internet (dictionary, Qur'an editions, hadith collections, recitation
audio) goes through here so they all share the same behaviour:

* a real ``User-Agent`` — some public APIs reject the default ``Python-urllib``
  agent, which silently broke lookups/downloads before this was centralised;
* a sane timeout;
* one automatic retry on transient failure;
* never raising to the caller — failures return ``None`` / ``False`` so callers
  degrade gracefully instead of surfacing tracebacks.
"""

from __future__ import annotations

import time
import urllib.request

_UA = {"User-Agent": "Mozilla/5.0 (abaAcademy NVDA add-on)"}


def fetch_bytes(url, timeout=30, retries=1):
    """Return the response body as bytes, or None on failure."""
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001 - deliberately swallow, return None
            last = e
            if attempt < retries:
                time.sleep(0.6)
    return None


def fetch_text(url, timeout=30, retries=1, encoding="utf-8"):
    data = fetch_bytes(url, timeout=timeout, retries=retries)
    if data is None:
        return None
    try:
        return data.decode(encoding, "replace")
    except Exception:
        return None


def download_to(url, path, timeout=30, retries=1):
    """Download to ``path`` atomically (via a .part file). Returns True on success."""
    data = fetch_bytes(url, timeout=timeout, retries=retries)
    if not data:
        return False
    tmp = path + ".part"
    try:
        with open(tmp, "wb") as out:
            out.write(data)
        import os
        os.replace(tmp, path)
        return True
    except Exception:
        try:
            import os
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return False
