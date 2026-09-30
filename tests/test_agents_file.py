#!/usr/bin/env python3
"""Checks AGENTS.md: the file every AI coding agent reads first must stay accurate and English only."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "AGENTS.md"


class AgentsFile(unittest.TestCase):
    def setUp(self):
        self.text = AGENTS.read_text(encoding="utf-8")

    def test_is_english_only_without_a_polish_twin(self):
        # Polish letters would mean part of the file was written in Polish by mistake.
        self.assertEqual(re.findall(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]", self.text), [])
        self.assertFalse((ROOT / "AGENTS.pl.md").exists())
        self.assertFalse((ROOT / "docs" / "pl" / "AGENTS.md").exists())

    def test_every_file_it_points_to_exists(self):
        # Backticked names that look like repository paths (a suffix or a directory slash) must exist.
        for name in set(re.findall(r"`([A-Za-z0-9_./-]+)`", self.text)):
            if not re.search(r"\.(md|py|sh|yml)$|/$", name) or name.startswith("--"):
                continue
            if name == "abuseipdb.conf" or "/X." in name or name.startswith("X."):   # real config / placeholders
                continue
            self.assertTrue((ROOT / name.rstrip("/")).exists(), f"AGENTS.md mentions missing path {name}")

    def test_names_every_hard_safeguard_constant(self):
        for token in ("EXCLUDE_SCENARIOS", "WEAK_ONLY_SCENARIOS", "kind == \"crowdsec\"", "Accept: application/json"):
            self.assertIn(token, self.text)

    def test_contributor_mode_of_the_hook_exists(self):
        # CONTRIBUTING.md tells contributors to commit with EN_ONLY=1; the hook must really honour it.
        hook = (ROOT / "tools" / "pre-commit").read_text(encoding="utf-8")
        self.assertIn("EN_ONLY", hook)
        self.assertIn("EN_ONLY=1", (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8"))
        self.assertIn("EN_ONLY=1", (ROOT / "CONTRIBUTING.pl.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
