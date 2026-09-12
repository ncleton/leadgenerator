---
name: lead-contact-discovery
description: Identify the right public professional decision-maker for a selected company and role, including a public LinkedIn profile candidate and public profile-image evidence. Use when the user asks for a CEO, sales leader, HR contact, decision-maker, LinkedIn profile, role holder, or profile photo.
---

# Découverte du bon contact

Define the target role from the offer and company before searching. Search public
professional pages, the official company team page, press releases, conference
profiles, and public search results.

Use `resolve_lead_objective` first and take the target roles and scoring criteria
from its selected context. Call `get_linkedin_public_capabilities`, then call
`rank_public_contact_profiles` with every plausible candidate, the total number
discovered, and an honest coverage note. Render at most five ranked profiles.
Use `select_best_public_contact` only when the user needs one primary person;
continue only for `selected`, ask the human to choose for `ambiguous`, and report
the missing evidence for `no_match`.

Accept a person only when evidence links all three elements: full name, current
role, and the exact company. Return the source URLs and observed date. Mark prior
roles, ambiguous homonyms, and inferred reporting lines as unverified.

A LinkedIn URL is a candidate identifier, not proof by itself. For connected
LinkedIn research, use $lead-linkedin-browser: reuse the user's current host browser,
hand off login when necessary, and read the visible professional profile, photo
and up to five recent posts. Keep explicit `authenticated_browser` provenance;
never describe connected content as a public search result. Corroborate current
employment independently and keep LinkedIn-only identities unverified.

For sessionless photo discovery, use `inspect_person_profile_images` on a public
professional page belonging to the exact person. Do not pass LinkedIn URLs to
that sessionless scraper. Preserve photo source, observed date, post permalinks
and dates, ranking rationale and missing data in the Contacts view.

Keep the public identity evidence separate from any later provider-backed
coordinates. Follow the current `get_lead_interface_mode` result: refresh
`render_lead_workspace` with `initial_view: contacts` only in `chat_ui`; in
`text_only`, return the evidence and direct links in chat without a render call.
