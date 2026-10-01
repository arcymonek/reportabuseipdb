<!--
Thank you for the pull request. Write in English. One topic per pull request.
Everything you write here is public: no real host names, domains, own IP addresses, ntfy topics or keys.
-->

## What changed and why

<!-- In plain language: the problem, and why this is the right fix. The reviewer may not read every line, so this text and the tests have to carry the argument. -->

## Checklist

- [ ] One topic; the tests pass locally (`python3 -m unittest discover -v tests`).
- [ ] I did not weaken a safeguard (see [AGENTS.md](https://github.com/arcymonek/reportabuseipdb/blob/main/AGENTS.md)), or I opened an issue and agreed on it first.
- [ ] If I touched a safeguard or code next to one, I broke it on purpose and a test failed (mutation check).
- [ ] A refactor or translation leaves the generated CSV byte-for-byte identical for the same `--input-json`.
- [ ] Tests use only fake data (reserved addresses, `example.org`, fake keys); nothing real, nothing uploaded to AbuseIPDB.
- [ ] Documentation is updated in English; I did not raise the version (describe the change under "Unreleased" in `CHANGELOG.md`; the maintainer translates and versions).
- [ ] If an AI assistant wrote part of this, I read the diff myself.

## What I did not verify

<!-- Be honest: untested platforms, Python versions, real data you did not have, behaviour you are unsure about. -->
