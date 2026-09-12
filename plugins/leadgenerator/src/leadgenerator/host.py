"""Explicit host identity, independent of user profiles and private storage."""

from __future__ import annotations

import os


def host_name() -> str:
    """Claude launchers opt in; preserve Codex's existing runtime behavior."""
    return "claude" if os.environ.get("LEADGENERATOR_HOST") == "claude" else "codex"


def host_contract() -> dict[str, object]:
    """Describe integration limits without claiming unavailable host tools."""
    return {
        "name": host_name(),
        "ui_protocol": "mcp_apps",
        "ui_requires": "A host that renders text/html;profile=mcp-app resources. CLI-only clients cannot display the interface.",
        "browser": "Discover the current host's browser tools. In Claude prefer Claude in Chrome for an existing signed-in account; the Code tab's built-in Browser (Claude Browser / Claude Preview tools) can also open LinkedIn for a direct user login in its separate profile. Execute the navigation and inspect the visible session, not just a handoff. Never invoke another host's tools or reuse its authentication implicitly.",
        "schedule_editable": host_name() == "codex",
        "schedule_owner": "codex",
        "private_storage": "Existing local storage under ~/.codex/leadgenerator is shared only by processes running as the same OS user. No profiles or secrets are bundled.",
    }
