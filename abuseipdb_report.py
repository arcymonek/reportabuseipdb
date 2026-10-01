#!/usr/bin/env python3
"""
abuseipdb_report.py - v3.6.26

Generates a bulk CSV of AbuseIPDB reports from LOCALLY detected CrowdSec alerts.
It sends NOTHING itself; sending is done by abuseipdb_send.sh (see README.md).
`--validate FILE` checks a finished CSV against the AbuseIPDB rules (no cscli,
no network).
`--after`/`--before` define strictly disjoint windows (by the alert `created_at`,
interval (after, before]) - abuseipdb_send.sh uses them so that consecutive runs
never overlap (double-reporting the same events) and never leave gaps.

=============================================================================
COMPLIANCE WITH THE AbuseIPDB POLICY (https://www.abuseipdb.com/reporting-policy)
=============================================================================
1. "Reports of attacks older than 60 days" - FORBIDDEN.
   -> Hard filter MAX_AGE_DAYS=60 on every row (we do not rely on --since,
      because --input-json may point at an old file).

2. "Report MUST contain a detailed description of the attack (port numbers,
   payloads, timestamps)".
   -> The comment contains: protocol + port, scenario names, event count,
      the full time range AND the real HTTP paths from the logs (payload).

3. FAQ: "limit your comments to only the key information... [avoid] email or
   IP address in the comment section".
   -> The comment does NOT contain the reported IP address, the hostname of our
      server or the names of our subdomains.

4. FAQ: "for continuous abuse... report the IP roughly once per day".
   -> One run per day (cron via abuseipdb_send.sh). Do NOT run it by hand on the
      same day as the cron run.

5. "Reports where the source address is likely spoofed (SYN/UDP floods)" -
   FORBIDDEN.
   -> Not applicable: all reported scenarios come from application logs
      (nginx/sshd), i.e. after an established TCP connection.

6. False reports = risk of account suspension.
   -> SEVEN independent safeguards, see the section below.

=============================================================================
SAFEGUARDS AGAINST REPORTING OUR OWN / AN INNOCENT IP
=============================================================================
1. Filter for private/reserved/loopback addresses (docker networks, VPN
   clients, CGNAT, documentation ranges).
2. EXCLUDE_SCENARIOS - scenarios with a documented history of false alarms on
   our own traffic (http-crawl-non_statics).
3. WEAK_ONLY_SCENARIOS - signals too weak to justify a report on their own.
4. Exclusion list - ENABLED BY DEFAULT: the EXCLUDE entries of the config file
   (~/.secrets/abuseipdb.conf) plus the legacy ~/.secrets/abuseipdb_exclude.txt,
   no need to remember a flag in cron.
5. SSH auto-trust - every IP address from which an SSH login SUCCEEDED in the
   last 60 days is unconditionally excluded. This is the most effective
   automatic defence against reporting the administrator's own, changing
   address. Addresses are additionally remembered in a file
   (DEFAULT_SSH_TRUST_FILE), because journald may be trimmed and the journal
   itself covered only ~15 days in practice instead of 60.
6. The server's own public addresses (from `ip addr`) are always excluded.
7. Unknown scenarios are never reported: only scenarios of the trusted author
   that are in CATEGORY_MAP or named after a real CVE id (see category_for()). A scenario for another service or the operator's own
   application must not be published as "hacking".

=============================================================================
CORRECTNESS OF THE COMMENT DATA (verified on real alerts, 2026-09-28)
=============================================================================
* Event count: the same HTTP request feeds several scenarios at once (e.g.
  http-probing + http-sensitive-files), so SUMMING events_count over all alerts
  inflated the counter (~20%, in extreme cases several times). We count:
  max( unique HTTP requests (timestamp+verb+path+host),
       max over scenarios of the SUM of events_count of that scenario's alerts ).
  This is a conservative value (lower bound), never exaggerated.
* Time: SSH events (journalctl) carry LOCAL time labelled as UTC in
  `events[].timestamp` (a +2 h shift in CEST). Therefore time is NOT taken from
  events but from the alert's `start_at`/`stop_at`/`created_at` (correct UTC).
* Protocol: from the events' `service` field (http/ssh), not from the scenario
  name.
* Sample requests: the HTTP paths come FROM THE ATTACKER, who may put anything in
  them - including our domain name (scanners paste the target host name into the
  path) or his own address ("wget http://<his IP>/x.sh"). A sample that contains
  an own-name marker, the reported IP or one of the server's own public addresses
  is OMITTED from the comment (the rest of the report is kept). Without this the
  validator below would reject the whole file because of one hostile path.

=============================================================================
OUTPUT VALIDATION (AbuseIPDB requirements: /bulk-report and /reporting-policy)
=============================================================================
Every generated file is checked by validate_csv_text() before it replaces the
previous one: headers, limits (10,000 lines, 8 MB, 1,024 B comment), global and
unique IP, categories 1-23, ISO 8601 date with a timezone (not older than 60
days and not from the future), ASCII comment without control characters,
without the reported IP and without our domain names. An error = exit code 2
and reports.csv is not replaced.

=============================================================================
DATA SOURCE
=============================================================================
`cscli alerts list -o json`. Deliberately NOT `cscli decisions list` - those
include bans from the CAPI (community blocklist) and external lists
(tor-exit-nodes, otx-webscanners), i.e. IPs that THIS server never observed.
Reporting them would be reporting someone else's detection. We additionally
filter on `kind == "crowdsec"` and drop `simulated` alerts.

The JSON structure was verified on real data (2026-08-27).
"""
import argparse
import csv
import io
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

SCRIPT_VERSION = "3.6.26"

# --- Hard limits from the AbuseIPDB documentation (bulk report) --------------
MAX_COMMENT_BYTES = 1024      # "Truncated after 1,024 characters (bytes)"
MAX_ROWS = 10_000 - 1         # "less than or equal to 10,000 lines, including the headings"
MAX_FILE_BYTES = 8 * 1024 * 1024   # "The CSV file must be under 8 MB"
MAX_AGE_DAYS = 60             # "Timestamps MUST NOT be older than two months"
# Printed at the start of every stderr line that says data was CUT OFF. This is an
# interface: abuseipdb_send.sh greps for it and sends an ntfy alert (the watermark
# still moves, so the cut-off alerts would otherwise be lost without anyone noticing).
TRUNCATED_MARKER = "[TRUNCATED]"
# Same idea for a safeguard that is NOT working although the run goes on (the journal cannot be
# read, so SSH auto-trust is missing; no `ip` program, so the own addresses are unknown; the trusted-IP
# list cannot be saved). abuseipdb_send.sh greps for it and sends an ntfy alert: a line in a log nobody
# reads is not enough for a safeguard that protects against reporting your own address.
SAFEGUARD_OFF_MARKER = "[SAFEGUARD-OFF]"
# The message of exit code 1. abuseipdb_send.sh treats code 1 as "nothing to report" ONLY when this
# line is present, because an interpreter failure outside main() (a syntax error, a missing module)
# also ends with code 1 and must not be mistaken for an empty day. Interface: do not reword.
NO_REPORTS_MESSAGE = "No qualifying reports - not writing a CSV."
MAX_CATEGORY_ID = 23          # https://www.abuseipdb.com/categories (1..23)

# Default paths - deliberately OUTSIDE the script directory (i.e. outside the
# git repository), next to the API key. This way the operator's own IP
# addresses and host names never end up in a repository.
# The single configuration file (see abuseipdb.conf.example). ABUSEIPDB_CONFIG
# overrides the location; --config overrides both.
DEFAULT_CONFIG_FILE = os.path.expanduser(
    os.environ.get("ABUSEIPDB_CONFIG") or "~/.secrets/abuseipdb.conf")
# DEPRECATED: replaced by the EXCLUDE keys of the config file, still honoured
# (added to the config entries, never instead of them) while migrating.
DEFAULT_EXCLUDE_FILE = os.path.expanduser("~/.secrets/abuseipdb_exclude.txt")
DEFAULT_SSH_TRUST_FILE = os.path.expanduser("~/.secrets/ssh_trusted_seen.txt")

# Fragments that must NEVER appear in a comment (our domains/host). Checked by
# validate_csv_text() as an independent control of the templates. Lower-case.
# Loaded from the OWN_NAME_MARKERS key of the config file by main(); an empty
# tuple means the check is INACTIVE (main() warns, abuseipdb_send.sh refuses to
# upload).
OWN_NAME_MARKERS = ()

CONFIG_KEYS = ("ABUSEIPDB_API_KEY", "NTFY_TOPIC", "NTFY_URL", "OWN_NAME_MARKERS", "EXCLUDE",
               "HTTP_PORTS", "EXTRA_EXCLUDE_SCENARIOS")
_CONFIG_KEY = re.compile(r"^[A-Z][A-Z0-9_]*$")
_INLINE_COMMENT = re.compile(r"\s#")

# =============================================================================
# !!! ENGLISH ONLY - DO NOT TRANSLATE !!!
# =============================================================================
# The templates below go DIRECTLY into the public AbuseIPDB database as the
# report text. AbuseIPDB is an English-language service - the comment is read
# by administrators and systems all over the world. A report in any other
# language is useless to the recipient.
#
# This is the ONLY place in this script that defines text sent outside. All
# other messages (stderr, --help) are for the administrator in the terminal
# and never leave the server. The whole project is English now, so a slip into
# another language could happen anywhere; keep these constants reviewed.
#
# sanitize_comment() removes non-ASCII characters, but it does NOT detect
# non-English text written without diacritics. The only real guarantee is to
# keep these constants in English.
# =============================================================================
TPL_SOURCE = "Detected by CrowdSec IDS on a self-hosted server."
TPL_PROTO = "Target: {proto}."                        # protocol + port
TPL_DETECTION = "Triggered rules: {scenarios}."       # list of scenarios
TPL_EVENTS = "{count} matching log event{plural}"     # event counter
TPL_OBSERVED = "Observed"                             # when there is no event count
TPL_WINDOW = "between {first} and {last} (UTC)."      # time range
TPL_WINDOW_SINGLE = "at {first} (UTC)."               # single moment
TPL_TARGETS = "Sample requests: {targets}"            # HTTP paths (payload)
TPL_HTTP = "HTTP/HTTPS ({ports})"                     # HTTP protocol label
TPL_SSH = "SSH"                                       # SSH protocol label

# Protocol/port - satisfies the policy recommendation ("recommended port
# numbers") without revealing our subdomains. Source of precedence: the
# `service` field of CrowdSec events (http/ssh). CrowdSec does not record the
# port number, so the HTTP ports are what the operator declares with the
# HTTP_PORTS key of the config: the reverse proxy of a typical server accepts
# traffic on 80 and 443 (redirects to 443), hence the default "80/443". A server
# on other ports must set its own, or the public report states a wrong port.
DEFAULT_HTTP_PORTS = "80/443"
_HTTP_PORTS = re.compile(r"^\d{1,5}(/\d{1,5})*$")


def http_label(ports: str = DEFAULT_HTTP_PORTS) -> str:
    """'HTTP/HTTPS (ports 80/443)' or, for a single port, 'HTTP/HTTPS (port 8443)'."""
    word = "ports" if "/" in ports else "port"
    return TPL_HTTP.format(ports=f"{word} {ports}")


# Set from HTTP_PORTS by main(); the default keeps the CSV of existing installs unchanged.
HTTP_LABEL = http_label()

# Protocol keys: from the events' `service` field and, as a fallback when events carry no
# `service`, from the scenario name prefix. Unknown = no "Target" sentence (we do not guess).
PROTO_BY_SERVICE = {"ssh": "ssh", "http": "http"}
PROTO_BY_PREFIX = (("ssh-", "ssh"), ("http-", "http"), ("nginx-", "http"))


def proto_label(key: str) -> str:
    return TPL_SSH if key == "ssh" else HTTP_LABEL

# --- Mapping CrowdSec scenario -> AbuseIPDB categories ------------------------
# Categories per https://www.abuseipdb.com/categories:
#   4=DDoS  9=Open Proxy  14=Port Scan  15=Hacking  16=SQL Injection
#   18=Brute-Force  19=Bad Web Bot  20=Exploited Host  21=Web App Attack  22=SSH
# Rule: do NOT assign a category stronger than what is actually visible in the
# log (overestimation = a false report in the eyes of the policy).
CATEGORY_MAP = {
    # --- SSH ---
    "ssh-bf": "18,22",
    "ssh-bf_user-enum": "18,22",
    "ssh-slow-bf": "18,22",
    "ssh-slow-bf_user-enum": "18,22",
    "ssh-time-based-bf": "18,22",
    "ssh-time-based-bf_user-enum": "18,22",
    "ssh-refused-conn": "14,22",
    "ssh-generic-test": "14,22",
    "ssh-cve-2024-6387": "15,22",
    # --- HTTP: scanning / reconnaissance ---
    "http-probing": "14,21",
    "http-technology-probing": "14,21",
    "http-generic-test": "14,21",
    "http-sensitive-files": "15,21",
    "http-path-traversal-probing": "15,21",
    "http-admin-interface-probing": "15,21",
    "http-sap-interface-probing": "15,21",
    "http-wordpress-scan": "19,21",
    "http-backdoors-attempts": "15,21",
    "http-bad-user-agent": "19",
    # --- HTTP: specific attack classes ---
    "http-sqli-probing": "16,21",
    "http-xss-probing": "15,21",
    "http-cve-probing": "15,21",
    "http-generic-bf": "18,21",
    # 14, NOT 9: category 9 ("Open proxy, open relay, or Tor exit node") says
    # that the reported host IS an open proxy. Here someone was only checking
    # (CONNECT) whether OUR server is one - i.e. scanning for a vulnerable
    # service.
    "http-open-proxy": "14",
    "http-w00tw00t": "14,21",
    # 4 (DDoS) deliberately NOT used: exceeding a rate limit is not a
    # volumetric attack, and an excessive category is a false report.
    "nginx-req-limit-exceeded": "21",
    # --- Specific exploits/CVEs ---
    "netgear_rce": "15,21",
    "thinkphp-cve-2018-20062": "15,21",
    "CVE-2017-9841": "15,21",
    "http-cve-2021-41773": "15,21",
    "http-cve-2021-42013": "15,21",
    "grafana-cve-2021-43798": "15,21",
    "jira_cve-2021-26086": "15,21",
}
# Used ONLY for a scenario of the trusted author whose name carries a CVE id (e.g.
# `crowdsecurity/http-cve-2024-1234`) that is not in the map: an exploit attempt against a web
# application is what such a scenario detects.
# Every other scenario that is not in the map is NOT reported (see category_for()).
DEFAULT_CATEGORY = "15,21"  # hacking + web app attack
# Only scenarios published under this author are trusted to mean what CATEGORY_MAP says
# ("someoneelse/ssh-bf" may detect anything).
TRUSTED_SCENARIO_AUTHOR = "crowdsecurity"
_CVE_ID = re.compile(r"cve-\d{4}-\d{4,}", re.IGNORECASE)

# --- Safeguard 2: scenarios NEVER reported -----------------------------------
# `http-crawl-non_statics` gave a false alarm THREE times on the operator's OWN
# traffic (bulk upload / WebDAV to ownCloud Infinite Scale) - incidents
# 2026-07-06, 2026-07-10 and 2026-07-15. Reporting legitimate WebDAV traffic is
# exactly the kind of false report for which an account may be suspended.
# The scenario stays in CrowdSec for banning, but does NOT reach the reports.
EXCLUDE_SCENARIOS = {"http-crawl-non_statics"}
# The operator's own additions (EXTRA_EXCLUDE_SCENARIOS in the config, set by main()): a
# scenario that gave false alarms on THEIR traffic. It can only ADD exclusions, never remove
# one of the list above. A short name ("http-probing") matches every author, a full name
# ("author/name") only that author.
EXTRA_EXCLUDE_SCENARIOS = frozenset()
_SCENARIO_NAME = re.compile(r"^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)?$")

# --- Safeguard 3: signals too weak to justify a report on their own ----------
# A merely unusual user agent, without any attempt to access anything specific,
# is typical of passive research scanners (Censys/Shodan), which by design do
# not try to log in or exploit. An IP gets a PASS only if this is the ONLY
# reason; one more specific scenario next to it still qualifies it for a
# report. We deliberately do NOT do this with an ASN allowlist - an ASN only
# tells where someone rented a machine, not about intent (the same reason the
# project rejected an ASN allowlist for IP bans).
WEAK_ONLY_SCENARIOS = {"http-bad-user-agent"}


class ReportBuildError(RuntimeError):
    """An error that makes it impossible to build the report safely."""


class ConfigError(ReportBuildError):
    """A config file that cannot be trusted. Fail closed: a skipped EXCLUDE entry or a
    marker that never matches would silently switch a safeguard off, so the run stops."""


def short_scenario(scenario: str) -> str:
    return scenario.split("/", 1)[-1]


def category_for(scenario: str):
    """AbuseIPDB categories for a CrowdSec scenario (the full name, with the author
    prefix), or None when we do not know what it detects. None means the alert is
    NOT reported.

    Why not a default category for everything unknown: a scenario for postfix, MySQL
    or the operator's own application would go to the public database as "hacking +
    web application attack", which is a false report (a stronger claim than the log
    supports). Only scenarios of the trusted author that are in CATEGORY_MAP or are
    named after a real CVE id are reported. A CVE id in the name of ANOTHER author's
    scenario is not enough: "someone/postfix-cve-2024-1234" is not a web application
    attack, and the default category would claim it is. A scenario of another author
    is reported only when the operator adds it to CATEGORY_MAP under its FULL name
    ("author/name"): a deliberate opt-in, since we cannot know what it detects."""
    if "/" in scenario and scenario in CATEGORY_MAP:   # opt-in by full name
        return CATEGORY_MAP[scenario]
    author, sep, name = scenario.partition("/")
    if not sep or author != TRUSTED_SCENARIO_AUTHOR:
        return None
    if name in CATEGORY_MAP:
        return CATEGORY_MAP[name]
    if _CVE_ID.search(name):
        return DEFAULT_CATEGORY
    return None


def proto_for(scenarios, services=()):
    """Protocol(s) attacked by a given IP, or None when it cannot be determined.
    Returns ALL matching ones, because one address may try both SSH and HTTP in
    the same window - giving only the first would hand the reader information
    that contradicts the list of rules (e.g. 'Target: HTTP' next to `ssh-bf`).
    The events' `service` field first, the scenario prefix as a fallback; never
    a default 'HTTP' - an unknown protocol must not get a false label."""
    keys = []
    for svc in sorted(services):
        key = PROTO_BY_SERVICE.get(svc)
        if key and key not in keys:
            keys.append(key)
    if not keys:
        for sc in sorted(scenarios):
            for prefix, key in PROTO_BY_PREFIX:
                if sc.startswith(prefix) and key not in keys:
                    keys.append(key)
                    break
    # The order of the labels follows the keys: sorted services ("http" before "ssh").
    return " + ".join(proto_label(k) for k in keys) if keys else None


def truncate_bytes(text: str, limit: int) -> str:
    """Truncates text to `limit` BYTES (not characters) without splitting a
    multi-byte character. A plain text[:1024] could let a string >1024 B pass."""
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text
    return raw[:limit].decode("utf-8", errors="ignore")


# Something that looks like an e-mail address (personal data, see leaks_identity()).
_EMAIL_LIKE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Characters at which Excel/LibreOffice interprets a cell as a formula.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_comment(text: str) -> str:
    """Hard safeguard for the comment text sent to AbuseIPDB.

    LANGUAGE: enforces pure ASCII - if someone pastes text with diacritics into
    a template in the future (or an attacker sends a URL with diacritics), the
    CSV gets a version without non-ASCII characters.

    SECURITY: HTTP paths come FROM THE ATTACKER, so we remove control
    characters (they could break the CSV structure) and neutralise formula
    prefixes (CSV injection when the file is opened in a spreadsheet).

    CSV PARSING ON THE AbuseIPDB SIDE: the bulk-report page says that
    "backslashes and quotes require escaping", i.e. its parser treats a backslash
    as an escape character. Python's csv module writes a quote as "" and leaves a
    backslash alone, so a backslash right before a quote (or at the very end of the
    field, before the closing quote) could make AbuseIPDB read the field wrongly.
    A double quote is therefore written as %22 (nginx logs it as \\x22 anyway) and a
    trailing backslash as %5C. Backslashes elsewhere stay: they are evidence
    ("\\x5Cthink\\x5Capp" is a real ThinkPHP exploit path).
    """
    ascii_only = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in text)
    cleaned = " ".join(ascii_only.split()).replace('"', "%22")
    if cleaned.endswith("\\"):
        cleaned = cleaned[:-1] + "%5C"
    if cleaned.startswith(_FORMULA_PREFIXES):
        cleaned = "'" + cleaned
    return cleaned


def load_config(path):
    """Parses the config file: KEY=value lines, a line starting with '#' is a
    comment, blank lines are ignored. The file is read as plain text and NEVER
    executed. Returns {KEY: [values in file order]}; a missing file gives {}.
    The secrets in it (API key, ntfy topic) are not used by the generator and
    are never printed.
    A malformed line, an unknown key, a comment after a value or a file that exists but cannot be
    read raises ConfigError: each of them could quietly disable a safeguard (see ConfigError)."""
    cfg = {}
    if not path:
        return cfg
    try:
        mode = os.stat(path).st_mode
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        print(f"[info] config file {path} does not exist (own-name markers and "
              f"config exclusions are NOT active)", file=sys.stderr)
        return cfg
    except (PermissionError, UnicodeDecodeError, OSError) as exc:
        # Fail closed. The file EXISTS but cannot be used (wrong permissions, not UTF-8, ...): going on
        # without it would silently switch off the own-name check and every EXCLUDE entry.
        raise ConfigError(f"cannot read config file {path} ({type(exc).__name__}) - "
                          f"fix the file or its permissions (it must be UTF-8 text)")
    if mode & 0o077:
        print(f"[warn] config file {path} is accessible to other users "
              f"(mode {mode & 0o777:o}); it holds secrets - chmod 600", file=sys.stderr)
    problems = []
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not _CONFIG_KEY.match(key):
            problems.append(f"line {lineno}: not a KEY=value line")
            continue
        if key not in CONFIG_KEYS:
            # A typo (EXLUDE=...) would otherwise drop an exclusion without anyone noticing.
            problems.append(f"line {lineno}: unknown key {key}")
            continue
        if _INLINE_COMMENT.search(value):
            # "EXCLUDE=203.0.113.7 # home" is not a comment here: the whole text would become
            # the value, and the entry would never match. Comments must be on their own line.
            problems.append(f"line {lineno}: {key} has a '#' comment after the value "
                            f"(put comments on their own line)")
            continue
        if value:
            cfg.setdefault(key, []).append(value)
    if problems:
        raise ConfigError(f"config file {path} is invalid - " + "; ".join(problems))
    return cfg


def config_markers(cfg):
    """OWN_NAME_MARKERS values (comma-separated, may repeat) as a lower-case tuple.
    A marker with a space or '#' inside is refused (ConfigError): domain and host names
    have neither, so such a marker is a typo that would never match anything."""
    parts = ",".join(cfg.get("OWN_NAME_MARKERS", [])).split(",")
    markers = tuple(dict.fromkeys(p.strip().lower() for p in parts if p.strip()))
    bad = [mk for mk in markers if "#" in mk or any(ch.isspace() for ch in mk)]
    if bad:
        raise ConfigError(f"OWN_NAME_MARKERS has {len(bad)} invalid entries (a space or '#' "
                          f"inside); list domain and host names separated by commas")
    return markers


def config_exclusions(cfg, path):
    """EXCLUDE values of the config as ip_network objects. An invalid entry raises
    ConfigError instead of being skipped: skipping it would make an address the
    operator wanted protected reportable."""
    nets = []
    for value in cfg.get("EXCLUDE", []):
        try:
            nets.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            raise ConfigError(f"{path} - invalid EXCLUDE entry: {value!r} "
                              f"(expected an IP address or a CIDR network)")
    if nets:
        print(f"[info] loaded {len(nets)} exclusion entries from the config file", file=sys.stderr)
    return nets


def config_http_ports(cfg):
    """HTTP_PORTS (the last value wins, like every single-value key): '80/443', '443' or
    '8080/8443'. Only digits and '/' can be written, so nothing but port numbers can
    reach the public comment through it."""
    values = cfg.get("HTTP_PORTS", [])
    if not values:
        return DEFAULT_HTTP_PORTS
    ports = values[-1]
    if not _HTTP_PORTS.match(ports) or not all(1 <= int(p) <= 65535 for p in ports.split("/")):
        raise ConfigError(f"HTTP_PORTS {ports!r} is invalid: port numbers 1-65535 separated by '/', "
                          f"e.g. 80/443")
    return ports


def config_extra_scenarios(cfg):
    """EXTRA_EXCLUDE_SCENARIOS values (comma-separated, may repeat) as a frozenset."""
    parts = ",".join(cfg.get("EXTRA_EXCLUDE_SCENARIOS", [])).split(",")
    names = frozenset(p.strip() for p in parts if p.strip())
    bad = sorted(n for n in names if not _SCENARIO_NAME.match(n))
    if bad:
        raise ConfigError(f"EXTRA_EXCLUDE_SCENARIOS has invalid names: {', '.join(bad)} "
                          f"(expected 'name' or 'author/name', separated by commas)")
    if names:
        print(f"[info] {len(names)} extra scenarios excluded by the config: "
              f"{', '.join(sorted(names))}", file=sys.stderr)
    return names


def load_exclusions(path):
    """Loads a list of IPs/CIDRs to skip unconditionally (one per line,
    '#' = comment). Put your own addresses here when you notice them in alerts."""
    nets = []
    if not path:
        return nets
    try:
        with open(path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                try:
                    nets.append(ipaddress.ip_network(line, strict=False))
                except ValueError:
                    # Fail closed, as for the EXCLUDE key (see config_exclusions).
                    raise ConfigError(f"{path}:{lineno} - invalid exclusion entry: {line!r}")
    except FileNotFoundError:
        print(f"[info] exclusion file {path} does not exist (normal if you never created it)",
              file=sys.stderr)
    except (PermissionError, UnicodeDecodeError) as exc:
        # Fail closed, as for the config file: an exclusion list that cannot be read is not "no list".
        raise ConfigError(f"cannot read the exclusion file {path} ({type(exc).__name__})")
    if nets:
        print(f"[info] loaded {len(nets)} exclusion entries from {path}", file=sys.stderr)
    return nets


_ISO_FRACTION = re.compile(r"\.(\d+)")
_ISO_OFFSET_NO_COLON = re.compile(r"([+-]\d{2})(\d{2})$")


def normalize_iso(text: str) -> str:
    """Rewrites an ISO 8601 timestamp so that datetime.fromisoformat() accepts it
    on Python 3.9 and later.

    Why: before Python 3.11 fromisoformat() rejects (a) a UTC offset without a
    colon, which is exactly what journalctl prints ('+0200'), and (b) a
    fraction of seconds that does not have 3 or 6 digits (CrowdSec may print 9).
    On 3.11+ both work natively. Only text is rewritten (so it can be tested on
    any Python version); whether the result is valid is still decided by
    fromisoformat()."""
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if ":" in text:  # only text with a time part; never touch a bare date
        text = _ISO_OFFSET_NO_COLON.sub(r"\1:\2", text)
    # Exactly 6 digits: pad a short fraction, cut a longer one (the same
    # truncation Python 3.11+ does).
    return _ISO_FRACTION.sub(lambda mo: "." + mo.group(1)[:6].ljust(6, "0"), text, count=1)


def parse_iso_datetime(text: str) -> datetime:
    """datetime.fromisoformat() of the normalised text. Invalid text still raises
    ValueError; a value without an offset stays naive (the caller decides what
    that means). The CSV validator deliberately does NOT use this: it must stay
    strict about the format we write ourselves."""
    return datetime.fromisoformat(normalize_iso(text))


# A full login success in the journalctl `-o short-iso` format, e.g.:
#   2026-09-13T16:03:28+0200 host sshd[123]: Accepted keyboard-interactive/pam for alice from 1.2.3.4 port 5 ssh2
# The message MUST start with "Accepted <method> for" - a loose `grep Accepted`
# would also catch "Invalid user Accepted from <IP>", i.e. an attacker using
# such a login name would exclude themselves from reports. With a second factor
# (publickey + TOTP) sshd logs the first step as "Partial publickey" (NOT matched
# here) and only the final keyboard-interactive step as "Accepted": only a
# COMPLETE login gives trust. "Accepted publickey" appears only on servers where
# the key alone is enough to log in.
# Methods: publickey, password, keyboard-interactive/<device> (pam on Linux, bsdauth
# elsewhere), hostbased and gssapi-* (Kerberos). "Accepted none" (a login without any
# authentication) is deliberately NOT trusted: on such a misconfigured server anyone logs in.
_SSH_ACCEPTED = re.compile(
    r"^(\S+)\s+\S+\s+\S+:\s+Accepted (?:publickey|password|keyboard-interactive(?:/\S+)?"
    r"|hostbased|gssapi-\S+) for \S+ from (\S+) port \d+")


def parse_ssh_accepted(text: str, now=None) -> dict:
    """Extracts {ip: last_login_time} from `journalctl -o short-iso` output.
    An unreadable timestamp = 'now' (safer: the address stays trusted)."""
    now = now or datetime.now(timezone.utc)
    seen = {}
    for line in text.splitlines():
        m = _SSH_ACCEPTED.match(line)
        if not m:
            continue
        try:
            ip = str(ipaddress.ip_address(m.group(2)))
        except ValueError:
            continue
        try:
            when = parse_iso_datetime(m.group(1))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except ValueError:
            when = now
        if ip not in seen or when > seen[ip]:
            seen[ip] = when
    return seen


def load_trust_store(path, now=None) -> dict:
    """Loads the persistent list of SSH-trusted IPs ('IP<TAB>ISO date'),
    skipping entries older than MAX_AGE_DAYS and corrupted lines."""
    now = now or datetime.now(timezone.utc)
    store = {}
    if not path:
        return store
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                try:
                    ip_str, when_str = line.split("\t", 1)
                    ip = str(ipaddress.ip_address(ip_str.strip()))
                    when = parse_iso_datetime(when_str.strip())
                    if when.tzinfo is None:
                        when = when.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                if now - when <= timedelta(days=MAX_AGE_DAYS):
                    store[ip] = max(when, store.get(ip, when))
    except FileNotFoundError:
        pass
    except OSError as exc:
        print(f"{SAFEGUARD_OFF_MARKER} cannot read {path} ({exc}) - remembered trusted IPs are "
              f"INACTIVE", file=sys.stderr)
    return store


def save_trust_store(path, store) -> bool:
    """Saves the list atomically with 0600 permissions (the administrator's addresses)."""
    tmp = f"{path}.tmp"
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("# IP<TAB>last successful SSH login (UTC) - generated by "
                    "abuseipdb_report.py, entries expire after 60 days\n")
            for ip, when in sorted(store.items()):
                f.write(f"{ip}\t{when.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')}\n")
        os.replace(tmp, path)
        return True
    except OSError as exc:
        print(f"{SAFEGUARD_OFF_MARKER} could not save {path} ({exc}) - trusted IPs will not "
              f"survive journal rotation", file=sys.stderr)
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


def harvest_ssh_trusted(days: int = MAX_AGE_DAYS, store_path=DEFAULT_SSH_TRUST_FILE,
                        persist: bool = True):
    """SAFEGUARD 5 - the most important automatic defence against reporting
    our own address.

    Collects the IP addresses from which someone SUCCESSFULLY logged in over
    SSH in the last `days` days ("Accepted ... for <user> from <IP>"). Such an
    address by definition belongs to the administrator (or someone who has the
    key and TOTP), not to an attacker - it must never end up in a report.

    This covers the main risk scenario: a changing ISP-pool address that was
    first used to work on the server and then tripped some CrowdSec threshold.

    The journal may be trimmed, so the result is merged with a persistent list
    (`store_path`); this way the protection does not depend on journal
    retention. `persist=False` (e.g. --dry-run) writes nothing.

    A log read error does NOT stop the run - we use the persistent list alone
    and warn loudly, because the other safeguards keep working.
    """
    now = datetime.now(timezone.utc)
    journalctl = shutil.which("journalctl") or "/usr/bin/journalctl"
    # The unit is "ssh" on Debian/Ubuntu and "sshd" on RHEL/Fedora/Arch/SUSE; naming both
    # is harmless (journalctl ignores a unit that does not exist) and keeps this
    # safeguard working on every distribution.
    cmd = [journalctl, "-u", "ssh", "-u", "sshd", "--since", f"-{days}d",
           "--grep", "Accepted", "-o", "short-iso", "--no-pager"]
    journal = {}
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        journal = parse_ssh_accepted(res.stdout, now)
        # Measured on journalctl 252: exit code 1 with an EMPTY stderr means only "no
        # matching entries". Missing permissions also give 1 (or 0 with a partial view),
        # but always with a message on stderr, as does a journalctl built without --grep.
        # Without this check such a failure was silent whenever the remembered list was
        # not empty, and new logins stopped being trusted.
        problem = (res.stderr or "").strip()
        if problem or res.returncode not in (0, 1):
            first = problem.splitlines()[0][:160] if problem else "no message"
            print(f"{SAFEGUARD_OFF_MARKER} journalctl returned code {res.returncode} ({first}) - new SSH "
                  f"logins may be MISSING from the auto-trust; the user needs the group 'adm' or "
                  f"'systemd-journal'", file=sys.stderr)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"{SAFEGUARD_OFF_MARKER} could not read the SSH logs ({exc}) - "
              f"using the remembered list only", file=sys.stderr)

    stored = load_trust_store(store_path, now)
    merged = dict(stored)
    for ip, when in journal.items():
        if ip not in merged or when > merged[ip]:
            merged[ip] = when

    if persist and store_path and merged != stored:
        save_trust_store(store_path, merged)

    if merged:
        print(f"[info] SSH auto-trust: {len(merged)} addresses with a successful login "
              f"(last {days} days; journal: {len(journal)}, remembered: {len(stored)}) "
              f"- they will never be reported", file=sys.stderr)
    else:
        print("[warn] SSH auto-trust: NO successful login found. "
              "Check that the user may read journalctl (group 'adm'/'systemd-journal'), "
              "otherwise this safeguard does not protect.", file=sys.stderr)
    return [ipaddress.ip_network(ip) for ip in sorted(merged)]


def harvest_local_addresses():
    """SAFEGUARD 6 - the server's own PUBLIC addresses (from `ip addr`).
    Traffic from our own IP (e.g. hairpin through the reverse proxy) must never
    end up in a report. No `ip` program (e.g. macOS) = empty list and a [SAFEGUARD-OFF] line, no error."""
    ip_bin = shutil.which("ip") or next(
        (p for p in ("/usr/sbin/ip", "/sbin/ip", "/usr/bin/ip") if os.path.exists(p)), None)
    if not ip_bin:
        print(f"{SAFEGUARD_OFF_MARKER} no `ip` program found - the server's own public addresses are "
              f"NOT excluded (list them as EXCLUDE entries, or install iproute2)", file=sys.stderr)
        return []
    try:
        out = subprocess.run([ip_bin, "-o", "addr", "show"], capture_output=True,
                             text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"{SAFEGUARD_OFF_MARKER} `ip addr` failed ({type(exc).__name__}) - the server's own "
              f"public addresses are NOT excluded (list them as EXCLUDE entries)", file=sys.stderr)
        return []
    nets = []
    for m in re.finditer(r"\binet6?\s+([0-9a-fA-F:.]+)/\d+", out):
        try:
            ip = ipaddress.ip_address(m.group(1))
        except ValueError:
            continue
        if ip.is_global:
            nets.append(ipaddress.ip_network(ip))
    if nets:
        print(f"[info] excluded {len(nets)} own public addresses of the server",
              file=sys.stderr)
    return nets


def is_reportable_ip(ip_str: str, exclusions) -> tuple:
    """Returns (True, None) if the IP may be reported, or (False, reason).
    Non-global addresses (private, loopback, reserved, CGNAT 100.64/10,
    documentation...) NEVER go to AbuseIPDB - it is a public database of
    internet addresses. `is_private` alone does NOT catch 100.64.0.0/10, hence
    `is_global`."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False, "invalid IP address"
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if (not ip.is_global or ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
        return False, "private/reserved address"
    for net in exclusions:
        if ip.version == net.version and ip in net:
            return False, "on the trusted/excluded list"
    return True, None


def parse_ts(ts: str):
    """Parses ISO8601 from CrowdSec ('2026-08-27T07:06:43Z') into an aware datetime."""
    if not ts or not isinstance(ts, str):  # missing, or e.g. a number: unusable
        return None
    try:
        parsed = parse_iso_datetime(ts)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def extract_ip(alert: dict):
    """The IP address from an alert. Scope 'Range' is deliberately NOT
    supported - the AbuseIPDB bulk CSV accepts single addresses, not CIDR."""
    src = alert.get("source") or {}
    # `or ""`: a JSON null gives None here, and None.lower() would crash the run.
    if (src.get("scope") or "").lower() == "ip" and (src.get("value") or src.get("ip")):
        return src.get("value") or src.get("ip")
    val = alert.get("value") or ""
    if val.lower().startswith("ip:"):
        return val.split(":", 1)[1]
    return None


def iter_event_meta(alert: dict):
    """Pairs (event, meta dict) from an alert."""
    for ev in alert.get("events") or []:
        yield ev, {m.get("key"): m.get("value") for m in (ev.get("meta") or [])}


# Names of query parameters whose VALUE is probably a credential. A short word is matched
# only as a whole word (letter boundaries), not as a substring: "keyword" must NOT match
# "key" (its value is often the attack payload we want to show), while "api_key" and
# "client-secret" must match. Compound names that are safe as substrings (PHPSESSID,
# sessionId, apikey, accessToken) are matched anywhere. Best effort by design: see
# redact_query().
_SENSITIVE_PARAM = re.compile(
    r"(?<![a-z])(?:token|key|secret|pass|passwd|password|pwd|sess|session|sid|auth|sig|"
    r"signature|jwt|code|otp|cred|credentials?|bearer|csrf|xsrf)s?(?![a-z])"
    r"|sessid|sessionid|apikey|accesstoken",
    re.IGNORECASE)


def redact_query(path: str) -> str:
    """Masks the VALUES of query-string parameters whose NAME looks like a credential
    ('?token=abc&x=1' becomes '?token=***&x=1'); everything else is kept, so the
    attack (an SQL injection or XSS payload in an ordinary parameter) stays visible.

    Why: the comment goes into a PUBLIC database. The request is usually the
    attacker's, but a false alarm on a real user's traffic would publish a token
    from that user's URL. Limits (best effort, not a guarantee): a secret in the
    PATH itself ('/share/<token>') or under an unusual parameter name is not
    recognised, and a percent-encoded name ('%74oken') is not decoded."""
    base, sep, query = path.partition("?")
    if not sep:
        return path
    parts = []
    for item in query.split("&"):
        name, eq, _value = item.partition("=")
        parts.append(f"{name}=***" if eq and _SENSITIVE_PARAM.search(name) else item)
    return base + "?" + "&".join(parts)


def extract_evidence(alert: dict) -> list:
    """Concrete evidence from events[].meta - HTTP paths with the method and the
    response code. This is the 'payload' required by the AbuseIPDB policy.
    We deliberately do NOT take `target_fqdn` - those are our subdomains, not
    data about the attacker. Values of credential-like query parameters are masked
    (redact_query)."""
    out = []
    for _, meta in iter_event_meta(alert):
        path = meta.get("http_path")
        if not path:
            continue
        verb = meta.get("http_verb", "")
        status = meta.get("http_status", "")
        out.append(f"{verb} {redact_query(str(path))}".strip() + (f" -> {status}" if status else ""))
    return out


def http_request_keys(alert: dict) -> set:
    """Identities of the HTTP requests in an alert. The same request may feed
    several scenarios at once - the key (timestamp, verb, path, host) lets us
    count it once. The host serves ONLY to tell requests apart, it does not go
    into the comment. The event timestamp is just an identifier here (not the
    time of the attack)."""
    keys = set()
    for ev, meta in iter_event_meta(alert):
        path = meta.get("http_path")
        if not path:
            continue
        keys.add((ev.get("timestamp", ""), meta.get("http_verb", ""), path,
                  meta.get("target_fqdn", "")))
    return keys


def event_services(alert: dict) -> set:
    """The set of `service` meta values (http/ssh) from the alert's events."""
    return {meta["service"] for _, meta in iter_event_meta(alert) if meta.get("service")}


def alert_window(alert: dict, created: datetime, cutoff: datetime):
    """(start, end) of the attack in UTC from the alert's `start_at`/`stop_at`.
    NOT from events[].timestamp: SSH events carry local time labelled as UTC
    (+2 h in CEST). Inconsistent/empty values (e.g. '0001-01-01T00:00:00Z')
    = fall back to `created_at` as a single moment."""
    start = parse_ts(alert.get("start_at"))
    stop = parse_ts(alert.get("stop_at"))
    if (start is None or stop is None or start > stop
            or stop > created + timedelta(minutes=5) or start < cutoff):
        return created, created
    return start, stop


def as_alert_list(data, source: str) -> list:
    """Checks that the parsed JSON is a list of alerts. `cscli` may print `null`
    instead of `[]` when there are no alerts, which means 'nothing to report',
    not an error. Any other shape is a format we do not understand: we stop
    instead of guessing (a guess could report the wrong thing)."""
    if data is None:
        return []
    if not isinstance(data, list):
        raise ReportBuildError(f"{source}: expected a JSON list of alerts, "
                               f"got {type(data).__name__}")
    return data


def fetch_alerts(since: str, limit: int):
    cscli = shutil.which("cscli") or "/usr/bin/cscli"  # cron has a poor PATH
    sudo = shutil.which("sudo") or "/usr/bin/sudo"
    # cscli needs to read /etc/crowdsec/local_api_credentials.yaml (root:root, 600).
    # An ACL granting the operator r-- on that file may get masked (by a chmod in
    # the package postinst, which recomputes the ACL mask) on every crowdsec
    # upgrade (seen with 1.7.8 -> 1.8.0). sudo with a NOPASSWD rule (a file in
    # /etc/sudoers.d/) survives a package upgrade, an ACL does not.
    # -n = do not ask for a password; in cron without a terminal it would only hang.
    # root needs no sudo (a minimal server or container may not even have it).
    runner = [cscli] if os.geteuid() == 0 else [sudo, "-n", cscli]
    try:
        raw = subprocess.check_output(
            runner + ["alerts", "list", "-o", "json", "--since", since, "--limit", str(limit)],
            text=True, timeout=120,
        )
    except FileNotFoundError:
        raise ReportBuildError(f"cscli ({cscli}) or sudo ({sudo}) not found")
    except subprocess.CalledProcessError as exc:
        raise ReportBuildError(f"cscli failed (exit code {exc.returncode}) - "
                               f"check 'sudo -n cscli alerts list' by hand (NOPASSWD may be missing in sudoers)")
    except subprocess.TimeoutExpired:
        raise ReportBuildError("cscli did not respond within 120 s")

    try:
        data = json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError as exc:
        raise ReportBuildError(f"cscli returned invalid JSON: {exc}")
    data = as_alert_list(data, "cscli output")

    if len(data) >= limit:
        print(f"{TRUNCATED_MARKER} fetched {len(data)} alerts = the --limit ({limit}). "
              f"Some alerts may have been cut off - consider a higher --limit.", file=sys.stderr)
    return data


def format_window(first: datetime, last: datetime) -> str:
    """The time range in the comment. When events span different DAYS it shows
    the full date on both sides - otherwise '2026-08-26T22:00:00Z..07:00:00Z'
    would look as if the attack ended before it began."""
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    if first == last:
        return TPL_WINDOW_SINGLE.format(first=first.strftime(fmt))
    if first.date() == last.date():
        return TPL_WINDOW.format(first=first.strftime(fmt), last=last.strftime("%H:%M:%SZ"))
    return TPL_WINDOW.format(first=first.strftime(fmt), last=last.strftime(fmt))


def decoded_views(text: str) -> list:
    """The text as written, then after one and after two rounds of percent-decoding (only the
    views that differ from the previous one). A request path is attacker-controlled and a scanner may
    encode the very characters we look for: 'www%2Eexample%2Eorg' hides a domain from a plain substring
    search, 'user%40mail.example' hides an e-mail address, '8%2E8%2E8%2E8' hides the reported IP. Two
    rounds because '%252E' (a double-encoded dot) is also seen in the wild. Never raises: a broken
    sequence ('%zz', a lone '%') stays as it is."""
    views = [text]
    for _ in range(2):
        decoded = unquote(views[-1])
        if decoded == views[-1]:
            break
        views.append(decoded)
    return views


def leaks_identity(text: str, ip: str, own_addresses=()) -> bool:
    """True if a comment fragment contains an own-name marker, the reported IP, one
    of the server's own public addresses or something that looks like an e-mail
    address. It mirrors what validate_csv_text() rejects (plus the own addresses and
    e-mails, which the validator only warns about), so a hostile sample can be
    omitted instead of failing the whole file. E-mails: the AbuseIPDB FAQ asks not
    to put personal information in comments, and a path may carry a real user's
    address. Case-insensitive, substring match, also on the percent-decoded text (see
    decoded_views); deliberately over-cautious: dropping one sample too many costs nothing."""
    views = decoded_views(text)
    lows = [view.lower() for view in views]
    if any(marker in low for marker in OWN_NAME_MARKERS for low in lows):
        return True
    if any(_EMAIL_LIKE.search(view) for view in views):
        return True
    forms = {ip}
    try:
        forms.add(str(ipaddress.ip_address(ip)))
    except ValueError:
        pass
    forms.update(str(net.network_address) for net in own_addresses)
    return any(form.lower() in low for form in forms if form for low in lows)


SKIP_NOT_LOCAL = "not a local detection (kind != crowdsec)"


def build_rows(alerts, exclusions, after=None, before=None, own_addresses=()):
    grouped = defaultdict(lambda: {
        "cats": set(), "reasons": set(), "evidence": [], "keys": set(),
        "services": set(), "scenario_events": defaultdict(int),
        "first": None, "last": None,
    })
    stats = defaultdict(int)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)

    for a in alerts:
        if a.get("kind") != "crowdsec":
            stats[SKIP_NOT_LOCAL] += 1
            continue
        if a.get("simulated"):
            stats["alert in simulation mode"] += 1
            continue

        raw_scenario = a.get("scenario") or "unknown"
        scenario = short_scenario(raw_scenario)
        if scenario in EXCLUDE_SCENARIOS:
            stats[f"scenario on the blacklist ({scenario})"] += 1
            continue
        if scenario in EXTRA_EXCLUDE_SCENARIOS or raw_scenario in EXTRA_EXCLUDE_SCENARIOS:
            stats[f"scenario excluded by the config ({raw_scenario})"] += 1
            continue
        categories = category_for(raw_scenario)
        if categories is None:
            stats[f"unknown scenario {raw_scenario} - not reported (to report it, add its full "
                  f"name 'author/name' to CATEGORY_MAP)"] += 1
            continue

        ip = extract_ip(a)
        if not ip:
            stats["no recognised IP (scope != Ip?)"] += 1
            continue

        ok, reason = is_reportable_ip(ip, exclusions)
        if not ok:
            stats[f"IP rejected: {reason}"] += 1
            continue

        ts = parse_ts(a.get("created_at"))
        if ts is None:
            stats["missing/unreadable created_at"] += 1
            continue
        # Window (after, before] by created_at: consecutive runs split time
        # without overlaps and without gaps (cscli --since drifts by fractions
        # of a second).
        if (after is not None and ts <= after) or (before is not None and ts > before):
            stats["outside the time window (--after/--before)"] += 1
            continue
        if ts < cutoff:
            stats[f"event older than {MAX_AGE_DAYS} days (AbuseIPDB policy)"] += 1
            continue
        if ts > now + timedelta(minutes=5):
            stats["timestamp from the future (clock skew?)"] += 1
            continue

        g = grouped[ip]
        g["cats"].update(c.strip() for c in categories.split(","))
        g["reasons"].add(scenario)
        g["evidence"].extend(extract_evidence(a))
        g["keys"].update(http_request_keys(a))
        g["services"].update(event_services(a))
        # Alerts of the SAME scenario are separate bursts (the bucket empties
        # after overflowing) - we sum them. Alerts of DIFFERENT scenarios
        # largely describe the SAME events - we take the max (see the
        # CORRECTNESS OF THE COMMENT DATA section in the docstring).
        g["scenario_events"][scenario] += a.get("events_count") or len(a.get("events") or [])
        first, last = alert_window(a, ts, cutoff)
        if g["first"] is None or first < g["first"]:
            g["first"] = first
        if g["last"] is None or last > g["last"]:
            g["last"] = last

    rows = []
    skipped_weak = []
    omitted_samples = 0
    for ip, g in grouped.items():
        if g["reasons"] <= WEAK_ONLY_SCENARIOS:
            skipped_weak.append(ip)
            continue

        reasons = sorted(g["reasons"])
        events = max(len(g["keys"]), max(g["scenario_events"].values(), default=0))
        # ReportDate = "latest observance" per AbuseIPDB; never from the future.
        g["last"] = min(g["last"], now)
        g["first"] = min(g["first"], g["last"])
        # The text is built ONLY from the TPL_* constants (the "ENGLISH ONLY"
        # block above). No IP address, no server hostname, no our subdomains.
        proto = proto_for(reasons, g["services"])
        parts = [TPL_SOURCE]
        if proto:
            parts.append(TPL_PROTO.format(proto=proto))
        parts.append(TPL_DETECTION.format(scenarios=", ".join(reasons)))
        parts.append(
            TPL_EVENTS.format(count=events, plural="s" if events != 1 else "")
            if events else TPL_OBSERVED
        )
        parts.append(format_window(g["first"], g["last"]))
        header = " ".join(parts) + " "

        comment = header.rstrip()
        seen, samples = set(), []
        for ev in g["evidence"]:
            if ev in seen:
                continue
            seen.add(ev)
            candidate = header + TPL_TARGETS.format(targets="; ".join(samples + [ev]))
            cleaned = sanitize_comment(candidate)
            # The path comes from the attacker: omit a sample that would reveal our
            # names/addresses or repeat the reported IP (see the docstring).
            if leaks_identity(cleaned, ip, own_addresses):
                omitted_samples += 1
                continue
            if len(cleaned.encode("utf-8")) > MAX_COMMENT_BYTES:
                break
            samples.append(ev)
            comment = candidate.rstrip()

        final_comment = truncate_bytes(sanitize_comment(comment), MAX_COMMENT_BYTES)
        # Truncation may cut "%5C" or a path right after a backslash; never end on one
        # (see sanitize_comment).
        final_comment = final_comment.rstrip("\\")
        # The last line of defence. Deliberately NOT an assert - an assert
        # disappears under `python3 -O`, and this is a security invariant, not
        # a debug aid.
        if not final_comment.isascii():
            raise ReportBuildError(f"comment for {ip} is not pure ASCII: {final_comment!r}")

        rows.append([
            ip,
            ",".join(sorted(g["cats"], key=int)),
            g["last"].strftime("%Y-%m-%dT%H:%M:%S+00:00"),  # ISO8601 with a timezone
            final_comment,
        ])

    for reason, count in sorted(stats.items()):
        print(f"[filter] skipped {count} alerts - {reason}", file=sys.stderr)
    if alerts and stats[SKIP_NOT_LOCAL] == len(alerts):
        # Every alert dropped by the `kind` filter: either the server really has only
        # non-local alerts, or this cscli version has no `kind` field, in which case the
        # tool would silently report nothing forever. Say so instead of staying quiet.
        print(f"[warn] ALL {len(alerts)} alerts were skipped because their `kind` is not "
              f"'crowdsec'. If this happens every day, check the JSON of "
              f"`cscli alerts list -o json`: this cscli version may not provide `kind`.",
              file=sys.stderr)
    if omitted_samples:
        print(f"[filter] omitted {omitted_samples} sample requests that contained an own name, "
              f"an IP address or an e-mail address (the reports themselves are kept)", file=sys.stderr)
    if skipped_weak:
        print(f"[filter] skipped {len(skipped_weak)} IPs - the only scenario is a weak signal "
              f"({', '.join(sorted(WEAK_ONLY_SCENARIOS))}): {', '.join(sorted(skipped_weak))}",
              file=sys.stderr)
    return rows


def enforce_size_limits(rows):
    """Enforces both file limits from the AbuseIPDB documentation: max 10,000
    lines (with the header) and max 8 MB."""
    if len(rows) > MAX_ROWS:
        print(f"{TRUNCATED_MARKER} {len(rows)} rows > limit {MAX_ROWS} - cutting to the limit.",
              file=sys.stderr)
        rows = rows[:MAX_ROWS]

    # We measure the REAL size after CSV serialisation, we do not estimate -
    # quoting and escaping of double quotes add bytes an estimate does not see,
    # and underestimating would mean a file rejected by AbuseIPDB.
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["IP", "Categories", "ReportDate", "Comment"])
    total = len(buf.getvalue().encode("utf-8"))

    for i, row in enumerate(rows):
        buf = io.StringIO()
        csv.writer(buf).writerow(row)
        total += len(buf.getvalue().encode("utf-8"))
        if total > MAX_FILE_BYTES:
            print(f"{TRUNCATED_MARKER} 8 MB limit exceeded at row {i} - cutting the file.",
                  file=sys.stderr)
            return rows[:i]
    return rows


def write_csv(handle, rows):
    writer = csv.writer(handle)
    writer.writerow(["IP", "Categories", "ReportDate", "Comment"])
    writer.writerows(rows)


_CSV_HEADERS = ("IP", "Categories", "ReportDate", "Comment")


def validate_csv_text(text: str, now=None):
    """An independent check of a finished CSV against the AbuseIPDB
    requirements (/bulk-report + /reporting-policy). It deliberately does NOT
    use the row-building functions - it parses the result from scratch to catch
    a generator bug. Returns (errors, warnings, number_of_data_rows). An error =
    the file must not be sent."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    errors, warnings = [], []

    if len(text.encode("utf-8")) >= MAX_FILE_BYTES:
        errors.append("file >= 8 MB")
    physical_lines = len(text.splitlines())
    if physical_lines > MAX_ROWS + 1:
        errors.append(f"{physical_lines} lines > limit {MAX_ROWS + 1} (with the header)")

    try:
        rows = list(csv.reader(io.StringIO(text, newline="")))
    except csv.Error as exc:
        return [f"invalid CSV: {exc}"], warnings, 0
    if not rows:
        return ["empty file"], warnings, 0
    header = rows[0]
    if sorted(header) != sorted(_CSV_HEADERS):
        return [f"headers {header} != {list(_CSV_HEADERS)}"], warnings, 0
    data = rows[1:]
    if not data:
        errors.append("no data rows")
    if physical_lines != len(rows):
        errors.append("number of lines != number of records (newline inside a field?)")

    col = {name: header.index(name) for name in _CSV_HEADERS}
    seen_ips = set()
    for n, row in enumerate(data, start=2):
        where = f"row {n}"
        if len(row) != len(_CSV_HEADERS):
            errors.append(f"{where}: {len(row)} fields instead of {len(_CSV_HEADERS)}")
            continue
        ip_s, cats_s = row[col["IP"]], row[col["Categories"]]
        date_s, comment = row[col["ReportDate"]], row[col["Comment"]]

        ok, reason = is_reportable_ip(ip_s, [])
        if not ok:
            errors.append(f"{where}: IP {ip_s!r} - {reason}")
        else:
            canon = str(ipaddress.ip_address(ip_s))
            if canon in seen_ips:
                errors.append(f"{where}: duplicate IP {canon} (AbuseIPDB: 'Duplicate IP')")
            seen_ips.add(canon)

        cats = [c.strip() for c in cats_s.split(",")]
        if not cats_s.strip() or not all(c.isdigit() and 1 <= int(c) <= MAX_CATEGORY_ID for c in cats):
            errors.append(f"{where}: categories {cats_s!r} outside the range 1..{MAX_CATEGORY_ID}")
        elif len(set(cats)) != len(cats):
            warnings.append(f"{where}: duplicate categories {cats_s!r}")

        try:
            when = datetime.fromisoformat(date_s.replace("Z", "+00:00"))
            if when.tzinfo is None:
                errors.append(f"{where}: ReportDate {date_s!r} has no timezone")
            elif when < cutoff:
                errors.append(f"{where}: ReportDate {date_s!r} older than {MAX_AGE_DAYS} days")
            elif when > now + timedelta(minutes=5):
                errors.append(f"{where}: ReportDate {date_s!r} is in the future")
        except ValueError:
            errors.append(f"{where}: ReportDate {date_s!r} is not ISO 8601")

        if not comment.strip():
            errors.append(f"{where}: empty comment")
        if len(comment.encode("utf-8")) > MAX_COMMENT_BYTES:
            errors.append(f"{where}: comment > {MAX_COMMENT_BYTES} B")
        if not comment.isascii():
            errors.append(f"{where}: comment contains non-ASCII characters")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in comment):
            errors.append(f"{where}: comment contains control characters")
        if comment.startswith(_FORMULA_PREFIXES):
            errors.append(f"{where}: comment starts with a spreadsheet formula character")
        if '\\"' in comment or comment.endswith("\\"):
            errors.append(f"{where}: comment has a backslash before a quote or at the end "
                          f"(AbuseIPDB treats a backslash as an escape character)")
        # The same percent-decoded views as leaks_identity(): an encoded name is still our name.
        views = decoded_views(comment)
        lows = [view.lower() for view in views]
        if ok and any(str(ipaddress.ip_address(ip_s)) in view for view in views):
            errors.append(f"{where}: comment contains the reported IP address (AbuseIPDB FAQ)")
        for marker in OWN_NAME_MARKERS:
            if any(marker in low for low in lows):
                errors.append(f"{where}: comment contains our own name ({marker})")
        if any(_EMAIL_LIKE.search(view) for view in views):
            warnings.append(f"{where}: comment looks like it contains an e-mail (check by hand)")
    return errors, warnings, len(data)


def validate_file(path: str):
    """validate_csv_text() for a file; an unreadable file = a validation error."""
    try:
        with open(path, "rb") as f:
            text = f.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"cannot read {path}: {exc}"], [], 0
    return validate_csv_text(text)


def report_validation(errors, warnings) -> None:
    for w in warnings:
        print(f"[validation-warn] {w}", file=sys.stderr)
    for e in errors:
        print(f"[VALIDATION-ERROR] {e}", file=sys.stderr)


def positive_int(text: str) -> int:
    """argparse type for --limit: 0 would make "limit reached" always true (a false [TRUNCATED]
    alert) and a negative number means nothing to cscli."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number")
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {SCRIPT_VERSION}")
    parser.add_argument("--since", default="24h", help="cscli time window (default 24h)")
    parser.add_argument("--after", metavar="ISO",
                        help="drop alerts with created_at <= ISO 8601 (e.g. 2026-09-28T03:30:00Z); "
                             "together with --before gives disjoint windows")
    parser.add_argument("--before", metavar="ISO",
                        help="drop alerts with created_at > ISO 8601 (the window is (after, before])")
    parser.add_argument("--limit", type=positive_int, default=5000,
                        help="cscli alert limit, a whole number >= 1 (default 5000)")
    parser.add_argument("--out", default="reports.csv", help="output CSV path")
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE, metavar="FILE",
                        help=f"config file with OWN_NAME_MARKERS and EXCLUDE entries, see "
                             f"abuseipdb.conf.example (default {DEFAULT_CONFIG_FILE}, "
                             f"or $ABUSEIPDB_CONFIG)")
    parser.add_argument("--exclude-file", default=DEFAULT_EXCLUDE_FILE,
                        help=f"DEPRECATED, use EXCLUDE in the config file. File with IPs/CIDRs to "
                             f"skip unconditionally, added to the config entries "
                             f"(default {DEFAULT_EXCLUDE_FILE})")
    parser.add_argument("--no-ssh-trust", action="store_true",
                        help="DISABLE auto-excluding addresses with a successful SSH login "
                             "(NOT recommended - it is the main defence against reporting your own IP)")
    parser.add_argument("--ssh-trust-file", default=DEFAULT_SSH_TRUST_FILE,
                        help=f"persistent list of SSH-trusted IPs, survives journal rotation "
                             f"(default {DEFAULT_SSH_TRUST_FILE})")
    parser.add_argument("--input-json", metavar="FILE",
                        help="read alerts from a JSON file instead of calling cscli (test mode)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the CSV to stdout instead of writing a file "
                             "(also does not save the trusted-IP list)")
    parser.add_argument("--validate", metavar="FILE",
                        help="only check a finished CSV against the AbuseIPDB rules (exit code 0 = "
                             "OK to send, 2 = error); calls neither cscli nor the network")
    args = parser.parse_args()

    after = before = None
    for name in ("after", "before"):
        raw = getattr(args, name)
        if raw is not None:
            val = parse_ts(raw)
            if val is None:
                parser.error(f"--{name}: invalid ISO 8601 date: {raw!r}")
            if name == "after":
                after = val
            else:
                before = val
    if after is not None and before is not None and after >= before:
        parser.error("--after must be earlier than --before")

    global OWN_NAME_MARKERS, HTTP_LABEL, EXTRA_EXCLUDE_SCENARIOS
    try:
        # Everything in the config is checked up front, in every mode: a broken entry
        # must stop --validate too, not only the generation.
        cfg = load_config(args.config)
        OWN_NAME_MARKERS = config_markers(cfg)
        cfg_exclusions = config_exclusions(cfg, args.config)
        HTTP_LABEL = http_label(config_http_ports(cfg))
        EXTRA_EXCLUDE_SCENARIOS = config_extra_scenarios(cfg)
    except ConfigError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)
    if not OWN_NAME_MARKERS:
        print("[warn] OWN_NAME_MARKERS is empty: the check that comments do not contain "
              "our own domain/host names is INACTIVE (set it in the config file)",
              file=sys.stderr)

    if args.validate:
        errors, warnings, count = validate_file(args.validate)
        report_validation(errors, warnings)
        if errors:
            print(f"[ERROR] {args.validate}: {len(errors)} errors - DO NOT SEND this file.",
                  file=sys.stderr)
            sys.exit(2)
        print(f"OK: {count} rows compliant with the AbuseIPDB requirements ({args.validate})")
        return

    try:
        if args.input_json:
            try:
                with open(args.input_json, "r", encoding="utf-8") as f:
                    alerts = as_alert_list(json.load(f), args.input_json)
            except (OSError, ValueError) as exc:  # unreadable file or invalid JSON
                raise ReportBuildError(f"cannot read alerts from {args.input_json}: {exc}")
        else:
            alerts = fetch_alerts(args.since, args.limit)

        own_addresses = harvest_local_addresses()
        exclusions = cfg_exclusions + load_exclusions(args.exclude_file) + own_addresses
        if args.no_ssh_trust:
            print("[WARNING] SSH auto-trust DISABLED by the --no-ssh-trust flag", file=sys.stderr)
        else:
            exclusions = exclusions + harvest_ssh_trusted(
                store_path=args.ssh_trust_file, persist=not args.dry_run)

        rows = enforce_size_limits(build_rows(alerts, exclusions, after, before, own_addresses))
    except ReportBuildError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)

    if not rows:
        # A non-zero exit code breaks an `&&` chain in cron, so nothing gets
        # sent for a file that contains only the header.
        print(NO_REPORTS_MESSAGE, file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        buf = io.StringIO(newline="")
        write_csv(buf, rows)
        errors, warnings, _ = validate_csv_text(buf.getvalue())
        report_validation(errors, warnings)
        sys.stdout.write(buf.getvalue())
        print(f"\n[dry-run] {len(rows)} rows - nothing written, nothing sent. "
              f"Validation: {'ERRORS (' + str(len(errors)) + ')' if errors else 'OK'}.",
              file=sys.stderr)
        if errors:
            sys.exit(2)
        return

    # Write to a temporary file -> validate -> atomic replace. A file with an
    # error NEVER replaces the previous reports.csv; exit code 2 breaks an `&&`
    # chain in cron, so nothing is sent.
    tmp_out = f"{args.out}.tmp"
    with open(tmp_out, "w", newline="", encoding="utf-8") as f:
        write_csv(f, rows)
    errors, warnings, _ = validate_file(tmp_out)
    report_validation(errors, warnings)
    if errors:
        os.remove(tmp_out)
        print(f"[ERROR] the generated file does not meet the AbuseIPDB requirements ({len(errors)} errors) "
              f"- not writing {args.out}.", file=sys.stderr)
        sys.exit(2)
    os.replace(tmp_out, args.out)

    src = f"file {args.input_json}" if args.input_json else f"window --since {args.since}"
    if after is not None or before is not None:
        src += f" (interval ({args.after or '-'} .. {args.before or '-'}]"
    print(f"Wrote {len(rows)} unique IPs to {args.out} "
          f"({os.path.getsize(args.out)} B, from {len(alerts)} alerts from {src}; validation OK)")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # Happens with `... --dry-run | head -5`: head closes the pipe before we
        # finish writing. It is not a script error. On shutdown Python tries to
        # flush stdout once more and would print a second, misleading
        # traceback - hence we swap stdout for /dev/null.
        # A pattern from the Python documentation (BrokenPipeError / note on SIGPIPE).
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        except OSError:
            pass
        sys.exit(0)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception:
        # Python ends an uncaught exception with exit code 1, and abuseipdb_send.sh
        # reads 1 as "no qualifying reports, nothing to send": it would move the
        # watermark and silently drop the whole time window. Exit code 2 = failure,
        # the wrapper then keeps the watermark, alerts via ntfy and retries the window.
        traceback.print_exc()
        print("[ERROR] unexpected internal error (traceback above) - nothing was sent.",
              file=sys.stderr)
        sys.exit(2)
