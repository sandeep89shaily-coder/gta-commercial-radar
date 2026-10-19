"""Regression tests for GTA Radar's crash-recovering database lock."""
import datetime as dt
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from radar_run_lock import ActiveRadarRun, once_lock


class RunLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_second_running_instance_is_blocked(self):
        with once_lock(self.folder):
            with self.assertRaises(ActiveRadarRun):
                once_lock(self.folder)
            self.assertTrue((self.folder / 'V6_RUNNING.lock').exists())
        self.assertFalse((self.folder / 'V6_RUNNING.lock').exists())
        with once_lock(self.folder):
            self.assertTrue((self.folder / 'V6_RUNNING.lock').exists())

    def test_dead_owner_marker_is_recovered_without_age_delay(self):
        marker = self.folder / 'V6_RUNNING.lock'
        marker.write_text('999999999\n2026-10-19T08:30:00+00:00\n',
                          encoding='utf-8')
        with once_lock(self.folder):
            self.assertEqual(int(marker.read_text(encoding='utf-8').splitlines()[0]),
                             os.getpid())
        self.assertFalse(marker.exists())

    def test_running_legacy_owner_not_interrupted(self):
        marker = self.folder / 'V6_RUNNING.lock'
        marker.write_text(str(os.getpid()) + '\n'
                          + dt.datetime.now(dt.timezone.utc).isoformat() + '\n',
                          encoding='utf-8')
        with self.assertRaises(ActiveRadarRun):
            once_lock(self.folder)
        self.assertTrue(marker.exists())
        marker.unlink()
        with once_lock(self.folder):
            pass

    def test_unreadable_recent_marker_is_not_blindly_deleted(self):
        marker = self.folder / 'V6_RUNNING.lock'
        marker.write_text('not a process ID', encoding='utf-8')
        with self.assertRaises(ActiveRadarRun):
            once_lock(self.folder)
        self.assertTrue(marker.exists())

    def test_reused_pid_marker_is_recovered(self):
        marker = self.folder / 'V6_RUNNING.lock'
        marker.write_text(str(os.getpid()) + '\n2026-01-01T00:00:00+00:00\n',
                          encoding='utf-8')
        with patch('radar_run_lock._process_alive', return_value=False):
            with once_lock(self.folder):
                self.assertEqual(int(marker.read_text(encoding='utf-8').splitlines()[0]),
                                 os.getpid())

    def test_os_lock_auto_releases_after_process_crash(self):
        """Leave V6_RUNNING.lock behind by exiting without finally/release."""
        code = (
            'import os, sys\n'
            'from radar_run_lock import once_lock\n'
            'lock=once_lock(sys.argv[1])\n'
            'print("LOCK_ACQUIRED", flush=True)\n'
            'os._exit(0)\n'
        )
        repo = Path(__file__).resolve().parents[1]
        env = dict(os.environ)
        env['PYTHONPATH'] = str(repo)
        child = subprocess.run([sys.executable, '-c', code, str(self.folder)],
                               cwd=str(repo), env=env, text=True,
                               capture_output=True, timeout=20)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertIn('LOCK_ACQUIRED', child.stdout)
        self.assertTrue((self.folder / 'V6_RUNNING.lock').exists())
        with once_lock(self.folder):
            # Crash leaves only a marker; the OS-owned lock is released.
            self.assertTrue((self.folder / 'V6_RUNNING.lock').exists())
        self.assertFalse((self.folder / 'V6_RUNNING.lock').exists())


if __name__ == '__main__':
    unittest.main()
