# -*- coding: utf-8 -*-
"""
abaAcademy.gui.surah_player
===========================

A whole-surah audio player, distinct from the ayah-by-ayah player in the Mushaf.
Here each recitation is a single audio file for an entire surah (the
``server*.mp3quran.net/<reciter>/<SSS>.mp3`` scheme), so the student picks a
reciter and a surah and listens to the full surah continuously, with optional
auto-advance to the next surah.

The reciter list and whole-surah URL scheme are adapted from the al-bayan NVDA
project (GPL v3); the recitation audio is served by mp3quran.net. Downloaded
surahs are cached in the NVDA config folder for offline listening.
"""

from __future__ import annotations

import json
import os
import threading

from .accessible import AccessibleDialog
from .audio_player import AudioPlayer
from .download_helper import download_to

try:
    import wx
except Exception:
    wx = None


def _load_surah_reciters(res_dir):
    try:
        with open(os.path.join(res_dir, "quran", "surah_reciters.json"),
                  encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


class SurahAudio:
    """Cache + fetch for whole-surah files, kept separate from ayah audio."""

    def __init__(self, cache_root):
        self.root = cache_root

    def _path(self, tag, surah):
        d = os.path.join(self.root, "surah_audio", tag)
        return os.path.join(d, f"{surah:03d}.mp3")

    def cached(self, tag, surah):
        p = self._path(tag, surah)
        return p if os.path.exists(p) and os.path.getsize(p) > 0 else None

    def url(self, base, surah):
        return f"{base.rstrip('/')}/{surah:03d}.mp3"

    def fetch(self, tag, base, surah):
        hit = self.cached(tag, surah)
        if hit:
            return hit
        p = self._path(tag, surah)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if download_to(self.url(base, surah), p, timeout=60) and os.path.getsize(p) > 0:
            return p
        return None


class SurahPlayer(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "مشغّل السور الكاملة", speech, size=(640, 520))
        self.academy = academy
        res = getattr(academy, "resource_dir", None) or \
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources")
        self._reciters = _load_surah_reciters(res)
        self._surah_names = self._load_surah_names(res)
        self._audio = SurahAudio(os.path.join(getattr(academy, "user_data_dir", "."), ""))
        self._player = AudioPlayer(self, on_finished=self._on_finished)
        self._auto = False

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)

        s.Add(wx.StaticText(panel, label="القارئ:"), 0, wx.ALL, 4)
        self.recChoice = wx.Choice(panel, choices=[
            f"{r['name']}" + (f" — {r['rewaya']}" if r.get('rewaya') else "")
            for r in self._reciters])
        self.recChoice.SetName("اختيار القارئ")
        if self._reciters:
            self.recChoice.SetSelection(0)
        self.bind_choice(self.recChoice, lambda e: self._refresh_surahs())
        s.Add(self.recChoice, 0, wx.EXPAND | wx.ALL, 4)

        s.Add(wx.StaticText(panel, label="السورة:"), 0, wx.ALL, 4)
        self.surahChoice = wx.Choice(panel, choices=[])
        self.surahChoice.SetName("اختيار السورة")
        s.Add(self.surahChoice, 0, wx.EXPAND | wx.ALL, 4)

        self.autoChk = wx.CheckBox(panel, label="تشغيل متواصل (الانتقال للسورة التالية تلقائياً)")
        self.autoChk.Bind(wx.EVT_CHECKBOX, lambda e: setattr(self, "_auto", self.autoChk.GetValue()))
        s.Add(self.autoChk, 0, wx.ALL, 6)

        b = wx.BoxSizer(wx.HORIZONTAL)
        b.Add(self.button(panel, "تشغيل", lambda e: self._play()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "إيقاف", lambda e: self._stop()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "تنزيل السورة", lambda e: self._download()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        s.Add(b, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self._refresh_surahs()
        self.set_first_control(self.recChoice)

    def _load_surah_names(self, res):
        try:
            with open(os.path.join(res, "quran", "quran_data.json"), encoding="utf-8") as f:
                data = json.load(f)
            return {int(k): v["name"] for k, v in data["surahs"].items()} \
                if isinstance(data.get("surahs"), dict) else \
                {s["number"]: s["name"] for s in data.get("surahs", [])}
        except Exception:
            return {i: f"سورة {i}" for i in range(1, 115)}

    def _reciter(self):
        i = self.recChoice.GetSelection()
        return self._reciters[i] if 0 <= i < len(self._reciters) else None

    def _refresh_surahs(self):
        r = self._reciter()
        if not r:
            return
        avail = r.get("available", list(range(1, 115)))
        self._avail = avail
        self.surahChoice.Set([f"{n}. {self._surah_names.get(n, '')}" for n in avail])
        if avail:
            self.surahChoice.SetSelection(0)

    def _current_surah(self):
        i = self.surahChoice.GetSelection()
        return self._avail[i] if 0 <= i < len(self._avail) else None

    def _play(self):
        r = self._reciter(); surah = self._current_surah()
        if not r or not surah:
            return
        self.announce(f"جارٍ تحضير سورة {self._surah_names.get(surah,'')} بصوت {r['name']}...")
        threading.Thread(target=self._play_worker, args=(r, surah), daemon=True).start()

    def _play_worker(self, r, surah):
        tag = self._tag(r)
        path = self._audio.fetch(tag, r["url"], surah)
        if path:
            wx.CallAfter(self._player.play_file, path)
        else:
            wx.CallAfter(self.announce, "تعذّر تشغيل السورة. تأكّد من الاتصال أو جرّب قارئاً آخر.")

    def _tag(self, r):
        # a filesystem-safe cache tag from the reciter's URL
        import hashlib
        return "s" + hashlib.md5(r["url"].encode()).hexdigest()[:10]

    def _stop(self):
        self._auto_saved = self._auto
        self._player.stop()

    def _on_finished(self):
        if not self._auto:
            return
        # advance to the next available surah
        i = self.surahChoice.GetSelection()
        if 0 <= i < len(self._avail) - 1:
            wx.CallAfter(self.surahChoice.SetSelection, i + 1)
            wx.CallAfter(self._play)

    def _download(self):
        r = self._reciter(); surah = self._current_surah()
        if not r or not surah:
            return
        tag = self._tag(r)
        if self._audio.cached(tag, surah):
            self.announce("هذه السورة منزّلة بالفعل بصوت هذا القارئ.")
            return
        from .download_progress import DownloadProgressDialog

        def worker(progress_cb, should_stop):
            progress_cb(0, 1)
            self._audio.fetch(tag, r["url"], surah)
            progress_cb(1, 1)

        dlg = DownloadProgressDialog(
            self, self.speech, f"تنزيل سورة {self._surah_names.get(surah,'')}",
            1, worker, unit="سورة")
        self.show_child(dlg)

    def on_closing(self):
        try:
            self._player.close()
        except Exception:
            pass

    def instructions(self) -> str:
        return ("مشغّل السور الكاملة: اختر القارئ ثم السورة ثم «تشغيل» لسماع السورة كاملة. "
                "فعّل «تشغيل متواصل» للانتقال التلقائي للسورة التالية. «تنزيل السورة» للاستماع "
                "دون إنترنت. هذا مختلف عن مشغّل الآيات في نافذة المصحف. Escape للإغلاق.")
