# -*- coding: utf-8 -*-
"""
abaAcademy.gui.hadith_reader
============================

A hadith reader modelled on cascading Book -> Chapter navigation (design pattern
adapted from the open-source Bible application): choose a **collection**, then a
**كتاب** (book), and only that كتاب's ahadith render into a text window — one
hadith per numbered block — so a large collection is never loaded or spoken all
at once. Small collections are bundled; large ones download on first use.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.request

from .accessible import AccessibleDialog
from .download_helper import download_to, BeepLoop, announce
from .command_bar import CommandBar, key

try:
    import wx
except Exception:
    wx = None


def _res_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources", "hadith")


class HadithReader(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "كتب الحديث الشريف", speech, size=(820, 640))
        self.academy = academy
        self._res = _res_dir()
        base = getattr(academy, "user_data_dir", None)
        if not base:
            import tempfile
            base = tempfile.gettempdir()
        self._cache = os.path.join(base, "hadith")
        with open(os.path.join(self._res, "index.json"), encoding="utf-8") as f:
            self.index = json.load(f)
        self._collection = None
        self._books = []
        self._line_hadith = []
        self._text_str = ""
        self._build_ui()
        last = self._get("hadith_last_collection", self._avail[0]["id"] if self._avail else "")
        ci = next((i for i, e in enumerate(self._avail) if e["id"] == last), 0)
        if self._avail:
            self.collChoice.SetSelection(ci)
            self._load_collection(self._avail[ci])

    def _is_available(self, entry):
        return (os.path.exists(os.path.join(self._res, f"{entry['id']}.json"))
                or os.path.exists(os.path.join(self._cache, f"{entry['id']}.json")))

    def _available_collections(self):
        return [e for e in self.index if self._is_available(e)]

    def _get(self, k, d):
        try:
            return self.academy.store.get_setting(k, d) or d
        except Exception:
            return d

    def _set(self, k, v):
        try:
            self.academy.store.set_setting(k, str(v))
        except Exception:
            pass

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(panel, label="المجموعة:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self._avail = self._available_collections()
        self.collChoice = wx.Choice(panel, choices=[e["name"] for e in self._avail])
        self.collChoice.SetName("اختيار مجموعة الحديث")
        self.bind_choice(self.collChoice, self._on_collection)
        row.Add(self.collChoice, 1, wx.ALL, 4)
        row.Add(self.button(panel, "تنزيل مجموعات", lambda e: self._open_downloads()), 0, wx.ALL, 4)
        row.Add(wx.StaticText(panel, label="الكتاب:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self.bookChoice = wx.Choice(panel, choices=[])
        self.bookChoice.SetName("اختيار الكتاب داخل المجموعة")
        self.bind_choice(self.bookChoice, self._on_book)
        row.Add(self.bookChoice, 2, wx.ALL, 4)
        sizer.Add(row, 0, wx.EXPAND)

        srow = wx.BoxSizer(wx.HORIZONTAL)
        self.searchBox = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.searchBox.SetName("بحث في الكتاب الحالي")
        self.searchBox.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        srow.Add(self.searchBox, 1, wx.ALL, 4)
        srow.Add(self.button(panel, "بحث (Ctrl+G)", self._on_search), 0, wx.ALL, 4)
        srow.Add(self.button(panel, "نسخ الحديث (Ctrl+C)", lambda e: self._copy()), 0, wx.ALL, 4)
        sizer.Add(srow, 0, wx.EXPAND)

        self.text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.text.SetName("نص الأحاديث")
        try:
            self.text.SetLayoutDirection(wx.Layout_RightToLeft)
        except Exception:
            pass
        sizer.Add(self.text, 1, wx.EXPAND | wx.ALL, 5)

        b = wx.BoxSizer(wx.HORIZONTAL)
        b.Add(self.button(panel, "الكتاب السابق (Alt+Left)", lambda e: self._step_book(-1)), 0, wx.ALL, 4)
        b.Add(self.button(panel, "الكتاب التالي (Alt+Right)", lambda e: self._step_book(1)), 0, wx.ALL, 4)
        b.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        sizer.Add(b, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(sizer)
        self._bind_font_keys()
        self._apply_saved_font()
        self._install_commands()
        self.set_first_control(self.collChoice)

    def _install_commands(self):
        cb = CommandBar(self)
        cb.add("الكتاب التالي", "Alt+Right", key(wx.WXK_RIGHT, alt=True), lambda: self._step_book(1))
        cb.add("الكتاب السابق", "Alt+Left", key(wx.WXK_LEFT, alt=True), lambda: self._step_book(-1))
        cb.add_separator()
        cb.add("بحث في الكتاب", "Ctrl+G", key(ord('G'), ctrl=True), lambda: self.searchBox.SetFocus())
        cb.add("نسخ الحديث", "Ctrl+C", key(ord('C'), ctrl=True), self._copy)
        cb.add_separator()
        cb.add("اختيار المجموعة", "Ctrl+L", key(ord('L'), ctrl=True), lambda: self.collChoice.SetFocus())
        cb.add("اختيار الكتاب", "Ctrl+K", key(ord('K'), ctrl=True), lambda: self.bookChoice.SetFocus())
        cb.add("الذهاب إلى النص", "Ctrl+Enter", key(wx.WXK_RETURN, ctrl=True), lambda: self.text.SetFocus())
        cb.add_separator()
        cb.add("تكبير الخط", "Ctrl+=", key(ord('='), ctrl=True), lambda: self._change_font(1))
        cb.add("تصغير الخط", "Ctrl+-", key(ord('-'), ctrl=True), lambda: self._change_font(-1))
        cb.install()

    def _on_collection(self, evt):
        i = self.collChoice.GetSelection()
        if 0 <= i < len(self._avail):
            self._load_collection(self._avail[i])

    def _load_collection(self, entry):
        self._set("hadith_last_collection", entry["id"])
        path = os.path.join(self._res, f"{entry['id']}.json")
        cache = os.path.join(self._cache, f"{entry['id']}.json")
        if os.path.exists(path):
            self._apply_collection(path)
        elif os.path.exists(cache):
            self._apply_collection(cache)
        else:
            # Not downloaded: do NOT auto-download while browsing. Point the user
            # to the downloads window instead.
            self.announce(f"{entry['name']} غير منزّلة. افتح تنزيل مجموعات لتنزيلها.")

    def _refresh_collections(self, select_id=None):
        self._avail = self._available_collections()
        self.collChoice.Set([e["name"] for e in self._avail])
        idx = 0
        if select_id:
            idx = next((i for i, e in enumerate(self._avail) if e["id"] == select_id), 0)
        if self._avail:
            self.collChoice.SetSelection(idx)
            self._load_collection(self._avail[idx])

    def _open_downloads(self):
        dlg = _HadithDownloads(self, self.speech, self)
        self.show_child(dlg)
        # after returning, refresh available collections (some may be new)
        self._refresh_collections()

    def _download_collection(self, entry):
        beep = BeepLoop(); beep.start()
        try:
            os.makedirs(self._cache, exist_ok=True)
            raw = os.path.join(self._cache, f"{entry['id']}.raw")
            last = [0.0]
            def _prog(done, total):
                import time as _t
                if total and _t.time() - last[0] > 2.0:
                    last[0] = _t.time()
                    announce(f"{int(done*100/total)} بالمئة", self.announce)
            if not download_to(entry["url"], raw, progress=_prog):
                raise IOError("download failed")
            with open(raw, encoding="utf-8") as f:
                d = json.loads(f.read())
            try: os.remove(raw)
            except OSError: pass
            sections = d.get("metadata", {}).get("sections", {})
            books = {}
            for h in d.get("hadiths", []):
                bno = h.get("reference", {}).get("book", 0)
                books.setdefault(bno, []).append(
                    {"n": h.get("hadithnumber"), "text": (h.get("text") or "").strip()})
            booklist = [{"no": b, "title": sections.get(str(b), "") or f"كتاب {b}",
                         "hadiths": books[b]} for b in sorted(books, key=lambda x: (x is None, x))]
            payload = {"id": entry["id"], "name": entry["name"], "books": booklist}
            tmp = os.path.join(self._cache, f"{entry['id']}.json.part")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, os.path.join(self._cache, f"{entry['id']}.json"))
            beep.stop()
            self.call_after(self._apply_collection, os.path.join(self._cache, f"{entry['id']}.json"))
        except Exception:
            beep.stop()
            self.call_after(self.announce, "تعذّر تنزيل المجموعة. تحقّق من الاتصال بالإنترنت.")

    def _apply_collection(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = None
        # Guard against a malformed/partial cache (e.g. a raw API dump saved by
        # an older build). If it lacks our {"books": [...]} shape, delete it and
        # rebuild from source.
        if not isinstance(data, dict) or "books" not in data:
            try:
                if path.startswith(self._cache):
                    os.remove(path)
            except OSError:
                pass
            entry = next((e for e in self.index
                          if os.path.basename(path).startswith(e["id"])), None)
            if entry is not None:
                self.announce("جارٍ إصلاح الملف وإعادة تنزيله...")
                import threading
                threading.Thread(target=self._download_collection, args=(entry,), daemon=True).start()
            return
        self._collection = data
        self._books = self._collection["books"]
        self.bookChoice.Set([f"{b['title']} ({len(b['hadiths'])} حديث)" for b in self._books])
        if self._books:
            self.bookChoice.SetSelection(0)
            self._render_book(0)
        self.announce(f"{self._collection['name']}: {len(self._books)} كتاب.")

    def _on_book(self, evt):
        self._render_book(self.choice_index(self.bookChoice))

    def _step_book(self, delta):
        i = self.choice_index(self.bookChoice) + delta
        if 0 <= i < len(self._books):
            self.bookChoice.SetSelection(i)
            self._render_book(i)

    def _render_book(self, i):
        book = self._books[i]
        lines = [f"{self._collection['name']} — {book['title']}"]
        self._line_hadith = [0]
        for h in book["hadiths"]:
            lines.append(f"[{h['n']}] {h['text']}")
            self._line_hadith.append(h["n"])
        self._text_str = "\n".join(lines)
        self.text.SetValue(self._text_str)
        self.text.SetInsertionPoint(0)
        self.text.SetFocus()

    def _current_text(self):
        ip = self.text.GetInsertionPoint()
        line = self._text_str.count("\n", 0, ip)
        parts = self._text_str.split("\n")
        return parts[line] if 0 <= line < len(parts) else ""

    def _copy(self):
        txt = self._current_text()
        if not txt:
            return
        try:
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(txt))
                wx.TheClipboard.Close()
                self.announce("تم نسخ الحديث.")
        except Exception:
            self.announce("تعذّر النسخ.")

    def _on_search(self, evt):
        from ..engine.grading import strip_arabic_diacritics
        q = strip_arabic_diacritics(self.searchBox.GetValue().strip())
        if not q or not self._books:
            return
        book = self._books[self.choice_index(self.bookChoice)]
        for j, h in enumerate(book["hadiths"]):
            if q in strip_arabic_diacritics(h["text"]):
                target = j + 1
                pos = sum(len(x) + 1 for x in self._text_str.split("\n")[:target])
                self.text.SetInsertionPoint(pos)
                self.text.SetFocus()
                self.announce(f"حديث رقم {h['n']}.")
                return
        self.announce("لا توجد نتائج في هذا الكتاب.")


    def _bind_font_keys(self):
        # Ctrl+=/Ctrl+- handled by the command bar char-hook; no binding needed.
        pass

    def _font_key(self, evt):
        if evt.ControlDown() and evt.GetKeyCode() in (ord('='), ord('+'), wx.WXK_NUMPAD_ADD):
            self._change_font(1)
        elif evt.ControlDown() and evt.GetKeyCode() in (ord('-'), wx.WXK_NUMPAD_SUBTRACT):
            self._change_font(-1)
        else:
            evt.Skip()

    def _change_font(self, delta):
        try:
            f = self.text.GetFont()
            size = max(8, min(48, f.GetPointSize() + delta * 2))
            f.SetPointSize(size)
            self.text.SetFont(f)
            try:
                self.academy.store.set_setting("reader_font_size", str(size))
            except Exception:
                pass
            self.announce(f"حجم الخط {size}")
        except Exception:
            pass

    def _apply_saved_font(self):
        try:
            size = int(self.academy.store.get_setting("reader_font_size", "0") or 0)
            if size >= 8:
                f = self.text.GetFont(); f.SetPointSize(size); self.text.SetFont(f)
        except Exception:
            pass

    def instructions(self) -> str:
        return ("اختر المجموعة (البخاري، مسلم، ...) ثم الكتاب (كتاب الإيمان، كتاب الصلاة، ...). "
                "يُعرض كل كتاب وحده، كل حديث في فقرة مرقّمة، فتنقّل بأوامر الأسطر في the screen reader. "
                "الكتاب السابق/التالي للتنقّل، ويمكنك البحث داخل الكتاب الحالي ونسخ الحديث. "
                "المجموعات الكبيرة تُنزَّل عند أول استخدام. Escape للإغلاق.")


class _HadithDownloads(AccessibleDialog):
    """Manage hadith collections: download absent ones, remove downloaded ones.
    Bundled collections are always present and cannot be removed."""

    def __init__(self, parent, speech, reader):
        super().__init__(parent, "تنزيل مجموعات الحديث", speech, size=(680, 500))
        self.reader = reader
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label="نزّل المجموعات التي تريدها للاستخدام دون إنترنت، "
                                        "أو احذف نسخة منزّلة."), 0, wx.ALL, 8)
        self.listBox = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.listBox.SetName("قائمة مجموعات الحديث")
        s.Add(self.listBox, 1, wx.EXPAND | wx.ALL, 6)
        b = wx.BoxSizer(wx.HORIZONTAL)
        b.Add(self.button(panel, "تنزيل", lambda e: self._download()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "حذف المنزّل", lambda e: self._remove()), 0, wx.ALL, 4)
        b.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        s.Add(b, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self._reload()
        self.set_first_control(self.listBox)

    def _reload(self):
        self._entries = self.reader.index
        rows = []
        for e in self._entries:
            if e.get("bundled"):
                tag = "مضمّنة"
            elif self.reader._is_available(e):
                tag = "منزّلة"
            else:
                tag = "غير منزّلة"
            rows.append(f"{e['name']} — {tag}")
        self.listBox.Set(rows)
        if self._entries:
            self.select_index(self.listBox, 0)

    def _sel(self):
        i = self.listBox.GetSelection()
        return self._entries[i] if i != wx.NOT_FOUND else None

    def _download(self):
        e = self._sel()
        if not e:
            return
        if self.reader._is_available(e):
            self.announce("منزّلة بالفعل.")
            return
        self.announce(f"جارٍ تنزيل {e['name']}...")
        import threading
        threading.Thread(target=self._dl_worker, args=(e,), daemon=True).start()

    def _dl_worker(self, entry):
        # reuse the reader's downloader, then refresh this list
        self.reader._download_collection(entry)
        self.call_after(self._after)

    def _after(self):
        self._reload()

    def _remove(self):
        e = self._sel()
        if not e:
            return
        if e.get("bundled"):
            self.announce("هذه المجموعة مضمّنة ولا يمكن حذفها.")
            return
        import os as _os
        cache = _os.path.join(self.reader._cache, f"{e['id']}.json")
        if _os.path.exists(cache):
            try:
                _os.remove(cache)
                self.announce(f"تم حذف {e['name']}.")
            except OSError:
                self.announce("تعذّر الحذف.")
        else:
            self.announce("غير منزّلة.")
        self._reload()

    def instructions(self) -> str:
        return ("اختر مجموعة ثم تنزيل لإضافتها، أو حذف المنزّل لإزالتها. المجموعات "
                "المضمّنة متوفّرة دائماً. Escape للإغلاق.")
