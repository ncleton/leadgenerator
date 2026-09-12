# Objective management and scheduled prospecting

`render_lead_objectives` opens the native objective manager without selecting a
research scope. The interface loads saved objectives, agent instructions,
examples, target roles, document metadata, notes and scheduling preferences.
`initial_view="settings"` opens per-objective scheduling directly. Existing
workspace results also load objective records when no explicit payload is supplied.

When several objectives exist, unmatched sourcing requests return those saved
objectives as choices. Seller onboarding is reserved for an empty objective
store. Explicit and sticky selections retain priority, and a clear semantic match
still selects automatically.

## Editing and documents

The editor calls `get_lead_objective` and `update_lead_objective` through the MCP
Apps tool bridge. Revision checks reject stale forms without discarding user input.
Both objective and agent fields are validated before either record is updated.
Documents selected in the browser use `upload_lead_objective_document` with a
10 MB limit; larger local attachments retain the existing 50 MB file-path tool.
Both paths share validation, hashing, extraction and objective-local storage.
`add_lead_objective_note` persists additional context. A host without direct tool
calls can send an explicit edit request through chat; it never shows a false save.

## Scheduler ownership

Each private objective stores a `schedule.json` next to its existing records.
Defaults are daily at 09:00 Europe/Paris, ten prospects, disabled. Cadence options
are daily, weekdays or selected weekdays, with validated local time, timezone and
volume. All operational values remain in private storage.

`save_lead_objective_schedule` records desired settings and returns a handoff.
The conversation uses the host's `automation_update` tool to create or update a
real scheduled task, then calls `confirm_lead_objective_schedule` with its ID,
status and matching revision. The UI distinguishes disabled, pending, confirmed
active and confirmed paused states, and labels the latest confirmation date.
It does not independently poll changes made outside Lead Generator.

The host owns execution and timezone interpretation. No daemon, crontab, launch
agent or handwritten automation file is installed. Existing automation IDs are
reused; an exact objective marker supports recovery after an interrupted binding.
One host automation cannot be assigned to two objective schedules. Thread
heartbeats are the default; standalone runs require the user's request.

Every scheduled run first reads `get_lead_objective_schedule_run`. Disabled,
pending or archived objectives do not authorize sourcing. Authorized runs then
resolve the explicit objective and reload its current agent/document context.
The returned volume and existing duplicate exclusion apply to the new list.
No paid enrichment, outreach or CRM synchronization runs unattended. Archiving
an objective prevents further research; pausing its host automation remains a
separate host action.

The machine must remain on with Codex running for local executions. The reference
workflow is in `skills/leadgenerator/references/scheduling.md`; see also the
[official scheduled-task documentation](https://learn.chatgpt.com/docs/automations?surface=app).

## Verification

Routing and schedule lifecycle tests exercise isolation, stale revisions,
idempotency, pause/archive gates and duplicate bindings. Browser tests connect
the forms to real local tools using temporary objective stores, including edit,
upload, note, schedule handoff and narrow-screen rendering. Installation smoke
tests discover the new tools and render the manager without running a schedule.
