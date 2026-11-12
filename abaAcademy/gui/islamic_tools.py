# -*- coding: utf-8 -*-
"""
abaAcademy.gui.islamic_tools
============================

A small set of Islamic tools for the students (Arabic, RTL):

* أسماء الله الحسنى (the 99 Names) — bundled offline with Arabic meanings, in a
  navigable read-only window, and addable as a flashcard deck for memorisation.
* مواقيت الصلاة (prayer times) — fetched for the student's city via the free
  AlAdhan API (no key), with today's Hijri date.

The 99 Names work fully offline. Prayer times need an internet connection at the
time of lookup. Nothing here requires an API key.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.parse
import urllib.request

from .accessible import AccessibleDialog

try:
    import wx
except Exception:
    wx = None

PRAYER_API = ("https://api.aladhan.com/v1/timingsByCity"
              "?city={city}&country={country}&method=2")


def _load_names(res_dir):
    try:
        with open(os.path.join(res_dir, "islamic", "asma_al_husna.json"),
                  encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


class IslamicToolsHome(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "أدوات إسلامية", speech, size=(560, 420))
        self.academy = academy
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label="اختر أداة:"), 0, wx.ALL, 10)
        s.Add(self.button(panel, "أسماء الله الحسنى", lambda e: self._names()),
              0, wx.EXPAND | wx.ALL, 6)
        s.Add(self.button(panel, "مواقيت الصلاة والتاريخ الهجري",
                          lambda e: self._prayer()), 0, wx.EXPAND | wx.ALL, 6)
        s.Add(self.button(panel, "الأذكار", lambda e: self._athkar()),
              0, wx.EXPAND | wx.ALL, 6)
        s.Add(self.button(panel, "المسبحة (عدّاد التسبيح)", lambda e: self._tasbih()),
              0, wx.EXPAND | wx.ALL, 6)
        s.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()),
              0, wx.ALIGN_RIGHT | wx.ALL, 6)
        panel.SetSizer(s)
        self.set_first_control(panel.GetChildren()[1])

    def _names(self):
        self.show_child(AsmaAlHusnaView(self, self.academy, self.speech))

    def _prayer(self):
        self.show_child(PrayerTimesView(self, self.academy, self.speech))

    def _athkar(self):
        self.show_child(AthkarView(self, self.academy, self.speech))

    def _tasbih(self):
        self.show_child(TasbihView(self, self.academy, self.speech))

    def instructions(self) -> str:
        return ("أدوات إسلامية: أسماء الله الحسنى للحفظ والتصفّح، ومواقيت الصلاة "
                "مع التاريخ الهجري. Escape للإغلاق.")


class AsmaAlHusnaView(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "أسماء الله الحسنى", speech, size=(720, 560))
        self.academy = academy
        res = getattr(academy, "resource_dir", None) or \
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources")
        self._names = _load_names(res)
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        body = []
        for n in self._names:
            body.append(f"{n['num']}. {n['name']}  —  {n.get('meaning_ar','')}")
        self.text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.text.SetName("أسماء الله الحسنى")
        try:
            self.text.SetLayoutDirection(wx.Layout_RightToLeft)
        except Exception:
            pass
        self.text.SetValue("\n".join(body))
        self.text.SetInsertionPoint(0)
        s.Add(self.text, 1, wx.EXPAND | wx.ALL, 6)
        b = wx.BoxSizer(wx.HORIZONTAL)
        b.Add(self.button(panel, "أضِفها كبطاقات للحفظ", lambda e: self._to_cards()),
              0, wx.ALL, 4)
        b.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        s.Add(b, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self.set_first_control(self.text)

    def _to_cards(self):
        try:
            added = 0
            for n in self._names:
                front = f"ما معنى اسم الله {n['name']}؟"
                back = n.get("meaning_ar", "") or n.get("translit", "")
                if back:
                    self.academy.flashcards.add(front, back, deck="أسماء الله الحسنى")
                    added += 1
            self.announce(f"أُضيفت {added} بطاقة في مجموعة أسماء الله الحسنى.")
        except Exception:
            self.announce("تعذّرت الإضافة.")

    def instructions(self) -> str:
        return ("أسماء الله الحسنى ومعانيها، تتنقّل بينها بالأسهم. زر أضِفها كبطاقات "
                "ينشئ مجموعة بطاقات لحفظها بالمراجعة الذكية. Escape للإغلاق.")


class PrayerTimesView(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "مواقيت الصلاة", speech, size=(560, 460))
        self.academy = academy
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(panel, label="المدينة:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self.city = wx.TextCtrl(panel, value=self._saved("prayer_city", ""))
        self.city.SetName("المدينة")
        row.Add(self.city, 1, wx.ALL, 4)
        row.Add(wx.StaticText(panel, label="الدولة:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self.country = wx.TextCtrl(panel, value=self._saved("prayer_country", ""))
        self.country.SetName("الدولة")
        row.Add(self.country, 1, wx.ALL, 4)
        s.Add(row, 0, wx.EXPAND)
        s.Add(self.button(panel, "عرض المواقيت", lambda e: self._fetch()), 0, wx.EXPAND | wx.ALL, 6)
        self.result = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.result.SetName("المواقيت")
        s.Add(self.result, 1, wx.EXPAND | wx.ALL, 6)
        s.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALIGN_RIGHT | wx.ALL, 4)
        panel.SetSizer(s)
        self.set_first_control(self.city)

    def _saved(self, k, d):
        try:
            return self.academy.store.get_setting(k, d) or d
        except Exception:
            return d

    def _set(self, k, v):
        try:
            self.academy.store.set_setting(k, v)
        except Exception:
            pass

    def _fetch(self):
        city = self.city.GetValue().strip()
        country = self.country.GetValue().strip()
        if not city or not country:
            self.announce("أدخل المدينة والدولة.")
            return
        self._set("prayer_city", city)
        self._set("prayer_country", country)
        self.announce("جارٍ جلب المواقيت...")
        threading.Thread(target=self._worker, args=(city, country), daemon=True).start()

    def _worker(self, city, country):
        try:
            url = PRAYER_API.format(city=urllib.parse.quote(city),
                                    country=urllib.parse.quote(country))
            req = urllib.request.Request(url, headers={"User-Agent": "abaAcademy"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
            d = data["data"]
            t = d["timings"]
            hijri = d["date"]["hijri"]
            names = [("الفجر", "Fajr"), ("الشروق", "Sunrise"), ("الظهر", "Dhuhr"),
                     ("العصر", "Asr"), ("المغرب", "Maghrib"), ("العشاء", "Isha")]
            lines = [f"التاريخ الهجري: {hijri['day']} {hijri['month']['ar']} {hijri['year']}", ""]
            for ar, key in names:
                v = t.get(key, "").split(" ")[0]
                lines.append(f"{ar}: {v}")
            body = "\n".join(lines)
            self.call_after(self._show, body)
        except Exception:
            self.call_after(self.announce, "تعذّر جلب المواقيت. تأكّد من الاتصال ومن اسم المدينة.")

    def _show(self, body):
        self.result.SetValue(body)
        self.result.SetInsertionPoint(0)
        self.result.SetFocus()
        self.announce(body.replace("\n", "؛ "))

    def instructions(self) -> str:
        return ("أدخل المدينة والدولة ثم عرض المواقيت لجلب أوقات الصلاة الخمس والتاريخ "
                "الهجري. يتطلّب اتصالاً بالإنترنت. Escape للإغلاق.")


def _load_athkar(res_dir):
    try:
        with open(os.path.join(res_dir, "islamic", "athkar.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


class AthkarView(AccessibleDialog):
    """A reader for the well-known adhkar (remembrances). Browse them in a list;
    the selected dhikr's full text is shown and can be added to the tasbih
    counter or memorised as flashcards."""

    def __init__(self, parent, academy, speech):
        super().__init__(parent, "الأذكار", speech, size=(700, 540))
        self.academy = academy
        res = getattr(academy, "resource_dir", None) or \
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources")
        self._athkar = _load_athkar(res)
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        self.listBox = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.listBox.SetName("قائمة الأذكار")
        self.listBox.Set([a.get("name", "") for a in self._athkar])
        self.listBox.Bind(wx.EVT_LISTBOX, lambda e: self._show())
        s.Add(self.listBox, 1, wx.EXPAND | wx.ALL, 6)
        self.text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
                                size=(-1, 160))
        self.text.SetName("نص الذكر")
        try:
            self.text.SetLayoutDirection(wx.Layout_RightToLeft)
        except Exception:
            pass
        s.Add(self.text, 0, wx.EXPAND | wx.ALL, 6)
        b = wx.BoxSizer(wx.HORIZONTAL)
        b.Add(self.button(panel, "أضِفه إلى المسبحة", lambda e: self._to_tasbih()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        s.Add(b, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        if self._athkar:
            self.select_index(self.listBox, 0)
            self._show()
        self.set_first_control(self.listBox)

    def _sel(self):
        i = self.listBox.GetSelection()
        return self._athkar[i] if i != wx.NOT_FOUND else None

    def _show(self):
        a = self._sel()
        if a:
            self.text.SetValue(a.get("text", ""))
            self.text.SetInsertionPoint(0)
            self.announce(a.get("text", ""))

    def _to_tasbih(self):
        a = self._sel()
        if not a:
            return
        try:
            store = self.academy.store
            names = json.loads(store.get_setting("tasbih_entries", "[]") or "[]")
            if a["name"] not in [n["name"] for n in names]:
                names.append({"name": a["name"], "count": 0})
                store.set_setting("tasbih_entries", json.dumps(names, ensure_ascii=False))
                self.announce(f"أُضيف {a['name']} إلى المسبحة.")
            else:
                self.announce("موجود في المسبحة بالفعل.")
        except Exception:
            self.announce("تعذّرت الإضافة.")

    def instructions(self) -> str:
        return ("قائمة الأذكار: تنقّل بالأسهم لسماع كل ذكر، ونصّه يظهر في الأسفل. "
                "زر أضِفه إلى المسبحة لعدّه. Escape للإغلاق.")


class TasbihView(AccessibleDialog):
    """A tasbih (dhikr) counter. Each remembrance has a running count that
    persists in the the application's data folder. Space or Enter counts the selected
    dhikr; the running total is announced. Counts survive restarts and
    reinstalls."""

    DEFAULTS = ["سبحان الله", "الحمد لله", "لا إله إلا الله", "الله أكبر",
                "أستغفر الله", "لا حول ولا قوة إلا بالله"]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, "المسبحة", speech, size=(560, 460))
        self.academy = academy
        self._entries = self._load()
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label="اختر ذكراً، ثم اضغط مسافة أو إنتر للعدّ:"),
              0, wx.ALL, 6)
        self.listBox = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.listBox.SetName("أذكار المسبحة")
        self.listBox.Bind(wx.EVT_LISTBOX, lambda e: self._announce_sel())
        s.Add(self.listBox, 1, wx.EXPAND | wx.ALL, 6)
        b = wx.BoxSizer(wx.HORIZONTAL)
        b.Add(self.button(panel, "عُدّ (+1)", lambda e: self._count()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "تصفير", lambda e: self._reset()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "إضافة ذكر", lambda e: self._add()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        s.Add(b, 0, wx.ALIGN_RIGHT)
        # optional periodic reminder that speaks a random dhikr
        self.remindChk = wx.CheckBox(panel, label="تذكير دوري بذكرٍ عشوائي كل بضع دقائق")
        self.remindChk.Bind(wx.EVT_CHECKBOX, lambda e: self._toggle_reminder())
        s.Add(self.remindChk, 0, wx.ALL, 6)
        panel.SetSizer(s)
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self._remind_tick())
        self.listBox.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self._refresh()
        self.set_first_control(self.listBox)

    def _load(self):
        try:
            data = json.loads(self.academy.store.get_setting("tasbih_entries", "") or "[]")
            if data:
                return data
        except Exception:
            pass
        return [{"name": n, "count": 0} for n in self.DEFAULTS]

    def _save(self):
        try:
            self.academy.store.set_setting("tasbih_entries",
                                           json.dumps(self._entries, ensure_ascii=False))
        except Exception:
            pass

    def _refresh(self, keep=0):
        self.listBox.Set([f"{e['name']} — {e['count']}" for e in self._entries])
        if self._entries:
            self.select_index(self.listBox, min(keep, len(self._entries) - 1))

    def _sel_i(self):
        i = self.listBox.GetSelection()
        return i if i != wx.NOT_FOUND else -1

    def _announce_sel(self):
        i = self._sel_i()
        if i >= 0:
            e = self._entries[i]
            self.announce(f"{e['name']}، العدد {e['count']}")

    def _count(self):
        i = self._sel_i()
        if i < 0:
            return
        self._entries[i]["count"] += 1
        self._save()
        c = self._entries[i]["count"]
        self._refresh(keep=i)
        # announce just the number for fast repeated counting
        self.announce(str(c))

    def _reset(self):
        i = self._sel_i()
        if i < 0:
            return
        self._entries[i]["count"] = 0
        self._save()
        self._refresh(keep=i)
        self.announce("صُفّر العدّاد.")

    def _add(self):
        dlg = wx.TextEntryDialog(self, "اكتب الذكر الجديد:", "إضافة ذكر")
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.GetValue().strip()
            if name and name not in [e["name"] for e in self._entries]:
                self._entries.append({"name": name, "count": 0})
                self._save()
                self._refresh(keep=len(self._entries) - 1)
                self.announce(f"أُضيف {name}.")
        dlg.Destroy()

    def _on_key(self, evt):
        if evt.GetKeyCode() in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._count()
        else:
            evt.Skip()

    def _toggle_reminder(self):
        if self.remindChk.GetValue():
            self._timer.Start(5 * 60 * 1000)   # every 5 minutes
            self.announce("فُعّل التذكير الدوري بالأذكار.")
        else:
            self._timer.Stop()
            self.announce("أُوقف التذكير الدوري.")

    def _remind_tick(self):
        import random
        res = getattr(self.academy, "resource_dir", None) or \
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources")
        ath = _load_athkar(res)
        if ath:
            self.announce(random.choice(ath).get("text", ""))

    def on_closing(self):
        try:
            self._timer.Stop()
        except Exception:
            pass

    def instructions(self) -> str:
        return ("المسبحة: اختر ذكراً واضغط مسافة أو إنتر لزيادة العدّ، ويُنطق العدد. "
                "تصفير لإعادة العدّاد، وإضافة ذكر لذكر جديد. تُحفظ الأعداد تلقائياً. "
                "Escape للإغلاق.")
