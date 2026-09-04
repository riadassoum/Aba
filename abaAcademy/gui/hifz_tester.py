# -*- coding: utf-8 -*-
"""
abaAcademy.gui.hifz_tester
==========================

Self-testing modes for Qur'an memorisation (حفظ), all driven by the real bundled
text:

* **أكمل الآية** — the first words of an ayah are shown; the learner recalls the
  continuation, then reveals the full ayah to check.
* **الآية التالية** — an ayah is shown; the learner recalls the *next* ayah, then
  reveals it — drilling smooth transitions between consecutive verses.
* **متشابهات** — two near-identical verses are found in the real text; the learner
  is shown one and its location, recalls how the *other* one differs, then hears
  the exact computed difference. Because both verses and their difference come
  straight from the mushaf text, nothing here is invented.

Weak items (ones the learner marks «صعبة») are stored so they can be revisited.
"""

from __future__ import annotations

import json
import os
import random

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..quran_engine.mutashabihat import MutashabihatFinder


class HifzTesterDialog(AccessibleDialog):
    TITLE = "اختبار الحفظ"

    MODE_COMPLETE = 0
    MODE_NEXT = 1
    MODE_MUTASHABIHAT = 2

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(730, 560))
        self.academy = academy
        self._rng = random.Random()
        self._ayat = self._load_ayat()
        self._finder = MutashabihatFinder.get(academy.resource_dir)
        self._current = None       # current question state
        self._revealed = False

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "اختبر حفظك: أكمل الآية، أو تذكّر الآية التالية، أو تدرّب على المتشابهات. "
            "فكّر أولاً ثم «أظهر الجواب».")), 0, wx.ALL, 6)

        mrow = wx.BoxSizer(wx.HORIZONTAL)
        mrow.Add(wx.StaticText(panel, label="النمط:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.modeChoice = wx.Choice(panel, choices=[
            "أكمل الآية", "الآية التالية", "متشابهات"])
        self.modeChoice.SetSelection(0)
        self.bind_choice(self.modeChoice, lambda e: self._new_question())
        mrow.Add(self.modeChoice, 0)
        s.Add(mrow, 0, wx.ALL, 6)

        self.prompt = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE,
                                  size=(-1, 150))
        self.prompt.SetName("السؤال")
        s.Add(self.prompt, 1, wx.EXPAND | wx.ALL, 6)

        self.answer = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE,
                                  size=(-1, 150))
        self.answer.SetName("الجواب")
        s.Add(self.answer, 1, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(690)
        s.Add(self.status, 0, wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "أظهر الجواب", lambda e: self._reveal()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "سؤال جديد", lambda e: self._new_question()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "علّمها صعبة", lambda e: self._mark_hard()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.modeChoice)
        wx.CallAfter(self._new_question)

    # -- data -------------------------------------------------------------
    def _load_ayat(self):
        try:
            qd = json.load(open(os.path.join(self.academy.resource_dir, "quran",
                                             "quran_data.json"), encoding="utf-8"))
            names = {s["n"]: s["name"] for s in qd.get("surahs", [])}
            ayat = []
            for row in qd.get("ayat", []):
                ayat.append({"surah": row[0], "ayah": row[1], "text": row[-1],
                             "surah_name": names.get(row[0], f"سورة {row[0]}")})
            return ayat
        except Exception:
            return []

    # -- questions --------------------------------------------------------
    def _new_question(self):
        self._revealed = False
        self.answer.SetValue("")
        mode = self.modeChoice.GetSelection()
        if mode == self.MODE_COMPLETE:
            self._q_complete()
        elif mode == self.MODE_NEXT:
            self._q_next()
        else:
            self._q_mutashabihat()

    def _q_complete(self):
        if not self._ayat:
            self._say("تعذّر تحميل نص القرآن.")
            return
        a = self._rng.choice(self._ayat)
        words = a["text"].split()
        # show first ~third of the ayah
        cut = max(2, len(words) // 3)
        shown = " ".join(words[:cut])
        self._current = {"kind": "complete", "full": a["text"], "ayah": a}
        loc = f"{a['surah_name']}، الآية {a['ayah']}"
        self.prompt.SetValue(f"[{loc}]\n\nأكمل: {shown} …")
        self._say(f"أكمل الآية من {loc}: {shown} … فكّر ثم «أظهر الجواب».")

    def _q_next(self):
        if len(self._ayat) < 2:
            return
        i = self._rng.randrange(0, len(self._ayat) - 1)
        a, nxt = self._ayat[i], self._ayat[i + 1]
        # keep them in the same surah for a meaningful transition
        if nxt["surah"] != a["surah"]:
            a, nxt = self._ayat[i + 1], self._ayat[i + 2] if i + 2 < len(self._ayat) else self._ayat[i]
        self._current = {"kind": "next", "next": nxt}
        loc = f"{a['surah_name']}، الآية {a['ayah']}"
        self.prompt.SetValue(f"[{loc}]\n\n{a['text']}\n\nما الآية التالية؟")
        self._say(f"ما الآية التي تلي هذه من {loc}؟ {a['text']}. فكّر ثم «أظهر الجواب».")

    def _q_mutashabihat(self):
        pair = self._finder.random_pair(self._rng)
        if not pair:
            self._say("لم يتم العثور على متشابهات.")
            return
        # show verse A, ask how the matching verse B differs
        self._current = {"kind": "mut", "pair": pair}
        la = self._finder.location_name(pair["a"]["surah"], pair["a"]["ayah"])
        lb = self._finder.location_name(pair["b"]["surah"], pair["b"]["ayah"])
        self.prompt.SetValue(
            f"هذه الآية:\n[{la}]\n{pair['a']['text']}\n\n"
            f"تشبهها آية في [{lb}].\nكيف تختلف الآية الأخرى؟")
        self._say(f"هذه آية من {la}: {pair['a']['text']}. "
                  f"تشبهها آية في {lb}. تذكّر كيف تختلف، ثم «أظهر الجواب».")

    # -- reveal -----------------------------------------------------------
    def _reveal(self):
        if not self._current:
            return
        self._revealed = True
        kind = self._current["kind"]
        if kind == "complete":
            self.answer.SetValue(self._current["full"])
            self._say("الآية كاملة: " + self._current["full"])
        elif kind == "next":
            nxt = self._current["next"]
            loc = f"{nxt['surah_name']}، الآية {nxt['ayah']}"
            self.answer.SetValue(f"[{loc}]\n{nxt['text']}")
            self._say(f"الآية التالية، {loc}: {nxt['text']}")
        elif kind == "mut":
            pair = self._current["pair"]
            lb = self._finder.location_name(pair["b"]["surah"], pair["b"]["ayah"])
            diff = self._finder.describe_difference(pair)
            self.answer.SetValue(f"[{lb}]\n{pair['b']['text']}\n\n{diff}")
            self._say(f"الآية الأخرى، {lb}: {pair['b']['text']}. {diff}")

    def _mark_hard(self):
        if not self._current:
            return
        try:
            key = "hifz_hard"
            prev = self.academy.store.get_setting(key, "")
            tag = self._current_tag()
            items = set(filter(None, prev.split("|")))
            items.add(tag)
            self.academy.store.set_setting(key, "|".join(sorted(items)))
            self._say("حُفظت كآية صعبة لمراجعتها لاحقاً.")
        except Exception:
            self._say("تعذّر الحفظ الآن.")

    def _current_tag(self):
        c = self._current
        if c["kind"] == "complete":
            return f"c:{c['ayah']['surah']}:{c['ayah']['ayah']}"
        if c["kind"] == "next":
            return f"n:{c['next']['surah']}:{c['next']['ayah']}"
        p = c["pair"]
        return f"m:{p['a']['surah']}:{p['a']['ayah']}"

    def _say(self, text):
        self.status.SetLabel(text[:200])
        self.announce(text)

    def instructions(self):
        return ("اختبار الحفظ: اختر النمط. «أكمل الآية» يعرض بداية آية لتكملها؛ «الآية "
                "التالية» يعرض آية لتتذكّر ما يليها؛ «متشابهات» يعرض آية ويطلب أن تتذكّر كيف "
                "تختلف عنها آية مشابهة لها في موضع آخر. «أظهر الجواب» يكشف النص الصحيح، و«علّمها "
                "صعبة» يحفظها للمراجعة. كل النصوص من مصحف الإضافة. Escape للإغلاق.")
