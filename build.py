#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py — build a distributable Arab Blind Academy desktop application.

Usage:
    python build.py                 # one-folder distributable in dist/
    python build.py --onefile       # single executable
    python build.py --clean         # remove build artefacts first
    python build.py --check         # validate only, don't build
    python build.py --portable      # ready-to-ship zip without PyInstaller

Every build ends with a ready-to-ship zip in dist/:

* the PyInstaller build is zipped as ``ArabBlindAcademy-<version>-<os>.zip``;
* ``--portable`` makes a self-contained Windows package that needs nothing
  installed: the academy (bytecode only), the official embeddable Python and
  the Windows wxPython, with ``ArabBlindAcademy.bat`` to start it, zipped as
  ``ArabBlindAcademy-<version>-windows-portable.zip``. It can be built on any
  OS: pip fetches the Windows packages, and the embedded Python is chosen to
  match the version compiling the bytecode.

Each zip carries the Arabic quick-start guide, the changelog, the credits and
the licence, and is checked after it is written: no source files inside the
packages, no tests, no learner data.

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
    return zip_pyinstaller_build(onefile)



# ---------------------------------------------------------------------------
# release packaging
# ---------------------------------------------------------------------------

QUICK_START = """أكاديمية الكفيف العربي {version}
المطوّر: رياض أَسّوم (Riad Assoum) — github.com/riadassoum

التشغيل
{run}

البرنامج محمول: يحفظ تقدّمك وإعداداتك في مجلّد userdata بجانبه. لنقله إلى جهاز آخر انسخ المجلّد كاملًا.

الاستعمال
كل شيء يعمل بلوحة المفاتيح ويُقرأ بقارئ الشاشة أو بالصوت المدمج. Tab وShift+Tab للتنقّل، وCtrl+Tab للتنقّل بين أقسام الشاشة الرئيسية، وEnter للفتح، وEscape للرجوع، وF1 للمساعدة في أيّ شاشة.
لضعاف البصر ومن يرافق المتعلّم: من الإعدادات اختر حجم الخطّ والتباين العالي، وفعّل إبراز العنصر المحدّد.

التغييرات: CHANGELOG.txt
المصادر والتراخيص: CREDITS.txt وLICENSE
"""


def app_version():
    import re
    try:
        src = open(os.path.join(ACADEMY, "gui", "hub.py"), encoding="utf-8").read()
        m = re.search(r'__version__\s*=\s*"([^"]+)"', src)
        if m:
            return m.group(1)
    except OSError:
        pass
    return "0"


def _platform_tag():
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _docs(dest, run_text):
    os.makedirs(dest, exist_ok=True)
    for src, name in ((os.path.join(ACADEMY, "CHANGELOG.txt"), "CHANGELOG.txt"),
                      (os.path.join(ACADEMY, "CREDITS.txt"), "CREDITS.txt"),
                      (os.path.join(ROOT, "LICENSE"), "LICENSE"),
                      (os.path.join(ROOT, "README.md"), "README.md")):
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dest, name))
    with open(os.path.join(dest, "اقرأني.txt"), "w", encoding="utf-8") as f:
        f.write(QUICK_START.format(version=app_version(), run=run_text))


def _bytecode_copy(src, dst):
    """Copy a package to ``dst`` with every .py replaced by its .pyc."""
    import compileall
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests", "userdata"))
    if not compileall.compile_dir(dst, quiet=2, force=True, legacy=True, optimize=2):
        raise RuntimeError(f"bytecode compilation failed for {src}")
    for dirpath, dirnames, filenames in os.walk(dst):
        if "__pycache__" in dirnames:
            shutil.rmtree(os.path.join(dirpath, "__pycache__"), ignore_errors=True)
            dirnames.remove("__pycache__")
        for f in filenames:
            if f.endswith(".py"):
                os.remove(os.path.join(dirpath, f))


def zip_folder(folder, zip_path):
    import zipfile
    if os.path.exists(zip_path):
        os.remove(zip_path)
    base = os.path.dirname(folder)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for dirpath, dirnames, filenames in os.walk(folder):
            dirnames.sort()
            for f in sorted(filenames):
                full = os.path.join(dirpath, f)
                z.write(full, os.path.relpath(full, base))
    return zip_path


def check_release_zip(zip_path, require=()):
    """Problems found in a release zip (empty list when it is ready to ship)."""
    import zipfile
    problems = []
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        bad = z.testzip()
        if bad:
            problems.append(f"corrupt entry: {bad}")
    for n in names:
        parts = n.split("/")
        ours = "abaAcademy" in parts or "abaDesktop" in parts
        if ours and ("tests" in parts or "__pycache__" in parts):
            problems.append(f"should not ship: {n}")
        if "userdata" in parts and not n.endswith("userdata/"):
            problems.append(f"learner data inside the zip: {n}")
        if n.endswith(".py") and ("abaAcademy" in parts or "abaDesktop" in parts):
            problems.append(f"source file in release: {n}")
    for r in require:
        if not any(n.endswith(r) for n in names):
            problems.append(f"missing from zip: {r}")
    return problems


EMBED_URL = "https://www.python.org/ftp/python/{v}/python-{v}-embed-amd64.zip"
RUNTIME_PACKAGES = ["wxPython>=4.2", "miniaudio>=1.59"]


def _download(url, dest):
    import urllib.request
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    os.replace(tmp, dest)
    return dest


def _embedded_python(cache):
    """The official embeddable CPython for Windows (64-bit) of the same minor
    version as the Python running this script, so the compiled academy runs on
    it. Tries this exact release first, then earlier patch releases (the
    later security-only releases of a series publish no Windows binaries)."""
    import urllib.error
    major, minor, micro = sys.version_info[:3]
    for patch in range(micro, -1, -1):
        v = f"{major}.{minor}.{patch}"
        dest = os.path.join(cache, f"python-{v}-embed-amd64.zip")
        if os.path.isfile(dest):
            return v, dest
        try:
            _download(EMBED_URL.format(v=v), dest)
            return v, dest
        except urllib.error.HTTPError:
            continue
    raise RuntimeError(f"no embeddable Python {major}.{minor} found on python.org")


def build_portable():
    """A self-contained Windows package: the academy (bytecode only), its own
    embedded Python and wxPython, and a launcher. Nothing needs to be
    installed on the learner's computer; it can be built from any OS."""
    import zipfile
    ver = app_version()
    name = f"{APP_NAME}-{ver}-windows-portable"
    dist = os.path.join(ROOT, "dist")
    cache = os.path.join(ROOT, "build", "cache")
    stage = os.path.join(dist, name)
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    os.makedirs(stage)

    log("fetching the embeddable Python for Windows…")
    try:
        pyver, embed_zip = _embedded_python(cache)
    except Exception as exc:
        log(f"could not get the embeddable Python: {exc}")
        return 1
    pydir = os.path.join(stage, "python")
    with zipfile.ZipFile(embed_zip) as z:
        z.extractall(pydir)
    tag = f"{sys.version_info.major}{sys.version_info.minor}"
    pth = os.path.join(pydir, f"python{tag}._pth")
    with open(pth, "w", encoding="ascii", newline="\r\n") as f:
        f.write(f"python{tag}.zip\n.\nLib\\site-packages\n..\nimport site\n")
    log(f"embedded Python {pyver}")

    log("installing wxPython and miniaudio for Windows into the package…")
    site = os.path.join(pydir, "Lib", "site-packages")
    res = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                          "--target", site, "--platform", "win_amd64",
                          "--python-version", f"{sys.version_info.major}.{sys.version_info.minor}",
                          "--implementation", "cp", "--only-binary=:all:"] + RUNTIME_PACKAGES)
    if res.returncode != 0:
        log("installing the Windows packages failed; see pip output above")
        return res.returncode
    for junk in ("bin",):
        shutil.rmtree(os.path.join(site, junk), ignore_errors=True)

    log("staging bytecode-only academy and desktop shell…")
    _bytecode_copy(ACADEMY, os.path.join(stage, "abaAcademy"))
    _bytecode_copy(os.path.join(ROOT, "abaDesktop"), os.path.join(stage, "abaDesktop"))
    if os.path.isdir(os.path.join(ROOT, "vendor")):
        shutil.copytree(os.path.join(ROOT, "vendor"), os.path.join(stage, "vendor"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(ENTRY, os.path.join(stage, "run_app.py"))
    with open(os.path.join(stage, f"{APP_NAME}.bat"), "w", encoding="ascii", newline="\r\n") as f:
        f.write('@echo off\nstart "" "%~dp0python\\pythonw.exe" "%~dp0run_app.py" %*\n')
    with open(os.path.join(stage, f"{APP_NAME}-debug.bat"), "w", encoding="ascii", newline="\r\n") as f:
        f.write('@echo off\n"%~dp0python\\python.exe" "%~dp0run_app.py" %*\npause\n')
    _docs(stage, f"افتح {APP_NAME}.bat. لا يحتاج إلى تثبيت بايثون ولا أيّ شيء آخر، ويعمل من أيّ مجلّد أو ذاكرة USB. "
                 f"إذا لم يفتح، شغّل {APP_NAME}-debug.bat لترى السبب.")

    log("checking the staged academy boots…")
    res = subprocess.run([sys.executable, "-c",
                          "import sys, tempfile; sys.path.insert(0, sys.argv[1]);"
                          "from abaAcademy.academy import Academy;"
                          "ac = Academy(sys.argv[1] + '/abaAcademy', tempfile.mkdtemp());"
                          "print(len(list(ac.courses())))", stage],
                         capture_output=True, text=True)
    if res.returncode != 0:
        log("the staged copy does not boot:")
        print(res.stderr)
        return 1
    zip_path = zip_folder(stage, os.path.join(dist, name + ".zip"))
    problems = check_release_zip(zip_path, require=(f"{APP_NAME}.bat", "python/pythonw.exe", "python/python.exe",
                                                    f"python/python{tag}.zip", "site-packages/wx/__init__.py",
                                                    "abaAcademy/academy.pyc", "abaDesktop/app.pyc", "اقرأني.txt"))
    if problems:
        log("release zip has problems:")
        for p in problems[:30]:
            print("   -", p)
        return 1
    log(f"READY TO SHIP: {zip_path} ({os.path.getsize(zip_path) // (1024 * 1024)} MB)")
    return 0


def zip_pyinstaller_build(onefile=False):
    ver = app_version()
    dist = os.path.join(ROOT, "dist")
    name = f"{APP_NAME}-{ver}-{_platform_tag()}"
    pack = os.path.join(dist, name)
    if os.path.isdir(pack):
        shutil.rmtree(pack)
    exe_name = APP_NAME + (".exe" if os.name == "nt" else "")
    if onefile:
        os.makedirs(pack)
        shutil.copy2(os.path.join(dist, exe_name), os.path.join(pack, exe_name))
    else:
        shutil.copytree(os.path.join(dist, APP_NAME), pack)
    _docs(pack, f"افتح {exe_name}. لا يحتاج إلى تثبيت بايثون ولا أيّ شيء آخر.")
    zip_path = zip_folder(pack, os.path.join(dist, name + ".zip"))
    problems = check_release_zip(zip_path, require=(exe_name, "اقرأني.txt"))
    if problems:
        log("release zip has problems:")
        for p in problems[:30]:
            print("   -", p)
        return 1
    log(f"READY TO SHIP: {zip_path}")
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
    ap.add_argument("--portable", action="store_true",
                    help="self-contained Windows zip (embedded Python), no PyInstaller needed")
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
    if args.portable:
        return build_portable()
    return build(onefile=args.onefile)


if __name__ == "__main__":
    sys.exit(main())
