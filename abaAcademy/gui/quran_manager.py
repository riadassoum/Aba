# -*- coding: utf-8 -*-
"""
abaAcademy.gui.quran_manager
============================

A dedicated manager window for Qur'an resources, so the Mushaf window itself
stays uncluttered and only shows the *defaults*. Here the user can, for each
category (Mushaf script / tafsir / translation / reciter):

  * see what is available and whether it is downloaded (offline) or online,
  * download an edition/reciter for offline use,
  * remove a downloaded one to free space,
  * set one as the default that the Mushaf uses.

Defaults are stored in settings (quran_default_script / _tafsir / _translation /
_reciter). Downloaded editions live in the editions cache; reciter audio is
cached per ayah on demand, and "download" here means fetching a whole surah or
the whole Qur'an for that reciter.
"""

from __future__ import annotations

import json
import os
import threading

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog


class QuranManager(AccessibleDialog):
    def __init__(self, parent, academy, speech, editions, audio, reciters, ayat, surahs):
        super().__init__(parent, "إدارة موارد القرآن (تنزيل وتعيين الافتراضي)",
                         speech, size=(720, 560))
        self.academy = academy
        self._ed = editions
        self._audio = audio
        self._reciters = reciters       # list of {name, rewaya, url, bitrate}
        self.ayat = ayat
        self.surahs = surahs

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(wx.StaticText(panel, label="اختر الفئة ثم عنصراً، ثم نزّله أو احذفه أو "
                                             "اجعله الافتراضي. تظهر الافتراضيات فقط في نافذة "
                                             "المصحف."), 0, wx.ALL, 8)

        catRow = wx.BoxSizer(wx.HORIZONTAL)
        catRow.Add(wx.StaticText(panel, label="الفئة:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self.catChoice = wx.Choice(panel, choices=["الرسم (المصحف)", "التفسير", "الترجمة", "القارئ"])
        self.catChoice.SetSelection(0)
        self.catChoice.SetName("فئة المورد")
        self.bind_choice(self.catChoice, lambda e: self._reload())
        catRow.Add(self.catChoice, 1, wx.ALL, 4)
        sizer.Add(catRow, 0, wx.EXPAND)

        self.listBox = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.listBox.SetName("قائمة الموارد")
        self.listBox.Bind(wx.EVT_LISTBOX, self._on_select)
        sizer.Add(self.listBox, 1, wx.EXPAND | wx.ALL, 6)

        b = wx.BoxSizer(wx.HORIZONTAL)
        b.Add(self.button(panel, "تعيين كافتراضي", lambda e: self._set_default()), 0, wx.ALL, 4)
        self.dlBtn = self.button(panel, "تنزيل", lambda e: self._download())
        b.Add(self.dlBtn, 0, wx.ALL, 4)
        b.Add(self.button(panel, "حذف المنزّل", lambda e: self._remove()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        sizer.Add(b, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(sizer)
        self._reload()
        self.set_first_control(self.catChoice)

    # -- data per category -------------------------------------------------

    def _category(self):
        return ["script", "tafsir", "translation", "reciter"][self.choice_index(self.catChoice)]

    def _items(self):
        cat = self._category()
        if cat == "script":
            return [(e["id"], e.get("arname") or e["name"]) for e in self._ed.by_type("quran")]
        if cat == "tafsir":
            return [(e["id"], self._ed.label(e)) for e in self._ed.by_type("tafsir")]
        if cat == "translation":
            return [(e["id"], self._ed.label(e)) for e in self._ed.by_type("translation")]
        out = []
        for r in self._reciters:
            ident = r.get("key", r.get("name"))
            rw = f" — {r['rewaya']}" if r.get("rewaya") else ""
            out.append((ident, f"{r.get('name','')}{rw} — {r.get('bitrate',128)} kbps"))
        return out

    def _default_key(self):
        return {"script": "quran_default_script", "tafsir": "quran_default_tafsir",
                "translation": "quran_default_translation", "reciter": "quran_default_reciter"}[self._category()]

    def _current_default(self):
        try:
            return self.academy.store.get_setting(self._default_key(), "") or ""
        except Exception:
            return ""

    def _is_downloaded(self, ident):
        cat = self._category()
        if cat in ("script", "tafsir", "translation"):
            return self._ed.is_offline(ident)
        # reciter: downloaded if a sample ayah is cached under this reciter's tag
        return self._audio.cached(ident, 1) is not None

    def _reload(self):
        self.listBox.Freeze()
        try:
            self.listBox.Clear()
            self._pairs = self._items()
            default = self._current_default()
            for ident, label in self._pairs:
                tags = []
                if ident == default:
                    tags.append("افتراضي")
                tags.append("منزّل" if self._is_downloaded(ident) else "عبر الإنترنت")
                self.listBox.Append(f"{label}  —  {'، '.join(tags)}")
        finally:
            self.listBox.Thaw()
        if self.listBox.GetCount():
            self.select_index(self.listBox, 0)
            self._on_select()

    def _selected(self):
        i = self.listBox.GetSelection()
        if i == wx.NOT_FOUND:
            return None
        return self._pairs[i]

    def _on_select(self, evt=None):
        # hide/disable the download button for items already fully downloaded
        sel = self._selected()
        if not sel:
            return
        downloaded = self._is_downloaded(sel[0])
        if hasattr(self, "dlBtn"):
            self.dlBtn.Enable(not downloaded)

    # -- actions -----------------------------------------------------------

    def _set_default(self):
        sel = self._selected()
        if not sel:
            return
        try:
            self.academy.store.set_setting(self._default_key(), sel[0])
            self.announce(f"تم تعيين {sel[1]} كافتراضي.")
            self._reload()
        except Exception:
            self.announce("تعذّر التعيين.")

    def _reciter_by_name(self, name):
        return next((r for r in self._reciters
                     if r.get("key") == name or r.get("name") == name), None)

    def _download(self):
        sel = self._selected()
        if not sel:
            return
        ident, label = sel
        cat = self._category()
        if cat in ("script", "tafsir", "translation"):
            if self._ed.is_offline(ident):
                self.announce("منزّل بالفعل.")
                return
            self.announce(f"جارٍ تنزيل {label}...")
            threading.Thread(target=self._dl_edition, args=(ident, label), daemon=True).start()
        else:
            self._download_reciter(ident, label)

    def _dl_edition(self, ident, label):
        ok = self._ed.fetch_edition(ident) is not None
        self.call_after(self._after_dl, label, ok)

    def _after_dl(self, label, ok):
        self.announce(f"اكتمل تنزيل {label}." if ok else f"تعذّر تنزيل {label}.")
        self._reload()

    def _download_reciter(self, name, label):
        r = self._reciter_by_name(name)
        if not r:
            return
        from .quran_audio import verse_url
        nums = [row[2] for row in self.ayat]                     # global numbers
        sa = {row[2]: (row[0], row[1]) for row in self.ayat}     # global -> (surah, aya)
        tag = r.get("key", r.get("name"))
        bitrate = r.get("bitrate", 128)
        if r.get("cdn"):
            cdn = r["cdn"]
            url_for = None
            tag = cdn                                            # CDN caches by edition id + global num
        else:
            base = r["url"]
            def url_for(num):
                su, a = sa[num]
                return verse_url(base, su, a)

        total = len(nums)
        self.announce(f"جارٍ تنزيل تلاوة {r['name']} لكامل القرآن ({total} آية). قد يستغرق وقتاً...")

        # only fetch missing ayat; if fully offline already, say so
        missing = self._audio.missing_numbers(tag, nums)
        if not missing:
            self.announce(f"تلاوة {r['name']} منزّلة بالكامل.")
            return

        from .download_progress import DownloadProgressDialog

        def worker(progress_cb, should_stop):
            self._audio.download_range(tag, bitrate, nums, progress=progress_cb,
                                       should_stop=should_stop, url_for=url_for)

        dlg = DownloadProgressDialog(
            self, self.speech, f"تنزيل تلاوة {r['name']}", len(nums), worker, unit="آية")
        self.show_child(dlg)
        self._reload()

    def _remove(self):
        sel = self._selected()
        if not sel:
            return
        ident, label = sel
        cat = self._category()
        removed = 0
        if cat in ("script", "tafsir", "translation"):
            # only remove from the on-disk cache (never the bundled defaults)
            p = os.path.join(self._ed.cache_dir, f"ed_{ident}.json")
            if os.path.exists(p):
                try:
                    os.remove(p)
                    self._ed._loaded.pop(ident, None)
                    removed = 1
                except OSError:
                    pass
            else:
                self.announce("هذا المورد مضمّن ولا يمكن حذفه، أو غير منزّل.")
                return
        else:
            folder = os.path.join(self._audio.cache_root, ident)
            if os.path.isdir(folder):
                for fn in os.listdir(folder):
                    try:
                        os.remove(os.path.join(folder, fn))
                        removed += 1
                    except OSError:
                        pass
        self.announce(f"تم حذف {label} من التنزيلات." if removed else "لا يوجد ما يُحذف.")
        self._reload()

    def on_closing(self):
        pass

    def instructions(self) -> str:
        return ("اختر الفئة (الرسم، التفسير، الترجمة، القارئ) ثم عنصراً من القائمة. الأزرار: "
                "تعيينه كافتراضي (وهو ما يظهر في نافذة المصحف)، تنزيله للاستخدام دون إنترنت، "
                "أو حذف نسخته المنزّلة. Escape للإغلاق.")
