# Create a private client pack

Client packs live only below `~/.codex/leadgenerator/packs/`. Start from the
synthetic `client-pack.yaml` template and choose explicit providers. Never add a
client identity, offer, scoring rule, or operational example to the repository.

Named sector packs use `<pack-id>.yaml`. `active.yaml` may list them in `extends`;
cycles and missing parents fail composition. The merge order is product defaults,
listed parents, active client pack, then an optional
`packs/objectives/<objective-id>.yaml`. Plugin enable/disable lists merge by ID,
providers and tokens use the more specific value, and tabs/panels merge by their
stable IDs. Conflicts in one layer are invalid.

Use the customization MCP tools rather than editing the pack by hand. They bind a
preview to the pack fingerprint, validate before atomic replacement, keep the
previous version, and set restrictive file permissions.
