# Codex and Claude hosts

The same MCP server, UI resources and skills support both hosts. Always discover
the tools available in the current session; MCP tool names may have a host-added
prefix. Do not call `mcp__codex_app`, `cua.*` or `automation_update` from Claude.

## Interface

Claude Desktop with MCP Apps can render the explorer and workspace. Use the
actual `render_lead_explorer`, `render_lead_workspace` and `render_lead_objectives`
tools; do not rebuild the product as an Artifact or claim a tool call displayed
an interface when the client reports it cannot render one. Claude Code's terminal
does not render HTML. In a terminal-only session explain that limit and offer
Claude Desktop or the user's explicit choice of `text_only`. Do not silently
change the shared presentation preference. A missing MCP server is an installation
problem, not authorization to replace the guarded workflow with generic tools.

## Browser

In Claude, discover Claude in Chrome, the graphical Code tab's built-in Browser
(Claude Browser / Claude Preview tools), or the actual Cowork browser. Read the
selected tool's documentation first. Chrome shares its existing signed-in profile;
the built-in Browser has a separate profile where the user can sign in directly.
Do not report "no browser" merely because Chrome tools are absent. In Codex, use the documented host
browser. Authentication belongs to that browser; a Codex LinkedIn session is not
automatically a Claude session. If no browser tool is available, report that only
connected LinkedIn research is unavailable; public professional research may
continue. Never launch a cookie importer or access saved browser credentials.

## Local data and schedules

Hosts share business data only when explicitly bound to the same
`LEADGENERATOR_HOME`. Read `storage.private_directory` from
`get_lead_interface_mode`; the same OS user alone does not establish shared data.
The default SQLite database and business files live in that private directory,
outside Git and the plugin cache. An old global store is never an automatic
fallback. Service credentials and browser sessions remain machine-local. A Cowork
VM or remote environment needs its own explicit accessible storage binding; never
promise it sees the Mac's files, an optional PostgreSQL database or its browser.
Do not copy private data into a plugin.

Schedules currently belong to Codex. In Claude they are read-only; the server
rejects schedule edits and confirmations. Do not invent a Claude automation ID,
turn saved preferences into a claimed active schedule, or migrate a bound Codex
automation. Ask the user to manage that schedule in Codex. Manual sourcing,
objectives, documents, public research and guarded CRM workflows remain available.
