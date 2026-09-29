**English** | [Polski](CHANGELOG.pl.md)

Version: 3.6.15 (`abuseipdb_report.py`)

# Changelog

All notable changes to this project. Every entry is mirrored in [CHANGELOG.pl.md](CHANGELOG.pl.md).

Version numbering is `X.Y.Z`. The project version is the version of `abuseipdb_report.py`. Every change that is
committed and pushed raises `Z` by 1; after `Z` reaches 99 the next version raises `Y` by 1 and resets `Z` to 0
(3.6.99 is followed by 3.7.0). `abuseipdb_send.sh` has its own version and follows the same rule whenever it changes.

## Unreleased

- Nothing yet.

## 2026-09-29 - author contact and README order (3.6.15)

- The contact address in the README, `SECURITY.md` and the pre-commit allow-list is now a dedicated GitHub address.
- README: a short "early stage" warning under the title; the "Status" section (now with a note that the project was
  written with Claude Code and that `--dry-run` and reading the CSV come first) moved before "Requirements";
  "License" and "Author" merged into one section.
- Commit author e-mail switched to the GitHub no-reply address.

## 2026-09-29 - ready for other users and contributors (3.6.14)

- README: a new "Is this tool for you?" section (the real client IP behind a CDN or proxy, the public address behind
  NAT, systemd journal, own false alarms, other web ports) and a complete install: `jq`, a passwordless sudo rule that
  allows only `cscli alerts list`, journal access for the SSH auto-trust, a password-less check.
- New `CONTRIBUTING.md` / `CONTRIBUTING.pl.md` and `SECURITY.md` / `SECURITY.pl.md` (private vulnerability reports),
  a bug report template that asks to anonymise logs, and a GitHub Actions workflow that runs the whole suite (wrapper
  tests included) on Ubuntu with Python 3.9 and the newest Python, plus `shellcheck`.
- `tools/pre-commit`: a commit that leaves the version alone passes (contributors do not bump it; the maintainer does
  when merging); a commit that changes it must still raise it by exactly one step. The new documents are paired EN/PL.
- `docs/COMPLIANCE.md`: the policy rule "TCP only after a completed three-way handshake, UDP never" and the daily
  bulk limits from the API documentation (Standard 5, Basic 100, Premium 500; the Webmaster and Supporter badges raise
  the free limit, 20 seen on the author's account). Re-verified against the raw AbuseIPDB pages on 2026-09-29.
- `docs/DEVELOPMENT.md`: contributor rules, CI, a fourth known equivalent mutant, and the release checklist no longer
  claims a single-commit history.
- No functional change in the generator or the wrapper (only the version number); CSV unchanged.

## 2026-09-29 - journal problems are reported, more SSH login methods, ALERT_LIMIT (3.6.13)

- `abuseipdb_report.py` 3.6.13: the exit code and stderr of `journalctl` are checked. Measured on journalctl 252:
  code 1 with an empty stderr only means "no matching entries", while missing journal rights (or a build without
  `--grep`) always print a message. Before, such a failure was silent whenever the remembered trust list was not
  empty, so new logins of the operator stopped being trusted. Now it is a loud `[warn]` with the fix.
- SSH auto-trust also recognises `keyboard-interactive/<device>` other than `pam` (e.g. `bsdauth`), `hostbased` and
  `gssapi-*` logins. `Accepted none` is deliberately not trusted.
- `abuseipdb_send.sh` 1.1.6: `ALERT_LIMIT` (set in the crontab line) is passed to the generator as `--limit`. The
  "data cut off" alert told the operator to raise `--limit`, which the wrapper had no way to do. An invalid value
  fails the run before anything is generated.
- CSV unchanged (checked byte for byte on 497 real alerts of the last 30 days).
- New tests for the journal outcomes, the login methods and `ALERT_LIMIT`.

## 2026-09-29 - HTTP ports and extra excluded scenarios in the config (3.6.12)

- `abuseipdb_report.py` 3.6.12: new optional config key `HTTP_PORTS` (default `80/443`). The ports in "Target:
  HTTP/HTTPS (ports 80/443)." were a constant that is true only on the author's server; on another server the public
  report would state a wrong port. A single port reads "port 443"; only digits and `/` are accepted, and an invalid
  value stops the run like any other config error.
- New optional config key `EXTRA_EXCLUDE_SCENARIOS`: scenarios the operator never wants reported (for example one that
  raised false alarms on their own traffic) without editing the code. A short name matches every author, a full
  `author/name` only that author. It only adds to the built-in `EXCLUDE_SCENARIOS`.
- CSV unchanged with the defaults (checked byte for byte on 497 real alerts of the last 30 days).
- New tests for both keys (parsing, validation, the comment, short and full names, end to end).

## 2026-09-29 - CVE rule only for the trusted author, safe quotes and backslashes, no e-mails (3.6.11)

- `abuseipdb_report.py` 3.6.11: a scenario named after a CVE id gets the default 15,21 only when its author is
  `crowdsecurity`. Before, `someone/postfix-cve-2024-1234` would have been published as a web application attack.
  Another author's CVE scenario needs an explicit full-name entry in `CATEGORY_MAP`, like any other foreign scenario.
- A double quote in a sample request is written as `%22`, and a comment never ends with a backslash. The bulk-report
  page says that backslashes and quotes require escaping (the AbuseIPDB parser treats a backslash as an escape
  character), and Python's `csv` module leaves backslashes alone. The validator now rejects a backslash before a quote
  or at the end of a comment. Other backslashes stay: they are evidence (`\x5Cthink\x5Capp`). Defensive: nginx
  already logs a quote as `\x22`, and AbuseIPDB has accepted every row so far; how it parses these cases cannot be
  checked without a real upload.
- A sample request that looks like it contains an e-mail address is omitted from the comment (AbuseIPDB FAQ: no
  personal information in comments), in the same way as a sample with an own name. The validator still only warns.
- CSV unchanged (checked byte for byte on 497 real alerts of the last 30 days, 7 rows with backslashes).
- New tests for the author rule, the quote, the trailing backslash, the validator and the e-mail omission.

## 2026-09-29 - the config file fails closed (3.6.10)

- `abuseipdb_report.py` 3.6.10: a malformed line, an unknown key (a typo such as `EXLUDE=`), a comment after a value
  (`EXCLUDE=203.0.113.7 # home`), an `OWN_NAME_MARKERS` entry with a space or `#` inside, or an invalid `EXCLUDE` or
  legacy exclusion entry now stop every mode of the generator with exit code 2. Before, they were skipped with a
  warning: the address the operator wanted protected became reportable, and a marker with a comment attached never
  matched while the wrapper still counted the list as set. Found in the pre-publication audit; the production config
  was not affected.
- `abuseipdb_send.sh` 1.1.5: a clear error for the example API key of the template, and alerts are not sent to an
  `NTFY_TOPIC` outside `[A-Za-z0-9_-]{1,64}` or an `NTFY_URL` with spaces or quotes (a `"` would break the curl config
  the URL goes through).
- CSV unchanged (checked byte for byte on 497 real alerts of the last 30 days).
- New tests for every rejected shape, for `--validate` and generation stopping with exit code 2, and for the wrapper
  checks.

## 2026-09-28 - credential-like query values are masked in sample requests (3.6.9)

- `abuseipdb_report.py` 3.6.9: in the "Sample requests" part of a comment, the VALUE of a query parameter whose name
  looks like a credential (`token`, `key`, `api_key`, `secret`, `password`, `session`, `PHPSESSID`, `auth`, `sig`, `jwt`,
  `code`, `csrf` and similar) is replaced by `***`. Before, the whole path went to the public database, so a false
  alarm on a real user's request could have published a token from that user's URL (found in a review by feeding the
  generator `?token=...`; not seen in real data). A short name is matched as a whole word, so `keyword=<script>`
  keeps its payload. Best effort, not a guarantee: a secret in the path itself or under an unusual name is not recognised.
- Checked on 502 real alerts from the last 30 days: all 182 rows byte-identical, nothing was masked (the samples of that
  period contain no credential-like parameter), so today this is a precaution, not a fix of an observed leak.
- The CSV is unchanged for requests without such a parameter (checked byte for byte).
- New tests: masking of many name shapes, names that only contain a keyword (`keyword`, `monkey`, `author`, `passenger`,
  `encode`), untouched paths, the end-to-end comment (secret gone, payload kept) and a non-text path.

## 2026-09-28 - unknown scenarios are no longer reported as "hacking" (3.6.8)

- `abuseipdb_report.py` 3.6.8: `category_for()` returns nothing for a scenario it does not know, and such an alert is
  skipped and listed on stderr (`unknown scenario X - not reported`). Before, every scenario outside `CATEGORY_MAP`
  went to the public database as "hacking + web application attack" (15,21), for example a postfix, MySQL or custom
  scenario, which is a stronger claim than the log supports. Reported now: scenarios of the author `crowdsecurity`
  that are in the map, scenarios named after a real CVE id (still 15,21), and scenarios that the operator adds to
  `CATEGORY_MAP` under their full name (`author/name`). The same short name from another author (`someone/ssh-bf`) used
  to be treated like the trusted one and no longer is. New safeguard 7 in the docstring and in COMPLIANCE.
- Checked on 502 real alerts from the last 30 days (cscli v1.8.1): 182 rows before and after, 181 byte-identical,
  none dropped. The one changed row lists one scenario less (`LePresidente/http-generic-401-bf`, a third-party brute
  force scenario that had been reported as 15,21); its categories did not change, because another scenario of the same
  address gives 15,21 too. The same run showed that this `cscli` version has the `kind` field and prints times with
  a precision of one second.
- The CSV is unchanged for input that contains only known scenarios (checked byte for byte).
- New tests: `category_for` (trusted author, foreign author, no author, manual ban, CVE names, explicit full-name entry),
  the skipped alert with its hint, one address with a known and an unknown scenario, a `null`/missing scenario, and
  that every mapped scenario keeps its category. Two protocol tests used invented scenario names and now use mapped ones.

## 2026-09-28 - fewer silent assumptions about the host (3.6.7)

- `abuseipdb_report.py` 3.6.7: SSH auto-trust now reads the journal of both `ssh` and `sshd` (`sshd` is the unit name
  on RHEL, Fedora, Arch and SUSE; before, the main defence against reporting your own address was silently empty
  there and only a warning was logged). When run as root, `cscli` is called directly, without `sudo`.
- Every message about data that was CUT OFF (alerts at the `--limit`, more than 9,999 rows, the 8 MB limit) now starts
  with `[TRUNCATED]`. The watermark still moves after such a run, so the cut-off alerts would have been lost with only a
  line in the log. `abuseipdb_send.sh` 1.1.4 greps for the marker and sends the ntfy alert `abuseipdb: data cut off`
  (also when there is nothing to send). The marker is an interface between the two scripts.
- If EVERY alert in a run is dropped because its `kind` is not `crowdsec`, the generator prints a loud warning: on a
  `cscli` version without the `kind` field the tool would otherwise report nothing forever and say only
  "No qualifying reports".
- `abuseipdb_send.sh` 1.1.4: the CSV path is quoted in `curl -F` (unquoted, a `,` or `;` in the install path made curl
  fail with `Failed to open/read local data`; measured with curl 8.7.1).
- The comment on the SSH login pattern now says exactly what is and is not trusted (`Partial publickey` is ignored, only a
  complete login counts). The code is unchanged.
- The CSV is unchanged. New tests: both unit names, root versus sudo, the `[TRUNCATED]` marker (alert `--limit`,
  row limit, only at the start of a line), the `kind` warning, and in the wrapper the ntfy alert (also with no rows and in a
  dry run) and the quoted `-F` path. The wrapper tests need Linux: the whole suite (162 tests, none skipped) ran on
  Debian 12 with Python 3.11.

## 2026-09-28 - timestamps parse the same on Python 3.9 to 3.14 (3.6.6)

- `abuseipdb_report.py` 3.6.6: a shared `parse_iso_datetime()` (used for CrowdSec timestamps, journalctl SSH logins and
  the trusted-IP file) rewrites the text so that Python 3.9 and 3.10 accept it: a UTC offset without a colon
  (`+0200`, exactly what journalctl prints) and a fraction of seconds with any number of digits (CrowdSec may print 9).
  Before, on Python < 3.11 the SSH login time silently became "now", so a trusted address expired later than the
  documented 60 days (found in a review; the direction is safe, but the promise was wrong), and an alert with a
  9-digit fraction in `created_at` would have been dropped as unreadable. On 3.11+ nothing changes.
- `parse_ts()` returns `None` (the alert is skipped and counted) for a value that is not text instead of crashing.
- The CSV validator still uses the strict `fromisoformat()` on purpose: it checks the format we write ourselves.
- The CSV is unchanged (checked byte for byte on the same alert file before and after, on 3.14).
- README: Python 3.9 or newer (tested on 3.9 and 3.14). The whole suite is green on both; before, two SSH trust tests
  failed on 3.9. Python 3.10 and 3.12/3.13 were not run.
- New tests: the text rewrite (offset, `Z`, 1 to 9 digit fractions, valid text untouched, garbage still rejected) and
  `parse_ts` with odd values.

## 2026-09-28 - a generator crash no longer looks like "no reports" (3.6.5)

- `abuseipdb_report.py` 3.6.5: any unexpected exception now ends the run with exit code 2 (and a traceback on stderr).
  Before, Python's default exit code 1 was read by `abuseipdb_send.sh` as "no qualifying reports", so a crash moved the
  watermark and silently dropped the whole time window without an alert. Found in a review by feeding the generator
  `null` and an alert with `"scope": null`. Exit code 2 makes the wrapper keep the watermark, send the ntfy alert and
  retry the same window on the next run.
- `cscli` output or `--input-json` holding `null` is now an empty list ("nothing to report", exit code 1, no
  traceback); any other non-list JSON, an unreadable file or invalid JSON is a clean error (exit code 2).
  `extract_ip` tolerates `null` in `source.scope` and `value`.
- The CSV is unchanged (checked byte for byte on the same alert file before and after).
- New tests: a crash gives exit code 2, `null` input, non-list input, invalid or unreadable input file, `null` scope
  and `null` value. The wrapper side (exit code 2 keeps the watermark and alerts) was already covered by
  `test_generator_error_alerts_and_keeps_watermark`; the missing link was the real generator's exit code.

## 2026-09-28 - hostile paths no longer block the file, example values refused (3.6.4)

- `abuseipdb_report.py` 3.6.4: a sample request whose path contains an own-name marker, the reported IP or one of the
  server's own public addresses is omitted from the comment; the report and its other samples are kept. Before, the
  validator rejected the whole file because of one such path (found on real data: a scanner that pastes the target
  host name into the path, 5 of 180 rows in 60 days), which meant no reports that day and lost data after a 48 h gap.
  The validator is unchanged and stays the last line of defence. The omitted samples are counted on stderr
  (`omitted N sample requests ...`), never printed. The CSV is unchanged for input without such paths.
- `abuseipdb_send.sh` 1.1.3: a live run is refused while `OWN_NAME_MARKERS` still holds the example values
  (`your-domain.example`, `your-host.example`); a dry run only warns. Alerts are never sent to the example topic
  `your-private-ntfy-topic` (logged as an error instead). `abuseipdb.conf.example` now uses these example values and says so.
- New tests: omitted samples (own name, IPv4/IPv6 of the reported host, own server address), an end-to-end run with
  hostile paths and a fake `ip` command (this also covers the exclusion of the server's own address from the reports),
  and the refusal of example values and topic in the wrapper.

## 2026-09-28 - ntfy over IPv4 (3.6.3)

- `abuseipdb_send.sh` 1.1.2: alerts are sent to ntfy with `curl -4`. `ntfy.sh` counts its daily message quota per
  address; over IPv6 the quota of a shared range can already be used up by other senders (HTTP 429, code 42908) while
  IPv4 still works, which silently swallowed alerts. On an IPv6-only host remove `-4`.
- `abuseipdb_report.py` 3.6.3: version bump only, the generated CSV is unchanged.

## 2026-09-28 - single config file, public release preparation (3.6.2)

- `abuseipdb_report.py` 3.6.2 and `abuseipdb_send.sh` 1.1.1: all local configuration moves into one file,
  `~/.secrets/abuseipdb.conf` (`ABUSEIPDB_API_KEY`, `NTFY_TOPIC`, `NTFY_URL`, `OWN_NAME_MARKERS`, `EXCLUDE`), documented
  line by line in `abuseipdb.conf.example`. The file is parsed as text, never executed; new `--config` and
  `ABUSEIPDB_CONFIG`.
- The own-name markers are no longer hard-coded. They fail closed: an empty list makes the generator warn and a live
  wrapper run is refused with an ntfy alert.
- The separate files `abuseipdb_api_key`, `ntfy_topic` and `abuseipdb_exclude.txt` still work as a deprecated fallback;
  the config wins and exclusions from both sources are combined. The wrapper logs a warning when it reads the old key
  file. Migrate and delete them.
- The generated CSV is unchanged for the same input.
- Personal and host-specific details removed from the code, tests and documentation (example paths, login names, own
  domains, references to the administration scripts). Tests use `example.org` and reserved address ranges.
- `tools/pre-commit` gained a privacy scan of added lines (own-name markers from the local config, real keys, a staged
  config file). New tests for the config parser, precedence and the fail-closed rule.
- The project is released under the MIT license (`LICENSE`); the README has License and Author sections.
- The public repository history starts from a single clean commit.

## 2026-09-28 - version rule (3.6.1)

- New numbering rule (see above): `Z` grows by 1 with every committed and pushed change.
- The current version of `abuseipdb_report.py` is shown at the top of the README, of every document and of both changelogs.
- The pre-commit hook and a unit test check that the version in the documents matches `SCRIPT_VERSION`, and that a commit
  raises the version by exactly one step.

## 2026-09-28 - project split, English-only code (3.6.0)

- `abuseipdb_report.py` 3.6.0: docstring, comments, messages and `--help` translated to English; new `--version`.
  The generated CSV is byte-for-byte identical to 3.5 for the same input.
- `abuseipdb_send.sh` 1.1.0: comments, log lines and ntfy alerts translated to English. Logic unchanged.
- The project moved into its own repository and directory.
- Tests moved into the repository; the test of the external monitoring script stays outside it.
- Added the pre-commit hook (`tools/pre-commit`) and bilingual (EN/PL) documentation.

## 2026-09-28 - earlier history (before the project had its own repository)

- `abuseipdb_report.py` 3.5 and `abuseipdb_send.sh` 1.0: disjoint time windows (`--after`,
  `--before`), watermark of the last successful report, 20 h guard, `Accept: application/json`, HTTP code and JSON
  reply checks, API key through stdin, retries only for transient errors, ntfy alerts.
- `abuseipdb_report.py` 3.4: unique-event counter instead of a sum across scenarios, attack window
  from `start_at`/`stop_at`, `http-open-proxy` moved from category 9 to 14, strict SSH login regex, protocol from the
  events' `service` field, non-global address filter (CGNAT), own public addresses excluded, persistent SSH trust
  store, `--validate` mode and automatic output validation.
- `abuseipdb_report.py` 3.3 and earlier: first working generator driven by a
  one-line cron command.
