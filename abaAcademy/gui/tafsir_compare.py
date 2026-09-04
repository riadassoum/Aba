# -*- coding: utf-8 -*-
"""
abaAcademy.gui.tafsir_compare
=============================

A comparative commentary reader: pick one ayah and move through several sources
for *that same ayah* without losing your place — the simplified tafsir
(الميسّر), the grammatical analysis (الإعراب), the reasons for revelation (أسباب
النزول), and the English and French translations. Left/Right arrows switch the
source; Up/Down move to the previous/next ayah keeping the current source. This
is the accessible equivalent of a scholar's side-by-side muqaranah, driven
entirely by the editions already bundled with the add-on.

Everything here reads real bundled data through the existing ``QuranEditions``
loader; nothing is generated or graded. Sources that aren't available offline are
simply skipped with a spoken note.
"""

from __future__ import annotations

import json
import os

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog

# (edition_id, spoken label) in the order we cycle through them
_SOURCES = [
    ("quran-uthmani", "الآية"),
    ("ar.muyassar", "التفسير الميسّر"),
    ("ar.e3rab", "الإعراب"),
    ("ar.asbab", "أسباب النزول"),
    ("en.sahih", "الترجمة الإنجليزية"),
    ("fr.hamidullah", "الترجمة الفرنسية"),
]


class TafsirCompareDialog(AccessibleDialog):
    TITLE = "مقارنة التفاسير"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(720, 560))
        self.academy = academy
        self._editions = self._get_editions()
        self._surahs, self._ayah_index, self._counts = self._load_index()
        self._global = 1            # 1..6236
        self._source = 0

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "اكتب موضع الآية (سورة:آية مثل 2:255) ثم Enter. بعدها تنقّل بين المصادر "
            "بالسهمين يمين ويسار، وبين الآيات بالسهمين أعلى وأسفل.")),
            0, wx.ALL, 6)

        self.refEntry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.refEntry.SetName("موضع الآية")
        self.refEntry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._go_ref())
        s.Add(self.refEntry, 0, wx.EXPAND | wx.ALL, 6)

        self.text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE,
                                size=(-1, 260))
        self.text.SetName("نص المصدر")
        self.text.Bind(wx.EVT_KEY_DOWN, self._on_key)
        s.Add(self.text, 1, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(680)
        s.Add(self.status, 0, wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "المصدر التالي (→)", lambda e: self._cycle(1)), 0, wx.ALL, 3)
        row.Add(self.button(panel, "الآية التالية (↓)", lambda e: self._step(1)), 0, wx.ALL, 3)
        row.Add(self.button(panel, "أعد القراءة", lambda e: self._render()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.refEntry)

    # -- data -------------------------------------------------------------
    def _get_editions(self):
        try:
            from .quran_editions import QuranEditions
            cache = os.path.join(self.academy.user_data_dir, "quran_editions")
            # provide uthmani text so "الآية" source works offline
            uthmani = self._load_uthmani()
            return QuranEditions(self.academy.resource_dir, cache, uthmani=uthmani)
        except Exception:
            return None

    def _load_uthmani(self):
        try:
            qd = json.load(open(os.path.join(self.academy.resource_dir, "quran",
                                             "quran_data.json"), encoding="utf-8"))
            # editions are indexed 1..6236 in mushaf order; the ayat rows are in
            # that same order, so a straight sequential list is correct
            return [row[-1] for row in qd.get("ayat", [])]
        except Exception:
            return None

    def _load_index(self):
        """Return (surah_names, {(surah,ayah):global}, {surah:count})."""
        surah_names, ayah_index, counts = {}, {}, {}
        try:
            qd = json.load(open(os.path.join(self.academy.resource_dir, "quran",
                                             "quran_data.json"), encoding="utf-8"))
            for surah in qd.get("surahs", []):
                surah_names[surah["n"]] = surah["name"]
                counts[surah["n"]] = surah.get("count", 0)
            g = 0
            for row in qd.get("ayat", []):
                g += 1
                ayah_index[(row[0], row[1])] = g
        except Exception:
            pass
        return surah_names, ayah_index, counts

    # -- navigation -------------------------------------------------------
    def _go_ref(self):
        ref = self.refEntry.GetValue().strip().replace("،", ":")
        try:
            surah, ayah = (int(x) for x in ref.split(":"))
        except Exception:
            self._say("موضع غير صحيح. اكتب مثل 2:255.")
            return
        g = self._ayah_index.get((surah, ayah))
        if not g:
            self._say("لا توجد آية بهذا الموضع.")
            return
        self._global = g
        self._source = 1 if len(_SOURCES) > 1 else 0     # start at the tafsir
        self._render()
        self.text.SetFocus()

    def _on_key(self, evt):
        code = evt.GetKeyCode()
        if code == wx.WXK_RIGHT:
            self._cycle(1)
        elif code == wx.WXK_LEFT:
            self._cycle(-1)
        elif code == wx.WXK_DOWN:
            self._step(1)
        elif code == wx.WXK_UP:
            self._step(-1)
        else:
            evt.Skip()

    def _cycle(self, direction):
        self._source = (self._source + direction) % len(_SOURCES)
        self._render()

    def _step(self, direction):
        ng = self._global + direction
        if 1 <= ng <= 6236:
            self._global = ng
            self._render()
        else:
            self._say("بلغت نهاية المصحف." if direction > 0 else "أنت عند البداية.")

    # -- rendering --------------------------------------------------------
    def _render(self):
        edition_id, label = _SOURCES[self._source]
        content = None
        if self._editions is not None:
            content = self._editions.text(edition_id, self._global)
        loc = self._loc_name()
        if content is None:
            self.text.SetValue("")
            self._say(f"{label} غير متوفّر لهذه الآية دون اتصال. "
                      f"جرّب مصدراً آخر بالسهمين. ({loc})")
            return
        header = f"{label} — {loc}"
        self.text.SetValue(header + "\n\n" + content)
        self.text.SetInsertionPoint(0)
        # announce the label + location + the content
        self._say(f"{header}. {content}")

    def _loc_name(self):
        # reverse map global -> (surah, ayah)
        for (s, a), g in self._ayah_index.items():
            if g == self._global:
                name = self._surahs.get(s, f"سورة {s}")
                return f"{name}، الآية {a}"
        return f"الآية {self._global}"

    def _say(self, text):
        self.status.SetLabel(text[:200])
        self.announce(text)

    def instructions(self):
        return ("مقارنة التفاسير: اكتب موضع آية (مثل 2:255) واضغط Enter، ثم تنقّل بين "
                "المصادر لنفس الآية بالسهمين يمين ويسار — الآية، التفسير الميسّر، الإعراب، "
                "أسباب النزول، والترجمتان الإنجليزية والفرنسية — دون فقدان موضعك. تنقّل بين "
                "الآيات بالسهمين أعلى وأسفل مع بقاء المصدر نفسه. كل النصوص من المصادر المرفقة "
                "بالإضافة. Escape للإغلاق.")
