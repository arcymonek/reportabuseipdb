# reportabuseipdb

**English** | [Polski](README.pl.md)

[![tests](https://github.com/arcymonek/reportabuseipdb/actions/workflows/tests.yml/badge.svg)](https://github.com/arcymonek/reportabuseipdb/actions/workflows/tests.yml)
![license: MIT](https://img.shields.io/badge/license-MIT-blue)
![python: 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![platform: Linux (systemd)](https://img.shields.io/badge/platform-Linux%20%28systemd%29-blue)
![python dependencies: none](https://img.shields.io/badge/python%20dependencies-none-brightgreen)
![reports: local detections only](https://img.shields.io/badge/reports-local%20detections%20only-brightgreen)

[Quick start](#quick-start) · [Configuration](#configuration) · [Safeguards](#safeguards) ·
[Documentation](#documentation) · [Changelog](CHANGELOG.md) ·
[Contributing and security](#contributing-and-security) · [License and author](#license-and-author)

Automated reporting of attackers detected by your own [CrowdSec](https://www.crowdsec.net/) instance to
[AbuseIPDB](https://www.abuseipdb.com/), built to follow the AbuseIPDB reporting policy.

The project is a pair of tools for a self-hosted Linux server:

- `abuseipdb_report.py` reads **locally detected** CrowdSec alerts and builds a bulk-report CSV that is
  validated against the AbuseIPDB rules. It sends nothing itself.
- `abuseipdb_send.sh` is the cron wrapper: it picks a gap-free time window, runs the generator, validates the file
  again, uploads it to the AbuseIPDB `bulk-report` endpoint, checks the API answer and raises an
  [ntfy](https://ntfy.sh/) alert when anything looks wrong.

> The project is complete and runs in production on a single self-hosted server. I am open to corrections and
> adjustments. You can check the results on my [AbuseIPDB profile](https://www.abuseipdb.com/user/339209).
>
> Unofficial project, not affiliated with or endorsed by AbuseIPDB or CrowdSec.
>
> Written by the author in collaboration with Claude Code (Anthropic).
> The author is not a professional programmer, which is why the project has extensive tests and documentation.
>
> Before live use, run `--dry-run` and review the CSV.

## The main rule

A false report can get an AbuseIPDB account suspended, so the tool is built around one priority: **never report
something that is not a real, locally observed attack**, and never report the operator's own address. Everything else
(convenience, coverage) comes second. Full list of protections: [Safeguards](#safeguards).

## Example of a report

An example row of the CSV file.

```csv
IP,Categories,ReportDate,Comment
203.0.113.45,"14,15,21",2026-10-01T11:09:03+00:00,"Detected by CrowdSec IDS on a self-hosted server. Target: HTTP/HTTPS (ports 80/443). Triggered rules: http-probing, http-sensitive-files. 4 matching log events between 2026-10-01T11:08:42Z and 11:09:03Z (UTC). Sample requests: GET /.env -> 404; GET /wp-login.php -> 404; GET /.git/config -> 404; GET /admin/config.php -> 404"
```

- `Categories` are mapped per CrowdSec scenario (here 14 = Port Scan, 15 = Hacking, 21 = Web App Attack).
- `ReportDate` is the time of the latest observation, in UTC.
- The `Comment` is built from fixed English sentences and never contains your host name, your domain names or the
  reported address (details in [Safeguards](#safeguards)).
- The IP address in the example is fictional (a range reserved for documentation); a real run reports real attackers.

## How it works

1. Cron runs `abuseipdb_send.sh` once a day (at 05:30 in the example). The wrapper picks the time window
   `(watermark, now]`: consecutive runs neither overlap nor leave gaps in time.
2. `abuseipdb_report.py` reads only **locally detected** alerts from `cscli alerts list`, applies the filters and
   safeguards and builds `reports.csv`.
3. The wrapper validates that file again, independently of the generator (`--validate`).
4. The wrapper uploads the file to AbuseIPDB and checks in the answer that the reports were accepted.
5. The watermark moves only after a successful upload.

On an error at any stage the operator gets an ntfy alert.

## Requirements

- Linux with systemd, `bash`, `curl`, `jq`, `flock` (util-linux), GNU `date`, `journalctl` and `ip`.
- Tested only on Debian 12 (production) and Ubuntu 24.04 (CI).
- Tested with CrowdSec 1.8 and nginx as the reverse proxy. Other versions, distributions and web servers are
  untested: run `--dry-run`, read the CSV and let me know how it went.
- Not supported: macOS and BSD (the wrapper needs GNU `date` and `flock`). Without systemd (for example in a
  container) SSH auto-trust has no journal to read: see [Before you go live](#before-you-go-live).
- `cscli` must run on the same host as the scripts (CrowdSec in a container needs a wrapper of your own).
- Python 3.9 or newer (developed on 3.11, tested in CI on 3.9 and on the newest Python), standard library only.
- CrowdSec with `cscli`, callable as `sudo -n cscli alerts list` by the service user (passwordless sudo rule);
  when the script runs as root, `cscli` is called directly and `sudo` is not needed.
- The service user must be allowed to read the whole journal (group `systemd-journal` or `adm`); without it the run
  continues, but SSH auto-trust is incomplete and the operator gets an alert.
- An AbuseIPDB API key.
- Optional: an ntfy topic for alerts.

## Before you go live

Every report is published under your AbuseIPDB account, so check these points before the first live run:

- **Real client address.** Behind a CDN, a load balancer or a proxy, make sure CrowdSec sees the client's IP.
- **NAT.** If the public IP is not on any interface, add it as an `EXCLUDE` entry.
- **No systemd journal.** SSH auto-trust is then empty: list your own addresses as `EXCLUDE` entries.
- **Your own traffic.** Put a scenario that fires on it into `EXTRA_EXCLUDE_SCENARIOS`; run `--dry-run` for a few days.
- **Shared IPv6 /64.** If your provider shares one /64 between customers, set `SSH_TRUST_IPV6_PREFIX=128`.
- **Other web ports.** If your web server does not listen on 80 and 443, set `HTTP_PORTS`.

Why and how: [docs/OPERATIONS.md](docs/OPERATIONS.md#before-the-first-live-run).

## Quick start

1. Install `jq` (Debian/Ubuntu; `curl`, `flock` and `ip` are usually present) and clone the repository:

   ```bash
   sudo apt install jq
   git clone https://github.com/arcymonek/reportabuseipdb.git abuseipdb && cd abuseipdb
   ```

2. Create the config file outside the repository and set your key, topic and own names (every line is commented):

   ```bash
   mkdir -p ~/.secrets && chmod 700 ~/.secrets
   cp abuseipdb.conf.example ~/.secrets/abuseipdb.conf
   chmod 600 ~/.secrets/abuseipdb.conf
   $EDITOR ~/.secrets/abuseipdb.conf
   ```

3. Let the service user read the CrowdSec alerts without a password, and only them, and read the journal for SSH
   auto-trust (replace `<user>`; check the path with `command -v cscli`; log in again after `usermod`). The last
   command must work without a password prompt:

   ```bash
   echo '<user> ALL=(root) NOPASSWD: /usr/bin/cscli alerts list *' | sudo tee /etc/sudoers.d/abuseipdb
   sudo chmod 440 /etc/sudoers.d/abuseipdb && sudo visudo -c
   sudo usermod -aG systemd-journal <user>
   sudo -n cscli alerts list --limit 1
   ```

4. Check everything without sending anything (it generates and checks, sends nothing, saves nothing):

   ```bash
   ./abuseipdb_send.sh --dry-run
   ```

5. Add the crontab entry. One run per day: AbuseIPDB asks to report the same IP about once a day.

   ```bash
   30 5 * * * /path/to/abuseipdb/abuseipdb_send.sh >> /path/to/abuseipdb/abuseipdb_cron.log 2>&1
   ```

## Configuration

All configuration lives in **one file outside the repository**, `~/.secrets/abuseipdb.conf` (mode 600; override
the path with `ABUSEIPDB_CONFIG` or `--config`). Copy [abuseipdb.conf.example](abuseipdb.conf.example), which explains
every line. The file is `KEY=value` text, read as data and never executed. It is checked strictly: a malformed line,
an unknown key, a comment after a value or an invalid `EXCLUDE` entry stops the run with an error instead of quietly
switching a safeguard off (comments go on their own line).

- `ABUSEIPDB_API_KEY`: AbuseIPDB API key (required)
- `NTFY_TOPIC`: ntfy topic for alerts (required for alerts; treat as a secret)
- `NTFY_URL`: ntfy server (optional, default `https://ntfy.sh`)
- `OWN_NAME_MARKERS`: your own domains and host name, comma-separated; they must never appear in a report comment, and
  a live upload is refused while the list is empty or still holds the example values
- `EXCLUDE`: an IP or CIDR that is never reported; repeat the key for more entries (optional)
- `HTTP_PORTS`: the ports your web server listens on, stated in HTTP reports (optional, default `80/443`)
- `SSH_TRUST_IPV6_PREFIX`: how wide a network is trusted around an IPv6 address with a successful SSH login
  (optional, 64-128, default `64`; `128` trusts only the exact address)
- `EXTRA_EXCLUDE_SCENARIOS`: comma-separated CrowdSec scenarios that are never reported, in addition to the built-in
  exclusions; a short name (`http-probing`) matches every author, a full name (`author/name`) only that author (optional)

Generated next to it: `~/.secrets/ssh_trusted_seen.txt` (IPs with a successful SSH login, entries expire after
60 days).

Runtime data next to the scripts (ignored by git): `reports.csv`, `abuseipdb_cron.log`, `.state/`.

## Usage

```bash
./abuseipdb_send.sh                  # normal run (what cron does)
./abuseipdb_send.sh --dry-run        # no upload, no watermark, no trusted-IP list update
./abuseipdb_send.sh --force          # skip the "last report < 20 h ago" guard (use deliberately)
python3 abuseipdb_report.py --validate reports.csv   # check a CSV against the AbuseIPDB rules
python3 abuseipdb_report.py --help
```

## Safeguards

- **Local detections only** (`kind == "crowdsec"`): addresses from blocklists are other people's observations and are
  never reported.
- **Age**: nothing older than 60 days is reported.
- **Address type**: private, reserved, CGNAT and other non-global addresses are never reported.
- **Scenarios**: those with a history of false alarms are excluded; a weak signal alone does not qualify.
- **Unknown scenarios** are never reported, only skipped and listed in the log (`unknown scenario ...`); open an issue
  with the name and the maintainer will check what it detects before adding it.
- **Your exclusions**: `EXCLUDE` entries of the config file, and **SSH auto-trust**: any address with a successful SSH
  login in the last 60 days (an IPv6 login trusts its whole /64, see `SSH_TRUST_IPV6_PREFIX`).
- **Own addresses**: the server's own public addresses are always excluded.
- **Comment**: fixed English sentences only, ASCII, at most 1,024 bytes, never the reported IP, the server's host name
  or its domain names (checked a second time against your `OWN_NAME_MARKERS`).
- **Double validation**: every file is validated twice (generator and wrapper) and a failing file never replaces the
  previous one.

Details: [docs/COMPLIANCE.md](docs/COMPLIANCE.md) (policy mapping and every safeguard) and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (validation and error handling).

## Tests

The tests use mocks: they never contact AbuseIPDB or ntfy and need no API key.

```bash
python3 -m unittest discover -v tests     # generator tests run anywhere; wrapper tests need Linux
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): data flow, time windows, state files, exit codes, error handling
- [docs/COMPLIANCE.md](docs/COMPLIANCE.md): AbuseIPDB policy and API limits mapped to the implementation
- [docs/OPERATIONS.md](docs/OPERATIONS.md): cron, monitoring, alerts, troubleshooting, first-run checklist
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md): setup, tests, hooks, language rules, workflow, versioning, standing checks
- [CHANGELOG.md](CHANGELOG.md): version history
- [CONTRIBUTING.md](CONTRIBUTING.md): how to report a bug, propose a change and send a pull request
- [SECURITY.md](SECURITY.md): how to report a vulnerability privately
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md): how we treat each other (Contributor Covenant 2.1)
- [AGENTS.md](AGENTS.md): rules for AI coding agents working on this repository (English only)

All documents exist in English and Polish (`README.pl.md`, `docs/pl/`), except `AGENTS.md` (English only).

## Contributing and security

Forks, bug reports and pull requests are welcome (MIT license), in English and also when written with an AI
assistant. Especially useful:

- how the tool ran on another distribution, web server or CrowdSec version;
- a CrowdSec scenario that is skipped as unknown;
- corrections to the documentation.

Start with [CONTRIBUTING.md](CONTRIBUTING.md); coding agents read [AGENTS.md](AGENTS.md).\
A pull request that weakens a safeguard needs a very good reason.\
Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md), not in a public issue.

## License and author

[MIT license](LICENSE).

Copyright (c) 2026 Arkadiusz Polak.

<github@arkadiuszpolak.pl> | [arkadiuszpolak.pl](https://arkadiuszpolak.pl)
