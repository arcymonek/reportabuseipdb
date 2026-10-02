**English** | [Polski](docs/pl/CHANGELOG.md)

Version: 3.6.33 (`abuseipdb_report.py`)

# Changelog

Notable changes for people who run the tool. Every entry is mirrored in [docs/pl/CHANGELOG.md](docs/pl/CHANGELOG.md). Format:
[Keep a Changelog](https://keepachangelog.com/). The detailed history of every commit is in `git log`.

Version numbering is `X.Y.Z`. The project version is the version of `abuseipdb_report.py`. It rises when the **program**
changes: the two scripts or the meaning of a line in `abuseipdb.conf.example` (`Z` for a fix, `Y` for a new function or
config key, `X` is a deliberate decision). Changes to hooks, tests, CI, templates and documentation do not raise it; the
ones that matter to maintainers and contributors are listed under "Development" with a date. `abuseipdb_send.sh` has
its own version (currently 1.1.7) and follows the same rule.

## Unreleased

- Nothing yet.

## Development

Hooks, tests, CI and GitHub files. Not versioned: these changes do not affect what runs on your server.

- 2026-10-02 - A test pins that community blocklist alerts (`kind` `capi`) are never reported.
- 2026-10-01 - The Polish versions of `CHANGELOG`, `CONTRIBUTING`, `SECURITY` and `CODE_OF_CONDUCT` moved from the root to
  `docs/pl/` (as `docs/pl/X.md`); `README.pl.md` stays in the root. The pre-commit hook and the tests follow the new pairs.
- 2026-10-01 - The pre-commit hook enforces the EN/PL pair of `CODE_OF_CONDUCT.md`; the pairing rule now has tests.
- 2026-10-01 - Code of conduct (Contributor Covenant 2.1, with an unofficial Polish translation) and a pull request template.
- 2026-10-01 - CI actions are pinned to commit SHAs; checking for newer versions is manual (see `docs/DEVELOPMENT.md`).
- 2026-10-01 - Privacy hooks: a hole is closed (a host name under the author's domain used to pass the scan), a new
  `tools/commit-msg` hook scans commit messages, the rules live in `tools/lib-privacy.sh`, and the hooks have tests.
- 2026-10-01 - Tests for the built-in scenario exclusion, the 8 MB cut and `ReportDate` in the future.
- 2026-09-30 - Bug report and Discussions forms; CI runs on pushes to `main` and on pull requests, on a pinned
  `ubuntu-24.04`; a branch workflow for code (see `docs/DEVELOPMENT.md`); `AGENTS.md` for AI coding agents;
  `EN_ONLY=1` lets contributors who write English only commit.
- 2026-09-29 - `CONTRIBUTING.md`, `SECURITY.md`, a CI workflow (Python 3.9 and the newest Python, `shellcheck`).
- 2026-09-28 - The pre-commit hook: syntax checks, the EN/PL pairing rule, version rules and a privacy scan.

## 3.6.33 - 2026-10-02

### Changed

- The log line for a CrowdSec scenario that has no known category (`unknown scenario ... - not reported`) now asks you to
  open an issue with the scenario name instead of suggesting that you edit `CATEGORY_MAP` on your server. Editing
  tracked code breaks `git pull --ff-only`, and the maintainer checks what a scenario detects before it is published.
  The generated CSV is unchanged. No action needed when updating.

## 3.6.32 - 2026-10-01

First version prepared for a public repository. It collects all changes since 3.6.0 (2026-09-28).

### Upgrade notes

- **Create the single config file.** All local settings now live in `~/.secrets/abuseipdb.conf` (copy
  `abuseipdb.conf.example`). The old files `abuseipdb_api_key`, `ntfy_topic` and `abuseipdb_exclude.txt` still work as a
  deprecated fallback; the config wins. Delete the old files after migrating.
- **`OWN_NAME_MARKERS` is required for a live run.** A live upload is refused while the list is empty or still holds the
  example values. A dry run only warns.
- **The config is checked strictly.** An unknown key, a malformed line, a comment after a value or an invalid `EXCLUDE`
  entry stops the run (exit code 2) instead of being skipped. Put comments on their own line. A config that exists but
  cannot be read (permissions, not UTF-8) also stops the run.
- **Unknown CrowdSec scenarios are no longer reported** (before: as "hacking"). Only `crowdsecurity` scenarios from
  `CATEGORY_MAP` or named after a CVE are reported; a scenario of another author needs an entry under its full name.
- **SSH logins from IPv6 trust the whole /64 network** (`SSH_TRUST_IPV6_PREFIX`, default 64; set 128 for the exact address,
  for example on a hosting provider that shares one /64 between customers). IPv4 is always exact.
- Run `./abuseipdb_send.sh --dry-run` after updating and read the CSV.

### Added

- Config keys: `NTFY_URL`, `OWN_NAME_MARKERS`, `EXCLUDE` (repeatable), `HTTP_PORTS` (default `80/443`),
  `EXTRA_EXCLUDE_SCENARIOS`, `SSH_TRUST_IPV6_PREFIX`; `--config` and `ABUSEIPDB_CONFIG`; `--version`.
- Wrapper: `ALERT_LIMIT` (crontab variable) raises the number of alerts read; new ntfy alerts "data cut off" and
  "safeguard not working".
- SSH auto-trust recognises `keyboard-interactive/<device>`, `hostbased` and `gssapi-*` logins and reads the journal of
  both `ssh` and `sshd`.

### Changed

- Alerts to ntfy are sent over IPv4 (`curl -4`) and no longer contain the install path or the home directory.
- The fetch from `cscli` reaches one hour before the window, so an alert that starts before the boundary but is created
  inside it is not lost.
- `ReportDate` and all times are converted to UTC; addresses are written in one canonical spelling (compressed IPv6,
  IPv4-mapped addresses as plain IPv4).
- A sample request that contains an own name, the reported IP, one of the server's own addresses or an e-mail address is
  left out of the comment (also when written percent-encoded) instead of blocking the whole file.

### Fixed

- A crash of the generator no longer looks like "no qualifying reports": any unexpected error ends with exit code 2, and the
  wrapper trusts exit code 1 only together with its message. Before, such a crash could silently close the time window.
- Python 3.9 and 3.10 parse journal and CrowdSec timestamps correctly (a UTC offset without a colon, long fractions of a
  second).
- A path with a comma or semicolon no longer breaks the upload (the `curl -F` path is quoted).
- `--limit 0` no longer produces a false "data cut off" alert.

### Security

- Values of query parameters that look like credentials (`token`, `key`, `password`, `session`, `jwt` and similar) are
  replaced by `***` in sample requests (best effort, not a guarantee).
- A double quote in a sample is written as `%22` and a comment never ends with a backslash (the AbuseIPDB CSV parser
  treats a backslash as an escape character).
- The own-name, reported-IP and e-mail checks also test percent-decoded text.
- A scenario named after a CVE is trusted only for the author `crowdsecurity`.

## 3.5 and earlier - 2026-09-28 and before

Disjoint time windows with a watermark, a 20 h guard, `Accept: application/json`, HTTP and JSON reply checks, the API key
through stdin, retries only for transient errors, ntfy alerts, a unique-event counter, strict SSH login matching,
a persistent SSH trust store, `--validate` mode, `http-open-proxy` reported as category 14 (9 would claim that the
reported host is an open proxy).
