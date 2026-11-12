# -*- coding: utf-8 -*-
"""
abaDesktop.profiles
===================

Several learners on one copy of the academy — a family sharing a computer, or
a teacher with a portable copy on a USB stick for a whole class.

Each profile has its own database, settings, flashcards and downloads. The
first profile is the data folder itself, so an existing installation simply
becomes the first profile and nothing moves. Further profiles live in
``userdata/profiles/<id>/``. The registry is ``userdata/profiles.json``.

No GUI imports, so the command line can list and use profiles too.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import List, Optional

REGISTRY = "profiles.json"
DEFAULT_ID = "default"


@dataclass
class Profile:
    id: str
    name: str
    created: float = 0.0
    last_used: float = 0.0


@dataclass
class Registry:
    active: str = DEFAULT_ID
    ask_on_start: bool = False
    profiles: List[Profile] = field(default_factory=list)


def _path(data_dir: str) -> str:
    return os.path.join(data_dir, REGISTRY)


def load(data_dir: str) -> Registry:
    reg = Registry()
    try:
        with open(_path(data_dir), encoding="utf-8") as f:
            raw = json.load(f)
        reg.active = raw.get("active", DEFAULT_ID)
        reg.ask_on_start = bool(raw.get("ask_on_start", False))
        reg.profiles = [Profile(p["id"], p.get("name") or p["id"], p.get("created", 0.0),
                                p.get("last_used", 0.0))
                        for p in raw.get("profiles", []) if p.get("id")]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    if not any(p.id == DEFAULT_ID for p in reg.profiles):
        reg.profiles.insert(0, Profile(DEFAULT_ID, "المتعلّم الأول", time.time(), 0.0))
    if not any(p.id == reg.active for p in reg.profiles):
        reg.active = DEFAULT_ID
    return reg


def save(data_dir: str, reg: Registry) -> None:
    os.makedirs(data_dir, exist_ok=True)
    tmp = _path(data_dir) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"active": reg.active, "ask_on_start": reg.ask_on_start,
                   "profiles": [asdict(p) for p in reg.profiles]},
                  f, ensure_ascii=False, indent=2)
    os.replace(tmp, _path(data_dir))


def profile_dir(data_dir: str, profile_id: str) -> str:
    if profile_id == DEFAULT_ID:
        return data_dir
    safe = re.sub(r"[^A-Za-z0-9_-]", "", profile_id) or "x"
    return os.path.join(data_dir, "profiles", safe)


def active_dir(data_dir: str) -> str:
    reg = load(data_dir)
    d = profile_dir(data_dir, reg.active)
    os.makedirs(d, exist_ok=True)
    return d


def get(reg: Registry, profile_id: str) -> Optional[Profile]:
    return next((p for p in reg.profiles if p.id == profile_id), None)


def create(data_dir: str, name: str) -> Profile:
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("اكتب اسمًا للملفّ.")
    reg = load(data_dir)
    if any(p.name == name for p in reg.profiles):
        raise ValueError("يوجد ملفّ بهذا الاسم.")
    p = Profile(uuid.uuid4().hex[:10], name, time.time(), 0.0)
    reg.profiles.append(p)
    os.makedirs(profile_dir(data_dir, p.id), exist_ok=True)
    save(data_dir, reg)
    return p


def rename(data_dir: str, profile_id: str, name: str) -> None:
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("اكتب اسمًا للملفّ.")
    reg = load(data_dir)
    p = get(reg, profile_id)
    if p is None:
        raise KeyError(profile_id)
    if any(o.name == name and o.id != profile_id for o in reg.profiles):
        raise ValueError("يوجد ملفّ بهذا الاسم.")
    p.name = name
    save(data_dir, reg)


def set_active(data_dir: str, profile_id: str) -> None:
    reg = load(data_dir)
    p = get(reg, profile_id)
    if p is None:
        raise KeyError(profile_id)
    reg.active = profile_id
    p.last_used = time.time()
    save(data_dir, reg)


def set_ask_on_start(data_dir: str, value: bool) -> None:
    reg = load(data_dir)
    reg.ask_on_start = bool(value)
    save(data_dir, reg)


def delete(data_dir: str, profile_id: str) -> str:
    """Remove a profile. Its folder is moved into ``userdata/profiles/_deleted``
    rather than erased, so a mistaken delete can be recovered by hand.
    Returns where the data went."""
    if profile_id == DEFAULT_ID:
        raise ValueError("لا يمكن حذف الملفّ الأول.")
    reg = load(data_dir)
    if get(reg, profile_id) is None:
        raise KeyError(profile_id)
    src = profile_dir(data_dir, profile_id)
    dest = ""
    if os.path.isdir(src):
        bin_dir = os.path.join(data_dir, "profiles", "_deleted")
        os.makedirs(bin_dir, exist_ok=True)
        dest = os.path.join(bin_dir, f"{profile_id}-{int(time.time())}")
        shutil.move(src, dest)
    reg.profiles = [p for p in reg.profiles if p.id != profile_id]
    if reg.active == profile_id:
        reg.active = DEFAULT_ID
    save(data_dir, reg)
    return dest


def describe(data_dir: str, p: Profile, active_id: str) -> str:
    d = profile_dir(data_dir, p.id)
    size = 0
    for root, _, files in os.walk(d):
        if os.path.join(data_dir, "profiles") in root and p.id == DEFAULT_ID:
            continue
        for f in files:
            try:
                size += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    mark = " (الحالي)" if p.id == active_id else ""
    last = time.strftime("%Y-%m-%d", time.localtime(p.last_used)) if p.last_used else "لم يُستخدم بعد"
    return f"{p.name}{mark} — آخر استخدام: {last}، الحجم {size // 1024} ك.ب"
