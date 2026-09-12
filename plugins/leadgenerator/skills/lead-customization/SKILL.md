---
name: lead-customization
description: Configure, extend, replace, diagnose, or restore the Lead Generator interface and its private plugin composition. Use when a user asks to hide, show, rename, reorder, theme, add a tab or panel, enable or disable a capability, install a business-specific extension, replace the complete UI, or repair an incompatible custom shell.
---

# Lead Generator customization

Distinguish client customization from product development. Explicit requests to
fix the product's behavior or implement native features in its source repository
use that repository's development workflow. The private-pack-only instructions
below apply to client UI customization, not to authorized engine development.

Adapt the installed product from the user's natural-language request without
editing bundled HTML, Python, skills, or native manifests. All changes belong in
the private pack below `~/.codex/leadgenerator/` through the MCP tools. When a new
extension is necessary, author it from a shipped template directly below the
private `extensions/` directory with normal coding tools, validate it, and only
then activate it through a preview; never create it inside the shared repository.

## Required sequence

1. Call `get_lead_composition`.
2. Call `inspect_lead_ui_catalog`.
3. Translate the request to one stable identifier. If the same visible label can
   identify several entries, ask one targeted clarification before changing it.
4. Choose the lightest supported level using
   [references/decision-tree.md](references/decision-tree.md).
5. Call `preview_lead_ui_customization` with a structured `UiChangeRequest`.
6. Explain the proposed level, visible diff, compatibility, restart requirement,
   and any ownership consequence in concise French.
7. Call `apply_lead_ui_customization` with the returned `plan_id` only after the
   preview has been shown. Never recreate or guess a plan ID.
8. Call `diagnose_lead_composition`.
9. If `restart_required=true`, tell the user that the MCP server must restart and
   do not claim the new plugin or shell is active yet. Otherwise rerender the
   relevant interface in the next lead result and verify the requested change.

## Interpret intent precisely

- “Cache ce bouton” means `hide`: presentation only. State that the server-side
  capability is still active.
- “Désactive HubSpot” means `disable_plugin` for `yaka.hubspot`: functional
  deactivation and restart.
- A label, order, visibility, default tab, logo, color, font, or density change is
  native configuration.
- A new view expressible with a supported component is an `add_tab` or
  `add_panel` contribution. When its observation kind does not exist, propose a
  separate data plugin; never calculate business data inside the view.
- A radically different navigation model or unsupported interactive application
  is `replace_shell`.
- Never convert a large request into repeated DOM or CSS overrides. Use a custom
  shell when the catalog cannot represent the behavior.

## Confirmation and safety

For a custom shell, reproduce the complete warning returned by the preview. The
user must explicitly accept ownership before sending
`confirm_custom_ui_ownership=true`. The client keeps compatible kernel and
business-plugin updates, but not native UI improvements. They can restore
`yaka.ui-workspace` at any time.

For executable or otherwise private extensions, show the declared permissions
and exact fingerprint status. Send `confirm_extension_permissions=true` only
after explicit approval. A changed fingerprint requires a new approval.

Refuse requests that hide evidence, facts versus hypotheses, missing information,
limitations, errors, paid-enrichment confirmations, or CRM confirmations. A UI
click is never consent for a paid read or external write. Do not accept free CSS,
JavaScript, DOM selectors, absolute asset paths, secrets, credentials, cookies,
or customer data in a shareable file.

Use `restore_previous_lead_composition` only when the user explicitly requests a
rollback. A quarantined shell stays quarantined: never silently restore the
native UI. Text tools remain usable while the issue is diagnosed.

Read [references/plugin-authoring.md](references/plugin-authoring.md) only when
the request requires a new data extension or complete shell.
