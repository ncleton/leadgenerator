#!/usr/bin/env python3
"""Register the project-owned Lead Generator MCP server with a local Claude host."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from leadgenerator.storage import private_home_for_code_root

ClaudeHost = Literal["claude-code", "claude-desktop"]


def desktop_config_path() -> Path:
    """Return the machine-owned Desktop configuration, never a business data file."""
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library/Application Support/Claude/claude_desktop_config.json"
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", home / "AppData/Roaming")) / (
            "Claude/claude_desktop_config.json"
        )
    return Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / (
        "Claude/claude_desktop_config.json"
    )


def _read_config(path: Path) -> tuple[bytes | None, dict[str, object]]:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(
            "Claude configuration must be a regular file; nothing overwritten."
        )
    if not path.exists():
        return None, {}
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise ValueError(
            "Claude configuration is not valid JSON; nothing overwritten."
        ) from error
    if not isinstance(value, dict) or not isinstance(value.get("mcpServers", {}), dict):
        raise TypeError(
            "Claude configuration has an unsupported structure; nothing overwritten."
        )
    return raw, value


def _owned_entry(entry: object) -> bool:
    """Recognize only this product's old project launcher or installed uv command."""
    if not isinstance(entry, dict):
        return False
    command, args = entry.get("command"), entry.get("args")
    if not isinstance(command, str) or not isinstance(args, list):
        return False
    if not all(isinstance(arg, str) for arg in args):
        return False
    executable = command.replace("\\", "/").rsplit("/", 1)[-1].casefold()
    if executable in {"node", "node.exe"} and len(args) == 1:
        launcher = PurePosixPath(args[0].replace("\\", "/"))
        return (
            PurePosixPath(args[0]).is_absolute()
            or PureWindowsPath(args[0]).is_absolute()
        ) and launcher.parts[-3:] == ("scripts", "claude", "project.cjs")
    if executable not in {"uv", "uv.exe"} or len(args) != 7:
        return False
    package = PurePosixPath(args[2].replace("\\", "/"))
    return (
        args[:2] == ["run", "--project"]
        and (
            PurePosixPath(args[2]).is_absolute()
            or PureWindowsPath(args[2]).is_absolute()
        )
        and package.parts[-2:] == ("plugins", "leadgenerator")
        and args[3:] == ["--frozen", "--python", "3.13", "leadgenerator-mcp"]
    )


def _write_private_file(path: Path, content: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(content)


def configure_claude(
    code_root: Path,
    uv_command: str,
    *,
    host: ClaudeHost = "claude-code",
    config_path: Path | None = None,
) -> dict[str, object]:
    """Bind one local host, retaining other servers and customized instructions."""
    if host not in {"claude-code", "claude-desktop"}:
        raise ValueError("Unsupported Claude host.")
    home = private_home_for_code_root(code_root)
    code = code_root.resolve()
    uv = Path(uv_command)
    if not uv.is_absolute() or not uv.is_file():
        raise ValueError("An absolute path to the installed uv executable is required.")
    config = config_path or (
        code / ".mcp.json" if host == "claude-code" else desktop_config_path()
    )
    snapshot, value = _read_config(config)
    servers = value.get("mcpServers", {})
    existing = servers.get("leadgenerator")
    if existing is not None and not _owned_entry(existing):
        # The tracked project template is a reviewed bootstrap registration.
        template = code / "scripts/claude/templates/.mcp.json"
        expected = json.loads(template.read_text(encoding="utf-8"))["mcpServers"][
            "leadgenerator"
        ]
        recognized_bootstrap = (
            host == "claude-code"
            and isinstance(existing, dict)
            and existing.get("command") == expected.get("command")
            and existing.get("args") == expected.get("args")
            and existing.get("type", "stdio") == "stdio"
        )
        if not recognized_bootstrap:
            raise ValueError(
                "A different Lead Generator connector already exists; review it before replacing it."
            )
    raw_environment = existing.get("env", {}) if isinstance(existing, dict) else {}
    if not isinstance(raw_environment, dict):
        raise TypeError("Existing Lead Generator environment must be an object.")
    environment = dict(raw_environment)
    environment.update(
        LEADGENERATOR_HOME=str(home),
        LEADGENERATOR_DATABASE_URL="",
        LEADGENERATOR_HOST="claude",
    )
    desired = {
        **(existing or {}),
        "command": str(uv),
        "args": [
            "run",
            "--project",
            str(code / "plugins/leadgenerator"),
            "--frozen",
            "--python",
            "3.13",
            "leadgenerator-mcp",
        ],
        "env": environment,
    }
    # The new project path is absolute in args; do not retain an obsolete cwd
    # from a recognized registration copied from another folder or computer.
    desired.pop("cwd", None)
    if host == "claude-code":
        desired["type"] = "stdio"

    instructions = code / "CLAUDE.md"
    if host == "claude-code" and (
        instructions.is_symlink()
        or (instructions.exists() and not instructions.is_file())
    ):
        raise ValueError("CLAUDE.md must be a regular file; nothing overwritten.")
    changed = existing != desired
    backup_created = False
    if changed:
        content = (
            json.dumps(
                {**value, "mcpServers": {**servers, "leadgenerator": desired}},
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode()
        config.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = config.with_name(f".leadgenerator-{uuid.uuid4().hex}.tmp")
        try:
            _write_private_file(temporary, content)
            if _read_config(config)[0] != snapshot:
                raise ValueError(
                    "Claude configuration changed concurrently; nothing overwritten."
                )
            if snapshot is not None:
                backup_root = (
                    Path.home() / ".claude/leadgenerator/config-backups"
                    if host == "claude-code"
                    else config.parent / ".leadgenerator-backups"
                )
                backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
                _write_private_file(backup_root / f"{uuid.uuid4().hex}.json", snapshot)
                backup_created = True
            temporary.replace(config)
        finally:
            temporary.unlink(missing_ok=True)

    instructions_created = False
    if host == "claude-code" and not instructions.exists():
        template = code / "scripts/claude/templates/CLAUDE.md"
        _write_private_file(instructions, template.read_bytes())
        instructions_created = True
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    home.chmod(0o700)
    return {
        "host": host,
        "configured": True,
        "configuration_path": str(config),
        "private_directory": str(home),
        "backend": "sqlite",
        "existing_objectives": sum(
            1 for _ in (home / "objectives").glob("*/objective.json")
        ),
        "changed": changed,
        "previous_binding_changed": existing is not None and changed,
        "private_backup_created": backup_created,
        "instructions_created": instructions_created,
        "legacy_data_imported": False,
        "restart_required": changed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", required=True, type=Path)
    parser.add_argument("--uv-command", required=True)
    parser.add_argument(
        "--host", choices=("claude-code", "claude-desktop"), default="claude-code"
    )
    args = parser.parse_args()
    try:
        result = configure_claude(args.code_root, args.uv_command, host=args.host)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, f"Claude registration failed: {error}\n")
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
