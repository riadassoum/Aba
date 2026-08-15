# -*- coding: utf-8 -*-
"""
abaAcademy.gui.quran_reader
===========================

A full Qur'an Mushaf reader presented as a **text window**: the current
division (surah / juz / hizb / rub' / page) is rendered into a read-only
multiline text control with exactly one ayah per line, so NVDA's line/say-all
commands become ayah commands and reading is natural. The ayah under the caret
is the one every action works on (listen, copy, translation, tafsir, bookmark,
info).

Design adapted (re-implemented) from the GPL projects Rattil and Al-Bayan by
TecWindow — see COPYING.txt. Text/audio via the Tanzil / alquran.cloud data,
played through the add-on's own bundled player with on-device caching.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading

try:
    import wx
    _HAS_WX = True
except Exception:
    _HAS_WX = False

from .accessible import AccessibleDialog
from ..engine.grading import strip_arabic_diacritics
from .audio_player import AudioPlayer
from .quran_audio import QuranAudio
from .quran_editions import QuranEditions
from .command_bar import CommandBar, key
from .quran_audio import verse_url

RECITERS = [
    ("ar.alafasy", "مشاري راشد العفاسي", 128),
    ("ar.abdulbasitmurattal", "عبد الباسط عبد الصمد (مرتّل)", 128),
    ("ar.husary", "محمود خليل الحصري", 128),
    ("ar.minshawi", "محمد صديق المنشاوي", 128),
    ("ar.mahermuaiqly", "ماهر المعيقلي", 128),
    ("ar.hudhaify", "علي بن عبد الرحمن الحذيفي", 128),
    ("ar.shaatree", "أبو بكر الشاطري", 128),
    ("ar.ahmedajamy", "أحمد بن علي العجمي", 128),
    ("ar.hanirifai", "هاني الرفاعي", 128),
    ("ar.abdullahbasfar", "عبد الله بصفر", 128),
]

# navigation modes: (label, key, count)
MODES = [("سورة", "surah", 114), ("جزء", "juz", 30), ("حزب", "hizb", 60),
         ("ربع الحزب", "rub", 240), ("صفحة", "page", 604)]

_AR_IND = "٠١٢٣٤٥٦٧٨٩"


def _ar_num(n) -> str:
    return "".join(_AR_IND[int(d)] for d in str(n))


def _norm_ar(s: str) -> str:
    s = strip_arabic_diacritics(s or "")
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"),
                 ("ى", "ي"), ("ة", "ه"), ("ـ", "")):
        s = s.replace(a, b)
    return " ".join(s.split()).strip()


_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def _load_quran():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "resources", "quran", "quran_data.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class QuranReader(AccessibleDialog):
    S, A, N, JUZ, PAGE, HQ, TEXT = range(7)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, "المصحف — قراءة القرآن الكريم", speech, size=(820, 640))
        self.academy = academy
        data = _load_quran()
        self.ayat = data["ayat"]
        self.surahs = {s["n"]: s for s in data["surahs"]}
        self._surah_norm = [(s["n"], _norm_ar(s["name"])) for s in data["surahs"]]

        # division indexes
        self._idx = {"surah": {}, "juz": {}, "hizb": {}, "rub": {}, "page": {}}
        for r in self.ayat:
            self._idx["surah"].setdefault(r[self.S], []).append(r)
            self._idx["juz"].setdefault(r[self.JUZ], []).append(r)
            self._idx["page"].setdefault(r[self.PAGE], []).append(r)
            self._idx["rub"].setdefault(r[self.HQ], []).append(r)
            self._idx["hizb"].setdefault((r[self.HQ] + 3) // 4, []).append(r)

        cache_root = os.path.join(getattr(academy, "user_data_dir", tempfile.gettempdir()),
                                  "quran_audio")
        self._audio = QuranAudio(cache_root)
        res_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "resources", "quran")
        self._res = res_dir
        ed_cache = os.path.join(getattr(academy, "user_data_dir", tempfile.gettempdir()),
                                "quran_editions")
        uthmani = [row[self.TEXT] for row in self.ayat]
        self._ed = QuranEditions(res_dir, ed_cache, uthmani=uthmani)
        # per-ayah reciters (from bundled reciters.json) + the alquran.cloud CDN default
        self._reciters = self._load_reciters(res_dir)
        # defaults come from settings; the Mushaf shows only these
        g = lambda k, d: (self.academy.store.get_setting(k, d) or d) if hasattr(self.academy, "store") else d
        self._script_id = g("quran_default_script", "quran-uthmani")
        self._default_translation = g("quran_default_translation", "en.sahih")
        self._default_tafsir = g("quran_default_tafsir", "ar.muyassar")
        self._default_reciter = g("quran_default_reciter", "cdn:ar.alafasy")

        self._mode = "surah"
        self._number = 1
        self._line_ayah = []     # line index -> global ayah number (0 = heading)
        self._text_str = ""
        self._repeat = False
        self._continuous = False
        self._hifz = None   # {"from":n,"to":n,"times":k,"count":done}

        self._build_ui()
        start_num = self._load_last_position()
        self._go_to_ayah(start_num, focus=True)

    def _load_reciters(self, res_dir):
        recs = [{"key": "cdn:ar.alafasy", "name": "مشاري راشد العفاسي", "rewaya": "حفص عن عاصم",
                 "cdn": "ar.alafasy", "bitrate": 128, "url": None}]
        try:
            with open(os.path.join(res_dir, "reciters.json"), encoding="utf-8") as f:
                for r in json.load(f):
                    recs.append({"key": r["name"], "name": r["name"],
                                 "rewaya": r.get("rewaya", ""), "cdn": None,
                                 "url": r.get("url"), "bitrate": r.get("bitrate", 128)})
        except Exception:
            pass
        return recs

    def _reciter_entry(self):
        return next((r for r in self._reciters if r["key"] == self._default_reciter),
                    self._reciters[0])

    # -- UI ----------------------------------------------------------------

    def _build_ui(self):
        panel = wx.Panel(self)
        self._panel = panel
        sizer = wx.BoxSizer(wx.VERTICAL)

        # compact: show current defaults + a button to the manager window
        r1 = wx.BoxSizer(wx.HORIZONTAL)
        self.defaultsLabel = wx.StaticText(panel, label=self._defaults_text())
        r1.Add(self.defaultsLabel, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        r1.Add(self.button(panel, "إدارة الموارد (Ctrl+O)", self._open_manager), 0, wx.ALL, 4)
        sizer.Add(r1, 0, wx.EXPAND)

        # row 3: navigation mode + number + go + prev/next
        r3 = wx.BoxSizer(wx.HORIZONTAL)
        r3.Add(wx.StaticText(panel, label="التنقل:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 3)
        self.modeChoice = wx.Choice(panel, choices=[m[0] for m in MODES])
        self.modeChoice.SetSelection(0); self.modeChoice.SetName("نوع التنقل")
        self.bind_choice(self.modeChoice, self._on_mode_change)
        r3.Add(self.modeChoice, 0, wx.ALL, 3)
        self.navNum = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.navNum.SetName("الرقم أو اسم السورة"); self.navNum.Bind(wx.EVT_TEXT_ENTER, self._on_go)
        r3.Add(self.navNum, 1, wx.ALL, 3)
        r3.Add(self.button(panel, "اذهب (Ctrl+J)", self._on_go), 0, wx.ALL, 3)
        r3.Add(self.button(panel, "السابق (Alt+Left)", lambda e: self._step_division(-1)), 0, wx.ALL, 3)
        r3.Add(self.button(panel, "التالي (Alt+Right)", lambda e: self._step_division(1)), 0, wx.ALL, 3)
        sizer.Add(r3, 0, wx.EXPAND)

        # row 4: search
        r4 = wx.BoxSizer(wx.HORIZONTAL)
        self.searchBox = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.searchBox.SetName("بحث في القرآن أو الترجمة"); self.searchBox.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        r4.Add(self.searchBox, 1, wx.ALL, 3)
        r4.Add(self.button(panel, "بحث (Ctrl+G)", self._on_search), 0, wx.ALL, 3)
        sizer.Add(r4, 0, wx.EXPAND)

        # the text window (one ayah per line)
        self.text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.text.SetName("نص المصحف")
        try:
            self.text.SetLayoutDirection(wx.Layout_RightToLeft)
        except Exception:
            pass
        self.text.Bind(wx.EVT_KEY_DOWN, self._on_text_key)
        sizer.Add(self.text, 1, wx.EXPAND | wx.ALL, 5)

        # buttons
        b = wx.BoxSizer(wx.HORIZONTAL)
        for label, handler in [
            ("استمع (Enter)", lambda e: self._play_current()),
            ("إيقاف (Ctrl+S)", lambda e: self._stop_audio()),
            ("ترجمة الآية (Ctrl+T)", lambda e: self._read_translation()),
            ("تفسير الآية (Ctrl+F)", lambda e: self._read_tafsir()),
            ("إعراب الآية (Ctrl+E)", lambda e: self._speak_edition("ar.e3rab", "الإعراب")),
            ("أسباب النزول (Ctrl+B)", lambda e: self._read_asbab()),
            ("معلومات الآية (Ctrl+I)", lambda e: self._ayah_info()),
            ("تحليل الكلمات (Ctrl+W)", lambda e: self._word_analysis()),
            ("نسخ (Ctrl+C)", lambda e: self._copy_ayah()),
            ("علامة (Ctrl+D)", lambda e: self._add_bookmark()),
            ("العلامات (Ctrl+M)", lambda e: self._open_bookmarks()),
            ("تنزيل السورة (Ctrl+Shift+D)", self._on_download_surah),
        ]:
            b.Add(self.button(panel, label, handler), 0, wx.ALL, 2)
        sizer.Add(b, 0, wx.ALIGN_RIGHT)

        c = wx.BoxSizer(wx.HORIZONTAL)
        self.contChk = wx.CheckBox(panel, label="تشغيل متواصل")
        self.contChk.Bind(wx.EVT_CHECKBOX, lambda e: setattr(self, "_continuous", self.contChk.GetValue()))
        c.Add(self.contChk, 0, wx.ALL, 4)
        self.repeatChk = wx.CheckBox(panel, label="تكرار الآية")
        self.repeatChk.Bind(wx.EVT_CHECKBOX, lambda e: setattr(self, "_repeat", self.repeatChk.GetValue()))
        c.Add(self.repeatChk, 0, wx.ALL, 4)
        c.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        sizer.Add(c, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(sizer)
        self._player = AudioPlayer(panel, on_finished=self._on_audio_finished)
        self._dl_stop = False
        self._bind_font_keys()
        self._apply_saved_font()
        self._install_commands()
        self.set_first_control(self.text)

    def _install_commands(self):
        cb = CommandBar(self)
        cb.add("استمع للآية", "Enter", None, self._play_current)
        cb.add("إيقاف الصوت", "Ctrl+S", key(ord('S'), ctrl=True), self._stop_audio)
        cb.add_separator()
        cb.add("ترجمة الآية", "Ctrl+T", key(ord('T'), ctrl=True), self._read_translation)
        cb.add("تفسير الآية", "Ctrl+F", key(ord('F'), ctrl=True), self._read_tafsir)
        cb.add("إعراب الآية", "Ctrl+E", key(ord('E'), ctrl=True),
               lambda: self._speak_edition("ar.e3rab", "الإعراب"))
        cb.add("أسباب النزول", "Ctrl+B", key(ord('B'), ctrl=True), self._read_asbab)
        cb.add("معلومات الآية", "Ctrl+I", key(ord('I'), ctrl=True), self._ayah_info)
        cb.add("تحليل كلمات الآية", "Ctrl+W", key(ord('W'), ctrl=True), self._word_analysis)
        cb.add_separator()
        cb.add("نسخ الآية", "Ctrl+C", key(ord('C'), ctrl=True), self._copy_ayah)
        cb.add("حفظ علامة", "Ctrl+D", key(ord('D'), ctrl=True), self._add_bookmark)
        cb.add("العلامات", "Ctrl+M", key(ord('M'), ctrl=True), self._open_bookmarks)
        cb.add("بحث", "Ctrl+G", key(ord('G'), ctrl=True), lambda: self.searchBox.SetFocus())
        cb.add_separator()
        cb.add("القسم التالي", "Alt+Right", key(wx.WXK_RIGHT, alt=True), lambda: self._step_division(1))
        cb.add("القسم السابق", "Alt+Left", key(wx.WXK_LEFT, alt=True), lambda: self._step_division(-1))
        cb.add("الانتقال إلى رقم/سورة", "Ctrl+J", key(ord('J'), ctrl=True), lambda: self.navNum.SetFocus())
        cb.add("الذهاب إلى سورة وآية", "Ctrl+Shift+J", key(ord('J'), ctrl=True, shift=True), self._open_goto_dialog)
        cb.add_separator()
        cb.add("تشغيل متواصل (تبديل)", "Ctrl+P", key(ord('P'), ctrl=True), self._toggle_continuous)
        cb.add("تكرار الآية (تبديل)", "Ctrl+R", key(ord('R'), ctrl=True), self._toggle_repeat)
        cb.add("حفظ: تكرار مقطع", "Ctrl+H", key(ord('H'), ctrl=True), self._start_hifz)
        cb.add("تنزيل السورة الحالية", "Ctrl+Shift+D", key(ord('D'), ctrl=True, shift=True),
               lambda: self._on_download_surah(None))
        cb.add("إدارة الموارد", "Ctrl+O", key(ord('O'), ctrl=True), lambda: self._open_manager(None))
        cb.add("مشغّل السور الكاملة", "Ctrl+U", key(ord('U'), ctrl=True), self._open_surah_player)
        cb.add_separator()
        cb.add("تكبير الخط", "Ctrl+=", key(ord('='), ctrl=True), lambda: self._change_font(1))
        cb.add("تصغير الخط", "Ctrl+-", key(ord('-'), ctrl=True), lambda: self._change_font(-1))
        cb.install()

    def _toggle_continuous(self):
        self._continuous = not self._continuous
        self.contChk.SetValue(self._continuous)
        self.announce("تشغيل متواصل مُفعّل." if self._continuous else "تشغيل متواصل متوقّف.")

    def _toggle_repeat(self):
        self._repeat = not self._repeat
        self.repeatChk.SetValue(self._repeat)
        self.announce("تكرار الآية مُفعّل." if self._repeat else "تكرار الآية متوقّف.")

    def _open_surah_player(self):
        from .surah_player import SurahPlayer
        self.show_child(SurahPlayer(self, self.academy, self.speech))

    def _open_manager(self, evt):
        from .quran_manager import QuranManager
        cur = self._current_num()
        dlg = QuranManager(self, self.academy, self.speech, self._ed, self._audio,
                           self._reciters, self.ayat, self.surahs)
        self.show_child(dlg)
        # reload defaults (they may have changed) and re-render
        g = lambda k, d: (self.academy.store.get_setting(k, d) or d)
        self._script_id = g("quran_default_script", "quran-uthmani")
        self._default_translation = g("quran_default_translation", "en.sahih")
        self._default_tafsir = g("quran_default_tafsir", "ar.muyassar")
        self._default_reciter = g("quran_default_reciter", "cdn:ar.alafasy")
        self.defaultsLabel.SetLabel(self._defaults_text())
        self._go(self._mode, self._number, target_num=cur, focus=True)

    # -- rendering ---------------------------------------------------------

    def _division_rows(self, mode, number):
        return self._idx.get(mode, {}).get(number, [])

    def _render(self, rows, target_num=None):
        lines = []
        self._line_ayah = []
        prev_s = None
        target_line = 0
        for r in rows:
            if r[self.S] != prev_s:
                m = self.surahs[r[self.S]]
                lines.append(f"{m['name']} — {m['type']} — {_ar_num(m['count'])} آية")
                self._line_ayah.append(0)
                prev_s = r[self.S]
            arr = self._ed.get_edition(self._script_id)
            text = arr[r[self.N] - 1] if arr else r[self.TEXT]
            lines.append(f"{text} {'﴿' + _ar_num(r[self.A]) + '﴾'}")
            self._line_ayah.append(r[self.N])
            if target_num is not None and r[self.N] == target_num:
                target_line = len(self._line_ayah) - 1
        self._text_str = "\n".join(lines)
        self.text.SetValue(self._text_str)
        # move caret to the target ayah's line
        pos = 0
        for i in range(target_line):
            pos += len(lines[i]) + 1
        self.text.SetInsertionPoint(pos)
        # prefetch this division's audio so any Enter is instant
        r = self._reciter_entry()
        if r.get("cdn"):
            self._audio.prefetch(r["cdn"], r["bitrate"], [x[self.N] for x in rows])
        else:
            sa = {x[self.N]: (x[self.S], x[self.A]) for x in rows}
            self._audio.prefetch(r["key"], r["bitrate"], [x[self.N] for x in rows],
                                 url_for=lambda num: verse_url(r["url"], *sa[num]))

    def _go(self, mode, number, target_num=None, focus=False, announce=True):
        rows = self._division_rows(mode, number)
        if not rows:
            if announce:
                self.announce("خارج النطاق.")
            return
        self._mode, self._number = mode, number
        self._render(rows, target_num=target_num)
        if focus:
            self.text.SetFocus()
        if announce:
            self._announce_current()

    def _go_to_ayah(self, global_num, focus=False, announce=True):
        row = next((r for r in self.ayat if r[self.N] == global_num), self.ayat[0])
        self._go(self._mode, row[{"surah": self.S, "juz": self.JUZ, "page": self.PAGE,
                                  "rub": self.HQ}.get(self._mode, self.S)]
                 if self._mode != "hizb" else (row[self.HQ] + 3) // 4,
                 target_num=global_num, focus=focus, announce=announce)

    def _step_division(self, delta):
        count = dict((m[1], m[2]) for m in MODES)[self._mode]
        n = self._number + delta
        if 1 <= n <= count:
            self._go(self._mode, n, focus=True)

    # -- caret -> ayah -----------------------------------------------------

    def _caret_line(self):
        ip = self.text.GetInsertionPoint()
        return self._text_str.count("\n", 0, ip)

    def _current_num(self):
        line = self._caret_line()
        n = self._line_ayah[line] if 0 <= line < len(self._line_ayah) else 0
        if n:
            return n
        for j in range(line + 1, len(self._line_ayah)):
            if self._line_ayah[j]:
                return self._line_ayah[j]
        for j in range(line - 1, -1, -1):
            if self._line_ayah[j]:
                return self._line_ayah[j]
        return None

    def _row(self, global_num):
        return next((r for r in self.ayat if r[self.N] == global_num), None)

    def _announce_current(self):
        n = self._current_num()
        r = self._row(n) if n else None
        if r:
            self.academy.store.set_setting("quran_last", str(n)) if hasattr(self.academy, "store") else None

    # -- navigation input --------------------------------------------------

    def _on_mode_change(self, evt):
        # Changing the navigation-mode combo should update the content quietly:
        # the combo box announces its own new value, and bind_choice keeps focus
        # on the combo. If we moved focus to the text and announced the ayah here,
        # it would talk over the combo's announcement and yank the user out of the
        # combo. So: no focus change, no announcement — just refresh the view.
        mode = MODES[self.modeChoice.GetSelection()][1]
        cur = self._current_num()
        self._mode = mode
        if cur:
            self._go_to_ayah(cur, focus=False, announce=False)
        else:
            self._go(mode, 1, focus=False, announce=False)

    def _on_go(self, evt):
        raw = self.navNum.GetValue().strip().translate(_AR_DIGITS)
        if not raw:
            # empty box -> open the precise surah+ayah dialog (al-bayan style)
            self._open_goto_dialog()
            return
        if raw.isdigit():
            self._go(self._mode, int(raw), focus=True)
        else:
            idx = self._find_surah_by_name(raw)
            if idx is None:
                self.announce("لم يُعثر على مطابقة.")
                return
            self._mode = "surah"
            self.modeChoice.SetSelection(0)
            self._go("surah", self.ayat[idx][self.S], target_num=self.ayat[idx][self.N], focus=True)

    def _open_goto_dialog(self):
        """A precise go-to: pick a surah, then an ayah number *within that surah*
        (the field's maximum updates to the surah's ayah count, and the Go button
        disables on an out-of-range number). Adapted from the al-bayan project
        (GPL v3)."""
        cur = self._current_num() or 1
        cur_row = self._row(cur)
        cur_surah = cur_row[self.S] if cur_row else 1
        cur_ayah = cur_row[self.A] if cur_row else 1
        names = [self.surahs[i]["name"] for i in range(1, 115)]

        dlg = wx.Dialog(self, title="الذهاب إلى سورة وآية")
        panel = wx.Panel(dlg); sz = wx.BoxSizer(wx.VERTICAL)
        sz.Add(wx.StaticText(panel, label="السورة:"), 0, wx.ALL, 4)
        surahChoice = wx.Choice(panel, choices=names)
        surahChoice.SetName("اختر السورة")
        surahChoice.SetSelection(cur_surah - 1)
        sz.Add(surahChoice, 0, wx.EXPAND | wx.ALL, 4)
        info = wx.StaticText(panel, label="")
        sz.Add(info, 0, wx.ALL, 4)
        sz.Add(wx.StaticText(panel, label="رقم الآية في السورة:"), 0, wx.ALL, 4)
        aySpin = wx.SpinCtrl(panel, min=1, max=286, initial=cur_ayah)
        aySpin.SetName("رقم الآية")
        sz.Add(aySpin, 0, wx.EXPAND | wx.ALL, 4)
        b = wx.BoxSizer(wx.HORIZONTAL)
        goBtn = wx.Button(panel, wx.ID_OK, "اذهب"); goBtn.SetDefault()
        cancelBtn = wx.Button(panel, wx.ID_CANCEL, "إلغاء")
        b.Add(goBtn, 0, wx.ALL, 4); b.Add(cancelBtn, 0, wx.ALL, 4)
        sz.Add(b, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(sz)

        def ayah_count(surah):
            rows = self._idx["surah"].get(surah, [])
            return rows[-1][self.A] if rows else 1

        def update_range(evt=None):
            surah = surahChoice.GetSelection() + 1
            mx = ayah_count(surah)
            aySpin.SetRange(1, mx)
            if aySpin.GetValue() > mx:
                aySpin.SetValue(1)
            info.SetLabel(f"{names[surah-1]} — عدد آياتها {mx}")

        def _update_keep_focus(evt, _c=surahChoice):
            update_range(evt)
            wx.CallAfter(lambda: _c.SetFocus() if _c else None)
        surahChoice.Bind(wx.EVT_CHOICE, _update_keep_focus)
        update_range()

        if dlg.ShowModal() == wx.ID_OK:
            surah = surahChoice.GetSelection() + 1
            ayah = aySpin.GetValue()
            g = self._global_of(surah, ayah)
            if g is not None:
                self._mode = "surah"
                self.modeChoice.SetSelection(0)
                self._go("surah", surah, target_num=g, focus=True)
            else:
                self.announce("رقم الآية خارج نطاق السورة.")
        dlg.Destroy()

    def _find_surah_by_name(self, query):
        q = _norm_ar(query)
        if not q or len(q) < 2:
            return None
        forward, reverse = [], []
        for n, name in self._surah_norm:
            core = name.replace("سوره", "").strip()
            core_noal = core[2:] if core.startswith("ال") else core
            if q in name:
                forward.append((n, q in (name, core, core_noal), bool(core_noal) and core_noal.startswith(q)))
            elif len(core_noal) >= 3 and core_noal in q:
                reverse.append(n)
        if forward:
            forward.sort(key=lambda t: (t[1], t[2]), reverse=True)
            best = forward[0][0]
        elif reverse:
            best = reverse[0]
        else:
            return None
        return next((i for i, r in enumerate(self.ayat) if r[self.S] == best), None)

    # -- text window keys --------------------------------------------------

    def _on_text_key(self, evt):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._play_current()
        else:
            evt.Skip()

    # -- script / editions -------------------------------------------------

    def _on_script_change(self, evt):
        e = self._scripts[self.scriptChoice.GetSelection()]
        sid = e["id"]
        cur = self._current_num()
        if self._ed.is_offline(sid):
            self._script_id = sid
            self._go(self._mode, self._number, target_num=cur, focus=True)
        else:
            self.announce("جارٍ تنزيل هذا النص لأول مرة...")
            threading.Thread(target=self._fetch_script, args=(sid, cur), daemon=True).start()

    def _fetch_script(self, sid, cur):
        arr = self._ed.fetch_edition(sid)
        if arr:
            def _apply():
                self._script_id = sid
                self._go(self._mode, self._number, target_num=cur, focus=True)
                self.announce("تم تغيير النص.")
            wx.CallAfter(_apply)
        else:
            wx.CallAfter(self.announce, "تعذّر تنزيل هذا النص.")

    def _read_translation(self):
        if not self._default_translation:
            self.announce("لم تُعيّن ترجمة افتراضية.")
            return
        self._speak_edition(self._default_translation, "الترجمة")

    def _read_tafsir(self):
        if not self._default_tafsir:
            self.announce("لم يُعيّن تفسير افتراضي.")
            return
        self._speak_edition(self._default_tafsir, "التفسير")

    def _read_asbab(self):
        n = self._current_num()
        if not n:
            return
        txt = self._ed.text("ar.asbab", n)
        if txt:
            self._show_text_window(self._edition_title("أسباب النزول", n), txt)
        else:
            self.announce("لا يوجد سبب نزول محدّد لهذه الآية.")

    def _show_text_window(self, title, body):
        try:
            size = int(self.academy.store.get_setting("reader_font_size", "0") or 0)
        except Exception:
            size = 0
        dlg = TextViewDialog(self, self.speech, title, body, font_size=size)
        self.show_child(dlg)

    def _edition_title(self, label, n):
        r = self._row(n)
        if r:
            m = self.surahs[r[self.S]]
            return f"{label} — {m['name']} : {r[self.A]}"
        return label

    def _speak_edition(self, edition_id, label):
        n = self._current_num()
        if not n:
            return
        txt = self._ed.text(edition_id, n)
        if txt is not None:
            self._show_text_window(self._edition_title(label, n), txt)
            return
        self.announce(f"جارٍ تنزيل {label} لأول مرة...")
        threading.Thread(target=self._fetch_edition_ayah, args=(edition_id, n, label), daemon=True).start()

    def _fetch_edition_ayah(self, edition_id, num, label):
        arr = self._ed.fetch_edition(edition_id)
        if arr and 1 <= num <= len(arr) and arr[num - 1]:
            wx.CallAfter(self._show_text_window, self._edition_title(label, num), arr[num - 1])
        else:
            wx.CallAfter(self.announce, f"تعذّر تنزيل {label}.")

    # -- audio -------------------------------------------------------------

    def _defaults_text(self):
        def nm(items, ident, fallback=""):
            for e in items:
                if e.get("id") == ident:
                    return e.get("arname") or e.get("name") or ident
            return fallback or ident
        script = nm(self._ed.by_type("quran"), self._script_id, "العثماني")
        rec = self._reciter_entry()["name"]
        return f"المصحف: {script} | القارئ: {rec} (غيّرها من إدارة الموارد)"

    def _play_url_for(self, num):
        """Return (cache_tag, bitrate, url) for the current default reciter."""
        r = self._reciter_entry()
        if r.get("cdn"):
            return r["cdn"], r["bitrate"], None            # alquran.cloud CDN (global num)
        row = self._row(num)
        return r["key"], r["bitrate"], verse_url(r["url"], row[self.S], row[self.A])

    def _play_current(self):
        n = self._current_num()
        if not n:
            return
        tag, bitrate, url = self._play_url_for(n)
        # Always play a downloaded ayah straight from the cache — no network,
        # so it works fully offline once the surah (or part of it) is downloaded.
        hit = self._audio.cached(tag, n)
        if hit:
            self._start(hit)
        else:
            self.announce("جارٍ تحميل التلاوة...")
            threading.Thread(target=self._fetch_then_play, args=(tag, bitrate, n, url), daemon=True).start()

    def _fetch_then_play(self, tag, bitrate, num, url):
        path = self._audio.fetch(tag, bitrate, num, url=url)
        if path:
            wx.CallAfter(self._start, path)
        else:
            wx.CallAfter(self.announce,
                         "هذه الآية غير منزّلة ولا يوجد اتصال بالإنترنت. "
                         "نزّل السورة أولاً للاستماع دون إنترنت.")

    def _start(self, path):
        if not self._player.play_file(path):
            err = getattr(self._player, "last_error", "")
            msg = "تعذّر تشغيل الصوت على هذا النظام."
            if err:
                msg += f" (التفاصيل: {err})"
            self.announce(msg)

    def _stop_audio(self):
        if self._player is not None:
            self._player.stop()

    def _on_audio_finished(self):
        if self._hifz:
            self._hifz_advance()
        elif self._repeat:
            self._play_current()
        elif self._continuous:
            self._move_next_and_play()

    def _start_hifz(self):
        """Memorisation (hifz) repeat over a range that may span surahs, e.g.
        from Al-Fatiha ayah 1 to Al-Baqarah ayah 3. The user picks the start
        surah+ayah, the end surah+ayah, how many repeats, and the repeat mode:
        repeat the whole range N times, repeat each ayah N times before moving
        on, or hybrid (each ayah N times AND the whole range N times)."""
        cur = self._current_num() or 1
        cur_row = self._row(cur)
        cur_surah = cur_row[self.S] if cur_row else 1
        cur_ayah = cur_row[self.A] if cur_row else 1
        surah_names = [self.surahs[i]["name"] for i in range(1, 115)]

        dlg = wx.Dialog(self, title="حفظ: تكرار مقطع للحفظ")
        p = wx.Panel(dlg); sz = wx.BoxSizer(wx.VERTICAL)

        def combo(label, choices, sel):
            sz.Add(wx.StaticText(p, label=label), 0, wx.ALL, 4)
            c = wx.Choice(p, choices=choices); c.SetSelection(sel)
            sz.Add(c, 0, wx.EXPAND | wx.ALL, 4); return c

        def field(label, val):
            sz.Add(wx.StaticText(p, label=label), 0, wx.ALL, 4)
            t = wx.TextCtrl(p, value=str(val)); sz.Add(t, 0, wx.EXPAND | wx.ALL, 4); return t

        from_surah = combo("من سورة:", surah_names, cur_surah - 1)
        from_ayah = field("من الآية (رقمها في السورة):", cur_ayah)
        to_surah = combo("إلى سورة:", surah_names, cur_surah - 1)
        to_ayah = field("إلى الآية (رقمها في السورة):", cur_ayah)
        times = field("عدد مرات التكرار:", 3)
        mode = combo("طريقة التكرار:",
                     ["تكرار المقطع كاملاً", "تكرار كل آية على حدة", "مزيج: كل آية ثم المقطع"], 0)

        b = wx.BoxSizer(wx.HORIZONTAL)
        ok = wx.Button(p, wx.ID_OK, "ابدأ"); cancel = wx.Button(p, wx.ID_CANCEL, "إلغاء")
        b.Add(ok, 0, wx.ALL, 4); b.Add(cancel, 0, wx.ALL, 4); sz.Add(b, 0, wx.ALIGN_RIGHT)
        p.SetSizer(sz)

        if dlg.ShowModal() == wx.ID_OK:
            try:
                s1 = from_surah.GetSelection() + 1
                s2 = to_surah.GetSelection() + 1
                a1 = int(from_ayah.GetValue())
                a2 = int(to_ayah.GetValue())
                tm = max(1, int(times.GetValue()))
                mode_i = mode.GetSelection()   # 0 whole, 1 each, 2 hybrid
                g_from = self._global_of(s1, a1)
                g_to = self._global_of(s2, a2)
                if g_from is None or g_to is None:
                    self.announce("رقم الآية خارج نطاق السورة المختارة.")
                    dlg.Destroy()
                    return
                if g_from > g_to:
                    g_from, g_to = g_to, g_from
                self._hifz = {"from": g_from, "to": g_to, "times": tm,
                              "mode": mode_i, "round": 1, "ayah_round": 1}
                modes = ["تكرار المقطع كاملاً", "تكرار كل آية", "مزيج"]
                self.announce(f"بدء الحفظ من {self.surahs[s1]['name']} آية {a1} "
                              f"إلى {self.surahs[s2]['name']} آية {a2}، "
                              f"{tm} مرات، {modes[mode_i]}.")
                self._goto_global(g_from)
                self._play_current()
            except ValueError:
                self.announce("أدخل أرقاماً صحيحة.")
        dlg.Destroy()

    def _global_of(self, surah, ayah_in_surah):
        for r in self._idx["surah"].get(surah, []):
            if r[self.A] == ayah_in_surah:
                return r[self.N]
        return None

    def _goto_global(self, num):
        row = self._row(num)
        if not row:
            return
        # ensure the ayah is in the current view; if not, jump its division
        if num not in [r[self.N] for r in self._division_rows(self._mode, self._number)]:
            col = {"surah": self.S, "juz": self.JUZ, "page": self.PAGE, "rub": self.HQ}.get(self._mode, self.S)
            numdiv = (row[self.HQ] + 3) // 4 if self._mode == "hizb" else row[col]
            self._go(self._mode, numdiv, target_num=num)
        else:
            for i, an in enumerate(self._line_ayah):
                if an == num:
                    pos = sum(len(x) + 1 for x in self._text_str.split("\n")[:i])
                    self.text.SetInsertionPoint(pos)
                    break

    def _hifz_advance(self):
        h = self._hifz
        if not h:
            return
        cur = self._current_num()
        mode = h.get("mode", 0)   # 0 whole, 1 each, 2 hybrid

        # mode 1 (each ayah) and the per-ayah part of mode 2: repeat the current
        # ayah `times` times before moving to the next.
        if mode in (1, 2) and h["ayah_round"] < h["times"]:
            h["ayah_round"] += 1
            self._play_current()
            return

        # done repeating this ayah -> reset its counter and move on
        h["ayah_round"] = 1
        if cur is not None and cur < h["to"]:
            self._goto_global(cur + 1)
            self._play_current()
            return

        # reached the end of the range
        if mode == 1:
            # per-ayah mode: each ayah already repeated; we're done
            self.announce("اكتمل حفظ المقطع.")
            self._hifz = None
            return

        # whole-range (0) or hybrid (2): repeat the whole range `times` times
        if h["round"] < h["times"]:
            h["round"] += 1
            self.announce(f"التكرار {h['round']} من {h['times']}.")
            self._goto_global(h["from"])
            self._play_current()
        else:
            self.announce("اكتمل حفظ المقطع.")
            self._hifz = None

    def _move_next_and_play(self):
        n = self._current_num()
        if not n:
            return
        line = None
        for i, an in enumerate(self._line_ayah):
            if an == n:
                line = i
                break
        if line is None:
            return
        for j in range(line + 1, len(self._line_ayah)):
            if self._line_ayah[j]:
                pos = sum(len(x) + 1 for x in self._text_str.split("\n")[:j])
                self.text.SetInsertionPoint(pos)
                self._play_current()
                return
        # end of division -> advance to next division and continue
        count = dict((m[1], m[2]) for m in MODES)[self._mode]
        if self._number < count:
            self._go(self._mode, self._number + 1)
            self._play_current()

    # -- info / copy / bookmarks / search ---------------------------------

    def _word_analysis(self):
        """Show the word-by-word grammar (root, lemma, part of speech) of the
        current ayah in a navigable window. The word *form* shown is taken from
        the script the reader is currently displaying (not always the Uthmani
        text); the grammar comes from the Quranic Arabic Corpus morphology (GPL).
        The two are aligned by word position within the ayah."""
        n = self._current_num()
        r = self._row(n) if n else None
        if not r:
            return
        surah, ayah = r[self.S], r[self.A]
        data = self._load_word_analysis()
        words = data.get(f"{surah}:{ayah}")
        if not words:
            self.announce("لا يتوفّر تحليل لهذه الآية.")
            return
        # words of the currently selected script, split on whitespace
        script_words = self._script_ayah_words(n)
        # The morphology corpus sometimes segments a word into more pieces than
        # the plain script text (attached pronouns, particles), so positional
        # alignment is only safe when the counts match. When they don't, we keep
        # the corpus form (which always matches the grammar shown) rather than
        # risk pairing a word with the wrong analysis.
        aligned = len(script_words) == len(words)
        lines = []
        for i, wd in enumerate(words, 1):
            form = script_words[i - 1] if aligned else wd.get("w", "")
            parts = [form]
            if wd.get("pos"):
                parts.append(f"النوع: {wd['pos']}")
            if wd.get("root"):
                parts.append(f"الجذر: {wd['root']}")
            if wd.get("lemma"):
                parts.append(f"الأصل: {wd['lemma']}")
            lines.append(f"{i}. " + "  —  ".join(parts))
        title = f"تحليل كلمات — {self.surahs[surah]['name']} : {ayah}"
        self._show_text_window(title, "\n".join(lines))

    def _script_ayah_words(self, num):
        """The words of the current ayah as written in the selected script."""
        try:
            arr = self._ed.get_edition(self._script_id)
            if arr and 1 <= num <= len(arr) and arr[num - 1]:
                return arr[num - 1].split()
        except Exception:
            pass
        r = self._row(num)
        return r[self.TEXT].split() if r else []

    def _load_word_analysis(self):
        if getattr(self, "_wa_cache", None) is None:
            import json
            try:
                path = os.path.join(self._res, "word_analysis.json")
                with open(path, encoding="utf-8") as f:
                    self._wa_cache = json.load(f)
            except Exception:
                self._wa_cache = {}
        return self._wa_cache

    def _ayah_info(self):
        n = self._current_num()
        r = self._row(n) if n else None
        if not r:
            return
        m = self.surahs[r[self.S]]
        hizb = (r[self.HQ] + 3) // 4
        self.announce(f"{m['name']}، آية {r[self.A]}. الجزء {r[self.JUZ]}، الحزب {hizb}، "
                      f"ربع الحزب {r[self.HQ]}، الصفحة {r[self.PAGE]}.")

    def _copy_ayah(self):
        n = self._current_num()
        r = self._row(n) if n else None
        if not r:
            return
        m = self.surahs[r[self.S]]
        # copy from the script the reader is currently showing, not always Uthmani
        arr = self._ed.get_edition(self._script_id)
        ayah_text = arr[n - 1] if (arr and 1 <= n <= len(arr) and arr[n - 1]) else r[self.TEXT]
        text = f"{ayah_text}\n({m['name']}: {r[self.A]})"
        try:
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(text))
                wx.TheClipboard.Close()
                self.announce("تم نسخ الآية.")
        except Exception:
            self.announce("تعذّر النسخ.")

    def _get_bookmarks(self):
        try:
            return json.loads(self.academy.store.get_setting("quran_bookmarks", "[]") or "[]")
        except Exception:
            return []

    def _save_bookmarks(self, bms):
        try:
            self.academy.store.set_setting("quran_bookmarks", json.dumps(bms, ensure_ascii=False))
        except Exception:
            pass

    def _add_bookmark(self):
        n = self._current_num()
        r = self._row(n) if n else None
        if not r:
            return
        m = self.surahs[r[self.S]]
        default = f"{m['name']} {r[self.A]}"
        dlg = wx.TextEntryDialog(self, "اسم العلامة:", "حفظ علامة", default)
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.GetValue().strip() or default
            bms = self._get_bookmarks()
            bms.append({"name": name, "num": n})
            self._save_bookmarks(bms)
            self.announce("تم حفظ العلامة.")
        dlg.Destroy()

    def _open_bookmarks(self):
        bms = self._get_bookmarks()
        if not bms:
            self.announce("لا توجد علامات محفوظة.")
            return
        dlg = wx.SingleChoiceDialog(self, "اختر علامة:", "العلامات", [b["name"] for b in bms])
        if dlg.ShowModal() == wx.ID_OK:
            self._go_to_ayah(bms[dlg.GetSelection()]["num"], focus=True)
        dlg.Destroy()

    def _on_search(self, evt):
        q = _norm_ar(self.searchBox.GetValue().strip())
        if not q or len(q) < 2:
            self.announce("اكتب كلمة للبحث.")
            return
        trans = self._ed.get_edition(self._default_translation) if self._default_translation else None
        hits = []
        for r in self.ayat:
            if q in _norm_ar(r[self.TEXT]):
                hits.append(r)
            elif trans:
                t = trans[r[self.N] - 1]
                if t and q in t.casefold():
                    hits.append(r)
            if len(hits) >= 400:
                break
        if not hits:
            self.announce("لا توجد نتائج.")
            return
        labels = [f"{self.surahs[r[self.S]]['name']} [{r[self.A]}] {r[self.TEXT][:60]}" for r in hits]
        dlg = wx.SingleChoiceDialog(self, f"عدد النتائج: {len(hits)}. اختر آية:", "نتائج البحث", labels)
        if dlg.ShowModal() == wx.ID_OK:
            self._go_to_ayah(hits[dlg.GetSelection()][self.N], focus=True)
        dlg.Destroy()

    # -- offline download --------------------------------------------------

    def _on_download_surah(self, evt):
        n = self._current_num()
        r = self._row(n) if n else None
        if not r:
            return
        surah = r[self.S]
        rows = [x for x in self.ayat if x[self.S] == surah]
        nums = [x[self.N] for x in rows]
        rec = self._reciter_entry()
        sname = self.surahs[surah]["name"]
        if rec.get("cdn"):
            tag, url_for = rec["cdn"], None
        else:
            sa = {x[self.N]: (x[self.S], x[self.A]) for x in rows}
            tag, url_for = rec["key"], (lambda num: verse_url(rec["url"], *sa[num]))
        # only fetch what's missing; if the whole surah is already offline, say so
        missing = self._audio.missing_numbers(tag, nums)
        if not missing:
            self.announce(f"{sname} منزّلة بالكامل بصوت هذا القارئ.")
            return

        from .download_progress import DownloadProgressDialog

        def worker(progress_cb, should_stop):
            self._audio.download_range(tag, rec["bitrate"], nums,
                                       progress=progress_cb, should_stop=should_stop,
                                       url_for=url_for)

        dlg = DownloadProgressDialog(
            self, self.speech, f"تنزيل سورة {sname}", len(nums), worker, unit="آية")
        self.show_child(dlg)

    # -- resume / lifecycle ------------------------------------------------

    def _load_last_position(self):
        try:
            return int(self.academy.store.get_setting("quran_last", "1") or 1)
        except (TypeError, ValueError):
            return 1

    def _cleanup(self):
        self._dl_stop = True
        n = self._current_num()
        if n:
            try:
                self.academy.store.set_setting("quran_last", str(n))
            except Exception:
                pass
        if self._player is not None:
            self._player.close()
            self._player = None

    def on_closing(self):
        self._cleanup()


    def _bind_font_keys(self):
        # Font keys (Ctrl+=/Ctrl+-) are dispatched by the command bar's char-hook,
        # so no separate binding is needed here (avoids double-firing).
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
        return ("نص المصحف نافذة نصية، كل آية في سطر، فتنقّل بأوامر الأسطر في NVDA أو اقرأ "
                "الكل. اضغط Enter على الآية للاستماع إليها فوراً. غيّر «التنقل» (سورة/جزء/حزب/"
                "ربع/صفحة) واكتب رقماً أو اسم سورة، أو استخدم «السابق/التالي». أزرار: ترجمة "
                "الآية، تفسيرها، معلوماتها، نسخها، حفظ علامة والرجوع إليها، والبحث. «تشغيل "
                "متواصل» يقرأ الآيات تباعاً حتى عبر الأقسام، و«تكرار الآية» يعيدها للحفظ. "
                "يُحفظ آخر موضع تلقائياً. Escape للإغلاق.")


class TextViewDialog(AccessibleDialog):
    """A read-only, arrow-navigable text window for showing a tafsir / translation
    / i'rab / asbab entry. Navigable with arrows and Ctrl+arrows, and closeable
    with a Close button reachable by Tab, or with Escape."""

    def __init__(self, parent, speech, title, body, font_size=0):
        super().__init__(parent, title, speech, size=(760, 520))
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        self.text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.text.SetName(title)
        try:
            self.text.SetLayoutDirection(wx.Layout_RightToLeft)
        except Exception:
            pass
        self.text.SetValue(body or "")
        self.text.SetInsertionPoint(0)
        if font_size and font_size >= 8:
            try:
                f = self.text.GetFont(); f.SetPointSize(font_size); self.text.SetFont(f)
            except Exception:
                pass
        s.Add(self.text, 1, wx.EXPAND | wx.ALL, 6)
        closeBtn = self.button(panel, "إغلاق", lambda e: self.close_screen())
        s.Add(closeBtn, 0, wx.ALIGN_RIGHT | wx.ALL, 6)
        panel.SetSizer(s)
        self.set_first_control(self.text)

    def instructions(self) -> str:
        return ("نص للقراءة فقط. تنقّل بالأسهم وCtrl+الأسهم، وزر «إغلاق» يُوصَل إليه "
                "بمفتاح Tab، أو اضغط Escape للإغلاق.")
