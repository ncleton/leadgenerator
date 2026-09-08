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

Read [references/naf-and-headcount.md](references/naf-and-headcount.md) when
mapping an activity or employee threshold.

After the user selects candidates or asks for qualification, call
`render_lead_workspace` with the applied filters, source limitations, and every
selected pipeline item only in `chat_ui`. In `text_only`, keep the same facts and
source links in the chat.
