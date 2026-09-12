# Private extension authoring

Start from a shipped template and keep the extension below the private
`~/.codex/leadgenerator/extensions/<plugin-id>/` root. A plugin requires a
`plugin.yaml`, JSON Schema 2020-12 configuration schema, semantic version, SDK
range, declared capabilities and permissions, health behavior, and conformance
tests.

Business code uses the `executable` runtime and the line-delimited
`leadgenerator-plugin-host/v1` protocol. It runs with a sparse environment and
receives only validated configuration plus declared permission handles. It must
return versioned observations, evidence, score contributions, or actions; it
never writes PostgreSQL directly and cannot weaken approvals.

SDK 1.x rejects direct network and filesystem access. Supply external material
through a native/kernel source capability and pass only the bounded input needed
by the extension. Executable code starts only with a supported OS sandbox
(`sandbox-exec` on macOS or Bubblewrap on Linux); otherwise it is quarantined.

A custom UI uses `ui-bundle`, declares both `explorer` and `workspace`, embeds
autonomous HTML/CSS/JS, and communicates only through the MCP Apps bridge. It
receives no integration secret or database connection. CSP domains must be
declared as explicit HTTPS origins in the manifest.

After installing or changing any extension, preview its activation, show its
permissions and ownership consequence, obtain explicit confirmation, apply the
plan, restart MCP, and run composition diagnostics. A file or permission change
invalidates the recorded fingerprint and quarantines the extension.
