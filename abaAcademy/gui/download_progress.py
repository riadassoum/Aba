# -*- coding: utf-8 -*-
"""
abaAcademy.gui.download_progress
================================

An accessible download-progress window. While a download runs, the user can
press keys to hear status on demand (nothing is spoken automatically except
start and finish, so it never floods the speech):

* Space  -> how many items are done out of the total (e.g. "٣٠ من ١١٤")
* 1      -> percentage completed
* 2      -> percentage remaining
* 3      -> current speed / estimated time remaining

There is a Close/Cancel button (Tab-reachable) and Escape cancels the download.
The actual downloading runs on a worker thread supplied by the caller; this
dialog only reports progress and lets the user cancel.

The design (on-demand status keys, cancellable background download) is adapted
from the al-bayan the screen reader project's download manager (GPL); re-implemented here.
"""

from __future__ import annotations

import threading
import time

from .accessible import AccessibleDialog

try:
    import wx
except Exception:
    wx = None


def _ar_digits(s):
    return str(s).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


class DownloadProgressDialog(AccessibleDialog):
    def __init__(self, parent, speech, title, total, worker, unit="آية"):
        super().__init__(parent, title, speech, size=(520, 300))
        self._total = max(1, int(total))
        self._unit = unit
        self._done = 0
        self._bytes = 0
        self._start_t = time.time()
        self._cancel = False
        self._finished = False
        self._worker = worker

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        self.status = wx.StaticText(panel, label="جارٍ التنزيل...")
        s.Add(self.status, 0, wx.ALL, 10)
        help_txt = ("مسافة: عدد المُنزَّل، 1: النسبة المئوية، 2: المتبقّي، "
                    "3: السرعة. Escape أو «إلغاء» لإيقاف التنزيل.")
        s.Add(wx.StaticText(panel, label=help_txt), 0, wx.ALL, 8)
        self.cancelBtn = self.button(panel, "إلغاء التنزيل", lambda e: self._do_cancel())
        s.Add(self.cancelBtn, 0, wx.ALIGN_RIGHT | wx.ALL, 6)
        panel.SetSizer(s)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.set_first_control(self.cancelBtn)

        # start the worker; it calls self.on_progress(done,total[,bytes]) and
        # self.on_done() via wx.CallAfter.
        threading.Thread(target=self._run, daemon=True).start()

    # -- worker plumbing ---------------------------------------------------

    def _run(self):
        try:
            self._worker(self._progress_cb, lambda: self._cancel)
        except Exception:
            pass
        wx.CallAfter(self._on_finished)

    def _progress_cb(self, done, total, nbytes=0):
        self._done = done
        self._bytes = nbytes or self._bytes
        wx.CallAfter(self._update_label)

    def _update_label(self):
        pct = int(self._done * 100 / self._total)
        self.status.SetLabel(f"تم تنزيل {_ar_digits(self._done)} من {_ar_digits(self._total)} "
                             f"({_ar_digits(pct)}٪)")

    def _on_finished(self):
        self._finished = True
        if self._cancel:
            self.announce("أُلغي التنزيل.")
        else:
            self.announce(f"اكتمل التنزيل: {_ar_digits(self._total)} {self._unit}.")
        self.cancelBtn.SetLabel("إغلاق")

    def _do_cancel(self):
        if self._finished:
            self.close_screen()
            return
        self._cancel = True
        self.announce("جارٍ الإلغاء...")

    # -- status keys -------------------------------------------------------

    def _speed(self):
        elapsed = max(0.001, time.time() - self._start_t)
        rate = self._done / elapsed
        remaining = self._total - self._done
        if rate <= 0:
            return "يجري الحساب..."
        eta = int(remaining / rate)
        return f"{rate:.1f} {self._unit} في الثانية، يتبقّى نحو {_ar_digits(eta)} ثانية"

    def _on_key(self, evt):
        code = evt.GetKeyCode()
        pct = int(self._done * 100 / self._total)
        if code == wx.WXK_SPACE:
            self.announce(f"{_ar_digits(self._done)} من {_ar_digits(self._total)} {self._unit}")
        elif code == ord('1'):
            self.announce(f"اكتمل {_ar_digits(pct)} بالمئة")
        elif code == ord('2'):
            self.announce(f"يتبقّى {_ar_digits(100 - pct)} بالمئة")
        elif code == ord('3'):
            self.announce(self._speed())
        elif code == wx.WXK_ESCAPE:
            self._do_cancel()
        else:
            evt.Skip()

    def on_repeat(self):
        self._update_label()
        self.announce(self.status.GetLabel())

    def instructions(self) -> str:
        return ("نافذة التنزيل. مسافة لعدد المُنزَّل، 1 للنسبة، 2 للمتبقّي، 3 للسرعة. "
                "Escape لإيقاف التنزيل.")
