---
name: lead-company-search
description: Translate a human B2B prospecting request into French NAF/APE, geography, category, and employee-band filters, then search the official API Recherche d'Entreprises. Use for company sourcing, NAF classification, headcount thresholds, SIREN/SIRET, or data.gouv company lists.
---

# Recherche d'entreprises

Convert the user's business description into explicit filters before searching.

1. Preserve exact criteria: activity, geography, exclusions, legal category, and
   employee bounds. Do not silently widen them.
2. Map the activity to one or more five-character NAF subclass codes. Show the
   proposed codes and labels. For ambiguity that materially changes the results,
   ask the user to choose; otherwise search a small transparent union.
3. Read `get_lead_interface_mode`, then search the official register. For one
   explicit NAF/APE code call `search_companies_by_naf`. For several codes or
   combined filters call `search_french_companies`. When `interface_enabled` is
   true, immediately pass the returned leads to `render_lead_explorer`; the search
   tools deliberately do not own a UI template so text-only mode remains possible.
   Both search tools persist returned identities in private local PostgreSQL and
   exclude companies already seen in earlier searches. Preserve this default;
   use `include_previously_seen=true` only when the user explicitly requests a
   review of earlier candidates.
   For every geographic filter, map and present the active matching establishment,
   never the legal unit's out-of-area headquarters. The establishment address and
   coordinates must satisfy the requested region, department, commune, or postal
   code. When activity and geography are combined, the same active establishment
   must satisfy both; a company-level NAF code and an unrelated local branch are
   not sufficient. Exclude a row when no active matching establishment can prove
   the scope, and label a branch as an establishment rather than as headquarters.
   Default to all matching active establishments. Apply `headquarters_only=true`
   only when the user explicitly requests or checks **Siège uniquement**; then
   exclude every company whose headquarters does not satisfy the same geography
   and activity filters. Pass the same value to `render_lead_explorer` so the
   checkbox reflects the server-side result.
4. In `chat_ui`, do not finish with a text-only list or Markdown table. A
   successful visual sourcing turn ends with exactly one
   `render_lead_explorer` call, even when the result is empty. Treat that explorer
   as the complete initial sourcing result: do not immediately duplicate it with
   `render_lead_workspace`.
   Do not serialize or echo the structured tool payload into commentary or the
   final answer; let the MCP App render it and keep prose to a short summary.
   In `text_only`, never call either render tool; present the same facts in a
   concise list with direct legal-source links.
   If the MCP server is unavailable, explain that the local plugin must be repaired
   instead of silently switching to an undocumented CLI.
5. Present legal facts separately from later web qualifications. A registry entry
   is a candidate company, not yet a qualified lead.
6. When the user asks for more results, increment `page` and preserve every prior
   filter exactly, including `headquarters_only`, employee bounds, geography,
   category, and all NAF codes. Never restart from page 1 or loosen the scope.
7. When the request names a specific company, SIREN, or domain, call
   `search_remembered_companies` before the public register. Reuse and render a
   matching stored card unless the user asks for a refresh or required data is
   missing or stale.

Read [references/naf-and-headcount.md](references/naf-and-headcount.md) when
mapping an activity or employee threshold.

After the user selects candidates or asks for qualification, call
`render_lead_workspace` with the applied filters, source limitations, and every
selected pipeline item only in `chat_ui`. In `text_only`, keep the same facts and
source links in the chat.
