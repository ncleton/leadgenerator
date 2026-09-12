# Modular troubleshooting

Start with `get_lead_composition`, then `diagnose_lead_composition`. The report
contains no secret or customer record.

- **Unavailable plugin:** install it below the private extensions root or remove
  the stale enable entry through a new preview.
- **Changed/untrusted extension:** review the new version, fingerprint, and
  permissions; confirm again only if expected.
- **Two shells:** select one provider and disable every other shell.
- **Unsupported SDK:** install a compatible extension release or return to the
  native shell. Do not loosen the declared version range without testing.
- **Broken panel:** correct its component or observation kind; the rest of the UI
  remains active.
- **Broken shell:** continue in text mode, repair the bundle, or explicitly restore
  `yaka.ui-workspace`. There is no silent fallback.
- **Failed private edit:** call `restore_previous_lead_composition`, restart, and
  diagnose again.
