# -*- coding: utf-8 -*-
"""Tests for the standalone desktop build: TTS fallback, NVDA migration, paths,
and the extras (report/backup/reminder). These run headless — no GUI toolkit and
no speech engine required."""

import os
import sqlite3
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..")))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..",
                                                "globalPlugins")))

from abaDesktop import migrate, extras
from abaDesktop.paths import user_data_dir, APP_DIR_NAME
from abaDesktop.tts import Speaker, _build_backend


class TestSpeech(unittest.TestCase):
    def test_backend_always_resolves(self):
        # even with no engine installed we must get a usable object
        b = _build_backend()
        self.assertTrue(hasattr(b, "speak"))

    def test_speaker_logs_without_engine(self):
        s = Speaker()
        try:
            s.speak("مرحبا")
            self.assertIn("مرحبا", s.log)
        finally:
            s.shutdown()

    def test_disabled_speaker_still_logs(self):
        s = Speaker(enabled=False)
        try:
            s.speak("اختبار")
            self.assertIn("اختبار", s.log)
        finally:
            s.shutdown()


class TestPaths(unittest.TestCase):
    def test_user_data_dir_is_absolute(self):
        self.assertTrue(os.path.isabs(user_data_dir()))

    def test_portable_by_default(self):
        """Data belongs beside the program so the app and everything it
        accumulates travel together."""
        from abaDesktop.paths import portable_dir
        p = user_data_dir()
        portable = portable_dir()
        if portable:
            self.assertEqual(p, portable)
            self.assertTrue(p.endswith("userdata"))
        else:
            # only when the program folder isn't writable
            self.assertIn(APP_DIR_NAME, p)


class TestMigration(unittest.TestCase):
    def _fake_addon(self):
        base = tempfile.mkdtemp()
        addon = os.path.join(base, "abaAcademy")
        os.makedirs(os.path.join(addon, "flashcards"))
        sqlite3.connect(os.path.join(addon, "aba_academy.db")).close()
        with open(os.path.join(addon, "notebook.json"), "w") as f:
            f.write('{"notes":[]}')
        with open(os.path.join(addon, "flashcards", "d.json"), "w") as f:
            f.write("{}")
        return addon

    def test_describe_finds_items(self):
        addon = self._fake_addon()
        info = migrate.describe(addon)
        self.assertTrue(info["found"])
        names = [n for n, _ in info["items"]]
        self.assertIn("aba_academy.db", names)

    def test_import_copies_everything(self):
        addon = self._fake_addon()
        dest = tempfile.mkdtemp()
        copied, _ = migrate.import_from_addon(dest, addon)
        self.assertIn("aba_academy.db", copied)
        self.assertTrue(os.path.exists(os.path.join(dest, "notebook.json")))
        self.assertTrue(os.path.isdir(os.path.join(dest, "flashcards")))

    def test_import_does_not_clobber(self):
        addon = self._fake_addon()
        dest = tempfile.mkdtemp()
        migrate.import_from_addon(dest, addon)
        copied2, skipped2 = migrate.import_from_addon(dest, addon)
        self.assertEqual(copied2, [])
        self.assertTrue(skipped2)

    def test_missing_source_is_safe(self):
        copied, skipped = migrate.import_from_addon(
            tempfile.mkdtemp(), os.path.join(tempfile.mkdtemp(), "nope"))
        self.assertEqual((copied, skipped), ([], []))


class TestExtras(unittest.TestCase):
    def test_reminder_message_when_short_of_goal(self):
        class S:
            def get_setting(self, k, d=None):
                return "20"
            def today_activity(self):
                return {"answered": 5}
        msg = extras.StudyReminder(S(), lambda t: None)._check()
        self.assertIsNotNone(msg)
        self.assertIn("15", msg)

    def test_reminder_silent_when_goal_met(self):
        class S:
            def get_setting(self, k, d=None):
                return "10"
            def today_activity(self):
                return {"answered": 10}
        self.assertIsNone(extras.StudyReminder(S(), lambda t: None)._check())

    def test_backup_creates_zip(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "x.json"), "w") as f:
            f.write("{}")
        z = extras.backup_now(d)
        self.assertTrue(os.path.exists(z))
        self.assertTrue(z.endswith(".zip"))

    def test_recorder_reports_availability(self):
        # must not raise when sounddevice is absent
        self.assertIsInstance(extras.AudioRecorder().available, bool)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestImportOrdering(unittest.TestCase):
    """The import must land before the academy reads its database.

    A tester hit this: after a successful import the app still asked for their
    name and daily goal, because the hub had already read the empty database to
    decide whether to show onboarding.
    """

    def _addon_with_progress(self):
        import tempfile
        from abaAcademy.database.store import Store
        base = tempfile.mkdtemp()
        addon = os.path.join(base, "abaAcademy")
        os.makedirs(addon)
        s = Store(os.path.join(addon, "aba_academy.db"))
        s.set_setting("onboarded", "1")
        s.set_setting("learner_name", "قيس")
        s.set_setting("daily_goal", "30")
        s.close()
        return addon

    def test_settings_survive_import(self):
        import tempfile
        from abaAcademy.database.store import Store
        addon = self._addon_with_progress()
        dest = tempfile.mkdtemp()
        migrate.import_from_addon(dest, addon)
        s = Store(os.path.join(dest, "aba_academy.db"))
        try:
            self.assertEqual(s.get_setting("onboarded"), "1")
            self.assertEqual(s.get_setting("learner_name"), "قيس")
            self.assertEqual(s.get_setting("daily_goal"), "30")
        finally:
            s.close()

    def test_academy_built_after_import_sees_data(self):
        """Building the academy on the imported folder must show the imported
        settings — this is the ordering the application relies on."""
        import tempfile
        from abaDesktop.core import build_academy
        addon = self._addon_with_progress()
        dest = tempfile.mkdtemp()
        migrate.import_from_addon(dest, addon)
        academy = build_academy(dest)
        self.assertEqual(academy.store.get_setting("onboarded"), "1")
