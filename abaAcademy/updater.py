# -*- coding: utf-8 -*-
"""
abaAcademy.updater
==================

Check whether a newer version of the add-on is available on GitHub, and (if the
user asks) download the newer build.

Design notes
------------
* Network access is optional and always wrapped: if there's no internet, the
  caller gets a clear "no connection" result rather than an error or a hang.
* All network work is meant to run off the UI thread (the GUI calls
  :func:`check_async`), so the interface never freezes waiting on the network.
* Version comparison is a simple, deterministic tuple compare of dotted numeric
  versions, tolerant of a leading ``v`` and of pre-release suffixes.
* This module only *reports* and *downloads*; installing is left to the user,
  who runs the downloaded installer or unpacks the archive.
"""

from __future__ import annotations

import json
import os
import re
import threading
import sys
import urllib.request

# The public GitHub API endpoint for the latest release of the repo.
LATEST_RELEASE_API = "https://api.github.com/repos/riadassoum/aba/releases/latest"
_TIMEOUT = 10

# result kinds
UP_TO_DATE = "up_to_date"
UPDATE_AVAILABLE = "update_available"
AHEAD = "ahead"            # local newer than server (a test build)
NO_CONNECTION = "no_connection"
ERROR = "error"


def parse_version(text):
    """'v2.0' / '2.1.3' -> (2,0) / (2,1,3). Non-numeric parts are ignored so a
    suffix like '2.0-beta' still compares sanely."""
    if not text:
        return (0,)
    text = text.strip().lstrip("vV")
    nums = []
    for part in re.split(r"[.\-_+]", text):
        if part.isdigit():
            nums.append(int(part))
        else:
            # take a leading number if present (e.g. '3beta' -> 3), else stop
            m = re.match(r"(\d+)", part)
            if m:
                nums.append(int(m.group(1)))
            break
    return tuple(nums) or (0,)


def compare_versions(local, remote):
    """Return -1 if local<remote, 0 if equal, 1 if local>remote."""
    a, b = parse_version(local), parse_version(remote)
    # pad to equal length
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return (a > b) - (a < b)


def _fetch_latest():
    """Return (tag, asset_url) for the latest GitHub release, or raise."""
    req = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "abaAcademy-updater"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    tag = data.get("tag_name") or data.get("name") or ""
    # Pick the artefact that suits this platform. Installers first, then a
    # portable archive; anything else is ignored so a release can also carry
    # source archives or checksums without confusing the updater.
    if sys.platform == "win32":
        preferred = (".msi", ".exe", "-windows.zip", ".zip")
    elif sys.platform == "darwin":
        preferred = (".dmg", "-macos.zip", ".zip")
    else:
        preferred = (".AppImage", "-linux.tar.gz", ".tar.gz", ".zip")
    assets = [(a.get("name", ""), a.get("browser_download_url", ""))
              for a in data.get("assets", [])]
    asset_url = ""
    asset_name = ""
    for suffix in preferred:
        for name, url in assets:
            if name.lower().endswith(suffix.lower()) and url:
                asset_url, asset_name = url, name
                break
        if asset_url:
            break
    return tag, asset_url, asset_name


def check(local_version):
    """Synchronous check. Returns a dict:
    {kind, local, remote, asset_url, message}."""
    try:
        tag, asset_url, asset_name = _fetch_latest()
    except urllib.error.URLError:
        return {"kind": NO_CONNECTION, "local": local_version, "remote": "",
                "asset_url": "", "asset_name": "",
                "message": "لا يوجد اتصال بالإنترنت للتحقّق من التحديثات."}
    except Exception as exc:
        return {"kind": ERROR, "local": local_version, "remote": "",
                "asset_url": "", "asset_name": "",
                "message": f"تعذّر التحقّق من التحديثات: {exc}"}

    cmp = compare_versions(local_version, tag)
    if cmp < 0:
        msg = (f"يتوفّر تحديث! نسختك {local_version} والنسخة الأحدث {tag}. "
               f"يمكنك تنزيل التحديث وتثبيته.")
        kind = UPDATE_AVAILABLE
    elif cmp == 0:
        msg = f"أنت على أحدث نسخة ({local_version})."
        kind = UP_TO_DATE
    else:
        msg = (f"نسختك ({local_version}) أحدث من المنشورة على الخادم ({tag})؛ "
               f"يبدو أنّك تستخدم نسخة اختبارية لم تُرفع بعد. انتظر تحديث الخادم.")
        kind = AHEAD
    return {"kind": kind, "local": local_version, "remote": tag,
            "asset_url": asset_url, "asset_name": asset_name, "message": msg}


def check_async(local_version, callback):
    """Run :func:`check` on a background thread and hand the result dict to
    ``callback``. The GUI passes a callback that marshals back to the UI thread
    (e.g. via wx.CallAfter)."""
    def work():
        result = check(local_version)
        callback(result)
    threading.Thread(target=work, daemon=True).start()


def download(asset_url, dest_path):
    """Download the release artefact to ``dest_path``. Returns the path on success,
    raises on failure. Meant to run off the UI thread."""
    req = urllib.request.Request(
        asset_url, headers={"User-Agent": "abaAcademy-updater"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    with open(dest_path, "wb") as f:
        f.write(data)
    return dest_path


# ---------------------------------------------------------------------------
# applying an update in place
# ---------------------------------------------------------------------------

def app_dir():
    """The folder the running program lives in (where an update is applied)."""
    import sys as _sys
    if getattr(_sys, "frozen", False):
        return os.path.dirname(_sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


#: never overwritten by an update — the learner's own material
PROTECTED = {"userdata", "academy.log", "backups"}


def install_zip(zip_path, target_dir=None, protected=None):
    """Extract an update archive over the installed program.

    The published build is empty of learner content: progress, downloaded
    recitations and course packs all live in ``userdata`` beside the executable.
    So an update replaces program files and leaves that folder untouched.

    Returns ``(replaced, skipped, errors)``. Files that cannot be replaced
    because they are locked (typically the running executable itself on Windows)
    are written alongside as ``<name>.new`` and reported, so a small relauncher
    or the next start can swap them in rather than the whole update failing.
    """
    import zipfile

    target_dir = target_dir or app_dir()
    protected = set(protected or PROTECTED)
    replaced, skipped, errors = [], [], []

    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        # An archive usually wraps everything in one top folder; strip it so the
        # contents land in the program folder rather than a nested copy.
        tops = {n.split("/", 1)[0] for n in names if "/" in n}
        strip = len(tops) == 1 and all("/" in n for n in names)
        root = tops.pop() if strip else None

        for name in names:
            rel = name[len(root) + 1:] if strip else name
            if not rel:
                continue
            first = rel.replace("\\", "/").split("/", 1)[0]
            if first in protected:
                skipped.append(rel)
                continue
            dest = os.path.join(target_dir, *rel.split("/"))
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                data = z.read(name)
                try:
                    with open(dest, "wb") as f:
                        f.write(data)
                    replaced.append(rel)
                except PermissionError:
                    # in use (e.g. the running .exe): stage it for the next run
                    with open(dest + ".new", "wb") as f:
                        f.write(data)
                    errors.append(rel)
            except Exception as exc:
                errors.append(f"{rel}: {exc}")
    return replaced, skipped, errors


def pending_replacements(target_dir=None):
    """Staged ``*.new`` files waiting to replace locked ones."""
    target_dir = target_dir or app_dir()
    out = []
    for dirpath, _dirs, files in os.walk(target_dir):
        for f in files:
            if f.endswith(".new"):
                out.append(os.path.join(dirpath, f))
    return out


def apply_pending(target_dir=None):
    """Swap in any staged ``*.new`` files. Call at startup, before they're used."""
    done, failed = [], []
    for staged in pending_replacements(target_dir):
        final = staged[:-4]
        try:
            if os.path.exists(final):
                os.remove(final)
            os.replace(staged, final)
            done.append(final)
        except Exception:
            failed.append(final)
    return done, failed
