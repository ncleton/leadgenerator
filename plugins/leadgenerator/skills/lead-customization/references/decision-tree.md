# Decision tree

Use this order. Stop at the first level that satisfies every required behavior.

1. Native configuration: supported token, label, tab order, default tab,
   visibility, logo, density, or existing panel order.
2. Declarative contribution: a supported component in `workspace.tab` or
   `workspace.panel`, reading observations by `kind`.
3. Autonomous shell: a different navigation model, bespoke JavaScript
   interaction, canvas/editor, or behavior absent from the component catalog.

Unknown data is not a UI limitation. Create a data source or analyzer extension
that emits an `Observation`, then display it through a declarative panel.

The following never become UI configuration: permissions, provider selection,
paid-read approval, CRM-write approval, provenance policy, URL safety, secret
handling, or fact validation.
