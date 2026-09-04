# -*- coding: utf-8 -*-
"""
abaAcademy.gui.audio_player
===========================

The add-on's own in-process audio player. No external program is ever launched,
and — importantly — it does **not** depend on ``wx.media`` (absent on some the screen reader
Python builds) or on the screen reader's ``nvwave`` (which faulted with an access violation
on some builds).

Primary engine: the **bundled miniaudio** library (in ``abaAcademy/lib``), which
both decodes the MP3 and plays it through its own low-level output device
(WASAPI on Windows). This is completely self-contained, so it works even when
wx.media is missing.

Fallbacks, only if miniaudio can't be used: wx.media, then nvwave (nvwave stays
off by default because of the crash risk). Everything is lazy and guarded.
"""

from __future__ import annotations

import os
import sys
import threading

_LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib")

try:
    import wx
    try:
        import wx.media
        _HAS_WXMEDIA = True
    except Exception:
        _HAS_WXMEDIA = False
except Exception:
    _HAS_WXMEDIA = False


class AudioPlayer:
    ALLOW_NVWAVE = False   # nvwave.feed can fault at C level on some builds

    def __init__(self, wx_parent=None, on_finished=None):
        self._wx_parent = wx_parent
        self._on_finished = on_finished
        self._ma = None
        self._ma_tried = False
        self._device = None        # miniaudio PlaybackDevice
        self._nv = None
        self._wx_ctrl = None
        self._manual_stop = False
        self._lock = threading.Lock()
        self._last_error = ""

    # -- notification ------------------------------------------------------

    def _notify_finished(self):
        if self._manual_stop:
            return
        if self._on_finished:
            try:
                import wx as _wx
                _wx.CallAfter(self._on_finished)
            except Exception:
                try:
                    self._on_finished()
                except Exception:
                    pass

    # -- primary: bundled miniaudio (decode + play, self-contained) --------

    def _load_miniaudio(self):
        """Load the audio backend, preferring a properly installed one.

        A normal installation gets miniaudio from the environment
        (``pip install miniaudio``), built for the exact Python in use. Only if
        that is missing do we fall back to a copy vendored beside the
        application — vendored binaries are version- and platform-locked, so
        they are a last resort rather than the default.
        """
        if self._ma_tried:
            return self._ma is not None
        self._ma_tried = True
        try:
            import miniaudio                      # installed for this Python
            self._ma = miniaudio
            return True
        except Exception:
            pass
        try:
            libp = os.path.abspath(_LIB)
            if os.path.isdir(libp):
                if libp not in sys.path:
                    sys.path.append(libp)         # append: never shadow a real install
                import miniaudio
                self._ma = miniaudio
                return True
            raise ImportError("no vendored audio library")
        except Exception as e:
            self._ma = None
            self._last_error = "audio backend unavailable: %s" % e
        return self._ma is not None

    def _wrap_stream(self, stream):
        """Wrap miniaudio's stream generator so we learn when the file ends.

        miniaudio's playback callback *sends* the required frame count into the
        generator, so we must forward those counts to the underlying stream (via
        its .send()) rather than just iterating it, and the generator must be
        primed (advanced to its first yield) before it's handed to the device.
        """
        finished = False
        try:
            required = yield b""            # prime: device sends first frame count
            while True:
                try:
                    data = stream.send(required)
                except StopIteration:
                    finished = True
                    return
                if data is None:
                    finished = True
                    return
                required = yield data
        finally:
            if finished:
                self._notify_finished()

    def _play_miniaudio(self, path):
        if not self._load_miniaudio():
            return False
        try:
            ma = self._ma
            stream = ma.stream_file(path)          # decodes lazily to int16/stereo/44100
            next(stream)                           # prime the file stream
            wrapped = self._wrap_stream(stream)
            next(wrapped)                           # prime our wrapper to its first yield
            device = ma.PlaybackDevice(
                output_format=ma.SampleFormat.SIGNED16, nchannels=2, sample_rate=44100)
            device.start(wrapped)
            self._device = device
            return True
        except Exception as e:
            self._last_error = "miniaudio play: %s" % e
            try:
                if self._device is not None:
                    self._device.close()
            except Exception:
                pass
            self._device = None
            return False

    # -- fallback: wx.media ------------------------------------------------

    def _play_wx(self, path):
        if not _HAS_WXMEDIA or self._wx_parent is None:
            self._last_error = self._last_error or "wx.media unavailable"
            return False
        try:
            if self._wx_ctrl is None:
                made = False
                for name in ("MEDIABACKEND_WMP10", "MEDIABACKEND_DIRECTSHOW"):
                    b = getattr(wx.media, name, None)
                    if not b:
                        continue
                    try:
                        self._wx_ctrl = wx.media.MediaCtrl(self._wx_parent, size=(0, 0), szBackend=b)
                        made = True
                        break
                    except Exception:
                        continue
                if not made:
                    self._wx_ctrl = wx.media.MediaCtrl(self._wx_parent, size=(0, 0))
                self._wx_ctrl.Bind(wx.media.EVT_MEDIA_LOADED, self._on_wx_loaded)
                self._wx_ctrl.Bind(wx.media.EVT_MEDIA_FINISHED, lambda e: self._notify_finished())
            if self._wx_ctrl.Load(path):
                try:
                    self._wx_ctrl.Play()
                except Exception:
                    pass
                return True
            return bool(self._wx_ctrl.Play())
        except Exception as e:
            self._last_error = "wx.media: %s" % e
            return False

    def _on_wx_loaded(self, evt):
        try:
            self._wx_ctrl.Play()
        except Exception:
            pass

    # -- fallback: nvwave (off by default) ---------------------------------

    def _play_nvwave(self, path):
        if not self.ALLOW_NVWAVE or not self._load_miniaudio():
            return False
        try:
            import winsound as nvwave  # native playback
            SF = self._ma.SampleFormat.SIGNED16
            dec = self._ma.decode_file(path, output_format=SF, nchannels=2, sample_rate=44100)
            pcm = bytes(memoryview(dec.samples).cast("B"))
            del dec
            try:
                player = nvwave.WavePlayer(channels=2, samplesPerSec=44100,
                                           bitsPerSample=16, outputDevice=None, wantDucking=False)
            except TypeError:
                player = nvwave.WavePlayer(2, 44100, 16)
            self._nv = player

            def _feed(p=player, data=pcm):
                try:
                    p.feed(data)
                    try:
                        p.idle()
                    except Exception:
                        pass
                    self._notify_finished()
                except Exception:
                    pass
            threading.Thread(target=_feed, daemon=True).start()
            return True
        except Exception as e:
            self._last_error = "nvwave play: %s" % e
            return False

    # -- public API --------------------------------------------------------

    def play_file(self, path) -> bool:
        with self._lock:
            self.stop()
            self._manual_stop = False
            if self._play_miniaudio(path):
                return True
            if self._play_wx(path):
                return True
            if self._play_nvwave(path):
                return True
            return False

    def stop(self):
        self._manual_stop = True
        if self._device is not None:
            try:
                self._device.stop()
            except Exception:
                pass
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None
        if self._nv is not None:
            try:
                self._nv.stop()
            except Exception:
                pass
            self._nv = None
        if self._wx_ctrl is not None:
            try:
                self._wx_ctrl.Stop()
            except Exception:
                pass

    def close(self):
        self.stop()
        if self._wx_ctrl is not None:
            try:
                self._wx_ctrl.Destroy()
            except Exception:
                pass
            self._wx_ctrl = None

    @property
    def last_error(self) -> str:
        return self._last_error
