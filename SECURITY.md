**English** | [Polski](SECURITY.pl.md)

# Security policy

## What counts as a vulnerability here

Anything that could make the tool:

- report an address that did not attack the server (for example the operator's own address, a CDN, or an address
  taken from another source than the local CrowdSec alerts);
- publish something about the operator in a report comment (a domain or host name, an own address, a credential or
  personal data from a request);
- leak the API key or the ntfy topic (logs, process list, repository, alerts);
- execute code or commands from the config file, the CrowdSec alerts or the API answers.

## How to report

Do not open a public issue. Use GitHub's private vulnerability reporting ("Security" tab, "Report a vulnerability")
or write to <github@arkadiuszpolak.pl>. Describe the problem, the affected version and, if you can, how to reproduce
it with fake data. Do not include real API keys, topics or other people's data.

This is a hobby project maintained by one person: expect a reply within about a week. A confirmed problem is fixed
in a new version and credited in the changelog unless you prefer to stay anonymous.

## Supported versions

Only the latest version on the `main` branch receives fixes.
