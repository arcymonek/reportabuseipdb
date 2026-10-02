#!/usr/bin/env python3
"""Version checks: one project version (SCRIPT_VERSION), the changelogs know it, no document repeats it.

The project has ONE version: SCRIPT_VERSION in abuseipdb_report.py, repeated in abuseipdb_send.sh. It is written
only where it is needed: in the two scripts and in the "## X.Y.Z - date" headings of the changelogs. Documents do not
carry a "Version:" line (it was the main source of forgotten edits); see docs/DEVELOPMENT.md, "Versioning".
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC_FILES = (["README.md", "README.pl.md", "CHANGELOG.md"]
             + [f"docs/{p.name}" for p in sorted((ROOT / "docs").glob("*.md"))]
             + [f"docs/pl/{p.name}" for p in sorted((ROOT / "docs" / "pl").glob("*.md"))])


def script_version(name="abuseipdb_report.py", pattern=r'^SCRIPT_VERSION = "(\d+\.\d+\.\d+)"'):
    text = (ROOT / name).read_text(encoding="utf-8")
    return re.search(pattern, text, re.M).group(1)


class Versioning(unittest.TestCase):
    def test_wrapper_has_the_same_version_as_the_generator(self):
        wrapper = script_version("abuseipdb_send.sh", r'^SCRIPT_VERSION="(\d+\.\d+\.\d+)"')
        self.assertEqual(wrapper, script_version())

    def test_changelogs_have_an_entry_for_the_current_version(self):
        # The entry is a heading "## X.Y.Z - date". A change that does not touch the program (documentation, hooks,
        # tests, CI) does not raise the version, so the newest entry may be older than the newest commit.
        version = script_version()
        for rel in ("CHANGELOG.md", "docs/pl/CHANGELOG.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertRegex(text, rf"(?m)^## {re.escape(version)} - \d{{4}}-\d{{2}}-\d{{2}}$", rel)

    def test_documents_carry_no_version_line(self):
        # A repeated "Version: X.Y.Z" line drifts; the version lives in the code and the changelog only.
        for rel in DOC_FILES:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"(?m)^(Version|Wersja): \d", rel)


if __name__ == "__main__":
    unittest.main(verbosity=2)
