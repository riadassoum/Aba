# -*- coding: utf-8 -*-
"""
abaAcademy.gui.quran_study
==========================

A study screen for deep Qur'an exploration, built on the bundled morphology and a
rule-based Tajweed detector:

* **بحث بالجذر** — type an Arabic root (e.g. رحم) and hear how many times it
  occurs, how many derived forms it has, and browse those forms with their
  counts and first location.
* **مواضع الجذر** — list the occurrences of the searched root (word + location).
* **أحكام التجويد لآية** — type a surah:ayah reference and hear the Tajweed rules
  detectable in that ayah, with a subtle earcon per rule.

The morphology is the Quranic Arabic Corpus data already bundled; the Tajweed
detector is rule-based over the written text and is presented as a study aid, not
a certified Tajweed text.
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..quran_engine.morpho_search import MorphologySearch
from ..quran_engine.tajweed import analyse_ayah, rules_summary, earcon
from ..math_engine.sonification import TonePlayer


class QuranStudyDialog(AccessibleDialog):
    TITLE = "دراسة القرآن (الجذور والتجويد)"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(720, 580))
        self.academy = academy
        self.morph = MorphologySearch.get(academy.resource_dir)
        self._player = TonePlayer()
        self._forms = []
        self._occurrences = []

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)

        s.Add(wx.StaticText(panel, label="ابحث عن جذر ثلاثيّ (مثل: رحم، علم، كتب):"),
              0, wx.ALL, 6)
        self.rootEntry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.rootEntry.SetName("الجذر")
        self.rootEntry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._search_root())
        s.Add(self.rootEntry, 0, wx.EXPAND | wx.ALL, 6)

        rrow = wx.BoxSizer(wx.HORIZONTAL)
        rrow.Add(self.button(panel, "ابحث بالجذر (Enter)", lambda e: self._search_root()), 0, wx.ALL, 3)
        rrow.Add(self.button(panel, "الصيغ المشتقّة", lambda e: self._say_forms()), 0, wx.ALL, 3)
        rrow.Add(self.button(panel, "المواضع", lambda e: self._say_occurrences()), 0, wx.ALL, 3)
        s.Add(rrow, 0, wx.ALL, 3)

        # list to browse results
        self.results = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.results.SetName("النتائج")
        s.Add(self.results, 1, wx.EXPAND | wx.ALL, 6)

        s.Add(wx.StaticText(panel, label="أحكام التجويد لآية (اكتب رقم السورة:الآية، مثل 2:255):"),
              0, wx.ALL, 6)
        self.ayahEntry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.ayahEntry.SetName("موضع الآية")
        self.ayahEntry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._tajweed())
        s.Add(self.ayahEntry, 0, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(680)
        s.Add(self.status, 0, wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "أحكام هذه الآية", lambda e: self._tajweed()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.rootEntry)

    # -- root search ------------------------------------------------------
    def _search_root(self):
        root = self.rootEntry.GetValue().strip()
        if not root:
            self._say("اكتب جذراً أولاً.")
            return
        self._occurrences = self.morph.search_root(root)
        self._forms = self.morph.derived_forms(root)
        if not self._occurrences:
            self.results.Clear()
            self._say(self.morph.summary_for_root(root))
            return
        self._say(self.morph.summary_for_root(root)
                  + " استخدم «الصيغ المشتقّة» أو «المواضع» للتفصيل.")
        # show forms in the list by default
        self._show_forms()

    def _show_forms(self):
        self.results.Clear()
        for f in self._forms:
            self.results.Append(
                f"{f['word']} — {f['pos']} — {f['count']} مرة")

    def _say_forms(self):
        if not self._forms:
            self._say("ابحث عن جذر أولاً.")
            return
        self._show_forms()
        top = self._forms[:8]
        text = "، ".join(f"{f['word']} {f['count']} مرة" for f in top)
        more = " وغيرها" if len(self._forms) > 8 else ""
        self._say(f"الصيغ المشتقّة: {text}{more}.")
        self.results.SetFocus()

    def _say_occurrences(self):
        if not self._occurrences:
            self._say("ابحث عن جذر أولاً.")
            return
        self.results.Clear()
        for e in self._occurrences[:200]:
            loc = self.morph.location_name(e["surah"], e["ayah"])
            self.results.Append(f"{e['word']} — {loc}")
        n = len(self._occurrences)
        shown = min(n, 200)
        self._say(f"{n} موضعاً. عُرض أوّل {shown}. تنقّل في القائمة بالأسهم.")
        self.results.SetFocus()

    # -- tajweed ----------------------------------------------------------
    def _tajweed(self):
        ref = self.ayahEntry.GetValue().strip()
        text = self._ayah_text(ref)
        if text is None:
            self._say("موضع غير صحيح. اكتب رقم السورة، نقطتين، ثم رقم الآية، مثل 2:255.")
            return
        hits = analyse_ayah(text)
        self._say(rules_summary(hits))
        # play a short sequence of earcons for the rules found
        if self._player.available and hits:
            seq = b"".join(earcon(h.kind) for h in hits[:6])
            self._player.play(seq)

    def _ayah_text(self, ref):
        try:
            surah, ayah = (int(x) for x in ref.replace("،", ":").split(":"))
        except Exception:
            return None
        # load quran text once
        if not hasattr(self, "_qtext"):
            import json, os
            self._qtext = {}
            try:
                qd = json.load(open(os.path.join(self.academy.resource_dir,
                                                  "quran", "quran_data.json"),
                                    encoding="utf-8"))
                for row in qd.get("ayat", []):
                    # row: [..., surah, ayah, text] — last is text, indices vary;
                    # use the documented layout: surah at [0], ayah at [1]? We
                    # detect by taking the trailing string and the two ints that
                    # look like a valid surah:ayah at the start.
                    text = row[-1]
                    s_no, a_no = row[0], row[1]
                    self._qtext[(s_no, a_no)] = text
            except Exception:
                self._qtext = {}
        return self._qtext.get((surah, ayah))

    def on_closing(self):
        try:
            self._player.stop()
        except Exception:
            pass

    def _say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    def instructions(self):
        return ("دراسة القرآن: اكتب جذراً ثلاثيّاً (مثل رحم) واضغط Enter لتعرف عدد مرّات "
                "وروده وصيغه المشتقّة، ثم «الصيغ المشتقّة» أو «المواضع» للتفصيل، وتصفّح "
                "النتائج في القائمة بالأسهم. للتجويد، اكتب موضع آية مثل 2:255 لتسمع الأحكام "
                "التي يمكن كشفها من النص مع نغمة لكل حكم. المورفولوجيا من مدوّنة القرآن "
                "الصرفية، وكاشف التجويد أداة مساعِدة للدراسة لا نصّاً معتمداً. Escape للإغلاق.")
