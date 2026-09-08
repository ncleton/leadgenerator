# Contributing

Use Python 3.13, `uv`, and a feature branch. Keep implementation text in English
and the product interface in concise French. Use Conventional Commits.

Before opening a pull request, run the canonical validation command documented in
`AGENTS.md`.
Do not commit secrets, profiles, scraped datasets, exports, browser state, caches,
or generated coverage files. Update dependencies with
`uv lock --project plugins/leadgenerator`; never edit the lockfile manually.

Changes to paid enrichment, personal data, or CRM writes must preserve explicit
human confirmation at the exact point of action and include focused tests.
Run `python3 scripts/check_distribution_privacy.py` before publishing or sharing
the plugin. Generated guides must never contain seller or client profile values.

Contributions are currently accepted by invitation. Open a feature request before
starting a substantial change so the repository owner can confirm scope and the
required human-review boundaries.
