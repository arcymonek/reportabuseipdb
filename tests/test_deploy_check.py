#!/usr/bin/env python3
"""Tests for tools/deploy-check.sh (stdlib unittest).

The script answers one question after a push: do the local main, Forgejo (origin) and GitHub (github) stand on the same
commit? The answer decides whether the next push is safe, so the states must not be confused: "github is simply not
pushed yet" is expected during a deployment, while "diverged" means rewritten history and calls for a stop. Every test
builds two bare repositories on disk (the "remotes"), a working clone and, when someone else must push, a second clone.
No network is involved. Needs git and bash (macOS and Linux have both).
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "deploy-check.sh"
HAVE_TOOLS = bool(shutil.which("git") and shutil.which("bash"))


@unittest.skipUnless(HAVE_TOOLS, "requires git and bash")
class DeployCheck(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.base = Path(self._td.name)
        self.env = dict(os.environ, HOME=self._td.name, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.test",
                        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.test")
        for var in ("BRANCH", "REMOTES"):
            self.env.pop(var, None)
        self.origin = self.base / "origin.git"
        self.github = self.base / "github.git"
        for bare in (self.origin, self.github):
            self.git("init", "-q", "--bare", "-b", "main", str(bare), cwd=self.base)
        self.work = self.base / "work"
        self.work.mkdir()
        self.git("init", "-q", "-b", "main", cwd=self.work)
        self.git("remote", "add", "origin", str(self.origin), cwd=self.work)
        self.git("remote", "add", "github", str(self.github), cwd=self.work)
        self.commit(self.work, "first")
        self.git("push", "-q", "origin", "main", cwd=self.work)
        self.git("push", "-q", "github", "main", cwd=self.work)

    def git(self, *args, cwd):
        return subprocess.run(["git", *args], cwd=cwd, env=self.env, capture_output=True, text=True, check=True)

    def commit(self, repo, name):
        (repo / f"{name}.txt").write_text(name + "\n")
        self.git("add", f"{name}.txt", cwd=repo)
        self.git("commit", "-q", "-m", name, cwd=repo)

    def second_clone(self):
        """Another person's clone, used to push a commit that the working clone has not seen."""
        other = self.base / "other"
        self.git("clone", "-q", str(self.origin), str(other), cwd=self.base)
        return other

    def check(self, *args, **env):
        r = subprocess.run(["bash", str(SCRIPT), *args], cwd=self.work, env=dict(self.env, **env),
                           capture_output=True, text=True)
        r.out = r.stdout + r.stderr
        # the output is meant to be pasted anywhere, so it must never contain a remote address
        for address in (self.origin, self.github, self.base / "gone"):
            self.assertNotIn(str(address), r.out)
        return r

    def line(self, r, label):
        """The output line that starts with label ('origin/main'); fails the test when there is none."""
        for text in r.out.splitlines():
            if text.startswith(label + " "):
                return text
        self.fail(f"no line for {label} in:\n{r.out}")

    def test_everything_the_same(self):
        r = self.check()
        self.assertEqual(r.returncode, 0, r.out)
        self.assertIn("same", self.line(r, "origin/main"))
        self.assertIn("same", self.line(r, "github/main"))
        self.assertIn("RESULT: everything is the same", r.out)

    def test_github_not_pushed_yet_is_reported_as_such(self):
        # the normal state in the middle of a deployment: origin first, deploy, github last
        self.commit(self.work, "second")
        self.git("push", "-q", "origin", "main", cwd=self.work)
        r = self.check()
        self.assertEqual(r.returncode, 1, r.out)
        self.assertIn("same", self.line(r, "origin/main"))
        self.assertIn("NOT PUSHED YET", self.line(r, "github/main"))
        self.assertNotIn("WARNING", r.out)

    def test_nothing_pushed_yet(self):
        self.commit(self.work, "second")
        r = self.check()
        self.assertEqual(r.returncode, 1, r.out)
        self.assertIn("NOT PUSHED YET", self.line(r, "origin/main"))
        self.assertIn("NOT PUSHED YET", self.line(r, "github/main"))

    def test_a_remote_ahead_of_you_is_reported(self):
        # e.g. a merge made on a web page: the remote has a commit that the local main lacks
        other = self.second_clone()
        self.commit(other, "from-someone-else")
        self.git("push", "-q", "origin", "main", cwd=other)
        r = self.check()
        self.assertEqual(r.returncode, 1, r.out)
        self.assertIn("AHEAD", self.line(r, "origin/main"))
        self.assertIn("same", self.line(r, "github/main"))   # github was not touched
        self.assertNotIn("DIVERGED", r.out)

    def test_diverged_history_is_an_alarm(self):
        other = self.second_clone()
        self.commit(other, "theirs")
        self.git("push", "-q", "origin", "main", cwd=other)
        self.commit(self.work, "mine")
        r = self.check()
        self.assertEqual(r.returncode, 1, r.out)
        self.assertIn("DIVERGED", self.line(r, "origin/main"))
        self.assertIn("STOP", self.line(r, "origin/main"))

    def test_github_before_origin_breaks_the_order(self):
        self.commit(self.work, "second")
        self.git("push", "-q", "github", "main", cwd=self.work)
        r = self.check()
        self.assertEqual(r.returncode, 1, r.out)
        self.assertIn("NOT PUSHED YET", self.line(r, "origin/main"))
        self.assertIn("same", self.line(r, "github/main"))
        self.assertIn("WARNING: github/main has 1 commit(s) that origin/main lacks", r.out)

    def test_no_fetch_compares_with_the_last_fetch(self):
        other = self.second_clone()
        self.commit(other, "from-someone-else")
        self.git("push", "-q", "origin", "main", cwd=other)
        self.assertEqual(self.check("--no-fetch").returncode, 0)   # offline: the new commit is not known yet
        self.assertEqual(self.check().returncode, 1)               # a normal run fetches and sees it

    def test_a_missing_remote_is_an_error(self):
        r = self.check(REMOTES="origin nosuch")
        self.assertEqual(r.returncode, 2, r.out)
        self.assertIn("no remote named 'nosuch'", r.out)

    def test_a_failed_fetch_is_an_error_that_hides_the_address(self):
        self.git("remote", "set-url", "origin", str(self.base / "gone"), cwd=self.work)
        r = self.check()
        self.assertEqual(r.returncode, 2, r.out)
        self.assertIn("'git fetch origin' failed", r.out)

    def test_a_missing_local_branch_is_an_error(self):
        r = self.check(BRANCH="nosuch")
        self.assertEqual(r.returncode, 2, r.out)

    def test_another_checked_out_branch_is_only_a_note(self):
        self.git("switch", "-q", "-c", "topic", cwd=self.work)
        r = self.check()
        self.assertEqual(r.returncode, 0, r.out)
        self.assertIn("you are on 'topic'", r.out)

    def test_uncommitted_changes_are_only_a_note(self):
        (self.work / "scratch.txt").write_text("not committed\n")
        r = self.check()
        self.assertEqual(r.returncode, 0, r.out)
        self.assertIn("uncommitted changes", r.out)

    def test_unknown_option_and_help(self):
        self.assertEqual(self.check("--bogus").returncode, 2)
        self.assertEqual(self.check("--help").returncode, 0)
        self.assertEqual(self.check("--no-fetch", "extra").returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
