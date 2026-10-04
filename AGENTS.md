# AGENTS.md

Instructions for AI coding agents (and a short read for humans) working on this repository. It is written in English
only, on purpose: it is read by tools, not chosen by language. Human-facing documentation exists in English and
Polish; see `CONTRIBUTING.md`.

## What this project is

`reportabuseipdb` reports attackers detected by the operator's own CrowdSec instance to AbuseIPDB.

- `abuseipdb_report.py`: generator and validator of the bulk-report CSV (Python, standard library only, Python 3.9 or
  newer). It sends nothing itself.
- `abuseipdb_send.sh`: cron wrapper (bash). Picks the time window, runs the generator, validates, uploads, alerts.
- `tests/`: unittest suites. `tools/pre-commit`: repository hook. `docs/`, `docs/pl/`: documentation.

Read `docs/ARCHITECTURE.md`, `docs/COMPLIANCE.md` and `docs/DEVELOPMENT.md` before a non-trivial change.

## The one priority

This tool publishes data under its users' AbuseIPDB accounts. A false report can get an account suspended, and a leaked
host name or address exposes the operator. Every change is judged first by one question: can it make the tool report
something that is not a real, locally observed attack, or reveal something about the operator? Convenience, coverage
and elegance come second.

## Hard safeguards: never weaken without an explicit decision by the maintainer

If a task seems to require touching one of these, stop and ask instead of working around it:

- the 60-day age filter, the filter for non-global addresses, `EXCLUDE_SCENARIOS`, `WEAK_ONLY_SCENARIOS`, SSH
  auto-trust (IPv6 logins trusted as a /64, never wider) and the `EXCLUDE` list of the config file, and the exclusion of the operator's own public addresses;
- the data source (`cscli alerts`, never `decisions`) and the `kind == "crowdsec"` filter;
- the comment rules: fixed English constants only, ASCII, no IP address, host name or domain, at most 1024 bytes;
- the double validation of the CSV, and the rule that a bad file never replaces the previous one;
- the watermark semantics (end of the window, advanced only after a successful upload), the 20 h guard,
  `Accept: application/json`, the API key passed only through stdin, and retries only for transient errors.

After you change a safeguard or code next to one, run a mutation check: break the safeguard on purpose and confirm that
a test fails (see `docs/DEVELOPMENT.md`). A refactor or a translation must keep the generated CSV byte-for-byte
identical for the same `--input-json`.

## Never do

- Never perform a real upload to AbuseIPDB, not even "as a test": it publishes data and spends the daily quota. Use the
  mocks in the tests and `--dry-run`.
- Never print, log, commit or paste the API key, the ntfy topic or the real config file. Tests use fake keys and topics.
- Never put a real host name, domain, own IP address, home directory path or ntfy topic into code, tests, docs, issues,
  pull requests or commit messages. Tests use reserved data only: `203.0.113.0/24`, `198.51.100.0/24`, `2001:db8::/32`,
  `example.org`, `.example`, `.test`.
- Never bypass the pre-commit hook (`--no-verify`) or edit the report templates (`TPL_*`) casually: they are published.

## Commands

```bash
python3 -m unittest discover -v tests     # generator tests run anywhere; wrapper tests need Linux (flock, GNU date, jq)
git config core.hooksPath tools           # enable the pre-commit hook once per clone
```

Run the suite on Python 3.9 as well as on the newest version when you can: timestamp parsing differs before 3.11. The
GitHub Actions workflow does this for every pull request.

## Conventions

- Code, comments, log and error messages, `--help`, alerts, tests, commit messages, issues and pull requests: English
  only. Comments explain why, not only what. Keep code simple and readable; avoid clever tricks.
- Documentation exists in English and Polish (`README.md` and `README.pl.md`, `CHANGELOG.md` and
  `docs/pl/CHANGELOG.md`, `docs/X.md` and `docs/pl/X.md`). English is the source. As a contributor you write and update **English only**; the
  maintainer adds the Polish translation. Do not create or edit Polish files yourself. This file (`AGENTS.md`) has no
  Polish twin.
- Do not raise the version. Describe your change under "Unreleased" in `CHANGELOG.md`; the maintainer decides
  whether the version rises (it does when the program changes) and translates when merging.
- One topic per pull request. Explain in plain language what changed and why: the reviewer may not read every line, so
  the description and the tests must carry the argument. State what you did not verify.
- Work on a branch (`git switch -c fix-short-description`) and never commit directly to `main`; do not merge. Outside
  contributors submit through a fork and a pull request (see `CONTRIBUTING.md`).
- Do not run `git push` or open pull requests on your own initiative; propose the change and let the person you work
  for decide.

## Non-obvious facts (verified against real data and AbuseIPDB documentation)

- SSH events from journald carry local time labelled as UTC in `events[].timestamp` (a shift of a few hours). Take
  times from the alert's `start_at`, `stop_at` and `created_at`. HTTP events are correct.
- One request can feed several scenarios; summing `events_count` overstates the count by about 20 %.
- AbuseIPDB bulk limits: 10,000 lines, 8 MB, 1024 bytes per comment. `ReportDate` is the last observation. The same
  comment and categories within 24 hours are merged, and the same IP is accepted once per 15 minutes. Errors returned
  without `Accept: application/json` arrive as HTML.
- Category 9 means the reported host IS an open proxy (which is why `http-open-proxy` maps to 14); 14 means "open ports
  and vulnerable services".
- A "200" answer to `/.env` and similar paths is usually a single-page-app fallback (HTML), not a leak.
- `cscli` needs `sudo -n` when the service user is not root; a sudoers rule survives package updates, an ACL does not.
- Tests must never contain real secrets; keys and topics in tests are artificial.

## Where to look

| Need | File |
|---|---|
| how a run works, state files, exit codes | `docs/ARCHITECTURE.md` |
| AbuseIPDB policy mapped to the code | `docs/COMPLIANCE.md` |
| cron, alerts, troubleshooting | `docs/OPERATIONS.md` |
| workflow, tests, versioning, language rules | `docs/DEVELOPMENT.md` |
| contributor rules for humans | `CONTRIBUTING.md` |
| reporting a vulnerability | `SECURITY.md` |
