# Plugin SDK 1.x

## Manifest

Every native or private extension has a `plugin.yaml` using
`leadgenerator.yaka/v1`, a semantic version, an SDK range, one runtime, explicit
capabilities, contributions, permissions, and a JSON Schema 2020-12 configuration
file. The manifest is validated before executable code is imported or started.

Runtimes are `python` for bundled native code, `ui-bundle` for autonomous client
HTML covering both surfaces, and `executable` for isolated client business code.
`ui.shell`, `memory.canonical`, `approvals`, `orchestrator`, and a selected primary
CRM are exclusive. Contributions are additive but IDs remain unique per registry.

## Data contracts

`Evidence` stores source, dates, excerpt hash, and trust. `Observation` stores
subject, objective, epistemic status, value, confidence, evidence, producer, and
schema version. A fact without registered evidence is rejected and IDs are
immutable. `ScoreContribution` makes measured, inferred, and missing states
explicit; missing data has zero points and remains incomplete.

`ActionDescriptor.effect` is `read`, `paid_read`, or `external_write`. The kernel
forces explicit confirmation for the last two regardless of UI.
`WorkspaceViewModel` is the extensible UI projection; `LeadViewItem` remains a
compatibility input throughout SDK 1.x.

## Lifecycle

Composition validates catalog hashes, schemas, SDK compatibility, extension
trust, dependencies, exclusive services, and permissions before startup. Plugins
activate in dependency order and stop in reverse order. A required service failure
aborts startup; an incompatible client extension is quarantined.

Executable plugins answer a `start` message with `ready` and the exact declared
capabilities. Calls carry an ID, capability, method, and bounded JSON parameters.
They never write canonical storage or weaken approvals. Direct filesystem and
network permissions are rejected in SDK 1.x: external data must be supplied as
bounded RPC input by a kernel/native source capability. The process starts only
when an OS sandbox is available (`sandbox-exec` on macOS or Bubblewrap on Linux);
otherwise the client plugin is quarantined. This fail-closed policy also applies
on Windows until a supported isolation backend is installed by the product.

Use the synthetic templates under the `lead-customization` skill. Never put
seller, customer, company, credential, or operational lead data in templates or
tests.
