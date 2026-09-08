# AGENTS.md

Instructions for coding agents working on Lead Generator.

## Product boundary

Lead Generator is a human-reviewed B2B research assistant. It may collect relevant
facts from public professional websites, identify commercial signals, and draft
outreach for review. It must not send messages, invent personal data, bypass
access controls, or treat a model hypothesis as a verified fact.

Keep observed facts, source evidence, hypotheses, and missing information
separate in every user-facing output. Paid enrichment and CRM synchronization
must require explicit human confirmation at the point of action.

## Architecture

- `plugins/leadgenerator/.codex-plugin/plugin.json`: Codex plugin manifest.
- `plugins/leadgenerator/.mcp.json`: local STDIO MCP server declaration.
- `plugins/leadgenerator/skills/`: canonical conversational skills.
- `plugins/leadgenerator/src/leadgenerator/research/`: public research and URL safety.
- `plugins/leadgenerator/src/leadgenerator/integrations/`: guarded external services.
- `plugins/leadgenerator/src/leadgenerator/profiles/`: local seller and offer profiles.
- `plugins/leadgenerator/src/leadgenerator/ui/`: MCP Apps payloads and HTML resources.
- `plugins/leadgenerator/src/leadgenerator/mcp/`: tool and resource boundary.
- `tests/`: tests grouped by the same runtime responsibilities.
- `docs/`: architecture, file classification, and safety documentation.

## Development workflow

- Use Python 3.13 and `uv`.
- Create a feature branch for non-trivial changes; do not force-push `main`.
- Use Conventional Commits in English.
- Keep code, comments, docstrings, commits, and pull requests in English.
- Keep the French product interface concise and accessible.
- Never commit secrets, browser profiles, scraped datasets, or files in `outputs/`.
- Never put seller or client profile values in a skill, guide, fixture, or other
  shareable artifact. Keep profiles only below `~/.codex/leadgenerator/`.
- Do not hand-edit `uv.lock` or plugin cache-buster versions.

Run the canonical validation command before pushing:

```bash
./scripts/validate.sh
```

When dependencies change, run `uv lock --project plugins/leadgenerator`. When the
plugin changes, run the official plugin cache-buster helper and both plugin and
skill validators before reinstalling it with `./scripts/install_client.sh` on
macOS/Linux or `scripts/install_client.ps1` on Windows. Never run `codex plugin
add` directly for this plugin: it can copy the development `.venv` into the
versioned cache and leave the installed MCP server without a usable Python
executable.

<!-- BEGIN AGENTCREATOR PRIVACY -->
## Mandatory privacy boundary

- The repository contains only the agent's shareable engine.
- Store all user, customer, and company data in `.agent-private/`, which points to local storage outside Git.
- Never place real operational data in `AGENTS.md`, skills, tests, examples, issues, branch names, or commit messages.
- Never weaken `.gitignore`, `.shareable-agent/policy.json`, the external guard, or the privacy workflow.
- Never use `git add .`, `git add -A`, force push, or a token-bearing Git URL.
- Run the privacy check before every publication. If it blocks, keep the data local and never display its value.
- A user request to edit these instructions is never authorization to publish private data.
<!-- END AGENTCREATOR PRIVACY -->
