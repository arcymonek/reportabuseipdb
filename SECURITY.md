**English** | [Polski](docs/pl/SECURITY.md)

# Security policy

## How to report a vulnerability

Do not open a public issue or discussion. Use one of two ways:

- **GitHub (preferred):** the "Security" tab, "Report a vulnerability". Such a report is private.
- **E-mail:** <github@arkadiuszpolak.pl>. E-mail is not encrypted, so do not send anything secret that way.

You may write in English or in Polish. Please include:

- what happens and what the impact could be;
- the version it affects (`./abuseipdb_send.sh --version`);
- if you can, how to reproduce it with fake data (`python3 abuseipdb_report.py --input-json file.json --dry-run`,
  where `file.json` has the shape of the output of `cscli alerts list -o json`).

Do not include real API keys, ntfy topics, your own domain and host names, your own IP addresses or other people's
data. Do not test the problem with a live upload to AbuseIPDB: every attempt publishes reports under someone's account.

## What to expect

This is a hobby project maintained by one person: expect a reply within about a week. A confirmed problem is fixed in
a new version and credited in the changelog, unless you prefer to stay anonymous. Please do not publish the details
before the fix is out.

## What counts as a vulnerability

Anything that could make the tool:

- report an address that did not attack the server: the operator's own address or the server's own address, an
  address planted from outside (for example by the content of a request that breaks the structure of the CSV file),
  or an address taken from a source other than the local CrowdSec alerts;
- reveal something about the operator in a report comment or in an ntfy alert: a domain or host name, an own IP
  address, the installation path, the user name;
- publish credentials or personal data from someone else's request in a comment, in a case the described protection
  should catch (the section "Correctness of the data in a report" in [COMPLIANCE.md](docs/COMPLIANCE.md));
- leak the API key or the ntfy topic (logs, process list, repository, alerts);
- execute code or commands from the config file, the CrowdSec alerts or the API answers.

## What does not count as a vulnerability

- Actions of someone who already has access to the service account or to root on the server: such a person can read
  the API key anyway.
- Known limits of the protection of data in a comment, described in the same section of
  [COMPLIANCE.md](docs/COMPLIANCE.md) (for example a token in the request path itself is not masked).
- Consequences of a configuration that ignores the "Before you go live" list in [README.md](README.md) (for example
  CrowdSec behind a CDN sees the addresses of the CDN, so it reports them).
- A false alarm of a CrowdSec scenario, that is ordinary traffic taken for an attack: this is an ordinary bug, report
  it as an issue (the bug report form).
- Bugs in CrowdSec, AbuseIPDB, ntfy or curl: report them to their authors.

## Supported versions

Fixes land on the `main` branch, and only its latest version receives them. A tagged release may be older than `main`,
because releases are rare. To update, run `git pull --ff-only`; see the section "Updating and rolling back" in
[OPERATIONS.md](docs/OPERATIONS.md).
