# Per-objective scheduled sourcing

This integration currently manages Codex automations only. In Claude, schedules
are read-only: use `get_lead_objective_schedule` or the settings UI and direct
edits back to Codex. Do not invoke `automation_update`, invent an equivalent tool,
or create a duplicate Claude schedule. The server enforces this host boundary.

Open `render_lead_objectives(initial_view="settings")` for the scheduling UI.
Each objective owns its cadence, local time, IANA timezone, desired lead count,
enabled preference and last confirmed host automation binding. Defaults are
daily at 09:00 Europe/Paris, 10 prospects, disabled until requested.

1. Resolve which saved objective the user wants to schedule. Reuse an explicit
   selection; if several exist and none is selected, present their names instead
   of asking what the user sells. Do not activate all objectives by inference.
2. Read `get_lead_objective_schedule`. Save only the requested settings with
   `save_lead_objective_schedule`, preserving the others and using its revision.
   An editor click already requests saving and activating or pausing that exact
   schedule; another generic confirmation is unnecessary.
3. Follow the returned host handoff with Codex's `automation_update` tool.
   Prefer a heartbeat in the current conversation. Use standalone runs only if
   explicitly requested. For an existing binding, inspect the automation and
   update its full fields while preserving unrelated options. If no ID is bound,
   first look for the exact `automation_marker` in existing saved automations,
   so recovery from an interrupted confirmation never creates duplicates.
4. Translate `when` to the host's supported recurrence using the stated timezone,
   including daylight saving time. Do not silently substitute UTC or a different
   local timezone. If the host cannot express that timezone, explain the exact
   limitation instead of claiming the requested schedule is active. Keep
   notification preferences in the host's notification field, not in the prompt.
5. After successful creation/update or a fresh host view verifying the exact
   prompt, recurrence and status, call `confirm_lead_objective_schedule` with
   the real automation ID, saved revision and actual status. Then rerender settings.
   Never record a binding on a failed or merely suggested host creation. A pending
   schedule is not active; explain errors and leave it available for retry.

The MCP server deliberately does not write scheduler files, start background
shell processes or install system cron jobs. If the host automation tool is not
available, preserve settings as pending and explain that host activation is still
needed. Pausing means disabling the local setting and pausing the same host
automation; do not create a second job. Deleting or externally changing a host
automation requires reconciling its saved binding before claiming it is current.
The interface labels the date of the last successful host confirmation.

For each scheduled execution, call `get_lead_interface_mode`, then
`get_lead_objective_schedule_run`. If disabled, pending or archived, stop without
research. Otherwise call `resolve_lead_objective` with the exact explicit ID and
read the complete current objective context, seller profile and website analysis.
Use the configured `lead_count`, preserve the objective's criteria, and retain
the default exclusion of previously seen companies. Show the sourced list, or
explain an empty/incomplete result. Do not spend enrichment credits, write CRM
data or send outreach. The saved prompt references durable IDs so manual edits
and newly attached documents are used on subsequent runs without rescheduling.

Local scheduled research needs the computer on and Codex running. Tell the user
this when activating a local schedule. See the official scheduled-task guidance:
https://learn.chatgpt.com/docs/automations?surface=app
