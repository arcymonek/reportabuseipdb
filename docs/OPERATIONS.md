**English** | [Polski](pl/OPERATIONS.md)

# Operations

This page is for the person who runs the tool: the first start, the cron job, the alerts, what to do when something
fails, and updates. How the program works inside is in [ARCHITECTURE.md](ARCHITECTURE.md); what is reported and why
is in [COMPLIANCE.md](COMPLIANCE.md). The sections follow the life of an installation.

## Before the first live run

Every report is published under your AbuseIPDB account. The README lists these points in one line each; this is the
longer explanation.

- **CrowdSec must see the real client address.** Behind Cloudflare or another CDN, a load balancer or a proxy that
  does not pass the client IP (for example Docker's userland proxy), CrowdSec sees the proxy's address and this tool
  would report the CDN. Configure the real-IP module of your web server (`set_real_ip_from` / `real_ip_header` in
  nginx) first, and consider adding the CDN ranges as `EXCLUDE` entries as a safety net.
- **Behind NAT, exclude your public address.** On many cloud VMs the public IP is not on any interface, so the
  "own public addresses" safeguard (read from `ip addr`) cannot see it. Add it as an `EXCLUDE` entry.
- **systemd journal.** SSH auto-trust reads successful logins from journald. Without it (for example in a container)
  the safeguard is empty: list your own addresses as `EXCLUDE` entries.
- **Your traffic, your false alarms.** A scenario that fires on your own legitimate traffic (bulk uploads, WebDAV,
  monitoring) belongs in `EXTRA_EXCLUDE_SCENARIOS`. SSH auto-trust protects only addresses that logged in over SSH, so
  a device that merely uses your services (a phone, an office network, a monitoring probe) needs an `EXCLUDE` entry.
  Run `--dry-run` for a few days and read the CSV before you let cron upload anything (see "Reading a dry run").
- **IPv6 and a shared /64.** A successful SSH login from an IPv6 address trusts its whole /64 (your devices rotate
  "temporary" addresses inside it), so other devices of your network are not reported either. On a hosting provider
  that shares one /64 between customers, set `SSH_TRUST_IPV6_PREFIX=128` to trust the exact address only. IPv4 is
  always exact.
- **Other web ports.** If your web server does not listen on 80 and 443, set `HTTP_PORTS`, or the reports state a
  wrong port.

## Scheduling

```bash
30 5 * * * /path/to/abuseipdb/abuseipdb_send.sh >> /path/to/abuseipdb/abuseipdb_cron.log 2>&1
```

One run per day. Before changing the crontab, keep a copy (`crontab -l > ~/crontab.bak-DATE`) and install the new
version from a file, never through a pipe that may be empty.

Do not run the tool by hand without a reason. The wrapper skips a second run within 20 h of the last success (the
"20 h guard"), so a manual run is normally refused with a log line. `--force` bypasses the guard on purpose, and that
has a side effect: the watermark moves to the time of your run, the next scheduled run is then skipped by the guard
(exit code 0, not an error), and the run after it covers the whole gap. No alerts are lost, because the window always
starts at the watermark. But with an external monitor (see below) a forced run between about 09:30 and 17:30 (for the
05:30 cron above) leaves the file older than 36 h a few hours before the run that fixes it, and the monitor warns for
nothing.

## First-run checklist

Do this after a fresh install or a move.

1. `./abuseipdb_send.sh --version` and `python3 abuseipdb_report.py --version`.
   Create the configuration file (the commands are in the README quick start) and set the API key, the ntfy topic and
   `OWN_NAME_MARKERS`. A live run is refused while the markers are empty or still the example values.
2. `./abuseipdb_send.sh --dry-run` and read the result (see "Reading a dry run" below).
3. Add the cron line. `crontab -l` must show the new path in both the command and the log redirection.
4. After the first scheduled run, `abuseipdb_cron.log` ends with lines like these (shortened, numbers will differ):

   ```
   2026-10-12 05:30:01 [send] start v3.6.34
   2026-10-12 05:30:01 [send] window: (2026-10-11T03:30:01Z, 2026-10-12T03:30:01Z] = 24.0 h
   2026-10-12 05:30:04 [send]   generator: Wrote 7 unique IPs to /path/to/abuseipdb/reports.csv (...)
   2026-10-12 05:30:04 [send] file ready: 7 reports, validation OK
   2026-10-12 05:30:06 [send] OK: sent 7, saved 7, rejected 0; window (...]; remaining bulk-report limit: 19
   2026-10-12 05:30:06 [send] watermark updated: 2026-10-12T03:30:01Z
   ```

   On a day with nothing to report the log says `no qualifying reports in the window - nothing to send` instead;
   that is normal, and the watermark still moves.
5. `cat .state/abuseipdb_last_ok` holds a recent epoch; your external monitor, if any, reports OK.

### Reading a dry run

`--dry-run` generates and checks the CSV but sends nothing and saves neither the watermark nor the trusted-IP list.
Alerts are only printed (`[DRY-RUN ntfy ...]`). It also does **not** check the API key and does not contact
AbuseIPDB or ntfy, so a good dry run does not prove that sending works: that proof is the first scheduled run.

```bash
./abuseipdb_send.sh --dry-run | grep 'generator:'
```

The `generator:` lines tell you whether the safeguards work:

- `SSH auto-trust: N addresses with a successful login`: N should be at least 1 on a server you log in to. The warning
  `SSH auto-trust: NO successful login found` means the tool cannot see your logins (see Troubleshooting).
- `excluded N own public addresses of the server`: if this line is missing, the tool found none (behind NAT, add yours
  as `EXCLUDE`). A `[SAFEGUARD-OFF]` line means a safeguard is not working: fix it before going live.
- `loaded N exclusion entries from the config file`: appears only when you have `EXCLUDE` entries.
- `[filter] skipped N alerts - reason`: why alerts were dropped (old, trusted, excluded scenario, unknown scenario).

The wrapper then prints `DRY-RUN: would send N reports` and up to three example rows cut to 170 characters. To see the
whole CSV, run the generator alone (last 24 h, written to the screen only):

```bash
python3 abuseipdb_report.py --dry-run --since 24h
```

If nothing qualifies, the wrapper prints `no qualifying reports in the window - nothing to send` and no
`DRY-RUN: would send` line. That is normal on a quiet day. If the last report was less than 20 h ago, it says
`(dry-run) a normal run would be SKIPPED`.

## Monitoring

The wrapper alerts by itself on failures, but it cannot alert when it stops running at all: a dead cron, a deleted
script, a run that hangs (it holds the lock, so later runs are skipped), or alerts that never arrive (ntfy down, a
wrong topic, an exhausted quota). Cover that with an external monitor (not part of this repository) that runs hourly
and warns when `.state/abuseipdb_last_ok` is missing or older than 36 h. The file name is a stable interface for such a
monitor.

Why 36 h: a normal cycle is 24 h, and 12 h of slack catches one missed run the same day. A day with nothing to report
also moves the file, so a quiet server causes no false warnings. After an outage you may get two warnings, one from
the wrapper and one from the monitor; that is not a fault.

## Alerts

Alerts go to your ntfy topic (priority 4 is "high", 3 is "default") and are also written to the log. The install path
and your home directory are masked in the text that leaves the server.

| ntfy title | Priority | Meaning | What to do |
|---|---|---|---|
| `abuseipdb: reporting ERROR` | 4 | the run stopped before the watermark moved: a failure of the generator, validation, API key, configuration or upload (the causes are listed in Troubleshooting); the message names the reason when the wrapper knows it, and for a generator failure the cause is in the `generator:` log lines | read the last lines of `abuseipdb_cron.log`; a transient error is caught up by the next run (at most 48 h back), a configuration error repeats every day until you fix it |
| `abuseipdb: corrupted watermark` | 3 | `.state/abuseipdb_last_ok` has invalid content; the default 24 h window was used | check the file, it is rewritten after the next success |
| `abuseipdb: gap in reports` | 3 | last success older than 48 h; the window was cut to 48 h | find why runs failed; older alerts are lost |
| `abuseipdb: rejected reports` | 3 | AbuseIPDB rejected some rows | see `rejected:` lines in the log; the watermark advanced |
| `abuseipdb: data cut off` | 3 | a limit cut data off: the `--limit` of alerts read from `cscli`, or the 10,000-row / 8 MB limit of the CSV; the window was closed anyway, so the cut-off alerts are not reported | in the log the line is `generator: [TRUNCATED] ...`. Only the alert limit can be raised: set `ALERT_LIMIT` in the crontab line (`30 5 * * * ALERT_LIMIT=20000 /path/to/abuseipdb_send.sh >> ...`; default 5,000). The row and size limits are AbuseIPDB's, so investigate the burst of alerts instead |
| `abuseipdb: safeguard not working` | 4 | the generator printed a line starting with `[SAFEGUARD-OFF]`: the journal cannot be read (SSH auto-trust incomplete), there is no `ip` program (the server's own public addresses are unknown) or the trusted-IP list cannot be read or saved; the run continued with the other safeguards | read the quoted reason: add the service user to `systemd-journal` or `adm`, install `iproute2`, fix the permissions of `~/.secrets`; until then list your own addresses as `EXCLUDE` |
| `abuseipdb: count mismatch` | 3 | saved + rejected differs from sent | inspect the API answer in the log |

## Quick health check

```bash
tail -n 30 abuseipdb_cron.log     # last run, lines tagged [send]
cat .state/abuseipdb_last_ok      # epoch of the end of the last successful window (a quiet day moves it too)
date -u -d @"$(cat .state/abuseipdb_last_ok)"
```

You do not need this every day, because alerts and the external monitor tell you when something is wrong.

## Troubleshooting

The first column is the text you see in the log (or in the alert).

### Configuration

| Symptom | Likely cause and fix |
|---|---|
| `OWN_NAME_MARKERS is empty ... NOT sending` | the configuration file is missing, unreadable, or has no `OWN_NAME_MARKERS`; fix `~/.secrets/abuseipdb.conf` (see `abuseipdb.conf.example`) |
| `OWN_NAME_MARKERS still holds the example values ... NOT sending` | `OWN_NAME_MARKERS` is still `your-domain.example,your-host.example` from the template; write your own domains and host name |
| `config file ... is invalid`, `invalid EXCLUDE entry`, `OWN_NAME_MARKERS has ... invalid entries`, `HTTP_PORTS ... is invalid`, `SSH_TRUST_IPV6_PREFIX ... is invalid`, `EXTRA_EXCLUDE_SCENARIOS has invalid names` | the file has a malformed line, an unknown key (a typo), a comment after a value, a value out of range or in the wrong format, or it exists but cannot be read (permissions, not UTF-8); the generator stops with exit code 2 and the wrapper alerts every day until you fix it; fix the named line (comments go on their own line) |
| `API key missing`, `ABUSEIPDB_API_KEY is still the example value`, `API key has an unexpected format` | set your own key in `~/.secrets/abuseipdb.conf`: at least 20 letters or digits, no quotes, nothing after it |
| `ALERT_LIMIT must be a whole number` | fix the `ALERT_LIMIT=` value in the crontab line (1 to 9,999,999) |

### CrowdSec, the system journal and the tools

| Symptom | Likely cause and fix |
|---|---|
| `cscli failed` / `sudo -n` errors | the passwordless sudo rule for `cscli` is missing or changed; test `sudo -n cscli alerts list --limit 1` (the rule from the README allows `alerts list` with arguments, so the bare command without arguments is refused) |
| `generator exited with code 2` | the generator stopped on purpose; the reason is in the `generator:` lines just above (configuration, `cscli`, unreadable input) |
| `generator exited with code 1 without its 'No qualifying reports' message` | the script crashed before it could report: a broken file or a Python older than 3.9. Check `python3 --version`, `python3 abuseipdb_report.py --version` and `git status` (a hand-edited file) |
| `journalctl returned code ... new SSH logins may be MISSING from the auto-trust` | the service user cannot read the whole journal (or `journalctl` has no `--grep`); add the user to the group `adm` or `systemd-journal` (`sudo usermod -aG systemd-journal <user>`, then log in again) and check `journalctl -u ssh --grep Accepted` |
| `[SAFEGUARD-OFF] could not read the SSH logs` on every run | there is no `journalctl` or no running journald (a container, a host without systemd): auto-trust uses only the remembered list `ssh_trusted_seen.txt`, and you get a priority 4 alert on every run, because the wrapper has no switch to silence it. List your own addresses as `EXCLUDE`; the tool is meant for hosts with systemd |
| `SSH auto-trust: NO successful login found` (a warning, no alert) | nobody logged in over SSH in the last 60 days, or the user cannot read the journal; check the group and `journalctl -u ssh --grep Accepted` |
| `ALL N alerts were skipped because their kind is not 'crowdsec'` | every alert came from a blocklist, or your `cscli` version has no `kind` field; if it happens every day, inspect `cscli alerts list -o json` |
| `jq is not installed` | `apt install jq` |

### Sending to AbuseIPDB

| Symptom | Likely cause and fix |
|---|---|
| HTTP 401 or 403 | wrong or revoked API key; check `ABUSEIPDB_API_KEY` in `~/.secrets/abuseipdb.conf` |
| HTTP 429 (`daily limit exceeded`) | the daily `bulk-report` limit is used up (possible after manual runs); no retry is made, wait for the `Retry-After` time; the next scheduled run covers the same window |
| HTTP 422 | malformed CSV; the API detail is in the log; run `python3 abuseipdb_report.py --validate reports.csv` |
| `upload to AbuseIPDB failed after 3 attempts` | network error, timeout or an HTTP 5xx; the wrapper waited 60 s and then 120 s between attempts; the next run tries the same window. If it repeats, check the host's network and the AbuseIPDB status |
| `file ... failed validation ... NOT sending` | the `validation:` lines above name the cause; the bad file never replaces the previous one. If the cause is unclear, open an issue |
| `HTTP 200 reply without the data.savedReports field` | AbuseIPDB answered in an unexpected format; the watermark did not move. If it repeats, open an issue |

### ntfy alerts

| Symptom | Likely cause and fix |
|---|---|
| `no ntfy topic ... alert not sent` | `NTFY_TOPIC` is missing in the configuration file; alerts reach only the log until you set it |
| `NTFY_TOPIC has invalid characters` or `NTFY_URL is not a plain http(s) URL` | a comment or a stray character after the value; a topic is letters, digits, `_` and `-` only |
| `NTFY_TOPIC is still the example value` | `NTFY_TOPIC` is still `your-private-ntfy-topic`; alerts are deliberately not sent to it, set your own private topic |
| alerts missing, log shows `ntfy ERROR ... 429` | the `ntfy.sh` daily message quota for your address; the wrapper already sends over IPv4 (`curl -4`) because a shared IPv6 range is easily exhausted. Check the reply body (`code 42908` = daily quota). Prefer your own ntfy (`NTFY_URL`); on an IPv6-only host the only other way is removing `-4` from `abuseipdb_send.sh`, and a hand-edited file makes `git pull --ff-only` refuse |

### Window, lock and guard

| Symptom | Likely cause and fix |
|---|---|
| `previous run is still in progress` | another run holds the lock. The lock belongs to the running process (`flock`) and disappears when it ends; deleting the file does not release it and could allow two runs at once. Check `pgrep -af abuseipdb_send`; if that run hangs, stop the process itself |
| `skipping: last report was ... ago` | the 20 h guard; normal after a manual run |
| `watermark from the future` | clock skew; check `timedatectl`, then fix or remove the watermark deliberately |

### Why something was or was not reported

| Symptom | Likely cause and fix |
|---|---|
| an attacker you expected is missing | run the dry run and read the `[filter] skipped` lines: the alert may be older than 60 days, from an address trusted through SSH or listed in `EXCLUDE`, from an excluded scenario, outside the window, or not a local detection |
| log shows `unknown scenario <author/name> - not reported` | a CrowdSec collection you installed (or a scenario from another author) has no known category, so its alerts are skipped on purpose. This is normal after `cscli collections install`. Open an issue with the scenario name; do not edit `CATEGORY_MAP` on the server, because that breaks `git pull --ff-only` |
| addresses from a blocklist you subscribed to are not reported | by design: blocklist entries (`kind` `capi`, scenario `update : +N/-M IPs`) are other parties' observations, and only attacks this server saw itself are reported to AbuseIPDB |
| one of your own addresses was reported | first delete your reports of that address at AbuseIPDB (the API has a `clear-address` call that removes only your own reports; see the AbuseIPDB API documentation, and keep the key out of command lines and shell history). Then add the address as an `EXCLUDE=` line in `~/.secrets/abuseipdb.conf` and investigate why SSH auto-trust missed it |

## Updating and rolling back

The configuration file is checked strictly (an unknown or malformed key stops the run), and new versions sometimes add
keys or tighten a check, so do not just pull and leave cron alone.

1. In the install directory: `git pull --ff-only`. Do not edit files there by hand, or the pull will refuse.
2. Read `CHANGELOG.md` from your old version (`./abuseipdb_send.sh --version`, `python3 abuseipdb_report.py --version`
   show it) up to the new one. Look for new or renamed config keys and for changes in what is excluded.
3. `./abuseipdb_send.sh --dry-run`: it must finish without an error and the CSV must look as before. It sends nothing.
4. After the next scheduled run, check `abuseipdb_cron.log` (see "First-run checklist", step 4).

To roll back a bad release, switch the install directory to an older version, check it, and keep the cron line as it
is:

```bash
git log --oneline                          # find the commit (tags exist only for some releases)
git switch --detach <commit or tag>
./abuseipdb_send.sh --dry-run
```

An older version rejects configuration keys that a newer one added (`unknown key`), so remove them for the time being;
a copy of the file from before the update helps. When the problem is fixed, `git switch main` and `git pull --ff-only`
bring you back. Restore the crontab from your copy only if the paths changed.

## Secrets and backups

- All configuration is one file, `~/.secrets/abuseipdb.conf` (mode 600, directory mode 700); the template is
  `abuseipdb.conf.example`. The API key and the ntfy topic never appear in the repository, arguments, logs or the
  process list. The file is parsed as text and never executed.
- The configuration (exclusions, own-name markers) and the trusted-IP list `ssh_trusted_seen.txt` are state that is
  hard to rebuild and protect against reporting your own address. Include `~/.secrets/` in your own backup routine, and
  protect the copy like the original: it holds your API key and the ntfy topic.
- If the API key leaks, create a new one on the AbuseIPDB account page (the link is in `abuseipdb.conf.example`), put
  it in the file and delete the old one. If the ntfy topic leaks, anyone can read your alerts and post fake ones:
  choose a new random topic and change `NTFY_TOPIC`.
