# -*- coding: utf-8 -*-
"""
abaAcademy.gui.dictionary
=========================

A lightweight dictionary lookup that serves the English course and general
study. It queries the free Dictionary API (dictionaryapi.dev, definitions under
CC BY-SA) on demand — a *lookup* tool, not a bundled database — and reads back
the pronunciation, parts of speech, definitions, examples, and synonyms. Recent
lookups are cached in memory for the session.

No key is required; an internet connection is needed only at lookup time.
"""

from __future__ import annotations

import json
import threading
import urllib.parse

from .net import fetch_text

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from .audio_player import AudioPlayer
from .quran_audio import QuranAudio

API = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"


def lookup_english(word):
    """Blocking lookup; returns dict {lines, audio, word, first_def} or None."""
    try:
        url = API.format(word=urllib.parse.quote(word.strip().lower()))
        raw = fetch_text(url, timeout=15)
        if raw is None:
            return None
        data = json.loads(raw)
        if not isinstance(data, list):
            return None
        lines = []
        entry = data[0]
        phon = entry.get("phonetic") or next(
            (p.get("text") for p in entry.get("phonetics", []) if p.get("text")), "")
        audio = next((p.get("audio") for p in entry.get("phonetics", []) if p.get("audio")), "")
        head = entry.get("word", word)
        lines.append(f"{head}  {phon}".strip())
        first_def = ""
        for m in entry.get("meanings", []):
            pos = m.get("partOfSpeech", "")
            lines.append(f"[{pos}]")
            for d in m.get("definitions", [])[:4]:
                if not first_def:
                    first_def = d.get("definition", "")
                line = "• " + d.get("definition", "")
                if d.get("example"):
                    line += f"  (مثال: {d['example']})"
                lines.append(line)
            syn = m.get("synonyms", [])[:6]
            if syn:
                lines.append("مرادفات: " + ", ".join(syn))
        return {"lines": lines, "audio": audio, "word": head, "first_def": first_def}
    except Exception:
        return None


class DictionaryDialog(AccessibleDialog):
    def __init__(self, parent, academy, speech, initial=""):
        super().__init__(parent, "القاموس (إنجليزي)", speech, size=(640, 520))
        self.academy = academy
        self._cache = {}
        self._audio_url = ""
        self._word = ""
        self._first_def = ""
        import os
        self._dl = QuranAudio(os.path.join(getattr(academy, "user_data_dir", "."), "dict_audio"))

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        r = wx.BoxSizer(wx.HORIZONTAL)
        r.Add(wx.StaticText(panel, label="الكلمة:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self.word = wx.TextCtrl(panel, value=initial, style=wx.TE_PROCESS_ENTER)
        self.word.SetName("الكلمة الإنجليزية"); self.word.Bind(wx.EVT_TEXT_ENTER, self._on_lookup)
        r.Add(self.word, 1, wx.ALL, 4)
        r.Add(self.button(panel, "بحث", self._on_lookup), 0, wx.ALL, 4)
        sizer.Add(r, 0, wx.EXPAND)

        self.result = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.result.SetName("نتيجة القاموس")
        sizer.Add(self.result, 1, wx.EXPAND | wx.ALL, 5)
        b = wx.BoxSizer(wx.HORIZONTAL)
        b.Add(self.button(panel, "استماع للنطق", lambda e: self._play()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "أضِف كبطاقة", lambda e: self._to_card()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        sizer.Add(b, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(sizer)
        self._player = AudioPlayer(panel)
        self.set_first_control(self.word)
        if initial:
            self._on_lookup(None)

    def _on_lookup(self, evt):
        w = self.word.GetValue().strip()
        if not w:
            return
        if w.lower() in self._cache:
            self._show(self._cache[w.lower()])
            return
        self.announce("جارٍ البحث...")
        threading.Thread(target=self._run, args=(w,), daemon=True).start()

    def _run(self, w):
        res = lookup_english(w)
        self.call_after(self._done, w, res)

    def _done(self, w, res):
        if not res:
            self.result.SetValue("لم يُعثر على الكلمة. تأكّد من التهجئة أو الاتصال بالإنترنت.")
            self.announce("لم يُعثر على الكلمة.")
            return
        self._cache[w.lower()] = res
        self._show(res)

    def _show(self, res):
        lines = res["lines"]
        self._audio_url = res.get("audio", "")
        self._word = res.get("word", "")
        self._first_def = res.get("first_def", "")
        text = "\n".join(lines)
        self.result.SetValue(text)
        self.result.SetInsertionPoint(0)
        self.result.SetFocus()
        self.announce(lines[0] if lines else "")

    def _play(self):
        # TTS works from the word itself, so pronunciation is available for any
        # looked-up word — not only those the dictionary supplied audio for.
        if not (self._word or "").strip():
            self.announce("ابحث عن كلمة أولاً.")
            return
        self.announce("جارٍ تحميل النطق...")
        threading.Thread(target=self._play_worker, daemon=True).start()

    def _play_worker(self):
        import hashlib
        # The dictionaryapi.dev media host is unreliable (frequent timeouts), so
        # pronunciation is generated from Google Translate's free TTS endpoint,
        # which is fast and works for ANY word (not only those with dict audio).
        word = (self._word or "").strip()
        path = None
        if word:
            import urllib.parse
            q = urllib.parse.quote(word)
            tts_url = ("https://translate.google.com/translate_tts?ie=UTF-8&q="
                       f"{q}&tl=en&client=tw-ob")
            tag = "tts_" + hashlib.md5(word.lower().encode()).hexdigest()[:10]
            path = self._dl.fetch(tag, 128, 1, url=tts_url)
        # fall back to the dictionary's own audio URL if TTS somehow failed
        if not path and self._audio_url:
            tag = "d" + hashlib.md5(self._audio_url.encode()).hexdigest()[:10]
            path = self._dl.fetch(tag, 128, 1, url=self._audio_url)
        if path:
            self.call_after(self._player.play_file, path)
        else:
            self.call_after(self.announce, "تعذّر تحميل النطق.")

    def _to_card(self):
        if not self._word or not self._first_def:
            self.announce("ابحث عن كلمة أولاً.")
            return
        try:
            self.academy.flashcards.add(self._word, self._first_def, deck="قاموس إنجليزي")
            self.announce("أُضيفت الكلمة إلى بطاقاتك في مجموعة قاموس إنجليزي.")
        except Exception:
            self.announce("تعذّرت الإضافة.")

    def on_closing(self):
        try:
            self._player.close()
        except Exception:
            pass

    def instructions(self) -> str:
        return ("اكتب كلمة إنجليزية واضغط Enter لعرض النطق والتعريفات والأمثلة والمرادفات. "
                "التعريفات تُجلب من قاموس مجاني عبر الإنترنت. Escape للإغلاق.")
