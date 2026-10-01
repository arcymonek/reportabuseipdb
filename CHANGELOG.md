**English** | [Polski](CHANGELOG.pl.md)

Version: 3.6.28 (`abuseipdb_report.py`)

# Changelog

All notable changes to this project. Every entry is mirrored in [CHANGELOG.pl.md](CHANGELOG.pl.md).

Version numbering is `X.Y.Z`. The project version is the version of `abuseipdb_report.py`. Every change that
reaches `main` (a direct push or a merged branch) raises `Z` by 1; after `Z` reaches 99 the next version raises `Y` by 1 and resets `Z` to 0
(3.6.99 is followed by 3.7.0). `abuseipdb_send.sh` has its own version and follows the same rule whenever it changes.

## Unreleased

- Nothing yet.

## 2026-10-01 - SSH auto-trust covers the whole IPv6 /64 (3.6.28)

Found while preparing the repository for publication: a user who logs in over IPv6 has "temporary" addresses that
change inside one /64 network, and the exact-address trust could not follow them, so the tool could report its
operator's own machine. IPv4 is unchanged. The generated CSV is byte for byte identical to 3.6.27 for data without an
IPv6 login (checked on synthetic alerts with IPv4 and IPv6 addresses).

- **IPv6 logins are trusted as a network.** An address with a successful SSH login now excludes its whole /64 (before:
  only the exact address). The new config key `SSH_TRUST_IPV6_PREFIX` (default `64`) sets the length: the allowed range
  is 64 to 128, anything else stops the run (exit code 2). `128` restores the exact-address behaviour, for a hosting
  provider that shares one /64 between customers. A network wider than /64 is deliberately impossible: it would trust
  other people's networks. IPv4 is always trusted exactly.
- **Trade-off:** other devices in the same /64 (family, guests) are not reported either, even if they attack. This is
  under-reporting, never a false report, which is the safe direction for this tool.
- **The remembered list is unchanged.** `ssh_trusted_seen.txt` still holds single addresses; the widening happens
  when the list is read, so a changed `SSH_TRUST_IPV6_PREFIX` applies at once and nothing has to be migrated. The
  server's own addresses stay exact. The startup line now says how many addresses became how many networks.
- **IPv4-mapped logins fixed:** a login logged as `::ffff:8.8.8.8` is now stored as the plain IPv4 `8.8.8.8`. Before, it
  was kept as an IPv6 address that never matched the (already unmapped) alert address, so it protected nothing, and
  under a /64 rule it would have become `::/64`.
- **Documentation:** `docs/COMPLIANCE.md` now states that the AbuseIPDB bulk format accepts IPv4 and IPv6 addresses
  (source: the bulk-report form, checked 2026-10-01). The documentation says nothing about /64 handling on their side.
- **Not verified:** no real IPv6 login exists in the author's data (31 logins in 60 days, all IPv4), so the behaviour was
  tested only on synthetic journal lines and by mutation (each safeguard broken on purpose turned a test red), not on a
  real IPv6 connection, and no IPv6 report has ever been uploaded by this tool.

## 2026-10-01 - one spelling of an address and UTC for every timestamp (3.6.27)

Found by the code audit of 2026-10-01. Hygiene: nothing in the data of the live server triggered either problem (437 real
alerts: every address already canonical, every timestamp `...Z`), so the generated CSV is byte for byte identical to 3.6.26.

- **Addresses are canonicalised** before alerts are grouped and written (`canonical_ip()`): compressed IPv6, and an
  IPv4-mapped IPv6 address (`::ffff:8.8.8.8`) as the plain IPv4. Before, the same host in two spellings became two
  rows, and the validator (which compares one canonical form) did not see the duplicate.
- **Timestamps with another offset are converted, not relabelled** (`parse_ts()`): `...T07:46:35+02:00` used to print as
  `07:46:35 UTC`, two hours late (a future `ReportDate`, which the validator would then reject and stop the whole run; with a
  negative offset the date would silently have gone into the past). cscli prints `Z` today, so this only guards against a
  format change.
- Tests: the canonical form (compressed, mapped, upper case, non-address), two spellings merged into one row, exclusions
  still matching every spelling, offsets `+02:00` / `-05:00` converted and `Z` unchanged. Verified by mutation.

## 2026-10-01 - own-name, IP and e-mail checks also see percent-encoded text (3.6.26)

Found by the code audit of 2026-10-01 (a sample `www%2Eexample%2Eorg` passed a marker `example.org`).

- A request path comes from the attacker, who (or whose scanner) may encode the very characters the checks look for.
  `leaks_identity()` (which leaves out a hostile sample) and the CSV validator (which rejects the file) now also test
  the text after one and after two rounds of percent-decoding (`decoded_views()`): an own name written `www%2Eexample%2Eorg`,
  an e-mail written `jane%40mail.example.net` or the reported IP written `8%2E8%2E8%2E8` is caught like the plain form.
  Ordinary encoding (`%20`, `%2F`, `%3C`) is left alone, and a broken sequence never raises.
- This strengthens a hard safeguard (the own-name check); it can only leave out MORE samples, never add one. On 437 real
  alerts (8 days) the generated CSV is byte for byte identical to the previous version.
- Tests: encoded name, double-encoded name, encoded e-mail, encoded reported IP, ordinary encoding unchanged,
  validator rejection, broken sequences. Verified by mutation (each plain-text-only variant turns a test red).

## 2026-10-01 - privacy hooks: no blanket allowance for the author's domain, commit messages scanned (3.6.25)

Found by the code audit of 2026-10-01; confirmed by running the hook in a throw-away repository.

- **Fixed a hole in `tools/pre-commit`.** The few strings allowed in the repository (the author's contact details) were
  removed from the scan as plain substrings, so a host name UNDER the author's domain (`host.<domain>`) lost its domain,
  left `host.` behind and passed the own-name scan even though the domain is one of the operator's own markers. The
  domain is now removed only when it stands on its own (not after a character of a host name or an e-mail local part);
  `github@<domain>`, the website, the author name and the GitHub profile path stay allowed, any other mailbox or host
  at the domain is refused.
- **New `tools/commit-msg` hook.** The pre-commit scan looks only at files, but the commit message goes into the public
  history too. The new hook applies the same rules to the message (own names, a key-like string), ignores git's `#`
  comment lines and, like the other hook, scans nothing without a local config. It is enabled by the same
  `git config core.hooksPath tools`.
- **`tools/lib-privacy.sh`**: the privacy rules (reading `OWN_NAME_MARKERS`, the allowed strings) now live in one file
  that both hooks source, so they cannot drift apart.
- `tools/pre-commit` prints a note when `shellcheck` is not installed instead of skipping the check silently (CI still
  runs it).
- **First tests for the hooks** (`tests/test_hooks.py`, 15 tests, each in a throw-away repository): clean change, own
  names, the author's details allowed, hosts under the author's domain refused, real config file, key-like strings,
  no config, only added lines scanned, the message hook, and both hooks running as real git hooks. Verified by mutation:
  the old substring behaviour and each removed check turns a test red.
- CI: `bash -n` and `shellcheck` now cover the new hook files as well.

## 2026-10-01 - fail closed on a bad config, alert on a degraded safeguard, wider fetch (3.6.24)

Found by the code audit of 2026-10-01 and checked against the live server. The wrapper `abuseipdb_send.sh` is now 1.1.7.

- **Config that cannot be read now stops the run** (`abuseipdb_report.py`). Before, a config file that existed but could not
  be used (wrong permissions, bytes that are not UTF-8, for example a comment typed in a legacy code page) only produced
  a warning, and the run went on WITHOUT the own-name check and without every `EXCLUDE` entry. The wrapper did not notice,
  because it reads the markers with `sed`. Now this is a `ConfigError` (exit code 2) in every mode, like a typo in a key.
  The same for the deprecated exclusion file. A missing file is still only an info line.
- **Exit code 1 is trusted only together with its message** (`abuseipdb_send.sh`). Code 1 means "nothing to report",
  but a crash before `main()` (a syntax error, a missing module) also exits with 1, and the wrapper would have closed
  the window silently. The wrapper now requires the line `No qualifying reports` (a constant of the generator) and treats
  code 1 without it as a failure: the watermark stays and an alert is sent.
- **New ntfy alert "safeguard not working"** (`abuseipdb_send.sh`). The generator marks every line that says a
  safeguard is not working while the run goes on with `[SAFEGUARD-OFF]`: the journal cannot be read (SSH auto-trust
  incomplete), no `ip` program (the server's own addresses unknown), the trusted-IP list cannot be read or saved. Before,
  these were lines in a log that nobody reads. The run still continues with the other safeguards.
- **The fetch reaches 1 hour before the window** (`abuseipdb_send.sh`). `cscli --since` filters by the START of an alert,
  the window by its creation time, so a slow bucket created inside the window could be lost at the boundary (measured on
  the live server: up to about 2 minutes between start and creation, 3 of 441 alerts above 30 s). `--after`/`--before`
  still make the window exact; the margin (`SINCE_MARGIN_S`, default 3600) only stops the loss.
- **ntfy alerts no longer carry the install path or the home directory** (`abuseipdb_send.sh`): the message goes through
  the public ntfy server, so `<dir>` and `~` replace them; the local log keeps the full text.
- `--limit` must be a whole number of 1 or more (`0` made "limit reached" always true and sent a false `[TRUNCATED]` alert).
- Tests: the test that kept the old "warn and go on" behaviour is replaced; new tests for the non-UTF-8 config in every
  mode, the marker of each degraded safeguard, exit code 1 with and without its message, the 1 hour reach, and the
  alert text. Checked by mutation: breaking each of these changes turns a test red.

## 2026-10-01 - tests for the built-in scenario exclusion and for two limits (3.6.23)

- Tests only, no change in behaviour. A mutation check (breaking a safeguard on purpose) showed that emptying
  `EXCLUDE_SCENARIOS` did not turn any test red: `http-crawl-non_statics` is not in `CATEGORY_MAP`, so the "unknown
  scenario" rule dropped it anyway and hid the broken safeguard. The tests now map the scenario first, so only the
  exclusion can stop it (also for `EXTRA_EXCLUDE_SCENARIOS`, which may only add to the built-in list).
- New tests for the 8 MB cut of the CSV (the file is cut as late as possible and marked `[TRUNCATED]`), for
  `ReportDate` never being in the future when an alert is stamped a few minutes ahead, and for the server's own
  addresses being read from `ip addr` (global addresses only). All four were verified by mutation.

## 2026-10-01 - tested environment stated in the README (3.6.22)

- `README.md` (Requirements): says plainly that the tool is tested only on Debian 12 and Ubuntu 24.04 with CrowdSec
  1.7 and 1.8 and nginx, that other setups are untested, and that macOS, BSD, systems without systemd and CrowdSec
  running in a container are not supported out of the box. Documentation only, no change in behaviour.

## 2026-09-30 - form for questions in Discussions (3.6.21)

- `.github/DISCUSSION_TEMPLATE/q-a.yml`: the Q&A category of GitHub Discussions now has a form, like Ideas: the privacy
  warning and link to `SECURITY.md`, a pointer to the README and `docs/OPERATIONS.md`, the same required privacy check,
  a required question, and optional fields for what was already tried, the versions and a log fragment (the last 60
  lines of `abuseipdb_cron.log`). People paste logs in questions too, so the privacy check belongs here as well.

## 2026-09-30 - form for ideas in Discussions (3.6.20)

- `.github/DISCUSSION_TEMPLATE/ideas.yml`: the Ideas category of GitHub Discussions now has a form too, with the privacy
  warning, the same required privacy check as the bug report, and fields for the goal, the idea and (optional)
  alternatives and risks. Ideas go to Discussions instead of a separate issue form: an idea often touches a safeguard
  and needs a decision first, and an accepted one can be converted to an issue.
- `.github/ISSUE_TEMPLATE/config.yml`: the own "Security vulnerability" link is removed. It pointed to the private
  vulnerability reporting form, which GitHub already offers itself once that feature is enabled, so it would have
  been a duplicate.

## 2026-09-30 - bug report as an issue form (3.6.19)

- `.github/ISSUE_TEMPLATE/bug_report.yml` replaces `bug_report.md`: the bug report is now a form with separate fields
  instead of one text box. The privacy warning and the link to `SECURITY.md` sit at the top and cannot be edited away,
  a required privacy check (two boxes) comes next, then required fields for what happened, what was expected, the
  wrapper and generator versions, and the CrowdSec and Python versions, an optional distribution field, and a log field
  for the last 60 lines of `abuseipdb_cron.log` (a fragment, not the whole file).
- `.github/ISSUE_TEMPLATE/config.yml`: blank issues are switched off, so every issue goes through the form; a new link
  sends questions and ideas to GitHub Discussions.

## 2026-09-30 - CI triggers, current actions, pinned runner (3.6.18)

- `.github/workflows/tests.yml`: tests run on pushes to `main` and on pull requests, not on every push to every branch,
  so a pull request no longer starts two identical runs. A branch is tested through its pull request (a draft is enough).
- `actions/checkout` and `actions/setup-python` moved from `@v4` / `@v5` to `@v7`: the old versions ran on Node 20,
  which GitHub is retiring (the warning in the CI run of 3.6.16).
- The runner is pinned to `ubuntu-24.04` instead of `ubuntu-latest`. GitHub moves that label to Ubuntu 26 on
  2026-10-19; the tools used by the tests should change when we decide. This is the first change that went through a
  branch and a pull request (the workflow described in 3.6.17).

## 2026-09-30 - branch workflow for code (3.6.17)

- `docs/DEVELOPMENT.md`: the workflow now has two paths. Documentation and wording go straight to `main`; code, tests, the
  hook, the CI workflow and any change to how a safeguard is described go through a branch, pushed to `github` only, with
  a green `tests` run before the maintainer merges it locally (`--ff-only`) and pushes `origin` and then `github`. The
  version is raised once per change that reaches `main` (on a branch, in its last commit), not once per commit.
- `docs/DEVELOPMENT.md`: "Accepting a pull request" rewritten for forks (`pull/N/head`, a local `pr-N` branch, merge on
  the maintainer's machine, the pull request closes by itself). The release checklist no longer asks for a required
  `tests` status check in the ruleset (it would block direct pushes of documentation); it asks for a ruleset that blocks
  force pushes and branch deletion.
- `CONTRIBUTING.md` / `CONTRIBUTING.pl.md`: a new "How to send a change" section (fork, branch, pull request, how to
  keep the branch current; only the maintainer merges).
- `AGENTS.md`: agents work on a branch and never commit to `main` or merge.

## 2026-09-30 - AGENTS.md and English-only contributions (3.6.16)

- New `AGENTS.md` (English only, no Polish twin): rules for AI coding agents that work on the repository, so that a
  contributor's assistant knows the safeguards that must not be weakened, what it must never do (a real upload, real
  keys, host names), the conventions and a few non-obvious facts about the data. Linked from the README and
  `CONTRIBUTING.md`.
- `CONTRIBUTING.md` / `CONTRIBUTING.pl.md`: a "Language" section (issues, pull requests and reviews in English) and a
  "Working with an AI assistant" section. Contributors write English documentation only; the maintainer adds the Polish
  translation and the changelog entry, so they no longer have to update both languages.
- `tools/pre-commit`: `EN_ONLY=1 git commit ...` skips only the EN/PL pairing rule for contributors who write English
  only; the privacy scan and every other check still run (checked by hand: without the variable a one-sided change is
  refused, with it the commit passes, and a fake key is still refused).
- `docs/DEVELOPMENT.md`: `AGENTS.md` as the single documented exception to the pairing rule, the `EN_ONLY` workflow and
  a new "Accepting a pull request" section (fetch locally, test, add the translation, raise the version, push to the
  private repository first). `docs/ARCHITECTURE.md` and both READMEs list the new file.

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
