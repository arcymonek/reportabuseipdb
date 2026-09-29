**English** | [Polski](CONTRIBUTING.pl.md)

# Contributing

Thank you for helping. This tool publishes data under its users' AbuseIPDB accounts, and a false report can get an
account suspended. Every change is judged first by one question: can it make the tool report something that is not a
real, locally observed attack, or reveal something about the operator? Convenience comes second.

## Reporting a bug

Open an issue with the bug report template. Include the version (`./abuseipdb_send.sh --version`,
`python3 abuseipdb_report.py --version`), your distribution, the CrowdSec and Python versions, and the relevant lines
of `abuseipdb_cron.log` or of a `--dry-run`.

Before you paste anything, remove your own domain and host names, your home directory path, your ntfy topic and your
own IP addresses. Never paste the API key or the config file. A vulnerability goes to [SECURITY.md](SECURITY.md), not
to a public issue.

## Proposing a change

For anything larger than a typo, open an issue first and describe the problem. Changes to the safeguards listed in
[docs/COMPLIANCE.md](docs/COMPLIANCE.md) are discussed before any code is written. A pull request that weakens one of
them (the 60-day filter, non-global addresses, excluded or weak scenarios, SSH auto-trust, exclusions, own addresses,
the local-alerts-only data source, the comment rules, the double validation, the watermark, the 20 h guard, the API
key handling) needs a very good reason and will be reviewed with that in mind.

A new CrowdSec scenario in `CATEGORY_MAP` needs the weakest category set that the log really supports and a test; see
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md). If you only want to stop reporting a scenario on your own server, use
`EXTRA_EXCLUDE_SCENARIOS` in your config instead.

## Pull requests

- One topic per pull request. Keep the code simple and readable; comments explain why, not only what.
- Code, comments, messages, tests and commit messages are English only. The report templates (`TPL_*`) must stay
  English because they are published on AbuseIPDB.
- Documentation exists in English and Polish (`README.md` and `README.pl.md`, `docs/X.md` and `docs/pl/X.md`, and so
  on). Update both. If you cannot write Polish, update the English file and say so in the pull request; the maintainer
  adds the translation.
- Do not raise the version. Describe your change under "Unreleased" in `CHANGELOG.md` (and `CHANGELOG.pl.md` if you
  can); the maintainer raises the version when merging.
- Tests use only fake data: reserved addresses (`203.0.113.0/24`, `198.51.100.0/24`, `2001:db8::/32`) or well-known
  public resolvers as attacker stand-ins, `example.org` / `.example` / `.test` names, fake keys and topics. Never a real
  API key, never a real upload to AbuseIPDB, never your own host names or addresses.
- A refactor must keep the generated CSV byte-for-byte identical for the same `--input-json`. After changing a
  safeguard, break it on purpose and check that a test fails (a mutation check, see
  [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)).

## Running the tests

```bash
python3 -m unittest discover -v tests     # generator tests run anywhere; wrapper tests need Linux
git config core.hooksPath tools           # optional: the pre-commit hook (syntax, EN/PL pairs, versions, privacy scan)
```

The GitHub Actions workflow runs the whole suite on Ubuntu for every pull request; it has to pass before a merge.

## License

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE) of this project.
