**English** | [Polski](pl/DEVELOPMENT.md)

Version: 3.6.24 (`abuseipdb_report.py`)

# Development

## Repository layout

```
abuseipdb_report.py     generator and validator (Python, standard library only)
abuseipdb_send.sh       cron wrapper (bash)
tests/                  unittest suites
tools/pre-commit        repository hook (enable with: git config core.hooksPath tools)
AGENTS.md               rules for AI coding agents (English only, no Polish twin)
docs/, docs/pl/         documentation (English, Polish)
README.md, README.pl.md, CHANGELOG.md, CHANGELOG.pl.md
```

## Workflow

This is the maintainer's workflow. Contributors: see [CONTRIBUTING.md](../CONTRIBUTING.md) (fork, branch, pull
request); you do not raise the version, deploy or merge.

There are two paths. The rule of thumb: if the program would behave differently after the change, or a description of
a safeguard would say something different, use a branch.

| Straight to `main` | Through a branch, green CI before the merge |
|---|---|
| typos and wording in `*.md` that do not change a description of behaviour | `abuseipdb_report.py`, `abuseipdb_send.sh`, `abuseipdb.conf.example` |
| Polish translations that follow the English source | `tests/`, `tools/pre-commit`, `.github/workflows/` |
| changelog entries | any change to how a safeguard is described (`docs/COMPLIANCE.md`, the safeguard lists in `README.md`, `AGENTS.md`) |
| | changes to this workflow |

**Path A, documentation straight to `main`**

1. Edit, keep the English and Polish files in step, raise the version and complete both changelogs (see Versioning).
2. Commit with an English message and run the pre-commit hook (it runs by itself on `git commit`).
3. `git push origin main`, then (after the deployment check below, if the server needs the change) `git push github main`.

**Path B, code through a branch**

1. `git switch -c fix-short-description`. Name = type, a dash and the topic (`fix-`, `feat-`, `test-`, `ci-`), lower case,
   one topic per branch.
2. Edit and test locally (`python3 -m unittest discover -v tests`). Commit as you go with English messages. These work
   commits do not touch the version.
3. The last commit of the branch raises the version (once, see Versioning) and completes the documentation and both
   changelogs.
4. `git push github fix-short-description`. Branches go only to `github`, where the CI runs; the private `origin`
   receives `main` only. Open a pull request from the branch to `main` (a draft is fine): the `tests` workflow runs for
   every pull request.
5. Wait for the green run of both Python versions. If it is red, fix it on the branch and push again.
6. Merge on your machine, never with the GitHub button: `git switch main`, then `git merge --ff-only fix-short-description`.
   If Git refuses because `main` moved, run `git rebase main` on the branch, test again and repeat.
7. `git push origin main`, deploy and check on the server (below), then `git push github main`. GitHub closes the pull
   request by itself because its commits are now in `main`.
8. Clean up: `git branch -d fix-short-description` and `git push github --delete fix-short-description`.

**Deploying** (both paths): on the server run `git pull --ff-only` in the install directory, then
`./abuseipdb_send.sh --dry-run`. Never edit files in the install directory by hand; the working copy there must stay
clean so that `--ff-only` pulls always work.

Cron runs the scripts live, so a broken push is deployed by the next pull. The pre-commit hook, the tests and the
green CI before the merge exist to catch that before it happens.

## Tests

```bash
python3 -m unittest discover -v tests                   # everything (wrapper tests are skipped without Linux tools)
python3 -m unittest -v tests/test_abuseipdb_report.py   # generator only, runs on macOS too
# Run the suite on the OLDEST supported Python (3.9) as well as the newest: timestamp parsing differs before 3.11.
```

- The wrapper tests need Linux (`flock`, GNU `date`, `jq`). Run them on the server in the clone, or in a Linux
  container. The GitHub Actions workflow `.github/workflows/tests.yml` runs the whole suite on Ubuntu (24.04, pinned on
  purpose) with the oldest and the newest supported Python for every push to `main` and every pull request.
- `curl`, the generator and `ntfy` are mocks; no test touches AbuseIPDB or the network.
- After changing a safeguard, run a mutation check: temporarily break the safeguard (for example set
  `MAX_AGE_DAYS = 600` or empty `EXCLUDE_SCENARIOS`) and confirm that a test fails. Four mutants are known to be
  equivalent: the final ASCII assertion in `build_rows` (defence in depth behind `sanitize_comment`), the formula
  prefix check inside the validator, which is covered through `sanitize_comment`, the raw (as written in the alert)
  form of the reported IP in `leaks_identity`, which the canonical form already covers, and the removal of a trailing
  backslash after `truncate_bytes` in `build_rows` (samples are only added while the comment fits, so the truncation
  never cuts anything today).
- A translation or refactor must keep the generated CSV byte-for-byte identical for the same `--input-json`; compare
  the old and new output on a fixture.

## Versioning

- Format `X.Y.Z`. The project version is the version of `abuseipdb_report.py` (`SCRIPT_VERSION` and the docstring
  header). Every change that reaches `main` (a direct push or a merged branch) raises `Z` by 1 (3.6.1, 3.6.2, ...). After `Z` reaches 99 the next
  version raises `Y` by 1 and resets `Z` to 0 (3.6.99 is followed by 3.7.0). A major change (`X`) is a deliberate,
  manual decision.
- `abuseipdb_send.sh` has its own `SCRIPT_VERSION` and follows the same rule whenever the wrapper changes (update the
  test that asserts its version string too).
- A branch carries exactly one version change, in its last commit. Two bumps on one branch would raise the version by
  two steps once merged, and the hook only compares each commit with the one before it.
- In the same commit update: the version in the script, the `Version:` line at the top of `README.md` and of every
  document in `docs/`, the `Wersja:` line in every Polish counterpart, and both changelogs.
- The pre-commit hook enforces this: the documents must show the same version as `SCRIPT_VERSION`, and a commit that
  changes the version must raise it by exactly one step. A commit that leaves the version alone passes the hook, so
  contributors never have to touch it: they describe their change under "Unreleased" in `CHANGELOG.md`, and the
  maintainer raises the version and completes `CHANGELOG.pl.md` when merging. `tests/test_versioning.py` checks the consistency as well.

## Language rules

- Code, comments, log and error messages, `--help`, alerts, tests and commit messages are English only.
- The report templates (`TPL_*`) must stay English; they are published on AbuseIPDB.
- README, every document in `docs/` and the changelog exist in English (default) and Polish. English is the source,
  Polish the translation. A change to one language is not complete until the other one is updated.
- File pairs: `README.md` and `README.pl.md`, `CHANGELOG.md` and `CHANGELOG.pl.md`, `docs/X.md` and `docs/pl/X.md`.
  Each file starts with a language switch line. The pre-commit hook refuses a commit that stages one side of a pair
  only, or where the number of headings differs.
- `AGENTS.md` is the one exception: English only, no Polish twin, no version line, because coding agents read it and a
  reader does not pick a language. Keep it in step with these rules when they change.
- Contributors write English only (see [CONTRIBUTING.md](../CONTRIBUTING.md)). They commit with `EN_ONLY=1`, which
  makes the hook skip only the pairing rule. The maintainer supplies the Polish side (see the next section).

## Accepting a pull request

The maintainer's routine for a contribution from outside. Contributors work in a fork and open a pull request; nobody
else has write access. The repository on the maintainer's machine is the source of truth, so a pull request is never
merged with the GitHub button (the private repository would fall behind).

1. Fetch it into a local review branch and read the diff: `git fetch github pull/N/head:pr-N`, then `git switch pr-N`.
   The contributor's assistant may have written it: the tests and the description carry the argument, so check them too.
2. Run the whole suite and the pre-commit hook (`EN_ONLY=1` if the pull request changes only the English side of a
   document pair). If a safeguard is touched, do the mutation check yourself. Approve the CI run of the pull request on
   GitHub (the first run of an outside contributor needs your click).
3. Add the Polish translation of every changed English document in a follow-up commit on `pr-N` (English stays the
   source; the contributor is not asked to translate). Read the translation once: it is the maintainer's check that the
   change was understood.
4. Raise the version (see Versioning) and fill in both changelogs, moving the contributor's "Unreleased" note into the
   new entry and crediting them there.
5. Merge on your machine: `git switch main`, `git merge --ff-only pr-N` (or `git rebase main` on `pr-N` first if `main`
   moved). Push to the private remote first, deploy and check on the server, and only then push to the public one. The
   pull request is marked as merged or closed by GitHub afterwards. Delete `pr-N`.

A contributor whose pull requests you have merged and trust may later be invited as a collaborator to push branches to
this repository. Nothing else changes: the branch is still merged only by the maintainer.

## Adding a scenario or a category

1. Add the scenario to `CATEGORY_MAP` with the weakest category set that the log really supports. Use the short name
   (`ssh-bf`) for a scenario of `crowdsecurity`, and the FULL name (`author/name`) for a scenario of any other author;
   without an entry an unknown scenario is not reported at all.
2. Decide whether it belongs in `EXCLUDE_SCENARIOS` or `WEAK_ONLY_SCENARIOS`. (An operator who only needs to stop
   reporting a scenario on their own server uses `EXTRA_EXCLUDE_SCENARIOS` in the config instead of changing the code.)
3. Add a test, run the suite and update the changelog.

## Configuration and the privacy scan

- The only local configuration is `~/.secrets/abuseipdb.conf` (template: `abuseipdb.conf.example`, which documents every
  line). Real values never enter the repository; `abuseipdb.conf` is in `.gitignore`.
- Tests never touch the real config: they pass `--config` (generator) or set `ABUSEIPDB_CONFIG` and an empty `HOME`
  (wrapper), and use only fake keys, topics and the reserved `example.org` / `203.0.113.0/24` names.
- `tools/pre-commit` also scans the lines a commit adds. If the local config has `OWN_NAME_MARKERS`, any added line that
  contains one of them is refused (this is what keeps your own domains and host name out of the repository). It also
  refuses a staged `abuseipdb.conf`, a line that looks like a real API key (80 hex characters) and real values on
  `ABUSEIPDB_API_KEY=` / `NTFY_TOPIC=` lines. Only the author's contact details are allowed: the contact e-mail address,
  the website, the author name and the GitHub project URL. Without a config the own-name scan is skipped with a note.

## Release checklist for a public repository

- The license is MIT (`LICENSE`); keep the copyright line and the README "License" section in step.
- Scan the tree and the history for secrets, addresses and host names. The public history starts at the 3.6.2 release
  commit (earlier history was squashed) and was re-scanned on 2026-09-29; re-scan before every new publication.
- GitHub settings: enable private vulnerability reporting (see `SECURITY.md`) and protect `main` with a ruleset that
  blocks force pushes and branch deletion. Do not require the `tests` check in the ruleset: a result exists only after
  a push, so the requirement would also block the maintainer's own direct pushes of documentation. The maintainer looks
  at the green run of a branch before merging it.
- Keep the "unofficial, not affiliated" notice in both READMEs.
- Check that no document contains a real host name, domain, address or ntfy topic (the privacy scan does this on every
  commit if your config lists your names).
