#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py — build a distributable Arab Blind Academy desktop application.

Usage:
    python build.py                 # one-folder distributable in dist/
    python build.py --onefile       # single executable
    python build.py --clean         # remove build artefacts first
    python build.py --check         # validate only, don't build

What it does
------------
1. Validates the tree the same way the add-on build does (ASCII names inside the
   package, valid JSON, every module byte-compiles).
2. Verifies the academy imports and boots *without NVDA present* — the whole
   premise of the standalone build — and fails loudly if it doesn't.
3. Invokes PyInstaller with the academy's data files (courses, Qur'an text,
   dictionary, resources) bundled, producing ``dist/ArabBlindAcademy``.

PyInstaller is the only build-time dependency; the program itself needs just
wxPython at runtime, plus an optional TTS backend. If PyInstaller is missing the
script says exactly how to install it instead of failing obscurely.
"""

from __future__ import annotations

import argparse
import json
import os
import py_compile
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ACADEMY_PARENT = ROOT
ACADEMY = os.path.join(ROOT, "abaAcademy")
APP_NAME = "ArabBlindAcademy"
ENTRY = os.path.join(ROOT, "run_app.py")


def log(msg):
    print(f"[build] {msg}")


def clean():
    removed = 0
    for d in ("build", "dist", "__pycache__"):
        p = os.path.join(ROOT, d)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
            removed += 1
    for dirpath, dirnames, filenames in os.walk(ROOT):
        for d in list(dirnames):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(dirpath, d), ignore_errors=True)
                removed += 1
        for f in filenames:
            if f.endswith((".pyc", ".pyo")):
                os.remove(os.path.join(dirpath, f))
                removed += 1
    spec = os.path.join(ROOT, f"{APP_NAME}.spec")
    if os.path.exists(spec):
        os.remove(spec)
    log(f"cleaned {removed} artefact(s)")


def validate():
    problems = []
    if not os.path.isdir(ACADEMY):
        problems.append(f"academy package not found at {ACADEMY}")
        return problems

    # ASCII names inside the academy package (Arabic belongs inside JSON)
    for dirpath, dirnames, filenames in os.walk(ACADEMY):
        for name in dirnames + filenames:
            if not name.isascii():
                problems.append(f"non-ASCII name: {os.path.join(dirpath, name)}")

    # valid JSON
    for dirpath, _dirs, files in os.walk(ACADEMY):
        for f in files:
            if f.endswith(".json"):
                path = os.path.join(dirpath, f)
                try:
                    json.load(open(path, encoding="utf-8"))
                except Exception as exc:
                    problems.append(f"bad JSON: {path}: {exc}")

    # everything compiles (both the academy and the desktop shell)
    for base in (ACADEMY, os.path.join(ROOT, "abaDesktop")):
        for dirpath, _dirs, files in os.walk(base):
            if "tests" in dirpath.split(os.sep):
                continue
            for f in files:
                if f.endswith(".py"):
                    path = os.path.join(dirpath, f)
                    try:
                        py_compile.compile(path, doraise=True)
                    except py_compile.PyCompileError as exc:
                        problems.append(f"compile error: {path}: {exc}")
    return problems


def verify_standalone():
    """Boot the academy in a subprocess with no NVDA available.

    This is the load-bearing check for a standalone build: if anything still
    requires the screen reader, the distributable would fail on a user's machine
    with no obvious cause. Better to fail here.
    """
    code = (
        "import sys, tempfile;"
        f"sys.path.insert(0, {ACADEMY_PARENT!r});"
        "from abaAcademy.academy import Academy;"
        f"ac = Academy({ACADEMY!r}, tempfile.mkdtemp());"
        "n = len(list(ac.courses()));"
        "print('COURSES', n);"
        "assert n > 0, 'no courses loaded'"
    )
    res = subprocess.run([sys.executable, "-c", code],
                         capture_output=True, text=True)
    if res.returncode != 0:
        return [f"academy does not boot standalone:\n{res.stderr.strip()}"]
    log(res.stdout.strip().replace("COURSES", "academy boots standalone; courses:"))
    return []


def _data_args():
    """PyInstaller --add-data entries for the academy package.

    The whole package is shipped as data (courses, resources, Qur'an text, the
    294k-word dictionary) and imported from the bundle at runtime.
    """
    sep = ";" if os.name == "nt" else ":"
    academy_src = _staged_academy()
    args = [f"--add-data={academy_src}{sep}abaAcademy"]
    vendor = os.path.join(ROOT, "vendor")
    if os.path.isdir(vendor):
        args.append(f"--add-data={vendor}{sep}vendor")
    return args



def _staged_academy():
    """Return the academy folder to ship.

    For a release build the ``.py`` sources are replaced with compiled ``.pyc``
    so the distributed program does not carry readable source. (The project
    remains open source — this only affects what ends up inside the shipped
    binary.) Data files such as courses, the Qur'an text and the dictionary are
    copied through untouched, since those are the content the app needs at
    runtime.

    Set ``ABA_KEEP_SOURCE=1`` to ship plain sources instead, which is handy when
    debugging a packaged build.
    """
    import compileall
    import shutil

    if os.environ.get("ABA_KEEP_SOURCE") == "1":
        log("shipping plain sources (ABA_KEEP_SOURCE=1)")
        return ACADEMY

    staging = os.path.join(ROOT, "build", "_academy_pyc")
    if os.path.isdir(staging):
        shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(os.path.dirname(staging), exist_ok=True)
    shutil.copytree(ACADEMY, staging,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc",
                                                  "tests"))
    log("compiling academy to bytecode…")
    ok = compileall.compile_dir(staging, quiet=2, force=True,
                                legacy=True, optimize=2)
    if not ok:
        log("bytecode compilation reported problems; shipping sources instead")
        return ACADEMY
    removed = 0
    for dirpath, dirnames, filenames in os.walk(staging):
        if "__pycache__" in dirnames:
            shutil.rmtree(os.path.join(dirpath, "__pycache__"),
                          ignore_errors=True)
            dirnames.remove("__pycache__")
        for f in filenames:
            if f.endswith(".py"):
                os.remove(os.path.join(dirpath, f))
                removed += 1
    log(f"replaced {removed} source files with bytecode")
    return staging

def build(onefile=False):
    try:
        import PyInstaller  # noqa: F401
    except Exception:
        log("PyInstaller is required to build the distributable.")
        log("Install it with:  pip install pyinstaller")
        return 1

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        f"--name={APP_NAME}",
        "--windowed",                 # no console window on Windows/macOS
        f"--distpath={os.path.join(ROOT, 'dist')}",
        f"--workpath={os.path.join(ROOT, 'build')}",
        f"--specpath={ROOT}",
        # the academy is imported dynamically from the bundled data folder
        "--hidden-import=wx",
        "--collect-submodules=abaDesktop",
    ]
    cmd += _data_args()
    cmd.append("--onefile" if onefile else "--onedir")
    cmd.append(ENTRY)

    log("running PyInstaller…")
    res = subprocess.run(cmd)
    if res.returncode != 0:
        log("PyInstaller failed")
        return res.returncode
    out = os.path.join(ROOT, "dist", APP_NAME)
    exe = os.path.join(out, APP_NAME + (".exe" if os.name == "nt" else ""))
    if onefile:
        exe = os.path.join(ROOT, "dist",
                           APP_NAME + (".exe" if os.name == "nt" else ""))
    log("")
    log("BUILD COMPLETE")
    log(f"  Run this:  {exe}")
    log("")
    log("  Note: the 'build' folder is PyInstaller scratch space and does NOT")
    log("  contain a runnable program. Running the copy inside 'build' fails")
    log("  with \"Failed to load Python DLL\". Always run from 'dist'.")
    return 0



def install_deps():
    """Install the dependencies that cannot be bundled.

    ``comtypes`` and ``pyttsx3`` ship in ``vendor/`` because they are pure
    Python and run anywhere. wxPython and miniaudio are compiled extensions:
    a copy built for one Python version and platform breaks on any other, so
    they are installed here for the interpreter actually running — one command
    instead of hunting for the right wheels.
    """
    wanted = ["wxPython>=4.2", "miniaudio>=1.59"]
    if os.name == "nt":
        wanted.append("sounddevice>=0.4")     # optional mic capture
    if sys.version_info >= (3, 14):
        # 3.14 is new enough that some projects only publish wheels for it a
        # little late; allow pip to build from source rather than failing.
        log("Python 3.14 detected: allowing source builds if a wheel is missing")
    log("installing build/runtime dependencies for "
        f"Python {sys.version_info.major}.{sys.version_info.minor}…")
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + wanted
    res = subprocess.run(cmd)
    if res.returncode != 0:
        log("dependency install failed; see pip output above")
        return res.returncode
    log("dependencies installed")
    return 0

def main():
    ap = argparse.ArgumentParser(description="Build the standalone academy app.")
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--onefile", action="store_true",
                    help="single executable instead of a folder")
    ap.add_argument("--check", action="store_true",
                    help="validate only; don't build")
    ap.add_argument("--deps", action="store_true",
                    help="install wxPython/miniaudio for this Python, then exit")
    args = ap.parse_args()

    if args.deps:
        return install_deps()

    if args.clean:
        clean()

    log("validating…")
    problems = validate() + verify_standalone()
    if problems:
        log(f"{len(problems)} problem(s):")
        for p in problems[:40]:
            print("   -", p)
        return 1
    log("validation passed")

    if args.check:
        return 0
    return build(onefile=args.onefile)


if __name__ == "__main__":
    sys.exit(main())
