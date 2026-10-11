**English** | [Polski](docs/pl/CHANGELOG.md)

# Changelog

Notable changes for people who run the tool. Every entry is mirrored in [docs/pl/CHANGELOG.md](docs/pl/CHANGELOG.md). Format:
[Keep a Changelog](https://keepachangelog.com/), with two sections of its own: "Upgrade notes" in the version entries and
"Development" at the end of the file. The detailed history of every commit is in `git log`.

The project has one version `X.Y.Z`, shared by both scripts (`--version` shows it). It rises only when the **program**
changes: `Z` for a fix, `Y` for a new function or config key. The full rules are in
[DEVELOPMENT.md](docs/DEVELOPMENT.md#versioning). Not every version is a release: the versions the maintainer marks with
a git tag appear as [GitHub Releases](https://github.com/arcymonek/reportabuseipdb/releases), and each Release lists every
entry that is newer than the previous Release.

## Unreleased

- Nothing yet.

## 3.6.34 - 2026-10-04

### Changed

- The deprecated separate files `abuseipdb_api_key`, `ntfy_topic` and `abuseipdb_exclude.txt` are no longer read, and
  the `--exclude-file` option of `abuseipdb_report.py` is gone. All local settings come only from
  `~/.secrets/abuseipdb.conf` (key `ABUSEIPDB_API_KEY`, `NTFY_TOPIC` and `EXCLUDE` entries). The generated CSV is unchanged.

### Upgrade notes

- If you still use one of the old files, move its content into `~/.secrets/abuseipdb.conf` **before** updating:
  otherwise the API key or the ntfy topic is missing, and addresses from the old exclusion file would be reportable.

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
  `abuseipdb.conf.example`). In 3.6.32 the old files `abuseipdb_api_key`, `ntfy_topic` and `abuseipdb_exclude.txt` still
  work as a deprecated fallback (the config wins), but since 3.6.34 they are no longer read: move their content into the
  config and delete them.
- **`OWN_NAME_MARKERS` is required for a live run.** A live upload is refused while the list is empty or still holds the
  example values. A dry run only warns.
- **The config is checked strictly.** An unknown key, a malformed line, a comment after a value or an invalid `EXCLUDE`
  entry stops the run (exit code 2) instead of being skipped. Put comments on their own line. A config that exists but
  cannot be read (permissions, not UTF-8) also stops the run.
- **Unknown CrowdSec scenarios are no longer reported** (before: as "hacking"). Only `crowdsecurity` scenarios from
  `CATEGORY_MAP` or named after a CVE are reported; a scenario of another author needs an entry under its full name.
- **SSH logins from IPv6 trust the whole /64 network** (`SSH_TRUST_IPV6_PREFIX`, default 64, allowed 64-128, any other
  value stops the run; set 128 for the exact address, for example on a hosting provider that shares one /64 between
  customers). IPv4 is always exact.
- Run `./abuseipdb_send.sh --dry-run` after updating and read the CSV.

### Added

- Config keys: `ABUSEIPDB_API_KEY`, `NTFY_TOPIC`, `NTFY_URL`, `OWN_NAME_MARKERS`, `EXCLUDE` (repeatable), `HTTP_PORTS`
  (default `80/443`), `EXTRA_EXCLUDE_SCENARIOS`, `SSH_TRUST_IPV6_PREFIX`; `--config` and `ABUSEIPDB_CONFIG`; `--version`.
- Wrapper: `ALERT_LIMIT` (crontab variable, a number from 1 to 9999999, default 5000) raises the number of alerts read;
  new ntfy alerts "data cut off" and "safeguard not working".
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

## 3.5 and earlier

Versions from before the project got its own repository (2026-09-28). Main features:

- Disjoint time windows with a watermark and a 20 h guard.
- `Accept: application/json`, HTTP and JSON reply checks, the API key through stdin, retries only for transient errors.
- ntfy alerts and a unique-event counter.
- Strict SSH login matching and a persistent SSH trust store.
- `--validate` mode.
- `http-open-proxy` reported as category 14 (9 would claim that the reported host is an open proxy).

## Development

Hooks, tests, CI, GitHub files and documentation. Not versioned: these changes do not affect what runs on your server.

- 2026-10-12 - Documentation: `docs/OPERATIONS.md` is reorganised along the life of an installation (a new "Reading a
  dry run", troubleshooting split into six small tables, rolling back next to updating) and corrected against the code:
  what `--dry-run` does and does not check, how a quiet day looks in the log, the side effect of `--force` on the
  next scheduled run, why the monitor threshold is 36 h, alert priorities, the `sudo -n cscli alerts list --limit 1`
  test, what the lock really is, how to roll back, and all configuration keys that stop the generator. It adds the
  missing messages (no ntfy topic, no system journal, upload failures) and the steps after a reported own address.
  No safeguard changed.
- 2026-10-11 - Documentation: `docs/DEVELOPMENT.md` is reorganised (the part for everyone first, the maintainer's workflow
  after it; new sections "Setting up", "Hooks" and "Standing checks") and corrected against the code: what each hook
  really checks (`commit-msg` scans only the key pattern and `OWN_NAME_MARKERS`), the `shellcheck` step in CI, both
  workflows that pin `actions/checkout`, `--force-with-lease` after a rebase of a work branch, deployment after every
  push, and that a published tag and Release cannot be taken back. `docs/ARCHITECTURE.md` describes `commit-msg` the
  same way. No safeguard changed.
- 2026-10-11 - Documentation: `CONTRIBUTING.md` is reorganised (a "where to go" table, setup and tests before the steps for
  sending a change) and corrected: proposals and questions go to Discussions, bugs and unknown scenarios to Issues; it
  now states the Python 3.9 and standard-library-only rule, the second hook (`commit-msg`), why tests need public
  resolvers, and that a rebased branch is pushed with `--force-with-lease`. The pull request template and `AGENTS.md`
  follow. No safeguard changed.
- 2026-10-11 - Documentation: `docs/ARCHITECTURE.md` is rewritten to match the code (a window with no reports, the
  `[TRUNCATED]` and `[SAFEGUARD-OFF]` alerts, a corrupted watermark, the configuration checks) and its error table now
  shows what happens to the watermark in each situation. It links to COMPLIANCE.md and OPERATIONS.md instead of
  repeating them. No safeguard changed.
- 2026-10-11 - Documentation: the README is shorter and clearer (numbered quick start, one-line safeguards, a
  contributor invitation), the project is described as complete, and the explanation of the pre-live checks moved to
  [docs/OPERATIONS.md](docs/OPERATIONS.md#before-the-first-live-run). No safeguard changed.
- 2026-10-08 - New maintainer script `tools/deploy-check.sh`: after a push or a deployment it fetches `origin` and
  `github` and reports whether the local `main` and both remotes stand on the same commit (not pushed yet, ahead,
  diverged, wrong push order). Read-only, offline mode with `--no-fetch`, never prints a remote address. It has tests, and
  CI now checks its syntax and runs `shellcheck` on it.
- 2026-10-08 - The pre-commit hook runs the generator tests (about 15 s) when a commit touches `abuseipdb_report.py` or its
  test file. It tests a copy of the index, not the working tree, and skips the tests after an earlier failure;
  `NO_TESTS=1` skips only them (for maintainer work-in-progress commits). The hook behaviour has tests.
- 2026-10-08 - The tests workflow has a 10-minute job timeout (the default is 6 hours) and `actions/checkout` no longer
  leaves the GitHub token in `.git/config` (`persist-credentials: false`).
- 2026-10-02 - Versioning simplified: one version for both scripts (the wrapper adopts the generator's version, so
  `abuseipdb_send.sh --version` now shows the project version instead of 1.1.7), `Z` has no upper limit (no rollover at 99),
  documents no longer carry a "Version:" line, and the pre-commit hook accepts a `Y` or `X` step, which it used to refuse.
- 2026-10-02 - Tags and GitHub Releases: a version tag `vX.Y.Z` pushed to GitHub starts `.github/workflows/release.yml`,
  which checks the tag against the code and the changelog and creates a Release (`tools/release_notes.sh` builds the notes).
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
