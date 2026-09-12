---
name: lead-company-visuals
description: Find reviewable company logos and representative images from the official company website with source evidence. Use when a lead card, company profile, shortlist, or CRM record needs a logo, hero image, office image, or brand visual.
---

# Visuels d'entreprise

Use only the verified official company domain. When `scrape_public_page` has
already read the page, consume its `logo_candidate`,
`representative_image_candidate`, and `visual_candidates` directly. This keeps
the logo attached to the company research instead of discarding it after the
scrape. Call `inspect_official_visuals` only when the scrape predates this
contract, returned no useful candidate, or the user explicitly asks for a fresh
visual inspection. Prioritize candidates in this order:

1. `Organization.logo` declared by the official website.
2. A logo image explicitly marked in the site's HTML.
3. The official `og:image` or editorial hero image as a representative visual.

Return the image URL, official source-page URL, evidence, and confidence. Keep it
as a candidate until human review. Do not copy images from unrelated directories,
social accounts, or image search results when the company identity is ambiguous.
Do not claim permission to reuse an image merely because it is publicly visible.

Pass each candidate unchanged in the company's `visuals` list. Its fields are
`kind`, `image_url`, `source_url`, `evidence` (a string) and `confidence`.
Use `logo_url` and `representative_image_url` for the corresponding card URLs,
not `logo`, `image` or an entire candidate object. Never send empty placeholders
over previously saved images. A browser-blocked preview is not a missing logo:
retain its URL and provenance and report the display failure separately.

Follow the current `get_lead_interface_mode` result. In `chat_ui`, refresh
`render_lead_workspace` with `initial_view: visuals`; include only the reviewable
image URL, official source URL, evidence, and confidence. In `text_only`, return
those same links and evidence in chat and never call a render tool.
