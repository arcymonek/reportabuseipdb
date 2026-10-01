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

For anything larger than a typo, open an issue first and describe the problem. Changes to the safeguards (the list is
under "Hard safeguards" in [AGENTS.md](AGENTS.md), the reasons are in [docs/COMPLIANCE.md](docs/COMPLIANCE.md)) are
discussed before any code is written. A pull request that weakens one of them needs a very good reason and will be
reviewed with that in mind.

A new CrowdSec scenario in `CATEGORY_MAP` needs the weakest category set that the log really supports and a test; see
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md). If you only want to stop reporting a scenario on your own server, use
`EXTRA_EXCLUDE_SCENARIOS` in your config instead.

## How to send a change

You do not need write access or an invitation: work in a fork.

1. Fork the repository on GitHub (the "Fork" button), then clone **your fork**.
2. Create a branch for one topic: `git switch -c fix-short-description`.
3. Make the change, run the tests, commit with an English message (see below).
4. Push the branch to your fork: `git push -u origin fix-short-description`.
5. On GitHub open a pull request from your branch to `main` of this repository (GitHub offers the button after the push).
6. The `tests` workflow runs on your pull request; the first run of a new contributor needs the maintainer's approval.
   Fix what fails by pushing more commits to the same branch.
7. Only the maintainer merges. To keep your branch current, add this repository as a second remote once
   (`git remote add upstream https://github.com/arcymonek/reportabuseipdb.git`) and run `git pull --rebase upstream main`.

The maintainer applies accepted changes on their own machine, adds the Polish translation and the version, and GitHub
then marks your pull request as merged or closed. Regular contributors may later be invited to push branches to this
repository directly; the pull request and the maintainer's merge stay the same.

## Pull requests

- One topic per pull request. Keep the code simple and readable; comments explain why, not only what.
- Code, comments, messages, tests and commit messages are English only. The report templates (`TPL_*`) must stay
  English because they are published on AbuseIPDB.
- Documentation exists in English and Polish (`README.md` and `README.pl.md`, `docs/X.md` and `docs/pl/X.md`, and so
  on). You only need to write the English file; you do not have to know Polish. The maintainer adds the Polish
  translation before merging, so please do not machine-translate it yourself.
- Do not raise the version. Describe your change under "Unreleased" in `CHANGELOG.md`; the maintainer decides
  whether the version rises (it does when the program changes) and updates `CHANGELOG.pl.md` when merging.
- Tests use only fake data: reserved addresses (`203.0.113.0/24`, `198.51.100.0/24`, `2001:db8::/32`) or well-known
  public resolvers as attacker stand-ins, `example.org` / `.example` / `.test` names, fake keys and topics. Never a real
  API key, never a real upload to AbuseIPDB, never your own host names or addresses.
- A refactor must keep the generated CSV byte-for-byte identical for the same `--input-json`. After changing a
  safeguard, break it on purpose and check that a test fails (a mutation check, see
  [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)).

## Language

Issues, pull requests, review comments and commit messages are in English, so that everyone can follow them. The
maintainer is Polish and may read your text in translation and answer in English; write plainly and you will be fine.

## Working with an AI assistant

AI-assisted contributions are welcome; the maintainer works that way too. Point your assistant at
[AGENTS.md](AGENTS.md): it holds the rules (the safeguards that must not be weakened, what never to do, the
conventions and a few non-obvious facts about the data) in the format that many coding agents read automatically. If
yours does not, tell it to read the file first (Claude Code reads `CLAUDE.md`, so put the line `@AGENTS.md` in one). You stay responsible
for what you submit: run the tests and the pre-commit hook yourself, read the diff, and state in the pull request what
you did and did not verify. Never let an assistant upload anything to AbuseIPDB or paste real keys, host names or
addresses.

## Running the tests

```bash
python3 -m unittest discover -v tests     # generator tests run anywhere; wrapper tests need Linux
git config core.hooksPath tools           # optional: the pre-commit hook (syntax, EN/PL pairs, versions, privacy scan)
```

The hook refuses a commit that changes only the English side of a documentation pair. Since you only write English,
commit with `EN_ONLY=1 git commit ...`: that skips this one rule and keeps every other check (the privacy scan
included). Do not use `--no-verify`, which switches all checks off.

The GitHub Actions workflow runs the whole suite on Ubuntu for every pull request; it has to pass before a merge.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By taking part in issues, discussions and pull
requests you agree to it.

## License

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE) of this project.
