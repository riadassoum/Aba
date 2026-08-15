#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py — package the Arab Blind Academy NVDA add-on.

Produces ``abaAcademy.nvda-addon`` (a zip of manifest.ini + globalPlugins + doc)
after verifying that:

  * every packaged file name is ASCII (the "Askie" problem — see
    doc/DEVELOPER.md), because NVDA's bundled Python mangles non-ASCII names;
  * every bundled JSON file is valid;
  * the engine test suite passes.

Run from the repository root:

    python build.py
"""

import json
import glob
import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "abaAcademy.nvda-addon")
INCLUDE = ["manifest.ini", "globalPlugins", "doc"]


def fail(msg):
    print("BUILD FAILED:", msg)
    sys.exit(1)


def check_json():
    bad = []
    for f in glob.glob(os.path.join(ROOT, "globalPlugins", "**", "*.json"),
                       recursive=True):
        try:
            with open(f, encoding="utf-8") as fh:
                json.load(fh)
        except Exception as e:
            bad.append((f, str(e)))
    if bad:
        for f, e in bad[:10]:
            print("  invalid JSON:", f, e)
        fail(f"{len(bad)} invalid JSON file(s)")
    print(f"  JSON: all valid")


def check_ascii(names):
    non_ascii = [n for n in names if any(ord(c) > 127 for c in n)]
    if non_ascii:
        for n in non_ascii[:10]:
            print("  non-ASCII name:", n)
        fail(f"{len(non_ascii)} non-ASCII file name(s) — see doc/DEVELOPER.md")
    print("  file names: all ASCII")


def run_tests():
    tests = os.path.join(ROOT, "globalPlugins", "abaAcademy", "tests",
                         "test_engine.py")
    if not os.path.exists(tests):
        print("  tests: (none found, skipping)")
        return
    r = subprocess.run([sys.executable, tests], cwd=os.path.dirname(tests),
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:])
        print(r.stderr[-2000:])
        fail("test suite failed")
    print("  tests: passed")


def collect_files():
    files = []
    for item in INCLUDE:
        p = os.path.join(ROOT, item)
        if os.path.isfile(p):
            files.append(item)
        else:
            for dirpath, dirnames, filenames in os.walk(p):
                if "__pycache__" in dirpath:
                    continue
                for fn in filenames:
                    if fn.endswith(".pyc"):
                        continue
                    full = os.path.join(dirpath, fn)
                    files.append(os.path.relpath(full, ROOT))
    return files


def main():
    print("Building abaAcademy.nvda-addon ...")
    if not os.path.exists(os.path.join(ROOT, "manifest.ini")):
        fail("manifest.ini not found — run from the repository root")

    files = collect_files()
    arc_names = [f.replace(os.sep, "/") for f in files]
    check_ascii(arc_names)
    check_json()
    run_tests()

    if os.path.exists(OUT):
        os.remove(OUT)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(ROOT, f), f.replace(os.sep, "/"))

    size = os.path.getsize(OUT) / 1024 / 1024
    print(f"\nOK -> {OUT}  ({size:.2f} MB, {len(files)} files)")


if __name__ == "__main__":
    main()
