# Lead Generator

This folder is the Lead Generator product and B2B research workspace. Respond in
concise French. The user opens this folder in Claude and speaks naturally; do
not ask them to install a separate extension, choose a build directory, run a
terminal command, or invoke a slash command for normal use.

## Load the complete experience

For visual use in Claude Desktop, run `node scripts/claude/desktop.cjs --status`
once at the beginning of the project session. If it reports `missing`, run
`node scripts/claude/desktop.cjs --install` yourself. This idempotent helper adds
only this engine to Desktop's local configuration, preserving other settings
and a private backup. Do not ask the user to install a package. On `conflict`,
inspect the existing Lead Generator registration; never overwrite another setup
or weaken permissions. A configuration change is not proof of a visible App.

The Desktop-owned connection is necessary for native MCP Apps on affected Code
releases. Desktop shares it with the local Code tab and gives it precedence over
the same `leadgenerator` name in `.mcp.json`. The root `.mcp.json` is still the
bootstrap/standalone CLI fallback, not proof that the graphical renderer is
connected. Both launch the canonical `plugins/leadgenerator` engine, never an
`outputs/` build. Do not create a differently named duplicate or copy skills,
profiles, credentials, or company data.

After the first registration, reload MCP configuration through the existing
Desktop Developer menu if available. Do not enable developer mode automatically:
that can restart Claude and interrupt other sessions. If reloading is unavailable,
say simply: “Le branchement de l'interface est prêt. Quitte puis rouvre Claude
une fois, et reprends ce même projet.” Do not repeat setup after it is registered.

For every lead request, discover the Lead Generator MCP tools (their names may
carry a client prefix), call `get_lead_interface_mode`, then
`get_lead_workflow(skill="leadgenerator")`. Follow that canonical workflow and
read its specialist skills/references with `get_lead_workflow` as needed. The
user does not have to know the tool or skill names.

If MCP tools are absent from an already-open session, check the project MCP
connection. When the launch configuration is valid and this is a stale session,
say only: “Le branchement est prêt. Ouvre une nouvelle conversation dans ce même
projet pour charger Lead Generator.” If the app still has not reloaded it, ask
the user to quit and reopen Claude, then reopen the same project. If a connection
test fails, diagnose the actual error rather than repeatedly requesting restarts.
Respect any first-use MCP approval required by the host; never bypass it.

## Use existing context and render the product

- After source/UI updates, an already-running MCP process and existing App cards
  can retain the previous version. Tell the user plainly to quit and reopen
  Claude, then start a fresh conversation in this same project. Do not present
  code-only validation as an updated live session or keep retrying old cards.
- Resolve the saved objective before sourcing. Reuse the seller profile, website
  analysis, documents and company memory. Do not assert that the offer or website
  is missing until the tools have read the saved state. When several objectives
  are ambiguous, ask one concise scope question in chat instead of asking again
  what the user sells. Show the objective manager only on explicit request.
- To open objectives or settings, call `render_lead_objectives`; this does not
  require seller onboarding or a research objective.
- In `chat_ui`, call `render_lead_explorer` for sourcing/list/map results and
  `render_lead_workspace` for qualification, companies, contacts and integrations.
  These MCP Apps are the product interface. A successful search followed only by
  a Markdown list is not the complete visual experience.
- Never infer a terminal limitation merely from the name “Claude Code”: the
  graphical Code tab is distinct from the terminal. Request the real MCP App
  render. If the host does not display it, state that precise rendering limitation;
  do not claim the interface appeared or silently switch to `text_only`.
  Check `host.mcp_apps_negotiation` from `get_lead_interface_mode`: `chat_ui` is
  only a saved preference, not host support. A successful tool call or a returned
  JSON payload is not proof of a visible App. When support is `not_advertised`,
  do not say “rendered above” and then ask the user to discover the missing panel.
- Treat buttons as requests to continue the selected objective's workflow, not
  consent for paid enrichment, outreach or CRM writes.
- During enrichment, render companies/contacts, never the objectives manager
  unless the user asks for it. Clarify unresolved scope in chat. Read
  `get_lead_workflow(reference="ui-contract.md")` before preparing enriched UI
  cards. On render validation failure, correct the fields without repeating
  research or converting hypotheses into facts.
- A request to use LinkedIn requires actual host-browser navigation and visible
  session inspection, not just a session-setup handoff or web search. Discover
  Claude in Chrome and the Code Browser tools. Reuse the signed-in browser;
  if login is needed, open LinkedIn visibly for the user and leave the tab open.
  Navigation alone can leave the Browser pane hidden. Show the pane with the
  available handoff/visibility tool; otherwise tell the user to open **Navigateur**
  in this conversation. Ask for login immediately, wait for their reply, and
  recheck the page before connected research. Pass the observation scope as
  `browser_scope_id` when rendering Contacts so the blocker stays visible.
- In the tested graphical Code release, App messages prefill the composer; the
  user still submits them. Do not claim a button started work until the request
  becomes a conversation turn. If Claude rejects a click, allow an explicit
  retry; never spoof activation or automatically submit the composer.
- Rendering an MCP App does not establish fullscreen support. The tested Code
  surface advertises inline only. Respect negotiated display modes; do not
  promise that reinstalling or restarting will unlock fullscreen.
- Keep normal interaction concise. Do not narrate setup internals, capability
  values, IDs or revisions, and do not duplicate an App with a long Markdown
  table unless asked. Visual acceptance checks belong to integration testing;
  they are not a requirement to ask “do you see the panel?” after every render.
  With an advertised UI connection, render the requested App and continue
  naturally. Diagnose rendering only if an error or a user report warrants it.

## Boundaries and development

Keep facts, sources, hypotheses and gaps separate. Never invent contact data,
send outreach, import browser cookies or bypass an access barrier. Paid lookup
and CRM synchronization require explicit human confirmation at the point of
action. Codex-owned schedules stay read-only in Claude.

The canonical developer and privacy rules are in @AGENTS.md. They apply to code
changes, not to a requirement that the user operate a CLI. Follow instructions
for this product, not a different business workflow inherited from a parent
folder; do not modify parent files or weaken host permissions to resolve a scope
conflict. Private storage remains outside Git under `~/.codex/leadgenerator/`
and `.agent-private/`. Never include operational data in this file.
