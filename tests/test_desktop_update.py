import json, os, subprocess, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

import desktop_update as du

GIT = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false"]


def git(cwd, *args):
    done = subprocess.run([*GIT, *args], cwd=str(cwd), capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError(f"git {args} failed: {done.stderr}")
    return done.stdout.strip()


class Repos:
    """origin (bare) + dev clone (publishes) + desktop clone (the installed code)."""
    def __init__(self):
        try:
            self.td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)   # git packs are read-only on Windows
        except TypeError:
            self.td = tempfile.TemporaryDirectory()
        base = Path(self.td.name)
        self.origin, self.dev, self.desktop = base / "radar-origin.git", base / "dev", base / "desktop"
        self.results = base / "results"
        self.results.mkdir()
        git(base, "init", "--bare", str(self.origin))
        git(self.origin, "symbolic-ref", "HEAD", "refs/heads/main")
        git(base, "clone", str(self.origin), str(self.dev))
        git(self.dev, "checkout", "-B", "main")
        self.publish("app.py", "VERSION = 1\n", "first")
        git(base, "clone", str(self.origin), str(self.desktop))
        git(self.desktop, "checkout", "-B", "main", "origin/main")
        self.expected = "radar-origin.git"

    def publish(self, name, text, msg):
        (self.dev / name).write_text(text, encoding="utf-8")
        git(self.dev, "add", name)
        git(self.dev, "commit", "-m", msg)
        git(self.dev, "push", "origin", "main")
        return git(self.dev, "rev-parse", "HEAD")

    def run(self, **kw):
        return du.preflight(self.desktop, self.results, expected_origin=self.expected, **kw)

    def head(self):
        return git(self.desktop, "rev-parse", "HEAD")

    def cleanup(self):
        self.td.cleanup()


class DesktopUpdateTests(unittest.TestCase):
    def setUp(self):
        self.r = Repos()
        self.addCleanup(self.r.cleanup)
        for var in ("GTA_RADAR_SKIP_UPDATE", "GTA_RADAR_ALLOW_UNVERIFIED"):
            os.environ.pop(var, None)

    def test_up_to_date_records_installed_commit(self):
        info = self.r.run()
        self.assertEqual(info["status"], "OK_UP_TO_DATE")
        self.assertTrue(info["ok"])
        self.assertEqual(info["installed_commit"], self.r.head())
        record = json.loads((self.r.results / du.RECORD_FILE).read_text())
        self.assertEqual(record["installed_commit"], self.r.head())

    def test_behind_main_is_fast_forwarded_and_verified(self):
        old = self.r.head()
        (self.r.results / "radar.sqlite").write_bytes(b"precious")
        new = self.r.publish("app.py", "VERSION = 2\n", "second")
        info = self.r.run()
        self.assertEqual(info["status"], "OK_FAST_FORWARDED")
        self.assertEqual(self.r.head(), new)
        self.assertEqual(info["updated_from"], old)
        self.assertEqual((self.r.desktop / "app.py").read_text(), "VERSION = 2\n")
        self.assertEqual((self.r.results / "radar.sqlite").read_bytes(), b"precious")   # data untouched

    def test_dirty_tree_is_refused_and_edits_survive(self):
        self.r.publish("app.py", "VERSION = 2\n", "second")
        (self.r.desktop / "app.py").write_text("VERSION = 99  # my local edit\n", encoding="utf-8")
        before = self.r.head()
        info = self.r.run()
        self.assertEqual(info["status"], "REFUSED_DIRTY_TREE")
        self.assertFalse(info["ok"])
        self.assertEqual(self.r.head(), before)
        self.assertIn("local edit", (self.r.desktop / "app.py").read_text())

    def test_diverged_history_is_refused_and_not_merged(self):
        (self.r.desktop / "local.py").write_text("x = 1\n", encoding="utf-8")
        git(self.r.desktop, "add", "local.py")
        git(self.r.desktop, "commit", "-m", "local only")
        mine = self.r.head()
        self.r.publish("app.py", "VERSION = 2\n", "second")
        info = self.r.run()
        self.assertEqual(info["status"], "REFUSED_DIVERGED")
        self.assertEqual(self.r.head(), mine)

    def test_local_commits_not_on_main_are_not_a_verified_release(self):
        (self.r.desktop / "local.py").write_text("x = 1\n", encoding="utf-8")
        git(self.r.desktop, "add", "local.py")
        git(self.r.desktop, "commit", "-m", "local only")
        self.assertEqual(self.r.run()["status"], "REFUSED_AHEAD_OF_MAIN")

    def test_wrong_origin_is_refused(self):
        info = du.preflight(self.r.desktop, self.r.results, expected_origin="someone-else/other-repo")
        self.assertEqual(info["status"], "REFUSED_WRONG_ORIGIN")

    def test_not_a_git_repo_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(du.preflight(t, None)["status"], "REFUSED_NOT_A_GIT_REPO")

    def test_unreachable_github_runs_but_is_flagged_unverified(self):
        moved = self.r.origin.with_name("gone.git")
        self.r.origin.rename(moved)
        info = self.r.run()
        self.assertEqual(info["status"], "REFUSED_UPDATE_CHECK_FAILED")
        self.assertFalse(info["ok"])
        self.assertIn("unverified release", info["message"])

    def test_broken_update_is_rolled_back(self):
        good = self.r.head()
        self.r.publish("app.py", "def broken(:\n", "bad commit")
        info = self.r.run()
        self.assertEqual(info["status"], "REFUSED_SYNTAX_ERROR")
        self.assertEqual(self.r.head(), good)                    # previous working commit restored
        self.assertEqual(info["rolled_back_to"], good)
        self.assertEqual((self.r.desktop / "app.py").read_text(), "VERSION = 1\n")
        self.assertTrue(any("app.py" in e for e in info["compile_errors"]))

    def test_skip_update_env_verifies_but_never_changes_code(self):
        old = self.r.head()
        self.r.publish("app.py", "VERSION = 2\n", "second")
        with patch.dict(os.environ, {"GTA_RADAR_SKIP_UPDATE": "1"}):
            info = self.r.run()
        self.assertEqual(self.r.head(), old)
        self.assertTrue(info["ok"])

    def test_no_update_flag_reports_behind_without_changing_code(self):
        old = self.r.head()
        self.r.publish("app.py", "VERSION = 2\n", "second")
        info = self.r.run(apply_update=False)
        self.assertEqual(info["status"], "REFUSED_OUTDATED_RELEASE")
        self.assertEqual(self.r.head(), old)

    def test_override_is_explicit_and_recorded(self):
        (self.r.desktop / "app.py").write_text("VERSION = 5\n", encoding="utf-8")
        with patch.dict(os.environ, {"GTA_RADAR_ALLOW_UNVERIFIED": "1"}):
            info = self.r.run()
        self.assertTrue(info["ok"])
        self.assertTrue(info["overridden"])
        self.assertEqual(info["status"], "REFUSED_DIRTY_TREE")   # the truth is still recorded

    def test_log_is_append_only_history(self):
        self.r.run()
        self.r.publish("app.py", "VERSION = 2\n", "second")
        self.r.run()
        lines = (self.r.results / du.LOG_FILE).read_text().strip().splitlines()
        self.assertEqual([json.loads(x)["status"] for x in lines], ["OK_UP_TO_DATE", "OK_FAST_FORWARDED"])

    def test_compile_errors_detects_syntax_errors_in_any_entry_point(self):
        with tempfile.TemporaryDirectory() as t:
            Path(t, "ok.py").write_text("x = 1\n", encoding="utf-8")
            Path(t, "bad.py").write_text("def f(:\n", encoding="utf-8")
            names = [n for n, _ in du.compile_errors(t)]
        self.assertEqual(names, ["bad.py"])


class OrchestratorGateTests(unittest.TestCase):
    def test_refused_verification_stops_before_any_stage(self):
        import gta_total_intelligence_run as total
        refusal = {"status": "REFUSED_DIRTY_TREE", "ok": False, "installed_commit": "abc123",
                   "remote_commit": "", "updated_from": "", "overridden": False,
                   "message": du.MESSAGES["REFUSED_DIRTY_TREE"]}
        with tempfile.TemporaryDirectory() as t, \
             patch.object(total.desktop_update, "preflight", return_value=refusal), \
             patch.object(total.subprocess, "run", side_effect=AssertionError("no stage may run")):
            code = total.execute(t,full_intelligence=True)
            status = json.loads((Path(t) / "GTA_RADAR_RESULTS" / "TOTAL_INTELLIGENCE_REVIEW"
                                 / "TOTAL_RUN_STATUS.json").read_text())
        self.assertEqual(code, 3)
        self.assertEqual(status["status"], "CODE_VERIFICATION_REFUSED")
        self.assertEqual(status["installed_commit"]["installed_commit"], "abc123")
        self.assertEqual(status["stages"], [])


if __name__ == "__main__":
    unittest.main()
