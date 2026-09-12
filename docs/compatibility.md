# Compatibility policy

The product, kernel, SDK, each native plugin, private pack, shell, campaign, and
scorecard have independent semantic versions. Plugin manifests declare
`requiresSdk`; a breaking SDK contract requires a major version and migration
guide.

SDK 1.x preserves current MCP tool names and inputs, legacy UI resource URIs,
presentation modes, objective records, company cards, and snapshots. Additive
fields may appear in structured outputs. Unknown observation kinds use a generic
card. Unknown declarative components disable one panel.

Native configuration and panels continue to receive compatible native UI updates.
A custom shell continues to receive compatible kernel and business-plugin updates
but owns its design, navigation, components, and visual fixes.
