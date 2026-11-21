# -*- coding: utf-8 -*-
"""
Build abaAcademy/resources/nvda/commands.json from NVDA's own sources.

NVDA (GPL-2.0-or-later, NV Access) declares every command with an @script
decorator giving its English description, its category and its keys. The
Arabic wording is the official translation in NVDA's Arabic nvda.po, made by
the Arabic translation team. Quick navigation keys in browse mode come from
the qn(...) calls in browseMode.py.

The files are parsed with ast and never imported or run.

Usage:  python3 build_nvda.py SRC_DIR OUT_JSON
SRC_DIR holds globalCommands.py, browseMode.py and nvda.po.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys


def read_po(path):
    """msgid (with optional msgctxt) -> msgstr, for translated, non-fuzzy entries."""
    out = {}
    ctx = mid = mstr = None
    cur = None
    fuzzy = False

    def flush():
        if mid and mstr and not fuzzy:
            out[(ctx, mid)] = mstr

    def unq(s):
        return ast.literal_eval(s)

    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("#,") and "fuzzy" in line:
            fuzzy = True
        elif line.startswith("msgctxt "):
            flush()
            ctx, mid, mstr, cur, fuzzy = unq(line[8:]), None, None, "ctx", fuzzy
        elif line.startswith("msgid "):
            if cur != "ctx":
                flush()
                ctx = None
            mid, mstr, cur = unq(line[6:]), None, "id"
        elif line.startswith("msgstr "):
            mstr, cur = unq(line[7:]), "str"
        elif line.startswith('"'):
            if cur == "id":
                mid += unq(line)
            elif cur == "str":
                mstr += unq(line)
            elif cur == "ctx":
                ctx += unq(line)
        elif not line.strip():
            flush()
            ctx = mid = mstr = cur = None
            fuzzy = False
    flush()
    return out


def gettext_arg(node):
    """('ctx', 'text') for _("text") or pgettext("ctx", "text")."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        args = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if node.func.id == "_" and len(args) == 1:
            return None, args[0]
        if node.func.id == "pgettext" and len(args) == 2:
            return args[0], args[1]
    return None


def nice_key(g):
    kind, _, key = g.partition(":")
    layout = ""
    if kind.startswith("kb("):
        layout = kind[3:-1]
    elif kind != "kb":
        return None                    # touch, braille display gestures
    parts = []
    for p in key.split("+"):
        low = p.lower()
        names = {"nvda": "NVDA", "control": "Control", "shift": "Shift", "alt": "Alt", "windows": "Windows",
                 "uparrow": "السهم الأعلى", "downarrow": "السهم الأسفل", "leftarrow": "السهم الأيسر",
                 "rightarrow": "السهم الأيمن", "space": "المسافة", "enter": "Enter", "escape": "Escape",
                 "tab": "Tab", "backspace": "Backspace", "delete": "Delete", "insert": "Insert", "home": "Home",
                 "end": "End", "pageup": "Page Up", "pagedown": "Page Down", "applications": "مفتاح التطبيقات",
                 "numpadenter": "Enter في لوحة الأرقام", "numpaddelete": "Delete في لوحة الأرقام",
                 "numpadinsert": "Insert في لوحة الأرقام", "numpadplus": "زائد لوحة الأرقام",
                 "numpadminus": "ناقص لوحة الأرقام", "numpaddivide": "قسمة لوحة الأرقام",
                 "numpadmultiply": "ضرب لوحة الأرقام", "printscreen": "Print Screen", "scrolllock": "Scroll Lock",
                 "capslock": "Caps Lock", "numlock": "Num Lock"}
        if low in names:
            parts.append(names[low])
        elif re.fullmatch(r"numpad\d", low):
            parts.append(f"{low[-1]} في لوحة الأرقام")
        elif re.fullmatch(r"f\d+", low):
            parts.append(low.upper())
        else:
            parts.append(p.upper() if len(p) == 1 else p)
    return layout, "+".join(parts)


def scripts_from(path, po, constants):
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            g = gettext_arg(node.value)
            if g:
                constants[node.targets[0].id] = g
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and getattr(dec.func, "id", None) == "script"):
                continue
            kw = {k.arg: k.value for k in dec.keywords}
            desc = gettext_arg(kw.get("description"))
            if not desc:
                continue
            gestures = []
            if "gesture" in kw and isinstance(kw["gesture"], ast.Constant):
                gestures.append(kw["gesture"].value)
            if "gestures" in kw and isinstance(kw["gestures"], (ast.Tuple, ast.List)):
                gestures += [e.value for e in kw["gestures"].elts if isinstance(e, ast.Constant)]
            keys = {"": [], "desktop": [], "laptop": []}
            for g in gestures:
                k = nice_key(g)
                if k:
                    keys[k[0]].append(k[1])
            if not any(keys.values()):
                continue
            cat = kw.get("category")
            cat_en = constants.get(cat.id) if isinstance(cat, ast.Name) else gettext_arg(cat) if cat else None
            ar = po.get(desc)
            out.append({
                "script": node.name[len("script_"):],
                "en": desc[1],
                "ar": ar,
                "category_en": cat_en[1] if cat_en else "",
                "category": po.get(cat_en, cat_en[1]) if cat_en else "",
                "keys": keys[""], "desktop": keys["desktop"], "laptop": keys["laptop"],
            })
    return out


def quicknav(path, po):
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = []
    for node in tree.body:
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and getattr(node.value.func, "id", None) == "qn"):
            continue
        kw = {k.arg: k.value for k in node.value.keywords}
        key = kw.get("key")
        if not isinstance(key, ast.Constant) or not key.value:
            continue
        for which, k in (("nextDoc", key.value), ("prevDoc", "Shift+" + key.value.upper())):
            g = gettext_arg(kw.get(which))
            if g and po.get(g):
                out.append({"script": f"quicknav_{node.value.args[0].value}_{which[:4]}", "en": g[1], "ar": po[g],
                            "category_en": "Browse mode", "category": "وضع التصفّح",
                            "keys": [k if which == "prevDoc" else k.upper()], "desktop": [], "laptop": []})
    return out


def main(src, out_path):
    po = {}
    raw = read_po(os.path.join(src, "nvda.po"))
    po.update(raw)
    constants = {}
    cmds = scripts_from(os.path.join(src, "globalCommands.py"), po, constants)
    cmds += quicknav(os.path.join(src, "browseMode.py"), po)
    cmds = [c for c in cmds if c["ar"]]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"source": "NVDA (NV Access), GPL-2.0-or-later; Arabic wording from NVDA's Arabic translation.",
                   "commands": cmds}, f, ensure_ascii=False, indent=0)
    print(len(cmds), "commands")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
