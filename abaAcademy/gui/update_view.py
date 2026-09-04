# -*- coding: utf-8 -*-
"""
abaAcademy.gui.update_view
==========================

A screen that tells the learner their current version and the latest version on
the server, and — when an update is available — offers to download it. All
network work runs off the UI thread so the window never freezes; the
four outcomes (up to date, update available, using a newer test build, and no
internet) are each reported clearly in Arabic.
"""

from __future__ import annotations

import os
import tempfile

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from .. import updater


def _local_version(academy):
    # read the version from the bundled manifest
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        manifest = os.path.join(os.path.dirname(base), "manifest.ini")
        # manifest.ini lives at the addon root (two levels up from gui/)
        for candidate in (
                os.path.join(base, "..", "..", "manifest.ini"),
                os.path.join(base, "..", "manifest.ini")):
            if os.path.exists(candidate):
                for line in open(candidate, encoding="utf-8"):
                    if line.strip().startswith("version"):
                        return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return "2.0"


class UpdateDialog(AccessibleDialog):
    TITLE = "التحقّق من التحديثات"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(660, 440))
        self.academy = academy
        self._local = _local_version(academy)
        self._result = None

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=f"نسختك الحالية: {self._local}"),
              0, wx.ALL, 8)

        self.report = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY,
                                  size=(-1, 220))
        self.report.SetName("حالة التحديث")
        s.Add(self.report, 1, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(620)
        s.Add(self.status, 0, wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "تحقّق الآن", lambda e: self._check()), 0, wx.ALL, 3)
        self.dlBtn = self.button(panel, "نزّل التحديث", lambda e: self._download())
        self.dlBtn.Disable()
        row.Add(self.dlBtn, 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.report)
        wx.CallAfter(self._check)

    def _check(self):
        self._say("جارٍ التحقّق من التحديثات…")
        updater.check_async(self._local,
                            lambda res: wx.CallAfter(self._on_result, res))

    def _on_result(self, result):
        self._result = result
        self.report.SetValue(result["message"])
        self._say(result["message"])
        self.dlBtn.Enable(result["kind"] == updater.UPDATE_AVAILABLE
                          and bool(result.get("asset_url")))

    def _download(self):
        if not self._result or not self._result.get("asset_url"):
            self._say("لا يوجد ملف للتنزيل.")
            return
        # ask where to save
        with wx.FileDialog(
                self, "احفظ ملف التحديث",
                defaultFile=(self._result.get("asset_name")
                             or "ArabBlindAcademy-update"),
                wildcard="كل الملفات (*.*)|*.*",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            dest = dlg.GetPath()
        self._say("جارٍ التنزيل…")
        url = self._result["asset_url"]

        def work():
            try:
                updater.download(url, dest)
                wx.CallAfter(done, True, dest)
            except Exception as exc:
                wx.CallAfter(done, False, str(exc))

        def done(ok, info):
            if not ok:
                self._say(f"تعذّر التنزيل: {info}")
                return
            if not str(info).lower().endswith(".zip"):
                self._say(f"اكتمل التنزيل: {os.path.basename(info)}. "
                          f"أغلق البرنامج ثم شغّل الملف لتثبيت التحديث.")
                return
            # a zip can be applied in place: replace the program files and keep
            # everything the learner has accumulated in userdata
            dlg = wx.MessageDialog(
                self,
                "اكتمل التنزيل. هل تريد تثبيت التحديث الآن؟\n"
                "ستُستبدل ملفّات البرنامج، ويبقى تقدّمك وملفّاتك كما هي.",
                "تثبيت التحديث", wx.YES_NO | wx.ICON_QUESTION)
            install = dlg.ShowModal() == wx.ID_YES
            dlg.Destroy()
            if not install:
                self._say("حُفظ ملف التحديث. يمكنك تثبيته لاحقًا.")
                return
            try:
                replaced, skipped, errors = updater.install_zip(info)
            except Exception as exc:
                self._say(f"تعذّر التثبيت: {exc}")
                return
            msg = f"تم تحديث {len(replaced)} ملفًا."
            if errors:
                msg += (f" {len(errors)} ملفًا قيد الاستخدام وسيُستبدل عند "
                        f"إعادة التشغيل.")
            msg += " أعد تشغيل البرنامج لتفعيل التحديث."
            self._say(msg)

        import threading
        threading.Thread(target=work, daemon=True).start()

    def _say(self, text):
        self.status.SetLabel(text[:200])
        self.announce(text)

    def instructions(self):
        return ("التحقّق من التحديثات: يعرض نسختك والنسخة الأحدث على الخادم، ويخبرك إن كنت "
                "محدَّثًا أو إن توفّر تحديث (فيمكنك تنزيله وتشغيله لتثبيته)، أو إن كنت "
                "تستخدم نسخة اختبارية أحدث من الخادم، أو إن لم يوجد اتصال بالإنترنت. Escape للإغلاق.")
