**English** | [Polski](README.pl.md)

Version: 3.6.20 (`abuseipdb_report.py`)

# reportabuseipdb

Automated, policy-compliant reporting of attackers detected by your own [CrowdSec](https://www.crowdsec.net/)
instance to [AbuseIPDB](https://www.abuseipdb.com/).

The project is a small pair of tools for a self-hosted Linux server:

- `abuseipdb_report.py` reads **locally detected** CrowdSec alerts and builds a bulk-report CSV that is
  validated against the AbuseIPDB rules. It sends nothing itself.
- `abuseipdb_send.sh` is the cron wrapper: it picks a gap-free time window, runs the generator, validates the file
  again, uploads it to the AbuseIPDB `bulk-report` endpoint, checks the API answer and raises an
  [ntfy](https://ntfy.sh/) alert when anything looks wrong.

> Unofficial project, not affiliated with or endorsed by AbuseIPDB or CrowdSec.
>
> Early stage, work in progress: run `--dry-run` and review the CSV before any live use.

## Why this exists

A false report can get an AbuseIPDB account suspended, so the tool is built around one priority: **never report
something that is not a real, locally observed attack**, and never report the operator's own address. Everything else
(convenience, coverage) comes second.

## How it works

```
cron 05:30 -> abuseipdb_send.sh
                 |  window = (watermark, now]         (no overlaps, no gaps)
                 v
              abuseipdb_report.py   <- cscli alerts list (local detections only)
                 |  filters + safeguards + CSV validation
                 v
              reports.csv  -> independent --validate -> curl (bulk-report)
                 |                                         |
                 |                          HTTP code + JSON checked
                 v                                         v
              watermark advances only after a successful upload; ntfy alert otherwise
```

The time window is the interval `(watermark, now]`, so consecutive runs neither overlap nor leave gaps. The
watermark moves only after a successful upload; on any error the operator gets an ntfy alert.

## Safeguards (never weaken these)

- Only alerts detected by this server (`kind == "crowdsec"`); community blocklist bans are never reported.
- Reports older than 60 days are dropped on every row.
- Private, reserved, CGNAT and other non-global addresses are never reported.
- Scenarios with a history of false alarms are excluded; scenarios that are only a weak signal do not qualify alone.
- Unknown scenarios are never reported (only `crowdsecurity` scenarios that are in the category map or named after a CVE);
  a scenario of another author needs an explicit entry in `CATEGORY_MAP` under its full name.
- Operator exclusion list (`EXCLUDE` in the config file, on by default) and **SSH auto-trust**: any address that logged in over SSH in the last
  60 days is never reported (kept in a persistent store because the journal gets trimmed).
- The server's own public addresses are always excluded.
- The comment text is built only from English constants, is ASCII-only, never contains the reported IP, the
  server's hostname or its domain names (a second check against your `OWN_NAME_MARKERS`), and is capped at
  1,024 bytes. A sample request from the attacker that would contain such a name, the reported IP or one of the
  server's own addresses is left out of the comment, so one hostile path never blocks the whole file.
- Every file is validated twice (generator and wrapper) and a failing file never replaces the previous one.

See [docs/COMPLIANCE.md](docs/COMPLIANCE.md) for the policy mapping.

## Is this tool for you?

Every report is published under your AbuseIPDB account, so check these points before the first live run:

- **CrowdSec must see the real client address.** Behind Cloudflare or another CDN, a load balancer or a proxy that
  does not pass the client IP (for example Docker's userland proxy), CrowdSec sees the proxy's address and this tool
  would report the CDN. Configure the real-IP module of your web server (`set_real_ip_from` / `real_ip_header` in
  nginx) first, and consider adding the CDN ranges as `EXCLUDE` entries as a safety net.
- **Behind NAT, exclude your public address.** On many cloud VMs the public IP is not on any interface, so the
  "own public addresses" safeguard (read from `ip addr`) cannot see it. Add it as an `EXCLUDE` entry.
- **systemd journal.** SSH auto-trust reads successful logins from journald. Without it (for example in a container)
  the safeguard is empty: list your own addresses as `EXCLUDE` entries.
- **Your traffic, your false alarms.** A scenario that fires on your own legitimate traffic (bulk uploads, WebDAV,
  monitoring) belongs in `EXTRA_EXCLUDE_SCENARIOS`. Run `--dry-run` for a few days and read the CSV before you let
  cron upload anything.
- **Other web ports.** If your web server does not listen on 80 and 443, set `HTTP_PORTS`, or the reports state a
  wrong port.

## Status

Early stage, work in progress. Running in production on a single self-hosted server.

Written by the author in collaboration with Claude Code (Anthropic). The author is not a professional programmer,
which is why the project has extensive tests and documentation; before live use, run `--dry-run` and review the CSV.

## Requirements

- Linux with systemd, `bash`, `curl`, `jq`, `flock` (util-linux), GNU `date`, `journalctl` and `ip`.
- Python 3.9 or newer (developed on 3.11, tested on 3.9 and 3.14), standard library only.
- CrowdSec with `cscli`, callable as `sudo -n cscli alerts list` by the service user (passwordless sudo rule);
  when the script runs as root, `cscli` is called directly and `sudo` is not needed.
- The service user may read the whole journal (group `systemd-journal` or `adm`).
- An AbuseIPDB API key.
- Optional: an ntfy topic for alerts.

## Quick start

```bash
sudo apt install jq                  # Debian/Ubuntu; curl, flock and ip are usually present
git clone https://github.com/arcymonek/reportabuseipdb.git abuseipdb && cd abuseipdb

mkdir -p ~/.secrets && chmod 700 ~/.secrets
cp abuseipdb.conf.example ~/.secrets/abuseipdb.conf
chmod 600 ~/.secrets/abuseipdb.conf
$EDITOR ~/.secrets/abuseipdb.conf    # every line is commented; set your key, topic and own names
```

Let the service user read the CrowdSec alerts without a password, and only them (replace `<user>`; check the path
with `command -v cscli`):

```bash
echo '<user> ALL=(root) NOPASSWD: /usr/bin/cscli alerts list *' | sudo tee /etc/sudoers.d/abuseipdb
sudo chmod 440 /etc/sudoers.d/abuseipdb && sudo visudo -c
sudo usermod -aG systemd-journal <user>   # SSH auto-trust reads the journal; log in again afterwards
sudo -n cscli alerts list --limit 1       # must work without a password prompt
```

Then check everything without sending anything:

```bash
./abuseipdb_send.sh --dry-run        # generates and checks, sends nothing, saves nothing
```

Crontab entry (one run per day is the AbuseIPDB guideline):

```bash
30 5 * * * /path/to/abuseipdb/abuseipdb_send.sh >> /path/to/abuseipdb/abuseipdb_cron.log 2>&1
```

## Usage

```bash
./abuseipdb_send.sh                  # normal run (what cron does)
./abuseipdb_send.sh --dry-run        # no upload, no watermark, no trusted-IP list update
./abuseipdb_send.sh --force          # skip the "last report < 20 h ago" guard (use deliberately)
python3 abuseipdb_report.py --validate reports.csv   # check a CSV against the AbuseIPDB rules
python3 abuseipdb_report.py --help
```

All configuration lives in **one file outside the repository**, `~/.secrets/abuseipdb.conf` (mode 600; override
the path with `ABUSEIPDB_CONFIG` or `--config`). Copy [abuseipdb.conf.example](abuseipdb.conf.example), which explains
every line. The file is `KEY=value` text, read as data and never executed. It is checked strictly: a malformed line,
an unknown key, a comment after a value or an invalid `EXCLUDE` entry stops the run with an error instead of quietly
switching a safeguard off (comments go on their own line):

| Key | Purpose |
|---|---|
| `ABUSEIPDB_API_KEY` | AbuseIPDB API key (required) |
| `NTFY_TOPIC` | ntfy topic for alerts (required for alerts; treat as a secret) |
| `NTFY_URL` | ntfy server (optional, default `https://ntfy.sh`) |
| `OWN_NAME_MARKERS` | comma-separated fragments (your own domains and host) that must never appear in a report comment; a live upload is refused while the list is empty or still holds the example values |
| `EXCLUDE` | an IP or CIDR that is never reported; repeat the key for more entries (optional) |
| `HTTP_PORTS` | the ports your web server listens on, stated in HTTP reports (optional, default `80/443`; e.g. `443` or `8080/8443`) |
| `EXTRA_EXCLUDE_SCENARIOS` | comma-separated CrowdSec scenarios never reported, e.g. one that gave false alarms on your own traffic; a short name (`http-probing`) matches every author, a full name (`author/name`) only that author; it only adds to the built-in exclusions (optional) |

Generated next to it: `~/.secrets/ssh_trusted_seen.txt` (IPs with a successful SSH login, entries expire after
60 days). The older separate files `abuseipdb_api_key`, `ntfy_topic` and `abuseipdb_exclude.txt` still work as a
deprecated fallback while you migrate; the config file wins.

Runtime data next to the scripts (ignored by git): `reports.csv`, `abuseipdb_cron.log`, `.state/`.

## Tests

```bash
python3 -m unittest discover -v tests     # generator tests run anywhere; wrapper tests need Linux
```

## Documentation

| Document | Content |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | data flow, time windows, state files, exit codes, error handling |
| [docs/COMPLIANCE.md](docs/COMPLIANCE.md) | AbuseIPDB policy and API limits mapped to the implementation |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | cron, monitoring, alerts, troubleshooting, first-run checklist |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | workflow, tests, versioning, language rules, release checklist |
| [CHANGELOG.md](CHANGELOG.md) | version history |
| [CONTRIBUTING.md](CONTRIBUTING.md) | how to report a bug, propose a change and send a pull request |
| [SECURITY.md](SECURITY.md) | how to report a vulnerability privately |
| [AGENTS.md](AGENTS.md) | rules for AI coding agents working on this repository (English only) |

All documents exist in English and Polish (`*.pl.md`, `docs/pl/`), except `AGENTS.md` (English only).

## Contributing and security

Bug reports and pull requests are welcome, in English and also when written with an AI assistant; see
[CONTRIBUTING.md](CONTRIBUTING.md) and, for coding agents, [AGENTS.md](AGENTS.md). A pull request that weakens a
safeguard needs a very good reason. Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md),
not in a public issue.

## License and author

[MIT](LICENSE). Copyright (c) 2026 Arkadiusz Polak.

Arkadiusz Polak, <github@arkadiuszpolak.pl>, [arkadiuszpolak.pl](https://arkadiuszpolak.pl).
