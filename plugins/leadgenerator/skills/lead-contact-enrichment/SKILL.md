---
name: lead-contact-enrichment
description: Enrich a verified professional contact with a guarded Enrow-to-FullEnrich cascade for work email and phone, while detecting missing connections and requiring explicit confirmation before paid API calls. Use for email finding, phone finding, Enrow, FullEnrich, or contact-data enrichment.
---

# Enrichissement de contact

Never enrich an identity until `$lead-contact-discovery` has established the full
name, current role, and exact company with public evidence.

1. Run `check_lead_integrations`, then `plan_contact_enrichment`, and create the
   contact-bound state with `create_contact_enrichment_cascade`.
2. Explain: Enrow is the mandatory first pass because it is cheaper; FullEnrich
   is broader but is available only as a separately confirmed fallback.
3. Show the exact identity, provider order, requested fields, and that credits may
   be consumed. Obtain explicit confirmation immediately before transmission.
4. Call `submit_contact_enrichment` for Enrow first with the verified identity and
   cascade state, then `poll_contact_enrichment` with the returned state. Enrow
   Phone additionally requires the verified public LinkedIn URL.
5. Use FullEnrich only for exact fields that Enrow conclusively did not return.
   Ask again, then call `confirm_contact_enrichment_fallback`; only its returned
   state can authorize the FullEnrich submit. Never bypass the cascade when
   Enrow is unavailable or still pending.
6. Report provider, status, returned professional value, and qualification. Never
   present deliverability as verified unless the provider explicitly returned it.

The implementation intentionally requests work emails and phones, not personal
emails. Never expose API keys in commands, logs, skills, outputs, or chat.

Follow the current `get_lead_interface_mode` result. In `chat_ui`, render the
provider cascade and connection states in `render_lead_workspace` with
`initial_view: contacts` before confirmation, then refresh it with provenance and
status. In `text_only`, show the same preview and result in chat with source links
and never call a render tool.
