# Modular migration and rollback

SDK 1.x keeps all existing MCP tool names, payload inputs, historical explorer
and workspace resource URIs, `chat_ui`/`text_only` behavior, objective files, and
PostgreSQL company snapshots.

When no private pack exists, a default pack enables every bundled native plugin
and selects `yaka.ui-workspace`. Existing users need no migration action and the
existing preferences file remains valid.

PostgreSQL initialization is idempotent and adds evidence, observation, score,
commercial-outcome, and plugin-state tables without removing company records.
`lead_payload` remains the compatibility projection while new plugins emit
versioned observations. Direct `LeadViewItem` writes remain supported in SDK 1.x.

Each private customization is validated before atomic replacement and retains
`active.previous.yaml`. Rollback is explicit and requires restart. Plugin state is
recorded only after successful schema creation and health checks.

A custom shell with an unsupported SDK or changed fingerprint is quarantined.
Lead Generator stays available in text mode and reports repair steps; it never
silently switches interfaces.

## Incremental company and contact projections

Render tools merge partial company updates with that objective's private memory
before building the returned interface. Omitted fields survive; explicit nulls
and empty arrays clear their own field. Contacts merge by durable ID or LinkedIn
URL, with a unique exact-name fallback within the company. Conflicting IDs never
fall back to a name; ambiguous homonyms require a more precise update. Visuals
merge by kind and pipeline state by step. Other supplied arrays replace their
previous value. An unavailable database is reported and cannot restore old fields.

New immutable snapshots contain a `_projection_version: 1` marker identifying a
complete projection. Replaying a complete snapshot resets the previous projection,
so explicitly cleared values never reappear. Older snapshots remain untouched
and are replayed as deltas for their exact objective. No destructive SQL migration
is needed. Two objectives on the same company do not share contact projections.

Transaction-scoped advisory locks serialize partial updates to the same company.
The resolved projection, including existing logo, photos, posts and other contacts,
is returned to the caller instead of rendering only the latest partial input.
Company identity continues to prefer SIREN; a shared website domain cannot merge
two distinct known SIRENs.

Real PostgreSQL regression tests create a disposable `leadgenerator_test_*`
database. Set `LEADGENERATOR_TEST_POSTGRES_URL` to a local administrative test
connection to run them; the quality CI job supplies its own ephemeral service.
Never point this setting at a production server. The test-created database is
dropped in cleanup; existing databases and company records are not modified.
