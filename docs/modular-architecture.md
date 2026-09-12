# Modular architecture

Lead Generator exposes one Codex plugin and one MCP server. Internally, the
server is composed at startup from a small stable kernel, bundled Yaka plugins,
and optional private client extensions.

This follows the official model in which a plugin can combine skills, an MCP
server, structured results, and optional UI resources. Rendering tools remain
useful without UI and bind their selected resource through `_meta.ui.resourceUri`:
[plugin architecture](https://developers.openai.com/plugins/concepts/plugins) and
[MCP Apps UI](https://developers.openai.com/plugins/build/chatgpt-ui).

```text
Codex plugin
└── MCP bootstrap
    ├── kernel: contracts, composition, approvals, persistence, diagnostics
    ├── native plugins: objectives, memory, research, enrichment, CRM, UI
    └── private layer: packs, declarative contributions, isolated extensions
```

The kernel never imports a customer, sector, CRM, enrichment vendor, LinkedIn,
or named UI tab. It owns schema versions, exclusive-service resolution,
multi-contributor registries, immutable observations, approval policy,
persistence, diagnostics, and the MCP boundary. Native capabilities are bundled
in the product at first but each has an independent manifest and version.

## Composition

The effective order is product defaults, sector pack, client pack, then active
objective. The first release stores one compiled private client pack in
`~/.codex/leadgenerator/packs/active.yaml`; pack inheritance fields are retained
for future named sector layers. Theme and labels use the most specific value.
Tabs and panels merge by stable identifier. Exclusive capabilities such as
`ui.shell` never use last-writer-wins: exactly one configured provider must start.

Multi-provider registries are `research.sources`, `research.analyzers`,
`signals.detectors`, `score.dimensions`, `contacts.policies`, `workflow.steps`,
`ui.tabs`, `ui.panels`, and `exports`. The registry rejects duplicate identifiers.

## Trust boundary

- Yaka native Python runs in the MCP process and is covered by the native catalog
  integrity check.
- Client configuration and UI contributions contain no executable code.
- A client UI bundle runs as an MCP Apps iframe and receives no secret or database
  connection.
- Client business code uses a separate JSON-line process with a sparse
  environment and only declared capabilities.

Private extensions are trusted by the hash of every installed file, version,
runtime, and declared permissions. Any change invalidates approval and places the
extension in quarantine. A broken custom shell never triggers an invisible native
fallback; text tools and diagnostics remain available.

See [plugin-sdk.md](plugin-sdk.md), [ui-customization.md](ui-customization.md),
and [migrations.md](migrations.md).
