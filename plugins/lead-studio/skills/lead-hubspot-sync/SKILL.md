---
name: lead-hubspot-sync
description: Add reviewed professional contacts to a HubSpot manual list and assign them to an exact HubSpot owner after an explicit preview and confirmation. Use for HubSpot export, CRM synchronization, lead lists, owner assignment, or giving a prospect to a colleague.
---

# Synchronisation HubSpot

Run `check_lead_integrations` first. If HubSpot is missing, explain the required local
connection and scopes from `$lead-studio` integration reference; do not request a
token in chat.

Before any write:

1. Validate every lead and show the exact contacts to upsert. An email is required
   as the stable identifier; a company-only candidate is not silently converted
   into a person. Require the verified company name plus its exact domain or
   nine-digit SIREN.
2. Run `list_hubspot_owners`, resolve the colleague by exact email or unique full name,
   and use the returned owner `id`, never `userId`.
3. Show the manual list name, contact count, fields to update, and assignment.
4. Ask for explicit confirmation at this point. A previous shortlist selection is
   not CRM authorization.
5. Run `sync_hubspot_contacts` with `confirm_hubspot_write: true` only after that
   answer.

The action looks up or creates the exact company, reads its domain/SIREN back,
batch-upserts contacts by email, associates every contact to that company,
reuses or creates the named manual contact list, adds the returned contact IDs,
and sets `hubspot_owner_id` when requested. It then reads contacts,
associations, and list memberships back. Report the HubSpot list ID, contact and
company IDs, assignment, reuse status, and read-back verification. Never send
messages or start sequences.

The preview must show connections, selected contacts, list name, resolved owner,
and readiness before asking for confirmation. Follow the current
`get_lead_interface_mode` result: use `render_lead_workspace` with
`initial_view: hubspot` for the pre-write review and final result only in
`chat_ui`; in `text_only`, provide the same preview in chat and never call a
render tool.
