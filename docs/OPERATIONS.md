**English** | [Polski](pl/OPERATIONS.md)

Version: 3.6.19 (`abuseipdb_report.py`)

# Operations

## Scheduling

```bash
30 5 * * * /path/to/abuseipdb/abuseipdb_send.sh >> /path/to/abuseipdb/abuseipdb_cron.log 2>&1
```

One run per day. Do not run the tool by hand on the same day unless you know why: the wrapper skips a second run
within 20 h, and `--force` bypasses that guard on purpose. Before changing the crontab, keep a copy
(`crontab -l > ~/crontab.bak-DATE`) and install the new version from a file, never through a pipe that may be empty.

## Monitoring

The wrapper alerts by itself on failures, but it cannot alert when it stops running at all (dead cron, deleted
script, stuck lock). Cover that with an external monitor (not part of this repository) that runs hourly and warns
when `.state/abuseipdb_last_ok` is older than 36 h. The file name is a stable interface for such a monitor.

## Alerts

| ntfy title | Meaning | What to do |
|---|---|---|
| `abuseipdb: reporting ERROR` | generator, validation or upload failed; the message names the reason; the watermark did not move | read the last lines of `abuseipdb_cron.log`; the next run catches up automatically |
| `abuseipdb: corrupted watermark` | `.state/abuseipdb_last_ok` has invalid content; the default 24 h window was used | check the file, it is rewritten after the next success |
| `abuseipdb: gap in reports` | last success older than 48 h; the window was cut to 48 h | find why runs failed; older alerts are lost |
| `abuseipdb: rejected reports` | AbuseIPDB rejected some rows | see `rejected:` lines in the log; the watermark advanced |
| `abuseipdb: data cut off` | a limit cut data off (the `--limit` of alerts read from `cscli`, or the 10,000-row / 8 MB limit of the CSV); the window was closed anyway, so the cut-off alerts are not reported | raise the alert limit with `ALERT_LIMIT` in the crontab line (`30 5 * * * ALERT_LIMIT=20000 /path/to/abuseipdb_send.sh >> ...`; default 5,000) or investigate the burst of alerts; the log line starts with `[TRUNCATED]` |
| `abuseipdb: count mismatch` | saved + rejected differs from sent | inspect the API answer in the log |
| a warning from your external monitor | no successful run for over 36 h, or the script or watermark is missing or invalid | check `crontab -l`, `systemctl status cron`, the log |

## First-run checklist (after a fresh install or a move)

1. `./abuseipdb_send.sh --version` and `python3 abuseipdb_report.py --version`.
   Create the config: `cp abuseipdb.conf.example ~/.secrets/abuseipdb.conf`, `chmod 600 ~/.secrets/abuseipdb.conf`, then
   set the API key, the ntfy topic and `OWN_NAME_MARKERS` (a live run is refused while the markers are empty or still the example values).
2. `./abuseipdb_send.sh --dry-run`: expect `window: (...)`, `generator:` lines and `DRY-RUN: would send N reports`.
3. `crontab -l` shows the new path in both the command and the log redirection.
4. After the first scheduled run, in `abuseipdb_cron.log`: `OK: sent N, saved N, rejected 0` and `watermark updated`.
5. `cat .state/abuseipdb_last_ok` holds a recent epoch; your external monitor, if any, reports OK.

## Daily checks

```bash
tail -n 30 abuseipdb_cron.log     # last run, lines tagged [send]
cat .state/abuseipdb_last_ok      # epoch of the end of the last successful window
date -u -d @"$(cat .state/abuseipdb_last_ok)"
```

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `cscli failed` / `sudo -n` errors | the passwordless sudo rule for `cscli` is missing or changed; test `sudo -n cscli alerts list` |
| HTTP 401 or 403 | wrong or revoked API key; check `ABUSEIPDB_API_KEY` in `~/.secrets/abuseipdb.conf` (mode 600, at least 20 alphanumeric characters) |
| `OWN_NAME_MARKERS is empty ... NOT sending` | the config file is missing, unreadable, or has no `OWN_NAME_MARKERS`; fix `~/.secrets/abuseipdb.conf` (see `abuseipdb.conf.example`) |
| `OWN_NAME_MARKERS still holds the example values ... NOT sending` | `OWN_NAME_MARKERS` is still `your-domain.example,your-host.example` from the template; write your own domains and host name |
| `config file ... is invalid`, `invalid EXCLUDE entry`, `OWN_NAME_MARKERS has ... invalid entries` | the config has a malformed line, an unknown key (a typo), a comment after a value or an entry that is not an address; the generator stops with exit code 2 and the wrapper alerts; fix the named line (comments go on their own line) |
| `ABUSEIPDB_API_KEY is still the example value` | the key is still `YOUR_ABUSEIPDB_API_KEY` from the template; set your own key |
| log shows `NTFY_TOPIC has invalid characters` or `NTFY_URL is not a plain http(s) URL` | a comment or a stray character after the value; a topic is letters, digits, `_` and `-` only |
| log shows `NTFY_TOPIC is still the example value` | `NTFY_TOPIC` is still `your-private-ntfy-topic`; alerts are deliberately not sent to it, set your own private topic |
| HTTP 429 | daily `bulk-report` limit reached (possible after manual runs); wait for `Retry-After`, no retry is made |
| HTTP 422 | malformed CSV; the API detail is in the log; run `--validate` on `reports.csv` |
| ntfy alerts missing, log shows `ntfy ERROR ... 429` | `ntfy.sh` daily message quota reached for your address; the wrapper already sends over IPv4 (`curl -4`) because a shared IPv6 range is easily exhausted. Check the reply body (`code 42908` = daily quota); on an IPv6-only host remove `-4`, or self-host ntfy (`NTFY_URL`) |
| `jq is not installed` | `apt install jq` |
| `previous run is still in progress` | another run holds the lock; check `pgrep -af abuseipdb_send` before touching the lock file |
| `skipping: last report was ... ago` | the 20 h guard; normal after a manual run |
| `watermark from the future` | clock skew; check `timedatectl`, then fix or remove the watermark deliberately |
| `journalctl returned code ... new SSH logins may be MISSING from the auto-trust` | the service user cannot read the whole journal (or `journalctl` has no `--grep`); add the user to the group `adm` or `systemd-journal` (`sudo usermod -aG systemd-journal <user>`, then log in again) and check `journalctl -u ssh --grep Accepted` |
| `ALERT_LIMIT must be a whole number` | fix the `ALERT_LIMIT=` value in the crontab line (1 to 9,999,999) |
| a documented own IP was reported | add it as an `EXCLUDE=` line in `~/.secrets/abuseipdb.conf` and investigate why SSH auto-trust missed it |

## Secrets and backups

- All configuration is one file, `~/.secrets/abuseipdb.conf` (mode 600, directory mode 700); the template is
  `abuseipdb.conf.example`. The API key and the ntfy topic never appear in the repository, arguments, logs or the
  process list. The file is parsed as text and never executed.
- The old separate files `abuseipdb_api_key`, `ntfy_topic` and `abuseipdb_exclude.txt` are a deprecated fallback: the
  config wins, and the wrapper logs a warning when it has to read the old key file. Delete them after migrating.
- The config (exclusions, own-name markers) and the SSH trust store are state that is hard to rebuild and protect
  against reporting your own address. Include `~/.secrets/` in your own backup routine.
- To roll back a bad release: `git checkout <previous tag or commit>` in the install directory, run `--dry-run`,
  and restore the crontab from your copy if the paths changed.
