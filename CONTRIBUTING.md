**English** | [Polski](docs/pl/CONTRIBUTING.md)

# Contributing

Thank you for helping. This tool publishes data under its users' AbuseIPDB accounts, and a false report can get an
account suspended. Every change is judged first by one question: can it make the tool report something that is not a
real, locally observed attack, or reveal something about the operator? Convenience comes second.

| You want to | Go to |
|---|---|
| report a bug, or a scenario that is skipped as unknown | [Issues](https://github.com/arcymonek/reportabuseipdb/issues/new/choose), with the bug report form |
| suggest a change or ask a question | [Discussions](https://github.com/arcymonek/reportabuseipdb/discussions) |
| report a vulnerability | privately, see [SECURITY.md](SECURITY.md) |
| send code or documentation | a fork and a pull request, see "How to send a change" below |

## Reporting a bug

Open an issue with the bug report form. It asks for the version (`./abuseipdb_send.sh --version`,
`python3 abuseipdb_report.py --version`), the CrowdSec and Python versions, optionally your distribution, and the
relevant lines of `abuseipdb_cron.log` or of a `--dry-run`.

Before you paste anything, remove your own domain and host names, your home directory path, your ntfy topic and your
own IP addresses. Never paste the API key or the config file. A vulnerability goes to [SECURITY.md](SECURITY.md), not
to a public issue.

## Proposing a change

For anything larger than a typo, start a discussion (category Ideas) first and describe the problem. Changes to the
safeguards (the list is under "Hard safeguards" in [AGENTS.md](AGENTS.md), the reasons are in
[docs/COMPLIANCE.md](docs/COMPLIANCE.md)) are discussed before any code is written. A pull request that weakens one of
them needs a very good reason and will be reviewed with that in mind.

A new CrowdSec scenario in `CATEGORY_MAP` needs the weakest category set that the log really supports and a test; see
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md). If you only want to stop reporting a scenario on your own server, use
`EXTRA_EXCLUDE_SCENARIOS` in your config instead. If you want a scenario from a new CrowdSec collection to be reported,
open an issue with the bug report form and give its full name (`author/name`) and what it detects, instead of editing
the code on your server.

## Setting up and testing

You need Python 3.9 or newer and nothing else: the tool uses the standard library only, so please add no dependencies.
The CI runs the tests on Python 3.9 and on the newest Python, so avoid syntax from 3.10 and later (`match`, `X | Y` in
type hints).

```bash
python3 -m unittest discover -v tests     # generator tests run anywhere; wrapper tests need Linux
git config core.hooksPath tools           # optional: the two hooks described below
```

The wrapper tests need Linux (`flock`, GNU `date`, `jq`) and are skipped elsewhere. The GitHub Actions workflow runs the
whole suite on Ubuntu for every pull request; it has to pass before a merge.

The second command turns on two hooks. `pre-commit` checks syntax, the EN/PL pairs, versions and privacy, and, when a
commit changes `abuseipdb_report.py` or its test file, runs the generator tests (about 15 s). `commit-msg` applies the
same privacy scan to the commit message. The scan for your own host names reads `OWN_NAME_MARKERS` from your own config
(`~/.secrets/abuseipdb.conf`, or the file named by `ABUSEIPDB_CONFIG`); without such a file it is skipped with a note, so
read your diff for private data yourself.

The hook refuses a commit that changes only the English side of a documentation pair. Since you only write English,
commit with `EN_ONLY=1 git commit ...`: that skips this one rule and keeps every other check (the privacy scan
included). Do not use `--no-verify`, which switches all checks off. Fix a failing test rather than skipping it.

## How to send a change

You do not need write access or an invitation: work in a fork.

1. Fork the repository on GitHub (the "Fork" button), then clone **your fork**.
2. Create a branch for one topic, named by type and topic (`fix-`, `feat-`, `test-`, `ci-` or `docs-`):
   `git switch -c fix-short-description`.
3. Make the change, run the tests, commit with an English message (see "Pull requests" below).
4. Push the branch to your fork: `git push -u origin fix-short-description`.
5. On GitHub open a pull request from your branch to `main` of this repository (GitHub offers the button after the push).
6. The `tests` workflow runs on your pull request; the first run of a new contributor needs the maintainer's approval.
   Fix what fails by pushing more commits to the same branch.
7. Only the maintainer merges. You do not have to keep your branch current: if `main` moves, the maintainer deals with
   it. If you are asked to, or GitHub reports a conflict, add this repository as a second remote once
   (`git remote add upstream https://github.com/arcymonek/reportabuseipdb.git`) and run `git pull --rebase upstream main`.
   A rebase rewrites your branch, so push it to your fork with `git push --force-with-lease`.

The maintainer applies accepted changes on their own machine, adds the Polish translation and, when the program changes,
the version (see "Accepting a pull request" in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#accepting-a-pull-request)).
GitHub then marks your pull request as merged or closed. Regular contributors may later be invited to push branches to
this repository directly; merging stays with the maintainer.

## Pull requests

- One topic per pull request. Keep the code simple and readable; comments explain why, not only what. The pull request
  template has a checklist: fill it in honestly and say what you did not verify.
- Code, comments, messages, tests, commit messages, issues, pull requests and review comments are English only. The
  maintainer is Polish and may read your text in translation and answer in English; write plainly and you will be fine.
  The report templates (`TPL_*`) must stay English because they are published on AbuseIPDB.
- Documentation exists in English and Polish (`README.md` and `README.pl.md`, every other `X.md` and `docs/pl/X.md`, and so
  on). You only need to write the English file; you do not have to know Polish. The maintainer adds the Polish
  translation before merging, so please do not machine-translate it yourself.
- Do not raise the version. Describe your change under "Unreleased" in `CHANGELOG.md`; the maintainer decides
  whether the version rises (it does when the program changes) and updates `docs/pl/CHANGELOG.md` when merging.
- Tests use only fake data: reserved addresses (`203.0.113.0/24`, `198.51.100.0/24`, `2001:db8::/32`), `example.org` /
  `.example` / `.test` names, fake keys and topics. Reserved addresses are not "global", so the tool's own filter drops
  them; where a test needs an address that passes the filter, use a well-known public resolver as the attacker
  stand-in. Never a real API key, never a real upload to AbuseIPDB, never your own host names or addresses.
- A refactor must keep the generated CSV byte-for-byte identical for the same `--input-json`. After changing a
  safeguard, break it on purpose and check that a test fails (a mutation check, see
  [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)).

## Working with an AI assistant

AI-assisted contributions are welcome; the maintainer works that way too.

- Point your assistant at [AGENTS.md](AGENTS.md): it holds the rules (the safeguards that must not be weakened, what never
  to do, the conventions and a few non-obvious facts about the data) in the format that many coding agents read
  automatically. If yours does not, tell it to read the file first (Claude Code reads `CLAUDE.md`, so put the line
  `@AGENTS.md` in one).
- You stay responsible for what you submit: run the tests and the hook yourself, read the diff, and state in the pull
  request what you did and did not verify.
- Never let an assistant upload anything to AbuseIPDB or paste real keys, host names or addresses.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By taking part in issues, discussions and pull
requests you agree to it.

## License

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE) of this project.
