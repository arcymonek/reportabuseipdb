**English** | [Polski](pl/ARCHITECTURE.md)

# Architecture

This document describes how the program works: the order of the steps, the state, the exit codes and the behaviour on
errors. The AbuseIPDB rules and the safeguards are in [COMPLIANCE.md](COMPLIANCE.md), operation (cron, alerts,
troubleshooting) is in [OPERATIONS.md](OPERATIONS.md), and work on the code is in [DEVELOPMENT.md](DEVELOPMENT.md).

## Components

### On the server

| Component | Role |
|---|---|
| `abuseipdb_report.py` | Builds and validates the bulk-report CSV from local CrowdSec alerts. Never connects to AbuseIPDB or the Internet (it talks to CrowdSec through `cscli`). |
| `abuseipdb_send.sh` | Cron wrapper: window selection, generator call, second validation, upload, API answer checks, alerts, watermark. |
| external monitor (optional) | Not part of this repository. Hourly check that the watermark is fresh (see [OPERATIONS.md](OPERATIONS.md#monitoring)). |

### In the repository

| Component | Role |
|---|---|
| `tests/` | Unit and end-to-end tests (Python `unittest`; the wrapper is tested with mocks for `curl`, the generator and `ntfy`, with no network) plus tests of the hooks, the versioning and the tools. |
| `tools/pre-commit` | Repository hook: syntax checks, the EN/PL documentation pairing rule, version rules, a privacy scan and the generator tests. |
| `tools/commit-msg` | Repository hook: the API key pattern and the `OWN_NAME_MARKERS` scan applied to the commit message, which is published too. |
| `tools/lib-privacy.sh` | The privacy rules both hooks share (sourced, not a hook). |
| `tools/deploy-check.sh` | Maintainer tool: checks (read-only) that the local `main`, `origin` and `github` stand on the same commit. |
| `tools/release_notes.sh` | Builds the release notes from `CHANGELOG.md`. |
| `.github/workflows/tests.yml` | CI: runs the whole suite on Ubuntu with the oldest and the newest supported Python for every push to `main` and every pull request. |
| `.github/workflows/release.yml` | When a tag `vX.Y.Z` is pushed to GitHub, checks the tag against the code and the changelog and creates a Release. |
| `AGENTS.md` | Rules for AI coding agents: safeguards, what never to do, conventions. English only. |

## Data flow

1. Cron starts `abuseipdb_send.sh` once a day. The wrapper takes a `flock` on `.state/abuseipdb-send.lock`; a second,
   overlapping run ends at once with exit code 0 and a log entry (no alert). Then it trims the log and checks that
   `jq` is installed.
2. The wrapper refuses a live upload while `OWN_NAME_MARKERS` is empty or still holds the example values (see
   [Configuration](#configuration)); `--dry-run` only warns.
3. The wrapper reads the watermark `.state/abuseipdb_last_ok`: epoch seconds of the end of the last successful window.
   Without a watermark the window is the last 24 h.
4. Window `(AFTER, NOW]`: `AFTER` is the watermark, `NOW` is the current time. Both are passed to the generator as
   `--after` / `--before` and the generator filters alerts by their `created_at`. The interval is half-open, so
   consecutive windows share a boundary and never overlap. `cscli` also gets a `--since` that reaches an hour further
   back (`SINCE_MARGIN_S`), because `cscli` filters by the start of an alert, and a slow alert is created only after
   its start (up to about 2 minutes measured); the generator still cuts the exact window.
5. The generator checks the configuration, calls `sudo -n cscli alerts list -o json` (`cscli` directly when running as
   root; the default limit is 5000 alerts), reads the successful SSH logins from the system journal (outside
   `--dry-run` it also saves them to `ssh_trusted_seen.txt`), determines the server's own public addresses
   (`ip addr`) and drops everything that must not be reported (see [COMPLIANCE.md](COMPLIANCE.md)). The rest is
   grouped per IP into one CSV row per IP.
6. The generator validates the file itself and replaces `reports.csv` atomically (write to `reports.csv.tmp`,
   validate, `os.replace`).
7. The wrapper runs `abuseipdb_report.py --validate reports.csv` as a second check: the same validator, run again on
   the finished file.
8. Right before the upload the wrapper checks the API key (present, not the example value, valid format), then uploads
   the file with `curl` (`Accept: application/json`, the key through stdin) and checks the HTTP status and the JSON
   body (`savedReports`, `invalidReports`).
9. Only after a valid answer the watermark is set to the window end. Rejected rows (bad IP or category) would not
   change on a re-send, so the watermark advances in that case too, with an alert.

When no row is left after the filters, the generator writes no file, prints `No qualifying reports` and exits with
code 1. The wrapper then treats the window as closed: it advances the watermark and exits with code 0, with no upload
and no alert.

`--dry-run` generates and checks the file but sends nothing: the CSV goes to a temporary file (`reports.csv` is left
alone), the watermark and the trusted-IP list do not change, and ntfy alerts are only printed. It does create the
`.state/` directory and the lock file and it trims the log. `--force` bypasses only the 20 h guard. Usage:
[README](../README.md#usage), procedures: [OPERATIONS.md](OPERATIONS.md).

## Time windows and the watermark

- The watermark is the window **end** (`--before`), not the completion time. Alerts created while a run is in
  progress therefore fall into the next window instead of a gap.
- After an outage the next run catches up, at most 48 h back (`MAX_LOOKBACK_H`); a longer gap is cut and reported, and
  the older alerts are lost.
- A run less than 20 h after the previous success is skipped (`MIN_INTERVAL_H`; the AbuseIPDB guideline is to report
  the same IP about once a day). `--force` overrides the guard.
- A corrupted watermark falls back to the default 24 h window with an alert; in that run the 20 h guard is off (there
  is no reliable time of the last success), and the file is overwritten after the next success. A watermark from the
  future (clock skew) is an error in every run until someone corrects it by hand.
- The watermark advances after a valid API answer, also when some rows were rejected, and when there was nothing to
  send. On a failure it stays, so the next run catches up on the same window. The table in
  [Error handling](#error-handling) gives this for every situation.

## Configuration

The wrapper and the generator read the same file (`~/.secrets/abuseipdb.conf`; `ABUSEIPDB_CONFIG` sets another path,
and the generator also takes `--config`, which the wrapper always passes to it). The file is read as `KEY=value` text
and is never executed. The keys are described in the [README](../README.md#configuration) and in
`abuseipdb.conf.example`. Exclusions come only from the `EXCLUDE` entries of the config. Environment variables of the
wrapper (e.g. `CURL_BIN`, `RETRIES`) are for the tests; where the same setting also exists in the file (e.g.
`NTFY_URL`), the variable wins. Cron sets none of them, except the optional `ALERT_LIMIT` (see
[OPERATIONS.md](OPERATIONS.md#alerts)).

The config is checked strictly in every mode of the generator (including `--validate`). On an error the generator
exits with code 2, because each such error would otherwise switch a safeguard off without a trace. It stops on:
- a malformed line, an unknown key (a typo) or a comment after a value,
- a value in the wrong format or out of range (e.g. `EXCLUDE`, `HTTP_PORTS`, `EXTRA_EXCLUDE_SCENARIOS`,
  `SSH_TRUST_IPV6_PREFIX`, an own-name marker with a space or `#`),
- a file that exists but cannot be read (permissions, encoding).

A **missing** file is milder: the generator only says so, and the wrapper sends nothing anyway, because the list of
own-name markers is then empty. Messages and the fix: [OPERATIONS.md](OPERATIONS.md#troubleshooting).

Own-name markers work on the "refuse when data is missing" principle (fail closed). An empty list switches off the
check that a comment does not reveal the operator's names, so a live wrapper run ends in a failure with an alert, and
the example values of `abuseipdb.conf.example` are treated like an empty list. The generator itself warns only about
an empty list; the example values are recognised by the wrapper alone. The wrapper also refuses the example API key
and never sends alerts to the example `NTFY_TOPIC`.

## State and data files

| Path | Owner | Notes |
|---|---|---|
| `.state/abuseipdb_last_ok` | wrapper | watermark, epoch seconds, written only after a successful run |
| `.state/abuseipdb-send.lock` | wrapper | `flock` lock file |
| `reports.csv` | generator | deleted by the wrapper before every real run so a stale file is never sent |
| `reports.csv.tmp` | generator | temporary file: gone after the replace or after a failed validation |
| `abuseipdb_cron.log` | cron | trimmed in place by the wrapper: when it exceeds 2,500 lines, the last 2,000 stay |
| `~/.secrets/abuseipdb.conf` | operator | the single config file, mode 600. The API key is never in arguments or logs, and the ntfy address (with the topic) reaches `curl` through stdin |
| `~/.secrets/ssh_trusted_seen.txt` | generator | trusted SSH addresses (single addresses; IPv6 is widened to `SSH_TRUST_IPV6_PREFIX` when read), mode 600, entries expire after 60 days |

## Error handling

| Situation | Behaviour | Alert | Watermark |
|---|---|---|---|
| network error, timeout, HTTP 5xx or 408 | up to 3 attempts, pauses of 60 s and 120 s, then failure | yes | unchanged |
| HTTP code other than 200 (e.g. 401, 403, 422, 429) | no retry, failure; for 429 the message includes `Retry-After` | yes | unchanged |
| HTTP 200 without the `savedReports` / `invalidReports` fields | failure | yes | unchanged |
| `invalidReports` not empty | rows rejected by the API; a re-send would not change them | yes | advances |
| saved + rejected differs from sent | warning in the log | yes | advances |
| generator or validation failure | nothing sent, stale `reports.csv` already deleted | yes | unchanged |
| config to be rejected, no `jq`, missing or example API key | failure before the upload | yes | unchanged |
| no qualifying reports | nothing to send, exit code 0 | no | advances |
| data cut off by a limit (`[TRUNCATED]`: 5000 alerts from `cscli`, 10,000 rows, 8 MB) | the run continues; the cut-off alerts will not be reported | yes | advances |
| safeguard not working (`[SAFEGUARD-OFF]`, e.g. the journal cannot be read) | the run continues with the other safeguards | yes | advances |
| corrupted watermark | 24 h window, 20 h guard off in this run | yes | overwritten after a success |
| gap longer than 48 h | window cut to 48 h | yes | advances |
| watermark from the future | failure | yes | unchanged (needs a manual fix) |
| previous run still in progress (lock) | skipped, exit code 0 | no | unchanged |
| less than 20 h since the last success | skipped, exit code 0 | no | unchanged |

Alert titles, priorities and what to do after each: [OPERATIONS.md](OPERATIONS.md#alerts). Re-sending the same file is
safe: AbuseIPDB merges reports with an identical comment and categories within 24 h.

## Exit codes

| Program | Code | Meaning |
|---|---|---|
| `abuseipdb_report.py` | 0 | file written (or dry-run / validation succeeded) |
| | 1 | no qualifying reports; nothing written |
| | 2 | error (bad arguments, cscli failure, bad configuration, validation failed, unreadable or unexpected input, any unexpected internal crash); previous file untouched |
| `abuseipdb_send.sh` | 0 | success, skipped by the lock or the 20 h guard, or nothing to send |
| | 1 | failure; the watermark is unchanged, the next run catches up |
| | 2 | unknown argument |

Why generator code 1 means "an empty day" only together with the line `No qualifying reports`: a crash before `main()`
(e.g. a syntax error) also exits with 1, and the wrapper must not mistake it for an empty day, because it would close
the window and lose the reports. So the wrapper treats code 1 without that line as a failure, and an unexpected
exception in the generator ends with code 2, not 1.

## Report comment

The comment is assembled only from the English `TPL_*` constants in the generator, in a fixed order: the source
sentence; the target protocol and ports; the triggered scenarios; the number of matching events with the time range in
UTC; a sample of the real HTTP requests (method, path, status). CrowdSec does not record the port number, so the HTTP
ports come from the `HTTP_PORTS` key (default `80/443`). The comment is at most 1024 bytes, and samples that would
reveal the operator's names or personal data are omitted. The rules, the reasons and the limits:
[COMPLIANCE.md](COMPLIANCE.md#correctness-of-the-data-in-a-report).

Example of one row (fictional documentation address; generated by the program from synthetic alerts):

```csv
IP,Categories,ReportDate,Comment
203.0.113.45,"14,15,21",2026-10-01T11:09:03+00:00,"Detected by CrowdSec IDS on a self-hosted server. Target: HTTP/HTTPS (ports 80/443). Triggered rules: http-probing, http-sensitive-files. 4 matching log events between 2026-10-01T11:08:42Z and 11:09:03Z (UTC). Sample requests: GET /.env -> 404; GET /wp-login.php -> 404; GET /.git/config -> 404; GET /admin/config.php -> 404"
```

The same example is in the [README](../README.md).

## Coupling with external monitors

An external monitor may read `abuseipdb_send.sh` and `.state/abuseipdb_last_ok` from the install directory. Treat both
names as a stable interface: renaming either requires a matching change in the monitor. What a monitor is for and
which threshold to set: [OPERATIONS.md](OPERATIONS.md#monitoring).
