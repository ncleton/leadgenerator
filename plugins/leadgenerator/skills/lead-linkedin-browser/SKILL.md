---
name: lead-linkedin-browser
description: Use the user's LinkedIn account in the available Codex or Claude browser integration for professional profile research, visible profile photos, recent posts, and company decision-makers. Use when connecting LinkedIn, reusing its session, or enriching selected professional profiles; never import cookies.
---

# LinkedIn in the host browser

Use the existing session in the current host's browser, not the sessionless HTTP scraper and not
a separate Chromium process. The browser owns authentication. Lead Generator's
MCP tools only prepare handoffs and record non-secret observations; a successful
handoff is not evidence that a browser opened or login succeeded.

## Connection and reuse

1. Read `get_linkedin_session_status` with a scope derived from the current
   conversation and selected browser. A missing or expired observation means
   **unknown**, not disconnected. Always inspect the actual page before research.
2. Call `start_linkedin_session_setup` when a check or login is needed. Execute
   its handoff with the host's available browser tool, reading that tool's current
   documentation. In Claude discover the browser tools before declaring them
   unavailable. Prefer Claude in Chrome for the user's existing signed-in browser.
   The graphical Code tab also has a built-in Browser (often exposed as Claude
   Browser / Claude Preview tools): it can open external sites and accept a direct
   user login, but its profile is separate from Chrome. Reuse it when already
   connected, or show it for login if Chrome integration is unavailable. Never
   silently substitute a different account. Cowork browser tools are another
   host-specific option; never call Codex CUA APIs there. Only in Codex's CUA interface, inventory with `cua.getState()`, reuse
   the matching LinkedIn tab, or create `cua.createBrowserTab("iab",
   "https://www.linkedin.com/", {visible: true})`. Do not hardcode runtime tab IDs.
3. If the user has requested research with their account, that request authorizes
   this browsing workflow; do not ask them again on every profile. Otherwise
   offer connected research when it would fill a gap. A refusal leaves public
   research available and must not trigger repeated connection prompts.
4. If LinkedIn shows login, show the tab and tell the user to connect directly
   there. Do not request or inspect passwords, MFA, cookies, local storage or
   browser profiles. Do not reload or close the tab while they sign in. Preserve
   it with the browser's handoff API (`tab.markHandoff()` when available).
   In graphical Claude Code, a tab can stay open while the Browser pane is
   hidden. Use the documented visibility/handoff operation as well as navigation;
   if the tools cannot expose the pane, say plainly to open the **Navigateur**
   button in that conversation. Ask for login immediately, not at the end of a
   lengthy research report. Pause connected research until the user replies;
   already-collected company facts remain available.
5. After login, inspect the visible account navigation. Call
   `record_linkedin_session_observation` with `connected` only after observing
   the account menu with no login wall or checkpoint. An open tab or “I'm logged
   in” message alone is not verification. Record `login_required`, `checkpoint`
   or `unavailable` when appropriate. Leave checkpoints/MFA to the user.
6. Keep using that browser and tab. Do not require the user to close it. Recheck
   after navigation; if the session expires, preserve already collected evidence
   and ask for reconnection once. Do not assume persistence across app restarts.

If the host browser tool is unavailable, explain that connected research requires
the browser connection to be enabled. Opening a URL through a shell or returning
`executed: false` is not completing the handoff: use the actual navigation tool,
then inspect the page. Do not replace this step with WebSearch or WebFetch and
call the result connected enrichment. Do not claim connection, silently switch accounts, launch a
cookie importer or substitute an unauthenticated scrape as authenticated data.

## Selected professional profiles

Resolve the active objective and exact company first. Discover candidates using
public evidence and the visible LinkedIn search/company pages. Do not enumerate
every employee by default: review a bounded shortlist relevant to the objective
and state the number discovered, reviewed, and any coverage limits.

For each exact profile, call `prepare_linkedin_browsing` then execute the handoff
in the same host browser. Use the rendered page/DOM supported by that browser
tool. Preserve the profile URL, full name, current role, current employer, short
professional summary and observation date. Verify the employer and role with an
independent source; a LinkedIn-only identity remains unverified, not missing.

For a photo, inspect the image belonging to the exact profile header. Use only
the actual image URL exposed by the rendered image element or the host's page
asset capability. Preserve it as `profile_image_url` and as `asset_url` in
`profile_image_evidence`, whose `source_url` is the exact `linkedin_url`,
`person_name` and `company_name` match, and `access_mode` is
`authenticated_browser`. Do not choose an arbitrary first CDN image, avatar from
a comment, banner or homonym. A screenshot alone does not establish an image URL.
If the URL cannot be obtained, keep the photo missing with a reason; do not invent
one or export browser state. Signed image URLs can expire: preserve the source
link and show a graceful fallback when an image no longer loads.

Open the profile's visible activity/posts link. Read at most five relevant recent
posts. Record a concise summary, exact author, permalink, `observed_on`, and
`published_on` when known; use `access_mode: authenticated_browser`. Preserve
unknown dates and distinguish original posts from reposts in the summary. Say
“recent posts observed,” not “the latest posts,” unless ordering and coverage
were actually verified. Never collect private messages or personal contact data.

Pass candidates to `rank_public_contact_profiles` with the objective criteria.
Despite its legacy name, this tool accepts explicitly sourced browser evidence.
Return at most five ranked contacts, with reasons and uncertainties. Keep facts,
commercial hypotheses and gaps separate. No outreach, invitation, like or paid
enrichment is part of this workflow; stop at a rate limit or access barrier.

## Render and persistence

In `chat_ui`, render contacts under their parent company in
`render_lead_workspace`. Preserve `company_siren`, objective, evidence URLs,
ranking, summary, photo provenance and post provenance. Map `observed_on` to
`observed_at` and `published_on` to `published_at` for UI posts. For the photo,
also pass `profile_image_source_url` and `profile_image_access_mode`.
Pass the exact observation scope as `browser_scope_id` to the workspace render.
The Contacts view displays its short-lived LinkedIn state and a resume action;
an omitted or expired scope is unknown, never another conversation's connection.
For later enrichment, retain each person's exact `contact_id` or LinkedIn URL.
Omit unchanged fields: render tools restore the company projection from private
memory for the active objective. An explicitly empty contacts list clears that
list; an explicit null clears a nullable field. Do not send empty placeholders
for an existing logo, photo, posts or other contacts. The updated rendering result
is authoritative; do not rebuild a second partial view from the input alone.
In `text_only`, provide sourced text without rendering. Never put real profiles,
posts or session data in the product repository or test fixtures.

`forget_linkedin_session` forgets only the recorded observation. To actually sign
out, use LinkedIn's logout in the browser or the host's browser-data settings;
do not say cookies were deleted by the MCP tool. LinkedIn may restrict automated
use under its terms; connected browsing is not an approved LinkedIn API.
