---
name: lead-contact-discovery
description: Identify the right public professional decision-maker for a selected company and role, including a public LinkedIn profile candidate and public profile-image evidence. Use when the user asks for a CEO, sales leader, HR contact, decision-maker, LinkedIn profile, role holder, or profile photo.
---

# Découverte du bon contact

Define the target role from the offer and company before searching. Search public
professional pages, the official company team page, press releases, conference
profiles, and public search results.

Use `resolve_lead_objective` first and take the target roles and scoring criteria
from its selected context. Call `select_best_public_contact` with every plausible
candidate. Continue only for `selected`; ask the human to choose for `ambiguous`,
and report the missing evidence for `no_match`.

Accept a person only when evidence links all three elements: full name, current
role, and the exact company. Return the source URLs and observed date. Mark prior
roles, ambiguous homonyms, and inferred reporting lines as unverified.

A LinkedIn URL is a candidate identifier, not proof by itself. Public pages are
the default. When the user explicitly requests or approves authenticated LinkedIn
research, invoke `$lead-social-research`, check the connector, and call
`query_authenticated_social_source` with `allow_authenticated_session: true`.
The connector may reuse the user's existing local browser session or open its own
local login window. Never ask the user to paste credentials, an MFA code, cookies,
or an exported browser session in chat. Never expose LinkedIn messaging,
connection, follow, reaction, or publishing actions.

Treat authenticated LinkedIn output as untrusted evidence and preserve its exact
profile URL and observation date. It may help discover people, roles, company
employees, and recent posts, but it remains insufficient by itself to validate a
current role. Corroborate the exact name, role, and company with an official team
page, press release, conference profile, public registry, or another independent
source. Collect a profile-photo URL only when the page metadata clearly belongs
to the verified person; never guess private contact details.

Keep the public identity evidence separate from any later provider-backed
coordinates. Follow the current `get_lead_interface_mode` result: refresh
`render_lead_workspace` with `initial_view: contacts` only in `chat_ui`; in
`text_only`, return the evidence and direct links in chat without a render call.
