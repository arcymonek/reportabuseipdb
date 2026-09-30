**English** | [Polski](pl/ARCHITECTURE.md)

Version: 3.6.21 (`abuseipdb_report.py`)

# Architecture

## Components

| Component | Role |
|---|---|
| `abuseipdb_report.py` | Builds and validates the bulk-report CSV from local CrowdSec alerts. Never touches the network. |
| `abuseipdb_send.sh` | Cron wrapper: window selection, generator call, second validation, upload, API answer checks, alerts, watermark. |
| `tests/` | Unit and end-to-end tests (Python `unittest`, mocks for `curl`, the generator and `ntfy`). |
| `tools/pre-commit` | Repository hook: syntax checks, the EN/PL documentation pairing rule, version rules and a privacy scan. |
| `AGENTS.md` | Rules for AI coding agents: safeguards, what never to do, conventions. English only. |
| external monitor (optional) | Not part of this repository. Hourly check that the watermark is not older than 36 h. |

## Data flow

1. Cron starts `abuseipdb_send.sh` once a day. A `flock` on `.state/abuseipdb-send.lock` prevents overlapping runs.
2. The wrapper reads the watermark `.state/abuseipdb_last_ok` (epoch seconds of the end of the last successful
   window). Without a watermark the window is the last 24 h.
3. Window `(AFTER, NOW]`: `AFTER` is the watermark, `NOW` is the current time. Both are passed to the generator as
   `--after` / `--before` and the generator filters alerts by their `created_at`. The interval is half-open, so
   consecutive windows share a boundary and never overlap.
4. The generator calls `sudo -n cscli alerts list -o json` (`cscli` directly when running as root), drops everything that must not be reported (see
   [COMPLIANCE.md](COMPLIANCE.md)), groups the alerts per IP and builds one CSV row per IP.
5. The generator validates the file itself and replaces `reports.csv` atomically (write to `reports.csv.tmp`,
   validate, `os.replace`).
6. The wrapper runs `abuseipdb_report.py --validate reports.csv` as an independent second check.
7. The wrapper uploads the file with `curl` (`Accept: application/json`, the API key through stdin) and checks the
   HTTP status and the JSON body (`savedReports`, `invalidReports`).
8. Only after a valid answer the watermark is set to the window end. Rejected rows (bad IP or category) would not
   change on a re-send, so the watermark advances in that case too, with an alert.

## Time windows and the watermark

- The watermark is the window **end** (`--before`), not the completion time. Alerts created while a run is in
  progress therefore fall into the next window instead of a gap.
- After an outage the next run catches up, at most 48 h back (`MAX_LOOKBACK_H`); a longer gap is cut and reported.
- A run less than 20 h after the previous success is skipped (`MIN_INTERVAL_H`); `--force` overrides the guard.
- A corrupted watermark falls back to the default 24 h window with an alert; a watermark from the future is an
  error.

## State and data files

| Path | Owner | Notes |
|---|---|---|
| `.state/abuseipdb_last_ok` | wrapper | watermark, epoch seconds, written only after a successful run |
| `.state/abuseipdb-send.lock` | wrapper | `flock` lock file |
| `reports.csv`, `reports.csv.tmp` | generator | deleted by the wrapper before every real run so a stale file is never sent |
| `abuseipdb_cron.log` | cron | trimmed in place by the wrapper to about 2,000 lines |
| `~/.secrets/abuseipdb.conf` | operator | the single config file, mode 600, `KEY=value` text that is never executed: `ABUSEIPDB_API_KEY` (never in arguments or logs), `NTFY_TOPIC` (passed to `curl` through stdin), `NTFY_URL`, `OWN_NAME_MARKERS`, `EXCLUDE`, `HTTP_PORTS`, `EXTRA_EXCLUDE_SCENARIOS` |
| `~/.secrets/abuseipdb_api_key`, `ntfy_topic`, `abuseipdb_exclude.txt` | operator | deprecated fallback while migrating; the config wins, exclusions from both are combined |
| `~/.secrets/ssh_trusted_seen.txt` | generator | trusted SSH addresses, mode 600, entries expire after 60 days |

## Exit codes

| Program | Code | Meaning |
|---|---|---|
| `abuseipdb_report.py` | 0 | file written (or dry-run / validation succeeded) |
| | 1 | no qualifying reports; nothing written |
| | 2 | error (bad arguments, cscli failure, validation failed, unreadable or unexpected input, any unexpected internal crash); previous file untouched |
| `abuseipdb_send.sh` | 0 | success, skipped by a guard, or nothing to send |
| | 1 | failure; the watermark is unchanged, the next run catches up |
| | 2 | unknown argument |

## Error handling

| Situation | Behaviour |
|---|---|
| network error, timeout, HTTP 5xx or 408 | up to 3 attempts with growing pauses, then failure and alert |
| HTTP 401, 403, 422, 429 | no retry; failure and alert (429 includes `Retry-After`) |
| HTTP 200 with an unexpected body | failure and alert |
| `invalidReports` not empty | alert, watermark advances |
| saved + rejected differs from sent | alert |
| generator or validation failure | failure and alert, stale CSV already deleted, nothing sent |

Re-sending the same file is safe: AbuseIPDB merges reports with an identical comment and categories within 24 h.

## Report comment

The comment is assembled only from the English `TPL_*` constants in the generator: source sentence, target protocol
and ports, triggered scenarios, number of matching events, time range in UTC and a sample of the real HTTP requests
(method, path, status). A sample that contains an own-name marker, the reported IP, one of the server's own public
addresses or an e-mail address is omitted (the paths come from the attacker). The event count is conservative (unique requests, never a sum across overlapping
scenarios). The text is sanitised to ASCII, control characters are removed and spreadsheet formula prefixes are
neutralised. A double quote is written as `%22` and the comment never ends with a backslash, because the AbuseIPDB CSV
parser treats a backslash as an escape character; other backslashes stay (they are evidence, e.g. `\x5Cthink`).

## Coupling with external monitors

An external monitor may read `abuseipdb_send.sh` and `.state/abuseipdb_last_ok` from the install directory. Treat both
names as a stable interface: renaming either requires a matching change in the monitor.

## Configuration sources

The wrapper and the generator read the same config file (`ABUSEIPDB_CONFIG`, default `~/.secrets/abuseipdb.conf`; the
wrapper passes it to the generator with `--config`). Precedence, highest first: explicit environment overrides
(used by the tests), the config file, the deprecated separate files. Exclusions are always the union of the config
`EXCLUDE` entries and the old exclusion file, never a replacement, so a migration cannot silently drop one. Own-name
markers fail closed: with an empty list, or one that still holds the example values of `abuseipdb.conf.example`, the
generator warns and a live wrapper run is refused with an alert. The example `NTFY_TOPIC` never receives alerts.
The config is also checked strictly in every mode of the generator (including `--validate`): a malformed line, an
unknown key, a comment after a value, a marker with a space or `#` inside, or an invalid `EXCLUDE` entry stop the run
with exit code 2, because each of them would otherwise switch a safeguard off without a trace.
