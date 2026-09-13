#!/usr/bin/env python3
"""Bind a local installation to its durable, Git-external business workspace."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from leadgenerator.storage import private_home_for_code_root


def configure_workspace(
    code_root: Path,
    *,
    plugin_root: Path | None = None,
    uv_command: str | None = None,
) -> dict[str, object]:
    """Prepare only the selected workspace, never importing global legacy data."""
    home = private_home_for_code_root(code_root)
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    home.chmod(0o700)
    if plugin_root is not None:
        config_path = plugin_root / ".mcp.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        server = config["mcpServers"]["leadgenerator"]
        environment = server.setdefault("env", {})
        environment["LEADGENERATOR_HOME"] = str(home)
        # An inherited legacy PostgreSQL URL must not reconnect a new workspace
        # to another installation's records. Portable installs always use SQLite.
        environment["LEADGENERATOR_DATABASE_URL"] = ""
        if uv_command is not None:
            server["command"] = uv_command
        temporary = config_path.with_name(".mcp.json.tmp")
        temporary.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.chmod(0o600)
        temporary.replace(config_path)
    return {
        "private_directory": str(home),
        "backend": "sqlite",
        "existing_objectives": sum(
            1 for _ in (home / "objectives").glob("*/objective.json")
        ),
        "legacy_data_imported": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", required=True, type=Path)
    parser.add_argument("--plugin-root", type=Path)
    parser.add_argument("--uv-command")
    parser.add_argument("--print-home", action="store_true")
    args = parser.parse_args()
    result = configure_workspace(
        args.code_root, plugin_root=args.plugin_root, uv_command=args.uv_command
    )
    if args.print_home:
        print(result["private_directory"])
    else:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
