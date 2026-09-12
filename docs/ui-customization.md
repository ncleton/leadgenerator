# UI customization

The product permits one shell and multiple declarative business contributions.
Always preview a change and choose the smallest sufficient level.

## Level 1: native configuration

Use stable IDs to hide/show actions, rename/reorder/hide tabs, select a default
tab, change approved theme tokens, or provide a private logo. No free CSS,
JavaScript, DOM selector, or absolute asset path is accepted. Theme, label, order,
and visibility changes apply to the next render. Hiding an action does not disable
its server capability.

Evidence, epistemic status, missing information, limitations, errors, paid-read
confirmation, and CRM-write confirmation are protected and cannot be hidden.

## Level 2: declarative tab or panel

Panels use one catalog component: `facts-list`, `metrics`, `timeline`, `table`,
`map`, `image-gallery`, `score-breakdown`, `status-list`, `contact-list`, or
`form`. A panel selects observations by `kind`; it never calculates business
logic. Missing observations produce a visible empty state and imply a separate
data plugin. An unknown component disables only its panel and emits a diagnostic.

## Level 3: autonomous shell

Use a full shell only for a different navigation model or interaction that the
catalog cannot express. It provides `explorer` and `workspace`, declares SDK and
CSP constraints, and communicates through the MCP Apps bridge.

The client keeps compatible kernel and business-plugin updates but owns visual
maintenance and does not automatically receive native UI improvements. The native
shell can be restored explicitly. Shell and plugin changes require an MCP restart.

## Conversation tools

1. `get_lead_composition`
2. `inspect_lead_ui_catalog`
3. `preview_lead_ui_customization`
4. `apply_lead_ui_customization`
5. `diagnose_lead_composition`
6. `restore_previous_lead_composition` for an explicit rollback

Plans expire after 30 minutes and bind to the exact pack fingerprint. Writes are
private, validated, atomic, and backed up before replacement.
