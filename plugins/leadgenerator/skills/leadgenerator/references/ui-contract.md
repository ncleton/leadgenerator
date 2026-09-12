# Research results to visual cards

Use the render tool's declared schema. A research candidate is not a UI card;
do not paste a ranker or corroborator output unchanged into `contacts` or `leads`.

Every explorer card requires sourced `location.latitude` and `location.longitude`.
Geocode missing project addresses before rendering. A verified street, business
park or municipality may be used with `precision: approximate` and an explicit
area-level label, never as a building or parking position. Preserve project
evidence separately from the geocoding source. Do not drop leads or invent
coordinates to pass the gate; report an unresolved geocoding blocker instead.

| Card field | Value |
| --- | --- |
| `id`, `company_name` | Stable company identifier and exact name |
| `website_url` | Official website URL, not a `website` field |
| `logo_url`, `representative_image_url` | Image URL strings, not candidate objects |
| `visuals` | Candidates with `kind`, `image_url`, `source_url`, string `evidence`, `confidence` |
| `hypotheses_to_validate` | Objects with `hypothesis` and `rationale`; never promote them to observed facts |
| `outreach_angle` | A string; supporting URLs go in `outreach_angle_source_urls` |
| `observed_facts` | Objects with `label`, `value`, `source_url` and optional dates |
| `contacts`, `director` | UI contact objects as described below |

A UI contact requires `name`, `evidence` (a concise string, not a list), and
`source_url`. Use `role`, `linkedin_url`, `evidence_urls`, `identity_status` and
`selection_reason` for the corresponding observations. Keep the source date and
company/objective binding. `PublicEvidence` objects used by research tools instead
use `source_type`, `observed_on`, `summary`, `person_name`, `person_role`, and
`role_is_current`; flatten only the explanation into UI `evidence`, retaining
all corroborating URLs. Never invent evidence just to satisfy validation.

Pass `active_objective_id` to `render_lead_workspace`, `objective_id` to
`render_lead_explorer`, and preserve the same objective on supplied items.
After enrichment use `initial_view: companies`, not `objectives`. After contact
work use `contacts`. Load the objective manager only on explicit request. Ask a
concise question in chat when the research scope genuinely needs clarification.

After observing LinkedIn in the host browser, pass its exact scope as
`browser_scope_id` to `render_lead_workspace`. The server supplies the ephemeral
connection status itself; no scope means unknown. Do not encode browser login
state as a company fact or claim authentication from an unexecuted handoff.

For partial updates, omit unchanged fields. Explicit nulls and empty lists can
clear saved values. On a validation error, fix the reported fields and retry the
render, not the research. Do not say the interface was shown after an error.
