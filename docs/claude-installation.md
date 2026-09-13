# Lead Generator in Claude

## Open this folder in Claude (normal project workflow)

The user can simply ask Claude: “Installe cet agent :
https://github.com/ncleton/leadgenerator”. The installing assistant follows
[installation.md](installation.md), downloads the source when needed and runs
`scripts/install_client.sh --host claude-desktop` for the graphical app (including
its Code tab), or `--host claude-code` for the terminal CLI. On Windows it uses
`scripts/install_client.ps1 -HostTarget` with the same host values. The user does
not have to run these commands, install dependencies or choose a package.

Keep the repository in a durable `code/` directory inside a main project folder.
Setup binds `LEADGENERATOR_HOME` to the sibling `donnees-privees/`; other checkout
names use a sibling `<checkout-name>-donnees-privees/`. The SQLite company database,
profiles, objectives and settings belong to that one private store. Setup does
not import an old user-global profile. See [storage.md](storage.md) before copying
an existing installation or choosing another folder.

Open the repository folder as a local project in Claude's graphical **Code** tab,
start a new conversation, and speak naturally. For example: “Affiche mes objectifs”
or “Trouve des prospects pour mon objectif”. No package import, special startup
command or slash command is required for this folder-based workflow.

The installer registers an absolute uv command pointing to the live
`plugins/leadgenerator` engine. It prepares uv and the Python dependencies;
Node is not needed for this recommended workflow. Desktop uses its machine-local
MCP configuration; the terminal uses the project's `.mcp.json`. The terminal
setup creates `CLAUDE.md` from the reviewed template when absent and preserves
customized instructions. `get_lead_workflow` exposes canonical skills without
installing a second copy.

After installation, **quit Claude completely and reopen it**, then start a new
conversation in the same project. A first-use MCP approval may be requested
by Claude. Do not bypass it or change global permissions.

MCP connection and MCP Apps rendering are separate acceptance checks. The GUI
Code tab is not the terminal. Call the actual render tools and verify that the
interface appears; do not claim graphical parity from a successful tools/list
alone. If that Claude surface does not render the App, report that limitation
instead of making the user perform repeated installation steps.

Developer connection check: `claude mcp get leadgenerator`. Runtime check:
`uv run --project plugins/leadgenerator python scripts/verify_claude.py --project .`.

### Native MCP Apps connection

The installer adds only the `leadgenerator` entry to the selected host's
configuration. Existing preferences, unrelated connectors and service environment
values are preserved. A recognized Lead Generator registration can be rebound to
the selected source folder with a byte-for-byte private backup; an unknown
connector is never overwritten. Backups that may contain service credentials
remain machine-local, outside portable business storage.

This registration matters: the Desktop shell negotiates MCP Apps, whereas the
project's embedded Code-engine connection may not. Desktop's definition takes
precedence for the same server name in local Code sessions, according to the
[official desktop reference](https://code.claude.com/docs/en/desktop#mcp-servers-from-the-claude-desktop-chat-app).
The `.mcp.json` entry remains useful for first-run discovery and the standalone CLI.

After registration, ask the user to quit and reopen Claude once. Do not restart
the application or enable developer mode automatically during active sessions.
Do not tell the user to install an extension, choose an output build, move to Chat
or switch to text-only mode as a substitute for configuring the correct host.

### Actual acceptance check (2026-09-11)

The same source engine was tested before and after Desktop registration:

| Check | Project connection only | Desktop-owned connection in Code |
| --- | --- | --- |
| Tools callable | Yes | Yes |
| UI extension negotiated | `not_advertised` | `advertised` |
| Objectives panel | JSON transcript only | Native nested MCP Apps iframe |
| Saved objectives hydrated | Not visually displayed | Cards and controls present |
| Objective button → chat → updated panel | Unavailable | Observed end to end |

The successful test used Claude Desktop **1.52386.0**, macOS, a local Code session
in this project, and a natural-language request to display objectives. The user
then activated an objective from its App button; Claude received that request,
loaded the objective and rendered an updated panel with the active state.
No proxy browser UI or replacement Artifact was used. This verifies the native
rendering path and conversation round trip, not every provider, browser permission,
map interaction, or paid/CRM operation. No private objective values or screenshots
belong in this acceptance record.

Normal replies must stay short. A visual acceptance check is a developer test,
not a requirement to ask the user whether the panel is visible after each render.

### Interaction limits verified in the Code tab

In the tested release, an accepted App button request fills the conversation
composer; the user still clicks **Envoyer** to submit it. Do not claim enrichment
has started merely because the host acknowledged the message. If the host refuses
a click, the interface offers **Réessayer la transmission**, requiring a fresh
user click. An uncertain timeout asks the user to inspect the chat first, avoiding
an automatic duplicate. No activation checks or host permissions are bypassed.

The installed Code surface advertises only the inline display mode. It renders
MCP Apps but does not offer native fullscreen, despite fullscreen support in
Claude's general MCP Apps documentation. The UI disables unavailable fullscreen
controls and uses the mode actually returned by capable hosts. Reinstalling the
server or restarting Claude does not add a mode its host does not support.

Source UI changes require a server reload and a fresh rendered panel; an existing
iframe keeps its loaded JavaScript. Do not interrupt an active conversation to
reload it without warning. The message already prepared in the composer can be
submitted without reloading.

For a source update, the simple user instruction is: quit Claude completely,
reopen it, and start a fresh conversation in the same project. Existing cards and
old conversational tool instructions are not updated retroactively. Ask for a
rerender from memory, not another full enrichment run.

An App may mount before its render tool completes. A 15-second delay is not a
failure: the panel keeps waiting and hydrates when the result arrives. Actual
tool errors remain distinct. This late hydration was observed in Claude after
the initial timeout message; the UI no longer asks the user to rerender merely
because that time has elapsed.

### Enrichment, logos and LinkedIn

Qualification opens **Entreprises**, contact work opens **Contacts**, and the
objective manager appears only on request. An uncertain objective is clarified
briefly in chat. A render error is corrected by rerendering saved results, not
repeating the entire research. Claude can load `ui-contract.md` through
`get_lead_workflow` for exact fields and evidence types.

Native image permissions use exact reviewed public HTTPS origins. Claude caches
resource content and CSP together, so a changed image policy receives a new
resource URI. The private policy registry contains only origins, not image bytes,
lead cards or credentials. A failed preview is not proof that no logo was found;
retain its source and describe a loading failure accurately.
Reading remembered cards or their history registers their image origins before
the following render, including when no fresh website research is needed.

The company identity has one logo slot; initials are its fallback, not a second
hero block. The representative-photo slot appears only for a distinct image.
Aerial previews support an explicit image-only reload with a fresh IGN cache
identity, preserve the geographic extent, and retain the prior image if a refresh
fails. The reticle is centered on the image viewport, independently of the caption.
No image pixels are synthesized or repaired. A transient white rectangle reported
in Claude was not reproduced in the exact source image; this is a recovery path,
not a proven host-compositor fix.

LinkedIn account use requires actual browser navigation, not a setup-tool result
or ordinary web search. Discover **Claude in Chrome** for an existing Chrome
login, or the graphical Code **Browser** tools. The latter has a separate profile
and may require the user to sign in visibly. Report the session state actually
observed; do not import cookies or claim that installing the MCP connects LinkedIn.
These paths are described in the official [Code Browser documentation](https://code.claude.com/docs/en/desktop#browser)
and [Chrome documentation](https://code.claude.com/docs/en/chrome).

A real Code session retained a LinkedIn login tab inside a hidden Browser pane.
Navigation alone therefore did not make the login handoff visible. Show the pane
and request login immediately; if the host tool cannot expose it, direct the user
to the conversation's **Navigateur** button. Do not repeat website enrichment to
recover this state. Authentication is still performed by the user, not the MCP.

Each company card has **Voir les contacts**, a local navigation action scoped to
that company. **Tous les contacts** and the Contacts tab show the full list,
independently of the company search filter. Neither action starts research.
The Contacts view also shows LinkedIn's scoped observation and a resume button.
Pass `browser_scope_id` from the recorded browser observation to the render;
missing or stale scopes display unknown, and another conversation's observation
is never used automatically. Resuming LinkedIn keeps existing company evidence
and requests only the missing professional profile work, without paid lookups.

## Optional distribution: Claude Desktop chat extension

The following packages are for installation outside the source-folder workflow.
They are not prerequisites for opening this repository in Claude's Code tab.

Use the generated `leadgenerator.mcpb` extension for the local Claude Desktop
chat. Open the file with Claude, or install it through Settings → Extensions →
Advanced settings → Install extension. Approve the local MCP server, then start
a new conversation. Do not also enable another Lead Generator MCP server in the
same conversation.

This package needs [uv](https://docs.astral.sh/uv/getting-started/installation/)
on the machine. Claude supplies Node; the launcher finds uv even when a GUI
process has a minimal PATH. uv installs the locked Python 3.13 environment on
first launch. No developer virtualenv is bundled. Internet access is needed for
that initial install and for public research. Configure the extension's
`LEADGENERATOR_HOME` binding to a durable private directory outside the package
and Git. SQLite stores company memory there by default; no PostgreSQL server is
required. PostgreSQL is used only with an explicit `LEADGENERATOR_DATABASE_URL`.
An extension never imports a previous user-global store automatically.

Optional service keys can be entered into the extension's secure configuration;
leave them empty to test public research. Neither the package nor a Claude chat
needs the values of your credentials. Paid enrichment and CRM writes continue
to require explicit confirmation.

First test prompt:

> Utilise Lead Generator. Vérifie le mode d'interface, puis affiche mes objectifs
> avec render_lead_objectives, sans lancer de recherche ni modifier de données.

Then select an objective and request a small company search. Check the map,
selection, **Enrichir la sélection**, company/contact tabs, source links and
**Agrandir**. The interface is served by the MCP tools, not by a Claude Artifact.
Geolocation and fullscreen depend on the permissions/capabilities Claude grants;
a refusal must not block the other views.

Desktop chat does not necessarily load plugin skills. The MCP initialization
instructions direct it to `get_lead_workflow`, which serves the same canonical
skills and references from the package. Use the plugin below when the client
supports plugin skills directly.

## Optional distribution: Claude Code / Cowork plugin

Import `leadgenerator.plugin` in a client with plugin upload support. It contains
`.claude-plugin/plugin.json`, all canonical skills, `.mcp.json`, the same
engine and the same UI. Node and uv must be available in the execution environment.

For a local Claude Code development session, point the CLI to the generated
directory (not the Codex source directory):

```sh
claude --plugin-dir "/absolute/path/from/build-output/leadgenerator"
```

Invoke `/leadgenerator:leadgenerator`. A terminal cannot render the HTML UI;
test the visual interface in Claude Desktop. In a terminal, explicitly request
text-only mode if desired; that preference is shared with Codex only when both
processes are explicitly bound to the same `LEADGENERATOR_HOME`.

Cowork may run plugin tools in a VM. In that case its filesystem, uv installation
and browser session differ from the Mac's. Configure an accessible private
directory explicitly in that environment. Installing a plugin does not share
the Mac's files or grant VM-to-host access to an optional PostgreSQL database.

## Boundaries retained

- Same explicit `LEADGENERATOR_HOME`: reuse that store, not an unrelated global home.
- Another machine: close the apps, copy the durable parent containing both `code`
  and `donnees-privees`, rerun setup from the new code path, then reconnect services.
- VM or external PostgreSQL: provide accessible storage and handle the database
  backup separately. Copying business files does not copy browser sessions,
  service credentials, dependencies or host-owned scheduled tasks.
- LinkedIn account research: use Claude's available browser integration and log
  in there if needed. Codex cookies are never imported. With no browser integration,
  report the connected-research limitation and retain public research.
- Codex schedules: visible in Claude, read-only. Manage them in Codex. This release
  does not create Claude schedules or claim that saved preferences execute.
- CRM and paid enrichment: preview, explicit confirmation, then guarded tools.

## Build and checks

```sh
uv run --project plugins/leadgenerator python scripts/build_claude.py
claude plugin validate "/absolute/path/from/build-output/leadgenerator"
uv run --project plugins/leadgenerator python scripts/verify_claude.py outputs/claude/leadgenerator.mcpb
./scripts/validate.sh
```

The builder runs the repository privacy checks, copies only engine/skill sources
and locked dependency metadata, and excludes private data, environments, caches
and Codex manifests. Artifacts live in ignored `outputs/claude/`. Both products
share source code; no hand-maintained Claude fork is necessary.

Installation/protocol references: [Claude plugins](https://code.claude.com/docs/en/plugins-reference),
[Desktop extension format](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md),
[MCP Apps](https://apps.extensions.modelcontextprotocol.io/).

Automated protocol/browser tests do not establish that a particular installed
Claude release renders every feature. The real-client interaction check remains
part of acceptance testing.
