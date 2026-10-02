#!/usr/bin/env python3
"""Tests for tools/pre-commit (privacy scan) and tools/commit-msg (stdlib unittest).

The hooks guard the one thing this project must never do: publish the operator's own host names. Until now
nothing tested them, so a change to the allow-list could silently let a real host name through (it did: the
author's domain was removed from the scan as a substring, so a host under it passed). Every test builds a
throw-away git repository from the real tools/ and docs, stages one change and runs the hook.

Needs git and bash (macOS and Linux have both). Own names in the tests are reserved names (example.org,
host.example); the author's domain, which the repository may contain, is assembled from pieces here so
that this file does not trip the very scan it tests.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOM = "arkadiusz" + "polak.pl"                 # the one domain of the author that the repository may mention
PROFILE = "github.com/arcy" + "monek/"          # the author's GitHub profile path (allowed)
NAME = "Arkadiusz" + " Polak"                   # the author's name (allowed)
HAVE_TOOLS = bool(shutil.which("git") and shutil.which("bash"))
# Root files only; docs/ (including docs/pl/ with the Polish CHANGELOG, CONTRIBUTING, ...) is copied as a whole.
FILES = ["abuseipdb_report.py", "abuseipdb_send.sh", "README.md", "README.pl.md", "CHANGELOG.md",
         "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md"]


@unittest.skipUnless(HAVE_TOOLS, "requires git and bash")
class HookBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.repo = Path(self._td.name) / "repo"
        self.repo.mkdir()
        for name in FILES:
            if (ROOT / name).exists():
                shutil.copy(ROOT / name, self.repo / name)
        for sub in ("docs", "tools"):
            shutil.copytree(ROOT / sub, self.repo / sub)
        # the config of the throw-away "operator": reserved names plus the author's domain as a marker,
        # because that is exactly the case the allow-list must not blanket-cover
        self.conf = Path(self._td.name) / "abuseipdb.conf"
        self.conf.write_text(f"OWN_NAME_MARKERS=example.org, host.example, {DOM}\n")
        self.env = dict(os.environ, HOME=self._td.name, ABUSEIPDB_CONFIG=str(self.conf),
                        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.test",
                        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.test",
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.git("-c", "core.hooksPath=/nonexistent", "commit", "-q", "-m", "baseline")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, env=self.env, capture_output=True, text=True, check=True)

    def run_hook(self, name, *args, env=None):
        r = subprocess.run(["bash", str(self.repo / "tools" / name), *args], cwd=self.repo,
                           env=env or self.env, capture_output=True, text=True)
        r.out = r.stdout + r.stderr
        return r


class PreCommit(HookBase):
    def stage(self, text, name="notes.txt"):
        (self.repo / name).write_text(text)
        self.git("add", name)

    def assert_blocked(self, text, what):
        self.stage(text)
        r = self.run_hook("pre-commit")
        self.assertEqual(r.returncode, 1, (what, r.out))
        self.assertIn("PRIVACY", r.out, what)

    def assert_allowed(self, text, what):
        self.stage(text)
        r = self.run_hook("pre-commit")
        self.assertEqual(r.returncode, 0, (what, r.out))
        self.assertNotIn("PRIVACY", r.out, what)

    def test_clean_change_passes(self):
        self.assert_allowed("a harmless line\n", "clean line")

    def test_own_names_are_blocked_case_insensitively(self):
        self.assert_blocked("ssh to chat.example.org\n", "own domain")
        self.assert_blocked("the box is called HOST.EXAMPLE\n", "own host, upper case")

    def test_the_authors_contact_details_are_allowed(self):
        for text in (f"contact github@{DOM}\n", f"web https://{DOM}/ and {DOM}\n", f"(c) {NAME}\n",
                     f"see https://{PROFILE}reportabuseipdb\n"):
            self.setUp()
            self.assert_allowed(text, text)

    def test_a_host_under_the_authors_domain_is_still_blocked(self):
        # The old allow-list removed the domain as a substring, so "nas.<domain>" became "nas." and passed.
        for text in (f"ssh nas.{DOM}\n", f"https://www.{DOM}/\n", f"mail someone@{DOM}\n", f"sub-{DOM}\n"):
            self.setUp()
            self.assert_blocked(text, text)

    def test_the_real_config_file_is_never_committed(self):
        self.stage("OWN_NAME_MARKERS=x\n", name="abuseipdb.conf")
        r = self.run_hook("pre-commit")
        self.assertEqual(r.returncode, 1, r.out)
        self.assertIn("real config file", r.out)

    def test_key_like_strings_are_blocked(self):
        self.assert_blocked("key " + "a1b2c3d4" * 10 + "\n", "80 hex characters")
        self.setUp()
        self.assert_blocked("NTFY_TOPIC=my-real-topic\n", "a real-looking ntfy topic")
        self.setUp()
        self.assert_allowed("NTFY_TOPIC=your-private-ntfy-topic\n", "the placeholder topic")

    def test_without_a_local_config_the_own_name_scan_is_skipped_with_a_note(self):
        self.conf.unlink()
        self.stage("ssh to chat.example.org\n")
        r = self.run_hook("pre-commit")
        self.assertEqual(r.returncode, 0, r.out)
        self.assertIn("privacy scan of own names skipped", r.out)

    def test_only_added_lines_are_scanned(self):
        # a name that is already in the baseline file must not block an unrelated edit of that file
        (self.repo / "notes.txt").write_text("chat.example.org\n")
        self.git("add", "notes.txt")
        self.git("-c", "core.hooksPath=/nonexistent", "commit", "-q", "-m", "old content")
        self.stage("chat.example.org\nand a clean new line\n")
        r = self.run_hook("pre-commit")
        self.assertEqual(r.returncode, 0, r.out)


class VersionRules(HookBase):
    """The version rules of tools/pre-commit: one project version, one allowed step per commit, Z without a limit."""

    def set_versions(self, report, wrapper=None, commit=False):
        wrapper = wrapper or report
        for name, pattern, new in (("abuseipdb_report.py", r'^SCRIPT_VERSION = ".*"$', f'SCRIPT_VERSION = "{report}"'),
                                   ("abuseipdb_send.sh", r'^SCRIPT_VERSION=".*"$', f'SCRIPT_VERSION="{wrapper}"')):
            text = (self.repo / name).read_text()
            text, n = re.subn(pattern, new, text, flags=re.M)
            self.assertEqual(n, 1, name)
            (self.repo / name).write_text(text)
        self.git("add", "abuseipdb_report.py", "abuseipdb_send.sh")
        if commit:
            self.git("-c", "core.hooksPath=/nonexistent", "commit", "-q", "--allow-empty", "-m", f"version {report}")

    def check(self, old, new, wrapper=None):
        self.set_versions(old, commit=True)
        self.set_versions(new, wrapper)
        return self.run_hook("pre-commit")

    def test_allowed_steps_pass(self):
        # Z+1, Z without an upper limit, Y+1 with Z=0 and X+1 with Y=Z=0
        for old, new in (("3.6.33", "3.6.34"), ("3.6.99", "3.6.100"), ("3.6.100", "3.6.101"),
                         ("3.6.33", "3.7.0"), ("3.6.99", "3.7.0"), ("3.6.33", "4.0.0")):
            self.setUp()
            r = self.check(old, new)
            self.assertEqual(r.returncode, 0, (old, new, r.out))

    def test_other_steps_are_blocked(self):
        for old, new in (("3.6.33", "3.6.35"),      # skipped one
                         ("3.6.33", "3.7.1"),       # Y raised but Z not reset
                         ("3.6.33", "4.1.0"),       # X raised but Y not reset
                         ("3.6.33", "3.6.32"),      # backwards
                         ("3.6.33", "3.8.0")):      # skipped a Y
            self.setUp()
            r = self.check(old, new)
            self.assertEqual(r.returncode, 1, (old, new, r.out))
            self.assertIn("VERSION STEP", r.out, (old, new))

    def test_an_untouched_version_passes(self):
        # a contributor's commit never touches the version
        self.set_versions("3.6.33", commit=True)
        (self.repo / "notes.txt").write_text("a harmless line\n")
        self.git("add", "notes.txt")
        r = self.run_hook("pre-commit")
        self.assertEqual(r.returncode, 0, r.out)

    def test_the_wrapper_must_carry_the_version_of_the_generator(self):
        r = self.check("3.6.33", "3.6.34", wrapper="3.6.33")
        self.assertEqual(r.returncode, 1, r.out)
        self.assertIn("VERSION MISMATCH", r.out)


class CommitMsg(HookBase):
    def check(self, message):
        path = Path(self._td.name) / "MSG"
        path.write_text(message)
        return self.run_hook("commit-msg", str(path))

    def test_clean_message_passes(self):
        r = self.check("Fix the window margin (3.6.25)\n\nA longer explanation.\n")
        self.assertEqual(r.returncode, 0, r.out)

    def test_own_names_in_the_message_are_blocked(self):
        for msg in ("Fix login on chat.example.org\n", "Subject\n\nbody mentions Host.Example here\n"):
            r = self.check(msg)
            self.assertEqual(r.returncode, 1, (msg, r.out))
            self.assertIn("PRIVACY", r.out)

    def test_git_comment_lines_are_ignored(self):
        r = self.check("Subject\n# chat.example.org is only in git's own comment block\n")
        self.assertEqual(r.returncode, 0, r.out)

    def test_authors_details_allowed_but_hosts_under_the_domain_blocked(self):
        self.assertEqual(self.check(f"Update contact github@{DOM}\n").returncode, 0)
        r = self.check(f"Deploy to nas.{DOM}\n")
        self.assertEqual(r.returncode, 1, r.out)

    def test_key_like_string_is_blocked(self):
        r = self.check("Subject\n\n" + "f0e1d2c3" * 10 + "\n")
        self.assertEqual(r.returncode, 1, r.out)
        self.assertIn("API key", r.out)

    def test_without_a_local_config_nothing_is_scanned(self):
        self.conf.unlink()
        self.assertEqual(self.check("Fix login on chat.example.org\n").returncode, 0)

    def test_it_runs_as_a_real_git_hook(self):
        # end to end: core.hooksPath=tools makes git itself call both hooks
        self.git("config", "core.hooksPath", "tools")
        (self.repo / "notes.txt").write_text("fine\n")
        self.git("add", "notes.txt")
        bad = subprocess.run(["git", "commit", "-q", "-m", "Fix chat.example.org"], cwd=self.repo,
                             env=self.env, capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0, bad.stdout + bad.stderr)
        self.assertIn("PRIVACY", bad.stdout + bad.stderr)
        good = subprocess.run(["git", "commit", "-q", "-m", "Add notes"], cwd=self.repo,
                              env=self.env, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)


class Pairing(HookBase):
    """The EN/PL pairing rule: a change to one side of a pair must be staged together with the other side.

    The rule only knows the pairs listed in pair_of(). A document missing from that list (CODE_OF_CONDUCT was, until
    now) could drift away from its translation without the hook noticing, so every pair is tested here.
    """
    PAIRS = [("README.md", "README.pl.md"), ("CHANGELOG.md", "docs/pl/CHANGELOG.md"),
             ("CONTRIBUTING.md", "docs/pl/CONTRIBUTING.md"), ("SECURITY.md", "docs/pl/SECURITY.md"),
             ("CODE_OF_CONDUCT.md", "docs/pl/CODE_OF_CONDUCT.md"),
             ("docs/ARCHITECTURE.md", "docs/pl/ARCHITECTURE.md")]

    def touch(self, name, extra="\nA harmless extra sentence.\n"):
        with open(self.repo / name, "a") as f:
            f.write(extra)
        self.git("add", name)

    def test_one_side_alone_is_refused_for_every_pair(self):
        for en, pl in self.PAIRS:
            for changed, other in ((en, pl), (pl, en)):
                with self.subTest(changed=changed):
                    self.git("reset", "-q")
                    self.touch(changed)
                    r = self.run_hook("pre-commit")
                    self.assertEqual(r.returncode, 1, r.out)
                    self.assertIn("EN/PL MISMATCH", r.out)
                    self.assertIn(other, r.out)

    def test_both_sides_together_pass_for_every_pair(self):
        for en, pl in self.PAIRS:
            with self.subTest(pair=en):
                self.git("reset", "-q")
                self.touch(en)
                self.touch(pl)
                r = self.run_hook("pre-commit")
                self.assertEqual(r.returncode, 0, r.out)

    def test_a_different_number_of_headings_is_refused(self):
        self.touch("CODE_OF_CONDUCT.md", "\n## One more heading\n")
        self.touch("docs/pl/CODE_OF_CONDUCT.md")
        r = self.run_hook("pre-commit")
        self.assertEqual(r.returncode, 1, r.out)
        self.assertIn("HEADING COUNT DIFFERS", r.out)

    def test_contributor_mode_skips_only_the_pairing_rule(self):
        self.touch("CODE_OF_CONDUCT.md")
        r = self.run_hook("pre-commit", env=dict(self.env, EN_ONLY="1"))
        self.assertEqual(r.returncode, 0, r.out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
