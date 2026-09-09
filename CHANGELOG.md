# Changelog

All notable changes to Lead Generator are documented here. The project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- Replace unrelated objective menus with a concise offer question, create a new
  objective directly from a clear selling intent, and let an explicit new-objective
  request override a stale conversation selection.
- Select a sole compatible objective without prompting, while explaining explicit
  geography conflicts and offering to create a separate objective.
- Require the seller website to be scraped and its sourced offer summary persisted
  before company search tools accept targeting filters.
- Require an active objective ID on every company search and persisted UI refresh,
  and store it in the lead payload, company relation, and immutable snapshot.
- Block lead sourcing until a persistent commercial objective is selected, and
  return a concrete setup example when none exists.
- Require the actual MCP Apps explorer render in `chat_ui` mode and prohibit
  claims that the interface was displayed when the render tool did not succeed.
- Require a Codex version that can load the plugin MCP tools in fresh processes,
  and update older local installations before installing the plugin.
- Run an isolated end-to-end MCP smoke test during installation against the live
  official company register, without requiring PostgreSQL.
- Recognize natural industrial prospecting requests without requiring the word
  "lead", and require the selected local establishment itself to belong to the
  requested activity section.
- Tell desktop users to restart the application so it reloads the installed
  plugin instead of keeping stale skills and MCP tool inventories.
## [0.4.0] - 2026-09-08

### Added

- Private local PostgreSQL memory for complete company cards, including
  SIREN/domain deduplication, retrieval and immutable snapshots.
- Private readable JSON export under `.agent-private/leadgenerator/database/`.
- Dedicated README documentation and badges for the guarded Enrow-to-FullEnrich
  professional contact enrichment cascade.

### Changed

- Plugin, Python package, commands, environment variables and local storage paths
  renamed consistently from `lead-studio` to `leadgenerator`.
- Public-facing product name normalized to **Lead Generator** and first-party
  attribution retained as **Yaka Performance**.
- New sourcing results exclude companies already present in private memory by
  default while continuing to update their stored records.

## [0.3.1] - 2026-09-08

### Added

- Professional Lead Generator logo and verified technology badges for GitHub.

### Changed

- Public product name changed from Lead Studio to Lead Generator.
- First-party author and copyright attribution changed to Yaka Performance.

## [0.3.0] - 2026-09-08

### Added

- Objective-scoped Lead Generator agents and document context.
- Interactive and text-only lead research experiences.
- Public company, contact, visual, and aerial research workflows.
- Guarded Enrow-to-FullEnrich enrichment and confirmed HubSpot synchronization.
- Cross-platform local installation and privacy validation.

[Unreleased]: https://github.com/ncleton/leadgenerator/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/ncleton/leadgenerator/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/ncleton/leadgenerator/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/ncleton/leadgenerator/releases/tag/v0.3.0
