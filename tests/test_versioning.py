#!/usr/bin/env python3
"""Checks that the version shown in the documentation matches SCRIPT_VERSION of the generator."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = (["README.md", "README.pl.md", "CHANGELOG.md", "CHANGELOG.pl.md"]
        + [f"docs/{n}.md" for n in ("ARCHITECTURE", "COMPLIANCE", "OPERATIONS", "DEVELOPMENT")]
        + [f"docs/pl/{n}.md" for n in ("ARCHITECTURE", "COMPLIANCE", "OPERATIONS", "DEVELOPMENT")])


def script_version():
    text = (ROOT / "abuseipdb_report.py").read_text(encoding="utf-8")
    return re.search(r'^SCRIPT_VERSION = "(\d+\.\d+\.\d+)"', text, re.M).group(1), text


class Versioning(unittest.TestCase):
    def test_docstring_header_matches_constant(self):
        version, text = script_version()
        self.assertIn(f"abuseipdb_report.py - v{version}", text)

    def test_every_document_shows_the_current_version(self):
        version, _ = script_version()
        for rel in DOCS:
            label = "Wersja" if rel.endswith(".pl.md") or "/pl/" in rel else "Version"
            text = (ROOT / rel).read_text(encoding="utf-8")
            m = re.search(rf"^{label}: (\d+\.\d+\.\d+) \(`abuseipdb_report\.py`\)$", text, re.M)
            self.assertIsNotNone(m, f"{rel}: missing '{label}: X.Y.Z (`abuseipdb_report.py`)' line")
            self.assertEqual(m.group(1), version, rel)

    def test_changelogs_have_an_entry_for_the_current_version(self):
        # The entry is a heading "## X.Y.Z - date". A change that does not touch the program (documentation, hooks,
        # tests, CI) does not raise the version, so the newest entry may be older than the newest commit.
        version, _ = script_version()
        for rel in ("CHANGELOG.md", "CHANGELOG.pl.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertRegex(text, rf"(?m)^## {re.escape(version)} - \d{{4}}-\d{{2}}-\d{{2}}$", rel)


if __name__ == "__main__":
    unittest.main(verbosity=2)
