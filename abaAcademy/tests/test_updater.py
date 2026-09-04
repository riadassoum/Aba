# -*- coding: utf-8 -*-
"""Tests for the update checker's version parsing and comparison. Network calls
are not exercised here (they need the live GitHub API); the deterministic
version logic is what matters for correctness."""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy import updater


class TestParseVersion(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(updater.parse_version("2.0"), (2, 0))
        self.assertEqual(updater.parse_version("2.1.3"), (2, 1, 3))

    def test_v_prefix(self):
        self.assertEqual(updater.parse_version("v2.0"), (2, 0))
        self.assertEqual(updater.parse_version("V3.4.5"), (3, 4, 5))

    def test_suffix_tolerated(self):
        self.assertEqual(updater.parse_version("2.0-beta"), (2, 0))
        self.assertEqual(updater.parse_version("2.1.0+build7"), (2, 1, 0))

    def test_empty(self):
        self.assertEqual(updater.parse_version(""), (0,))
        self.assertEqual(updater.parse_version(None), (0,))


class TestCompareVersions(unittest.TestCase):
    def test_less(self):
        self.assertEqual(updater.compare_versions("2.0", "2.1"), -1)
        self.assertEqual(updater.compare_versions("1.9", "2.0"), -1)
        self.assertEqual(updater.compare_versions("2.0", "2.0.1"), -1)

    def test_greater(self):
        self.assertEqual(updater.compare_versions("2.1", "2.0"), 1)
        self.assertEqual(updater.compare_versions("2.0", "1.0"), 1)

    def test_equal(self):
        self.assertEqual(updater.compare_versions("2.0", "v2.0"), 0)
        self.assertEqual(updater.compare_versions("2.0-beta", "2.0"), 0)

    def test_result_kinds_exist(self):
        for k in (updater.UP_TO_DATE, updater.UPDATE_AVAILABLE, updater.AHEAD,
                  updater.NO_CONNECTION, updater.ERROR):
            self.assertIsInstance(k, str)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestInstallZip(unittest.TestCase):
    """Applying an update in place must replace program files and never touch
    what the learner has accumulated."""

    def _app(self):
        import tempfile
        app = tempfile.mkdtemp()
        os.makedirs(os.path.join(app, "userdata"))
        with open(os.path.join(app, "userdata", "progress.db"), "w") as f:
            f.write("PROGRESS")
        with open(os.path.join(app, "prog.txt"), "w") as f:
            f.write("v1")
        return app

    def _zip(self, wrap=True):
        import tempfile
        import zipfile
        path = os.path.join(tempfile.mkdtemp(), "update.zip")
        prefix = "ArabBlindAcademy/" if wrap else ""
        with zipfile.ZipFile(path, "w") as z:
            z.writestr(prefix + "prog.txt", "v2")
            z.writestr(prefix + "added.txt", "new")
            z.writestr(prefix + "userdata/progress.db", "OVERWRITE ATTEMPT")
        return path

    def test_replaces_program_files(self):
        app = self._app()
        updater.install_zip(self._zip(), app)
        with open(os.path.join(app, "prog.txt")) as f:
            self.assertEqual(f.read(), "v2")
        self.assertTrue(os.path.exists(os.path.join(app, "added.txt")))

    def test_preserves_user_data(self):
        app = self._app()
        replaced, skipped, _ = updater.install_zip(self._zip(), app)
        with open(os.path.join(app, "userdata", "progress.db")) as f:
            self.assertEqual(f.read(), "PROGRESS")
        self.assertTrue(any("userdata" in s for s in skipped))

    def test_strips_single_top_folder(self):
        app = self._app()
        updater.install_zip(self._zip(wrap=True), app)
        # contents land in the app folder, not a nested copy
        self.assertFalse(os.path.isdir(os.path.join(app, "ArabBlindAcademy")))

    def test_handles_unwrapped_zip(self):
        app = self._app()
        updater.install_zip(self._zip(wrap=False), app)
        with open(os.path.join(app, "prog.txt")) as f:
            self.assertEqual(f.read(), "v2")

    def test_apply_pending_swaps_staged_files(self):
        import tempfile
        app = tempfile.mkdtemp()
        with open(os.path.join(app, "a.txt"), "w") as f:
            f.write("old")
        with open(os.path.join(app, "a.txt.new"), "w") as f:
            f.write("new")
        done, failed = updater.apply_pending(app)
        self.assertEqual(failed, [])
        with open(os.path.join(app, "a.txt")) as f:
            self.assertEqual(f.read(), "new")
