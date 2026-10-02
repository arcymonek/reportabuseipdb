#!/usr/bin/env python3
"""Tests for tools/release_notes.sh and the shape of .github/workflows/release.yml (stdlib unittest).

The Release text is published, and between two releases the version rises many times, so the notes must hold every
entry newer than the previous release (and only those). Needs bash and awk (macOS and Linux have both).
"""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "release_notes.sh"
HAVE_TOOLS = bool(shutil.which("bash") and shutil.which("awk"))

CHANGELOG = """# Changelog

## Unreleased

- Nothing yet.

## Development

- 2026-10-02 - tooling line

## 3.7.0 - 2026-10-10

### Added

- feature seven

## 3.6.100 - 2026-10-05

- fix one hundred

## 3.6.99 - 2026-10-04

- fix ninety-nine

## 3.6.5 - 2026-10-01

- fix five

## 3.5 and earlier - 2026-09-28 and before

- old history
"""


@unittest.skipUnless(HAVE_TOOLS, "requires bash and awk")
class ReleaseNotes(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.log = Path(self._td.name) / "CHANGELOG.md"
        self.log.write_text(CHANGELOG)

    def notes(self, *args):
        return subprocess.run(["bash", str(SCRIPT), *args, str(self.log)], capture_output=True, text=True)

    def headings(self, r):
        return re.findall(r"(?m)^## (\S+)", r.stdout)

    def test_first_release_has_only_its_own_entry(self):
        r = self.notes("3.6.99", "")
        self.assertEqual((r.returncode, self.headings(r)), (0, ["3.6.99"]), r.stderr)
        self.assertNotIn("fix five", r.stdout)

    def test_all_entries_since_the_previous_release_are_included(self):
        r = self.notes("3.7.0", "3.6.5")
        self.assertEqual(self.headings(r), ["3.7.0", "3.6.100", "3.6.99"], r.stderr)
        self.assertNotIn("fix five", r.stdout)           # the previous release itself is not repeated

    def test_z_above_99_sorts_after_99(self):
        r = self.notes("3.6.100", "3.6.99")
        self.assertEqual(self.headings(r), ["3.6.100"], r.stderr)

    def test_entries_newer_than_the_tag_are_left_out(self):
        r = self.notes("3.6.100", "3.6.5")
        self.assertEqual(self.headings(r), ["3.6.100", "3.6.99"], r.stderr)

    def test_unreleased_development_and_old_history_are_never_included(self):
        r = self.notes("3.7.0", "3.0.0")
        for text in ("Nothing yet", "tooling line", "old history"):
            self.assertNotIn(text, r.stdout)

    def test_the_entry_of_the_version_is_always_printed(self):
        # a wrong "previous" (higher than the tag) must not give empty notes
        r = self.notes("3.6.99", "9.9.9")
        self.assertEqual(self.headings(r), ["3.6.99"], r.stderr)

    def test_missing_entry_fails(self):
        r = self.notes("9.9.9", "")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no entry for version 9.9.9", r.stderr)


class ReleaseWorkflow(unittest.TestCase):
    """Guards the properties that matter for a workflow that can publish: tags only, minimal permissions, pinned."""

    def setUp(self):
        self.text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    def test_it_runs_only_on_version_tags(self):
        self.assertRegex(self.text, r"(?s)on:\s*\n\s*push:\s*\n\s*tags: \['v\[0-9\]\*'\]")
        self.assertNotIn("pull_request", self.text)
        self.assertNotIn("branches:", self.text)

    def test_write_permission_is_granted_to_the_job_only(self):
        self.assertEqual(self.text.count("contents: write"), 1)
        top, job = self.text.split("jobs:")
        self.assertIn("contents: read", top)
        self.assertIn("contents: write", job)

    def test_actions_are_pinned_to_a_commit_sha(self):
        uses = re.findall(r"(?m)^\s*- uses: (\S+)", self.text)
        self.assertTrue(uses)
        for ref in uses:
            self.assertRegex(ref, r"@[0-9a-f]{40}$", ref)

    def test_the_tag_name_reaches_the_shell_only_through_the_environment(self):
        # "${{ github.ref_name }}" pasted into a script would let a crafted tag name run commands
        for line in self.text.splitlines():
            if "github.ref_name" in line:
                self.assertRegex(line.strip(), r"^TAG: \$\{\{ github\.ref_name \}\}$", line)


if __name__ == "__main__":
    unittest.main(verbosity=2)
