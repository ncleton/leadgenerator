# Claude MCP Apps: same-folder integration

Research and actual-client verification: **2026-09-11**.
This report supersedes the 2026-09-10 assessment. That assessment conflated
Desktop, the embedded Code engine and plugin distribution, and therefore promised
graphical compatibility before proving the requested user journey.

## Answer

**Yes: a native Lead Generator MCP App can render in Claude Desktop's Code tab,
inside a local project conversation.** This was verified on the installed macOS
client, version **1.52386.0**, with the actual objectives interface, its saved
state and a button-to-conversation round trip. A separate browser dashboard,
Artifact or hosted copy of the database was not needed.

The decisive change was registration with **Desktop's MCP connection manager**.
The same engine reached only through the root `.mcp.json` exposed callable tools
but did not negotiate the UI extension. Merely adding `CLAUDE.md`, packaging a
plugin, or returning a valid UI payload did not solve that distinction.

## Question and acceptance criteria

The requested experience is: open the existing folder in Code, speak naturally,
see the product's interactive interface, and use its buttons to continue the
same conversation. The user must not choose a build, import another extension,
learn a slash command or move their data. A first-time application reload may be
necessary; it must be explained directly, not disguised as complete automation.

Acceptance separates four properties:

1. The folder identifies the correct workflow and engine.
2. Claude connects to and calls that engine.
3. The graphical host retrieves and displays the App.
4. An App action reaches the conversation and updates the interface.

Tests of properties 1 and 2 cannot establish properties 3 and 4.

## Current primary evidence

### Desktop-owned servers are shared with Code

Anthropic's current desktop reference says local Code sessions load servers from
`claude_desktop_config.json`. For a duplicate server name, that Desktop
definition takes precedence over `.mcp.json` and `~/.claude.json`. The
standalone CLI does not read the Desktop file. This provides a documented way to
retain the folder workflow while changing the owner of the MCP connection. The
same page documents a Browser pane, which was unnecessary after the native path
succeeded.
[Official Code desktop reference](https://code.claude.com/docs/en/desktop#mcp-servers-from-the-claude-desktop-chat-app).

### Local Apps are supported by Desktop

The MCP Apps quickstart registers a local example server in Desktop configuration
and requests its widget in conversation. A first-use display approval may be
requested. Its mention of a Claude Code *development skill* is not evidence that
every Code connection type renders Apps. The original assessment missed this
distinction.
[Official MCP Apps quickstart](https://claude.com/docs/connectors/building/mcp-apps/getting-started).

### The registration-path failure has a reproduced report

An issue filed on Anthropic's tracker on 2026-08-10 compares the same server
registered through Desktop, a plugin and a project configuration. Only the
Desktop-owned connection advertises `io.modelcontextprotocol/ui`; the author
reports successful rendering from the Code tab. This is a third-party
reproduction on the vendor's tracker, not an Anthropic guarantee. It motivated
our controlled local test, whose result matched that explanation.
[Reproduction and handshake evidence, issue 830](https://github.com/anthropics/claude-ai-mcp/issues/830).

### Other failures remain possible

Anthropic documents missing UI initialization, zero-height iframes and oversized
tool results as distinct problems. Its guide also documents Developer → Reload
MCP Configuration. Our project failure disappeared when the connection owner
changed, without rewriting the HTML. Enabling developer mode during this test
restarted the installed application, so folder instructions now prohibit doing
that automatically during other sessions.
[Official troubleshooting](https://claude.com/docs/connectors/building/mcp-apps/troubleshooting).

An additional report describes a Code feature gate blocking widgets with
third-party inference providers. Another describes a regression near protocol
version negotiation. Neither justifies changing hidden flags or weakening
permissions. They show why one success cannot certify every deployment or future
release.
[Third-party deployment report](https://github.com/anthropics/claude-code/issues/88566),
[negotiation regression report](https://github.com/anthropics/claude-code/issues/88370).

### Follow-up: message rejection and fullscreen in Code

The subsequent actual-client map test exposed two limits that the objectives
test did not establish:

- A public-enrichment click was rejected by the host's iframe user-activation
  check. The application log records an explicit `ui/message` rejection, not
  an oversized message. A later direct click on the same selection succeeded.
  The precise interaction that caused the initial false rejection was not
  reproduced, so a permanent host-side fix is not claimed.
- The successful click populated Code's composer; it did **not** submit a new
  model turn automatically. The request was left unsent for the user. A positive
  `ui/message` acknowledgement means host acceptance, not enrichment completion.
- The fullscreen button failed in the installed Code surface. Inspection of
  Anthropic's public client module confirms that this surface supplies only
  `availableDisplayModes: ["inline"]`. Its message handler also uses the composer
  prefill callback. This is version-specific implementation evidence, not a
  promise that every future release behaves identically.

[Observed Code renderer module](https://assets-proxy.anthropic.com/claude-ai/v2/assets/v1/cd5a31703-DVmgF4i9.js).

Anthropic's general App guidelines document fullscreen, but require negotiation
with the host. They do not override Code's actual inline-only capability.
[Official display-mode guidelines](https://claude.com/docs/connectors/building/mcp-apps/design-guidelines#display-modes),
[MCP Apps display-mode patterns](https://apps.extensions.modelcontextprotocol.io/api/documents/patterns.html).

The source UI now offers a new, explicit retry click only after an acknowledged
rejection, preserves the identical scoped request, and distinguishes an uncertain
timeout from a definite failure. There is no automatic retry, fabricated user
activation, host modification or programmatic composer submission. Unsupported
fullscreen controls are disabled; declined or invalid mode responses never fake
an expanded state. These corrections are covered by browser protocol tests;
they have not yet been loaded into the already-open Claude panel.

### Follow-up: enrichment, images and view isolation

A later enrichment run exposed failures beyond transport. Actual-client
inspection showed render validation errors followed by the misleading empty-view
message, successful company results reopening the Objectives tab, and official
logos whose hosts were absent from the iframe image CSP. The model also confused
research evidence objects with UI contact fields. Finding a logo in a scraper's
result did not establish that its image loaded in the App.

The source corrections are:

- Shared payload decoding accepts structured results and JSON text blocks, but
  treats `isError` as an error, not missing data. A failed update retains the last
  valid view. The UI contract documents exact card and evidence fields so a render
  retry need not repeat research or relabel hypotheses as facts.
- Explicit requested views take priority over saved navigation. Management and
  lead state are separated; qualification views omit the Objectives tab and
  per-objective schedule panel. Ambiguous scope is clarified in chat; the manager
  opens only on request.
- Native results omit the duplicate generic shell projection while retaining
  authoritative lead cards, evidence and custom-tab observations. Custom shells
  keep their full projection. This reduces payload size; it is not proof that
  arbitrarily large results fit every host's limit.
- Official visual extraction handles lazy images and structured logo objects,
  prioritizes full logos over favicons, and excludes a logo from representative
  image candidates. Sourced visual candidates can supply missing card URLs
  without turning derived display values into explicit memory overwrites.
- Claude's public renderer lists tools when mounting an App and caches both HTML
  and CSP by resource URI and server. Native tool URIs now carry a content hash of
  the approved image-origin policy, shared across local MCP connections in private
  storage. A changed allowlist gets a distinct cache identity. No wildcard,
  image proxy, cookie export or asset download is introduced.

The cache behavior is version-specific evidence from the public
[App renderer module](https://assets-proxy.anthropic.com/claude-ai/v2/assets/v1/cd9b7fccf-BJ2H6IqO.js)
and [shared resource loader](https://assets-proxy.anthropic.com/claude-ai/v2/assets/v1/shared-common-3-AryfxweQ.js).
Anthropic also documents
[oversized result handling](https://claude.com/docs/connectors/building/mcp-apps/troubleshooting).
Automated protocol and browser regressions cover these corrections; they have
not yet been reloaded and accepted in the already-open Claude conversation.

LinkedIn has a separate handoff requirement. The previous explorer prompt
explicitly requested access without login; it now requests real host-browser
navigation. The public provider reports the personal session as **unchecked**,
not disconnected. Claude must discover its available browser tools and inspect
the visible session. The built-in Code Browser uses its own clean profile;
Claude in Chrome can reuse the user's signed-in Chrome profile. Neither can
inherit Codex cookies. See the official
[Code Browser reference](https://code.claude.com/docs/en/desktop#browser)
and [Chrome integration](https://code.claude.com/docs/en/chrome).
No authenticated LinkedIn navigation has yet been observed in this retest.

## Controlled local result

Both paths used the canonical `plugins/leadgenerator` source and the same local
private storage. No operational objective values, business logs, session IDs or
screenshots are included in this shareable report.

| Evidence | Project only | Desktop registration, same Code project |
| --- | --- | --- |
| MCP tools | Working | Working |
| UI capability | `not_advertised` | `advertised` |
| Render call | Successful JSON result | Successful App result |
| Host content | Tool transcript | Nested MCP Apps iframes |
| Product content | No visible panel | Objectives, cards, settings tab, controls |
| Button continuation | Unavailable | Request received in conversation |
| Active-objective state | Not visually available | Re-rendered in native panel |

The first test requested display only. Once the panel appeared, the user clicked
an objective activation button; the resulting conversation request and updated
active state were observed. This is stronger evidence than a synthetic iframe
test or a model claiming an interface was rendered.

The screenshot check also exposed an experience defect: Claude interpreted an
overly broad diagnostic flag as a requirement to repeatedly ask for visual
confirmation and duplicate panel content in long text. The diagnostic now scopes
visual verification to **integration testing**. Root instructions require concise
normal replies, without repeated visibility questions or redundant tables.

## Implemented solution

| Component | Responsibility |
| --- | --- |
| Root `CLAUDE.md` | Natural-language routing and automatic local setup |
| Root `.mcp.json` | Initial discovery and standalone CLI fallback |
| `scripts/claude/desktop.cjs` | Idempotent, narrowly scoped Desktop registration |
| `scripts/claude/project.cjs` | Locate canonical engine without a generated build |
| `scripts/claude/launcher.cjs` | Start locked uv runtime; preserve complete MCP stdio |
| MCP tools and resources | Same logic, HTML, guards and private storage as Codex |

The helper has a read-only status mode. Installation adds only the named engine,
preserves unrelated settings, backs up original bytes privately, rejects malformed
or symlinked configuration, and refuses to overwrite a different installation.
It does not change trust settings or feature flags, or expose a network service.
Generated absolute paths stay in machine-local configuration.

For first use, Claude follows root instructions and performs setup itself.
If Desktop has not loaded the registration, the user is asked only to quit and
reopen Claude once, then resume the same project. Already-configured sessions
do not reinstall. Host-required approvals remain human decisions.

## Remaining limits

| Surface or feature | Conclusion |
| --- | --- |
| Local Code, tested macOS Desktop | Native objectives and conversation round trip verified |
| Project/plugin connection alone | Tools work; no panel in the observed setup |
| Desktop Chat | Supported by official local-App documentation; not our acceptance surface |
| Standalone terminal | No HTML surface; explicitly chosen text mode remains separate |
| Cowork VM | Do not assume access to Mac home, PostgreSQL or browser session |
| Cloud/mobile/remote sessions | Local registration does not expose the engine remotely |
| Codex schedules | Still read-only from Claude; scheduling parity is not delivered |
| Code fullscreen, installed release | Unavailable: host advertises inline only |
| Code App message, installed release | Can prefill the composer; user submits it; transient click rejection observed |
| Maps, every UI action, LinkedIn permissions, paid/CRM services | Not all certified by the objectives test |

A custom preview host would need a second UI host and a verified way to send App
actions back to the conversation. A public remote connector would change privacy,
authentication and deployment. Neither was implemented: native Desktop
registration enabled the tested folder-and-App rendering without them. It does
not establish full Codex interaction parity; the follow-up limits above remain.

## Regression checks

- `tests/runtime/test_claude_desktop_setup.py`: preservation, idempotence,
  conflicts, invalid JSON, backup permissions, missing configuration, symlinks.
- `tests/runtime/test_claude_distribution.py`: packaging, canonical workflow,
  root discovery, negotiated capabilities and full-size stdio responses.
- `tests/ui/test_claude_bridge.py`: standard iframe protocol without an
  OpenAI-specific host object.
- `scripts/verify_claude.py --project .`: actual source launcher and resources,
  without business mutations or model calls.
- `scripts/validate.sh`: repository quality gates and privacy checks.

Actual-client verification remains a release criterion. Protocol tests are
useful regressions, not substitutes for an App in the intended Claude surface.
