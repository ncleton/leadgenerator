# Create a native Yaka plugin

Native plugins are maintained and released with Lead Generator. Add code under a
focused runtime module, an activation function in `native/activators.py`, and a
catalog directory containing `plugin.yaml` plus `config.schema.json`.

The activation context exposes only declared capabilities. Call `require` for
dependencies, `provide` once per exclusive service, and `contribute` for every
declared stable registry ID. Never access a customer pack, global PostgreSQL
connection, or undeclared secret from plugin code.

Add contract tests, lifecycle/cleanup tests, disabled-plugin behavior, health
checks, and integration confirmation tests. Refresh the native catalog hashes,
run `./scripts/validate.sh`, bump the official plugin cache-buster, validate all
skills and the plugin, install through `scripts/install_client.*`, and execute the
real MCP handshake. Never install this plugin with a direct ad-hoc cache copy.
